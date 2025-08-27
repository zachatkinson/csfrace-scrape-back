"""Database service layer for scraping operations.

This module provides high-level database operations following CLAUDE.md patterns
with proper error handling, transaction management, and connection pooling.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import structlog
from sqlalchemy import and_, case, desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from ..core.exceptions import DatabaseError
from .models import (
    Base,
    Batch,
    ContentResult,
    JobLog,
    JobStatus,
    ScrapingJob,
    create_database_engine,
)

logger = structlog.get_logger(__name__)


class DatabaseService:
    """High-level database service for scraping operations.

    Provides transaction-safe operations with comprehensive error handling,
    connection management, and performance optimizations.
    """

    def __init__(self, database_path: Optional[Path] = None, echo: bool = False):
        """Initialize database service.

        Args:
            database_path: Path to SQLite database file
            echo: Whether to echo SQL statements for debugging
        """
        self.database_path = database_path
        self.engine = create_database_engine(database_path, echo=echo)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # Keep objects accessible after commit
        )

        logger.info(
            "Initialized database service",
            database_path=str(database_path) if database_path else "default",
            echo=echo,
        )

    def initialize_database(self) -> None:
        """Create all database tables.

        This is idempotent - safe to call multiple times.
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables initialized successfully")
        except SQLAlchemyError as e:
            logger.error("Failed to initialize database tables", error=str(e))
            raise DatabaseError(f"Database initialization failed: {e}") from e

    @contextmanager
    def get_session(self):
        """Context manager for database sessions with automatic cleanup.

        Yields:
            SQLAlchemy Session with transaction management
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Database session error, rolling back", error=str(e))
            raise
        finally:
            session.close()

    # Job Management Operations

    def create_job(
        self,
        url: str,
        output_directory: str,
        domain: Optional[str] = None,
        slug: Optional[str] = None,
        batch_id: Optional[int] = None,
        priority: str = "normal",
        **kwargs,
    ) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            url: URL to scrape
            output_directory: Directory for output files
            domain: Domain name (auto-extracted if not provided)
            slug: URL slug (auto-extracted if not provided)
            batch_id: Optional batch ID for grouping
            priority: Job priority level
            **kwargs: Additional job configuration

        Returns:
            Created ScrapingJob instance

        Raises:
            DatabaseError: If job creation fails
        """
        try:
            with self.get_session() as session:
                # Auto-extract domain and slug if not provided
                if not domain:
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    domain = parsed.netloc

                if not slug and not kwargs.get("custom_slug"):
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    path_parts = parsed.path.strip("/").split("/")
                    slug = path_parts[-1] if path_parts and path_parts[-1] else "homepage"

                # Convert string priority to enum if needed
                from .models import JobPriority

                if isinstance(priority, str):
                    try:
                        priority_enum = JobPriority(priority.lower())
                    except ValueError:
                        priority_enum = JobPriority.NORMAL
                else:
                    priority_enum = priority

                job = ScrapingJob(
                    url=url,
                    domain=domain,
                    slug=slug,
                    output_directory=output_directory,
                    batch_id=batch_id,
                    priority=priority_enum,
                    **kwargs,
                )

                session.add(job)
                session.flush()  # Get ID without committing

                logger.info(
                    "Created scraping job",
                    job_id=job.id,
                    url=url,
                    domain=domain,
                    slug=slug,
                )

                return job

        except IntegrityError as e:
            logger.error("Job creation failed - integrity constraint", url=url, error=str(e))
            raise DatabaseError(f"Job creation failed: {e}") from e
        except SQLAlchemyError as e:
            logger.error("Job creation failed - database error", url=url, error=str(e))
            raise DatabaseError(f"Job creation failed: {e}") from e

    def get_job(self, job_id: int) -> Optional[ScrapingJob]:
        """Retrieve a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            ScrapingJob instance or None if not found
        """
        try:
            with self.get_session() as session:
                job = session.get(ScrapingJob, job_id)
                return job
        except SQLAlchemyError as e:
            logger.error("Failed to retrieve job", job_id=job_id, error=str(e))
            raise DatabaseError(f"Job retrieval failed: {e}") from e

    def update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        error_message: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> bool:
        """Update job status with optional error and timing information.

        Args:
            job_id: Job identifier
            status: New job status
            error_message: Optional error message for failed jobs
            duration: Optional execution duration in seconds

        Returns:
            True if update successful, False if job not found
        """
        try:
            with self.get_session() as session:
                now = datetime.now(timezone.utc)
                update_data: dict[str, Any] = {"status": status}

                if status == JobStatus.RUNNING:
                    update_data["started_at"] = now
                elif status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                    update_data["completed_at"] = now
                    if duration is not None:
                        update_data["duration_seconds"] = duration
                    if error_message:
                        update_data["error_message"] = error_message

                result = session.execute(
                    update(ScrapingJob).where(ScrapingJob.id == job_id).values(**update_data)
                )

                success = result.rowcount > 0
                if success:
                    logger.debug("Updated job status", job_id=job_id, status=status.value)
                else:
                    logger.warning("Job not found for status update", job_id=job_id)

                return success

        except SQLAlchemyError as e:
            logger.error("Failed to update job status", job_id=job_id, error=str(e))
            raise DatabaseError(f"Job status update failed: {e}") from e

    def get_pending_jobs(self, limit: int = 100) -> list[ScrapingJob]:
        """Retrieve pending jobs for processing.

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of pending ScrapingJob instances ordered by priority and creation time
        """
        try:
            with self.get_session() as session:
                # Order by priority (URGENT -> HIGH -> NORMAL -> LOW) then by creation time
                from .models import JobPriority

                priority_order = {
                    JobPriority.URGENT: 4,
                    JobPriority.HIGH: 3,
                    JobPriority.NORMAL: 2,
                    JobPriority.LOW: 1,
                }

                stmt = (
                    select(ScrapingJob)
                    .where(ScrapingJob.status == JobStatus.PENDING)
                    .order_by(
                        desc(
                            case(
                                *[
                                    (ScrapingJob.priority == k, v)
                                    for k, v in priority_order.items()
                                ],
                                else_=0,
                            )
                        ),
                        ScrapingJob.created_at,
                    )
                    .limit(limit)
                )

                jobs = session.execute(stmt).scalars().all()

                logger.debug("Retrieved pending jobs", count=len(jobs), limit=limit)
                return list(jobs)

        except SQLAlchemyError as e:
            logger.error("Failed to retrieve pending jobs", error=str(e))
            raise DatabaseError(f"Pending jobs retrieval failed: {e}") from e

    def get_jobs_by_status(
        self, status: JobStatus, limit: int = 100, offset: int = 0
    ) -> list[ScrapingJob]:
        """Retrieve jobs by status with pagination.

        Args:
            status: Job status to filter by
            limit: Maximum number of jobs to retrieve
            offset: Number of jobs to skip

        Returns:
            List of ScrapingJob instances
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(ScrapingJob)
                    .where(ScrapingJob.status == status)
                    .order_by(desc(ScrapingJob.created_at))
                    .limit(limit)
                    .offset(offset)
                )

                jobs = session.execute(stmt).scalars().all()
                return list(jobs)

        except SQLAlchemyError as e:
            logger.error("Failed to retrieve jobs by status", status=status.value, error=str(e))
            raise DatabaseError(f"Jobs retrieval failed: {e}") from e

    def get_retry_jobs(self, max_jobs: int = 50) -> list[ScrapingJob]:
        """Retrieve failed jobs eligible for retry.

        Args:
            max_jobs: Maximum number of jobs to retrieve

        Returns:
            List of ScrapingJob instances ready for retry
        """
        try:
            with self.get_session() as session:
                now = datetime.now(timezone.utc)

                stmt = (
                    select(ScrapingJob)
                    .where(
                        and_(
                            ScrapingJob.status == JobStatus.FAILED,
                            ScrapingJob.retry_count < ScrapingJob.max_retries,
                            or_(
                                ScrapingJob.next_retry_at.is_(None),
                                ScrapingJob.next_retry_at <= now,
                            ),
                        )
                    )
                    .order_by(ScrapingJob.next_retry_at.asc().nullsfirst())
                    .limit(max_jobs)
                )

                jobs = session.execute(stmt).scalars().all()

                logger.debug("Retrieved retry jobs", count=len(jobs), max_jobs=max_jobs)
                return list(jobs)

        except SQLAlchemyError as e:
            logger.error("Failed to retrieve retry jobs", error=str(e))
            raise DatabaseError(f"Retry jobs retrieval failed: {e}") from e

    # Batch Management Operations

    def create_batch(
        self,
        name: str,
        description: Optional[str] = None,
        output_base_directory: str = "batch_output",
        **config,
    ) -> Batch:
        """Create a new batch processing operation.

        Args:
            name: Batch name
            description: Optional description
            output_base_directory: Base directory for batch outputs
            **config: Additional batch configuration

        Returns:
            Created Batch instance
        """
        try:
            with self.get_session() as session:
                batch = Batch(
                    name=name,
                    description=description,
                    output_base_directory=output_base_directory,
                    batch_config=config,
                    **config,  # Pass config parameters directly to model
                )

                session.add(batch)
                session.flush()

                logger.info(
                    "Created batch",
                    batch_id=batch.id,
                    name=name,
                    output_base_directory=output_base_directory,
                )

                return batch

        except SQLAlchemyError as e:
            logger.error("Batch creation failed", name=name, error=str(e))
            raise DatabaseError(f"Batch creation failed: {e}") from e

    def get_batch(self, batch_id: int) -> Optional[Batch]:
        """Retrieve a batch by ID with associated jobs.

        Args:
            batch_id: Batch identifier

        Returns:
            Batch instance with jobs loaded, or None if not found
        """
        try:
            with self.get_session() as session:
                stmt = select(Batch).where(Batch.id == batch_id)

                batch = session.execute(stmt).scalar_one_or_none()
                return batch

        except SQLAlchemyError as e:
            logger.error("Failed to retrieve batch", batch_id=batch_id, error=str(e))
            raise DatabaseError(f"Batch retrieval failed: {e}") from e

    def update_batch_progress(self, batch_id: int) -> bool:
        """Update batch progress counters based on current job statuses.

        Args:
            batch_id: Batch identifier

        Returns:
            True if update successful, False if batch not found
        """
        try:
            with self.get_session() as session:
                # Get current job counts using case statements for conditional counting
                counts_stmt = select(
                    func.count(ScrapingJob.id).label("total"),
                    func.sum(case((ScrapingJob.status == JobStatus.COMPLETED, 1), else_=0)).label(
                        "completed"
                    ),
                    func.sum(case((ScrapingJob.status == JobStatus.FAILED, 1), else_=0)).label(
                        "failed"
                    ),
                    func.sum(case((ScrapingJob.status == JobStatus.SKIPPED, 1), else_=0)).label(
                        "skipped"
                    ),
                ).where(ScrapingJob.batch_id == batch_id)

                counts = session.execute(counts_stmt).one()

                # Update batch with current counts
                update_stmt = (
                    update(Batch)
                    .where(Batch.id == batch_id)
                    .values(
                        total_jobs=counts.total,
                        completed_jobs=counts.completed,
                        failed_jobs=counts.failed,
                        skipped_jobs=counts.skipped,
                    )
                )

                result = session.execute(update_stmt)
                success = result.rowcount > 0

                if success:
                    logger.debug(
                        "Updated batch progress",
                        batch_id=batch_id,
                        total=counts.total,
                        completed=counts.completed,
                        failed=counts.failed,
                        skipped=counts.skipped,
                    )

                return success

        except SQLAlchemyError as e:
            logger.error("Failed to update batch progress", batch_id=batch_id, error=str(e))
            raise DatabaseError(f"Batch progress update failed: {e}") from e

    # Content and Logging Operations

    def save_content_result(
        self,
        job_id: int,
        html_content: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        file_paths: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> ContentResult:
        """Save converted content and metadata for a job.

        Args:
            job_id: Associated job ID
            html_content: Converted HTML content
            metadata: Extracted metadata dictionary
            file_paths: Dictionary of file paths (html, metadata, images)
            **kwargs: Additional content result data

        Returns:
            Created ContentResult instance
        """
        try:
            with self.get_session() as session:
                content_result = ContentResult(
                    job_id=job_id,
                    converted_html=html_content,
                    **kwargs,
                )

                # Set metadata fields if provided
                if metadata:
                    content_result.title = metadata.get("title")
                    content_result.meta_description = metadata.get("meta_description")
                    content_result.author = metadata.get("author")
                    content_result.tags = metadata.get("tags")
                    content_result.categories = metadata.get("categories")
                    content_result.extra_metadata = metadata

                # Set file paths if provided
                if file_paths:
                    content_result.html_file_path = file_paths.get("html")
                    content_result.metadata_file_path = file_paths.get("metadata")
                    content_result.images_directory = file_paths.get("images")

                session.add(content_result)
                session.flush()

                logger.debug("Saved content result", job_id=job_id, result_id=content_result.id)
                return content_result

        except SQLAlchemyError as e:
            logger.error("Failed to save content result", job_id=job_id, error=str(e))
            raise DatabaseError(f"Content result save failed: {e}") from e

    def add_job_log(
        self,
        job_id: int,
        level: str,
        message: str,
        component: Optional[str] = None,
        operation: Optional[str] = None,
        context_data: Optional[dict[str, Any]] = None,
    ) -> Optional[JobLog]:
        """Add a log entry for a job.

        Args:
            job_id: Associated job ID
            level: Log level (INFO, WARN, ERROR, DEBUG)
            message: Log message
            component: Component that generated the log
            operation: Operation being performed
            context_data: Additional structured context

        Returns:
            Created JobLog instance
        """
        try:
            with self.get_session() as session:
                log_entry = JobLog(
                    job_id=job_id,
                    level=level.upper(),
                    message=message,
                    component=component,
                    operation=operation,
                    context_data=context_data,
                )

                session.add(log_entry)
                session.flush()

                return log_entry

        except Exception as e:
            logger.error("Failed to add job log", job_id=job_id, error=str(e))
            # Don't raise here - logging failures shouldn't break the main process
            return None

    # Statistics and Monitoring

    def get_job_statistics(self, days: int = 7) -> dict[str, Any]:
        """Get job statistics for the specified time period.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with comprehensive job statistics
        """
        try:
            with self.get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

                # Overall statistics
                stats_stmt = select(
                    func.count(ScrapingJob.id).label("total_jobs"),
                    func.count(ScrapingJob.id)
                    .filter(ScrapingJob.status == JobStatus.COMPLETED)
                    .label("completed_jobs"),
                    func.count(ScrapingJob.id)
                    .filter(ScrapingJob.status == JobStatus.FAILED)
                    .label("failed_jobs"),
                    func.count(ScrapingJob.id)
                    .filter(ScrapingJob.status == JobStatus.PENDING)
                    .label("pending_jobs"),
                    func.avg(ScrapingJob.duration_seconds).label("avg_duration"),
                    func.sum(ScrapingJob.content_size_bytes).label("total_content_size"),
                    func.sum(ScrapingJob.images_downloaded).label("total_images"),
                ).where(ScrapingJob.created_at >= cutoff_date)

                stats = session.execute(stats_stmt).one()

                # Calculate success rate
                success_rate = 0.0
                if stats.total_jobs > 0:
                    success_rate = (stats.completed_jobs / stats.total_jobs) * 100

                return {
                    "period_days": days,
                    "total_jobs": stats.total_jobs or 0,
                    "completed_jobs": stats.completed_jobs or 0,
                    "failed_jobs": stats.failed_jobs or 0,
                    "pending_jobs": stats.pending_jobs or 0,
                    "success_rate_percent": round(success_rate, 2),
                    "avg_duration_seconds": float(stats.avg_duration or 0),
                    "total_content_size_bytes": stats.total_content_size or 0,
                    "total_images_downloaded": stats.total_images or 0,
                }

        except SQLAlchemyError as e:
            logger.error("Failed to get job statistics", error=str(e))
            raise DatabaseError(f"Statistics retrieval failed: {e}") from e

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up completed jobs older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of jobs deleted
        """
        try:
            with self.get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

                # Delete old completed jobs and their associated data
                deleted_count = session.execute(
                    select(func.count(ScrapingJob.id)).where(
                        and_(
                            ScrapingJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
                            ScrapingJob.completed_at < cutoff_date,
                        )
                    )
                ).scalar()

                session.execute(
                    update(ScrapingJob)
                    .where(
                        and_(
                            ScrapingJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
                            ScrapingJob.completed_at < cutoff_date,
                        )
                    )
                    .values(status=JobStatus.CANCELLED)  # Soft delete by changing status
                )

                logger.info("Cleaned up old jobs", deleted_count=deleted_count, days=days)
                return deleted_count

        except SQLAlchemyError as e:
            logger.error("Failed to cleanup old jobs", error=str(e))
            raise DatabaseError(f"Job cleanup failed: {e}") from e
