"""Database service layer for scraping operations.

This module provides high-level database operations following CLAUDE.md patterns
with proper error handling, transaction management, and connection pooling.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, overload
from uuid import uuid4

import structlog
from sqlalchemy import and_, case, desc, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from ..common.status import JobPriority, JobStatus
from ..constants import API_DEFAULT_LIMIT
from ..core.exceptions import DatabaseError
from .models import (
    Base,
    ContentResult,
    JobLog,
    ScrapingJob,
    create_database_engine,
)
from .utils import create_postgresql_enums, get_standard_enum_definitions

logger = structlog.get_logger(__name__)


class JobCreateRequest:  # pylint: disable=too-few-public-methods
    """Request object for creating scraping jobs."""

    def __init__(self, url: str, output_directory: str, **kwargs):
        """Initialize JobCreateRequest with flexible kwargs support."""
        self.url = url
        self.output_directory = output_directory
        self.domain = kwargs.get("domain")
        self.slug = kwargs.get("slug")
        self.batch_id = kwargs.get("batch_id")
        self.priority = kwargs.get("priority", "normal")

        # Store additional kwargs for backward compatibility
        for key, value in kwargs.items():
            if key not in ("domain", "slug", "batch_id", "priority"):
                setattr(self, key, value)


@dataclass
class JobLogRequest:
    """Request object for adding job logs."""

    job_id: str  # Fixed: Database model uses string job_id
    level: str
    message: str
    component: str | None = None
    operation: str | None = None
    context_data: dict[str, Any] | None = None


class DatabaseService:
    """High-level database service for scraping operations.

    Provides transaction-safe operations with comprehensive error handling,
    connection management, and performance optimizations.
    """

    def __init__(self, echo: bool = False):
        """Initialize database service for PostgreSQL.

        Args:
            echo: Whether to echo SQL statements for debugging
        """
        self.engine = create_database_engine(echo=echo)
        self.SessionLocal = sessionmaker(  # pylint: disable=invalid-name
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # Keep objects accessible after commit
        )

    @classmethod
    def _create_with_engine(cls, engine):
        """Create DatabaseService with existing engine (for testcontainers).

        Args:
            engine: Existing SQLAlchemy engine

        Returns:
            DatabaseService instance using the provided engine
        """
        service = cls.__new__(cls)  # Create instance without calling __init__
        service.engine = engine
        service.SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        return service

    def initialize_database(self) -> None:
        """Create all database tables with PostgreSQL enum safety.

        Following PostgreSQL and SQLAlchemy best practices:
        1. Create enum types first with concurrent safety
        2. Create tables using checkfirst=True
        3. Handle duplicate enum creation gracefully

        This is idempotent - safe to call multiple times.
        """
        try:
            # Create enum types first with PostgreSQL best practices
            self._create_enums_safely()

            # Create all tables using SQLAlchemy best practices with concurrent safety
            try:
                Base.metadata.create_all(bind=self.engine, checkfirst=True)
            except SQLAlchemyError as table_error:
                # Handle concurrent table/constraint creation conflicts gracefully
                error_msg = str(table_error).lower()
                if any(
                    phrase in error_msg
                    for phrase in [
                        "already exists",
                        "duplicate key",
                        "unique constraint",
                        "pg_type_typname_nsp_index",
                    ]
                ):
                    logger.debug(
                        f"Database objects already exist (concurrent execution): {table_error}"
                    )
                    # Continue - this is expected in concurrent test environments
                else:
                    # Unexpected error - re-raise
                    raise

            logger.info("Database tables initialized successfully")
        except SQLAlchemyError as e:
            logger.error("Failed to initialize database tables", error=str(e))
            raise DatabaseError(f"Database initialization failed: {e}") from e

    def _create_enums_safely(self) -> None:
        """Create PostgreSQL enum types safely for concurrent environments.

        Uses PostgreSQL's transaction-safe enum creation pattern recommended
        in the official documentation.
        """

        with self.engine.connect() as conn:
            create_postgresql_enums(conn, get_standard_enum_definitions())
            # Commit the transaction
            conn.commit()

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

    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse  # pylint: disable=import-outside-toplevel

        parsed = urlparse(url)
        return parsed.netloc

    def _extract_slug_from_url(self, url: str) -> str:
        """Extract slug from URL path."""
        from urllib.parse import urlparse  # pylint: disable=import-outside-toplevel

        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")
        return path_parts[-1] if path_parts and path_parts[-1] else "homepage"

    def _normalize_priority(self, priority: str | object) -> str:
        """Convert priority to string value for database storage."""

        if isinstance(priority, str):
            try:
                return JobPriority(priority.lower()).value  # Return string value
            except ValueError:
                return JobPriority.NORMAL.value  # Return default string value
        if isinstance(priority, JobPriority):
            return priority.value  # Convert enum to string value
        if isinstance(priority, int):
            # Convert old integer priorities to string equivalents
            priority_map = {1: "low", 5: "normal", 10: "high", 15: "urgent"}
            return priority_map.get(priority, "normal")  # Default to normal
        return JobPriority.NORMAL.value  # Default fallback

    @overload
    def create_job(
        self,
        *,
        url: str,
        output_directory: str,
        batch_id: int | None = None,
        priority: str = "normal",
        **kwargs,
    ) -> ScrapingJob:
        """Create job with keyword arguments (backward compatibility)."""

    @overload
    def create_job(self, request: JobCreateRequest, **kwargs) -> ScrapingJob:
        """Create job with JobCreateRequest."""

    def create_job(self, request: JobCreateRequest | None = None, **kwargs) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            request: Job creation request containing all parameters (new style)
            **kwargs: Legacy arguments (url, output_directory, batch_id, priority, etc.)

        Returns:
            Created ScrapingJob instance

        Raises:
            DatabaseError: If job creation fails
        """
        # Handle backward compatibility: convert keyword args to JobCreateRequest
        if request is None:
            url = kwargs.get("url")
            output_directory = kwargs.get("output_directory")

            if url is None or output_directory is None:
                raise ValueError(
                    "Either 'request' or both 'url' and 'output_directory' must be provided"
                )
            request = JobCreateRequest(
                url=url,
                output_directory=output_directory,
                batch_id=kwargs.get("batch_id"),
                priority=kwargs.get("priority", "normal"),
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k not in ("url", "output_directory", "batch_id", "priority")
                },
            )

        try:
            with self.get_session() as session:
                # Extract and process request parameters
                domain = request.domain or self._extract_domain_from_url(request.url)
                slug = request.slug or (
                    self._extract_slug_from_url(request.url)
                    if not kwargs.get("custom_slug")
                    else None
                )
                priority_enum = self._normalize_priority(request.priority)

                # Filter out kwargs that are already handled explicitly to avoid conflicts
                filtered_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k
                    not in (
                        "url",
                        "domain",
                        "slug",
                        "output_directory",
                        "batch_id",
                        "priority",
                        "custom_slug",
                    )
                }

                job = ScrapingJob(
                    source_url=request.url,  # Required field
                    job_type="single",  # Default job type
                    target_format="html",  # Default target format
                    batch_id=request.batch_id,
                    priority=priority_enum,
                    **filtered_kwargs,
                )

                session.add(job)
                session.flush()  # Get ID without committing

                logger.info(
                    "Created scraping job",
                    job_id=job.id,
                    url=request.url,
                    domain=domain,
                    slug=slug,
                )

                return job

        except IntegrityError as e:
            logger.error(
                "Job creation failed - integrity constraint", url=request.url, error=str(e)
            )
            raise DatabaseError(f"Job creation failed: {e}") from e
        except SQLAlchemyError as e:
            logger.error("Job creation failed - database error", url=request.url, error=str(e))
            raise DatabaseError(f"Job creation failed: {e}") from e

    def get_job(self, job_id: str) -> ScrapingJob | None:
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
        job_id: str,
        status: str | JobStatus,  # Accept both str and JobStatus enum
        error_message: str | None = None,
        duration: float | None = None,
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
                now = datetime.now(UTC)
                # Convert enum to string value if needed
                status_value = status.value if hasattr(status, "value") else str(status)
                update_data: dict[str, Any] = {"status": status_value}

                if status_value == "running":
                    update_data["started_at"] = now
                elif status_value in {"completed", "failed", "cancelled"}:
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
                    logger.debug("Updated job status", job_id=job_id, status=status_value)
                else:
                    logger.warning("Job not found for status update", job_id=job_id)

                return success

        except SQLAlchemyError as e:
            logger.error("Failed to update job status", job_id=job_id, error=str(e))
            raise DatabaseError(f"Job status update failed: {e}") from e

    def get_pending_jobs(self, limit: int = API_DEFAULT_LIMIT) -> list[ScrapingJob]:
        """Retrieve pending jobs for processing.

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of pending ScrapingJob instances ordered by priority and creation time
        """
        try:
            with self.get_session() as session:
                # Order by priority (URGENT -> HIGH -> NORMAL -> LOW) then by creation time

                priority_order = {
                    JobPriority.URGENT: 4,
                    JobPriority.HIGH: 3,
                    JobPriority.NORMAL: 2,
                    JobPriority.LOW: 1,
                }

                stmt = (
                    select(ScrapingJob)
                    .where(ScrapingJob.status == "pending")
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
        self, status: str | JobStatus, limit: int = API_DEFAULT_LIMIT, offset: int = 0
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
                # Convert enum to string value if needed
                status_value = status.value if hasattr(status, "value") else str(status)
                stmt = (
                    select(ScrapingJob)
                    .where(ScrapingJob.status == status_value)
                    .order_by(desc(ScrapingJob.created_at))
                    .limit(limit)
                    .offset(offset)
                )

                jobs = session.execute(stmt).scalars().all()
                return list(jobs)

        except SQLAlchemyError as e:
            status_value = status.value if hasattr(status, "value") else str(status)
            logger.error("Failed to retrieve jobs by status", status=status_value, error=str(e))
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
                # Calculate retry delay: exponential backoff (2^retry_count minutes)
                # Jobs are eligible if enough time has passed since completion
                stmt = (
                    select(ScrapingJob)
                    .where(
                        and_(
                            ScrapingJob.status == "failed",
                            ScrapingJob.retry_count < ScrapingJob.max_retries,
                            or_(
                                ScrapingJob.completed_at.is_(None),
                                ScrapingJob.completed_at
                                <= func.now() - text("INTERVAL '1 minute' * POW(2, retry_count)"),
                            ),
                        )
                    )
                    .order_by(ScrapingJob.completed_at.asc().nullsfirst())
                    .limit(max_jobs)
                )

                jobs = session.execute(stmt).scalars().all()

                logger.debug("Retrieved retry jobs", count=len(jobs), max_jobs=max_jobs)
                return list(jobs)

        except SQLAlchemyError as e:
            logger.error("Failed to retrieve retry jobs", error=str(e))
            raise DatabaseError(f"Retry jobs retrieval failed: {e}") from e

    # Elegant Array-Based Job Processing (auto-batch detection)

    def create_jobs(self, urls: list[str], **job_config) -> list[ScrapingJob]:
        """Create jobs from URL array with automatic batch detection.

        Elegant approach:
        - Single URL: batch_id = None (individual job)
        - Multiple URLs: auto-generate batch_id (batch processing)

        Args:
            urls: List of URLs to process (single item = individual, multiple = batch)
            **job_config: Configuration applied to all jobs

        Returns:
            List of created jobs
        """
        if not urls:
            raise ValueError("URLs list cannot be empty")

        try:
            with self.get_session() as session:
                # Auto-batch detection: multiple URLs = batch, single URL = individual
                batch_id = str(uuid4()) if len(urls) > 1 else None

                jobs = []
                for url in urls:
                    job = ScrapingJob(
                        source_url=url,
                        job_type="single",
                        target_format="html",
                        batch_id=batch_id,
                        **job_config
                    )
                    jobs.append(job)
                    session.add(job)

                session.flush()  # Get job IDs

                logger.info(
                    "Created jobs",
                    job_count=len(jobs),
                    batch_id=batch_id,
                    is_batch=batch_id is not None,
                )

                return jobs

        except SQLAlchemyError as e:
            logger.error("Job creation failed", urls_count=len(urls), error=str(e))
            raise DatabaseError(f"Job creation failed: {e}") from e

    def get_batch_jobs(self, batch_id: str) -> list[ScrapingJob]:
        """Get all jobs in a batch.

        Args:
            batch_id: Batch identifier

        Returns:
            List of jobs in the batch
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(ScrapingJob)
                    .where(ScrapingJob.batch_id == batch_id)
                    .order_by(ScrapingJob.created_at)
                )
                jobs = session.scalars(stmt).all()
                return list(jobs)

        except SQLAlchemyError as e:
            logger.error("Failed to get batch jobs", batch_id=batch_id, error=str(e))
            raise DatabaseError(f"Batch jobs retrieval failed: {e}") from e

    def get_batch_summary(self, batch_id: str) -> dict[str, Any]:
        """Get batch progress summary.

        Args:
            batch_id: Batch identifier

        Returns:
            Dictionary with job counts and progress
        """
        try:
            with self.get_session() as session:
                counts_stmt = select(
                    func.count(ScrapingJob.id).label("total"),
                    func.sum(case((ScrapingJob.status == "pending", 1), else_=0)).label("pending"),
                    func.sum(case((ScrapingJob.status == "running", 1), else_=0)).label("running"),
                    func.sum(case((ScrapingJob.status == "completed", 1), else_=0)).label(
                        "completed"
                    ),
                    func.sum(case((ScrapingJob.status == "failed", 1), else_=0)).label("failed"),
                    func.sum(case((ScrapingJob.status == "skipped", 1), else_=0)).label("skipped"),
                ).where(ScrapingJob.batch_id == batch_id)

                counts = session.execute(counts_stmt).one()

                return {
                    "batch_id": batch_id,
                    "total": counts.total,
                    "pending": counts.pending,
                    "running": counts.running,
                    "completed": counts.completed,
                    "failed": counts.failed,
                    "skipped": counts.skipped,
                    "success_rate": counts.completed / counts.total if counts.total > 0 else 0.0,
                }

        except SQLAlchemyError as e:
            logger.error("Failed to get batch summary", batch_id=batch_id, error=str(e))
            raise DatabaseError(f"Batch summary failed: {e}") from e

    # Content and Logging Operations

    def save_content_result(
        self,
        job_id: str,  # Fixed: Database model uses string job_id
        html_content: str | None = None,
        metadata: dict[str, Any] | None = None,
        file_paths: dict[str, str] | None = None,
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

    def add_job_log(self, request: JobLogRequest | None = None, **kwargs) -> JobLog | None:
        """Add a log entry for a job.

        Args:
            request: Job log request containing all parameters (new style)
            **kwargs: Legacy arguments (job_id, level, message, component, operation, context_data)

        Returns:
            Created JobLog instance
        """
        # Support both old and new calling styles
        if request is None:
            job_id = kwargs.get("job_id")
            level = kwargs.get("level")
            message = kwargs.get("message")

            if job_id is None or level is None or message is None:
                raise ValueError(
                    "Either request object or job_id, level, and message must be provided"
                )
            request = JobLogRequest(
                job_id=job_id,
                level=level,
                message=message,
                component=kwargs.get("component"),
                operation=kwargs.get("operation"),
                context_data=kwargs.get("context_data"),
            )
        try:
            with self.get_session() as session:
                log_entry = JobLog(
                    job_id=request.job_id,
                    level=request.level.upper(),
                    message=request.message,
                    component=request.component,
                    operation=request.operation,
                    context_data=request.context_data,
                )

                session.add(log_entry)
                session.flush()

                return log_entry

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to add job log", job_id=request.job_id, error=str(e))
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
                cutoff_date = datetime.now(UTC) - timedelta(days=days)

                # Overall statistics
                stats_stmt = select(
                    func.count(ScrapingJob.id).label("total_jobs"),  # pylint: disable=not-callable
                    func.count(ScrapingJob.id)  # pylint: disable=not-callable
                    .filter(ScrapingJob.status == "completed")
                    .label("completed_jobs"),
                    func.count(ScrapingJob.id)  # pylint: disable=not-callable
                    .filter(ScrapingJob.status == "failed")
                    .label("failed_jobs"),
                    func.count(ScrapingJob.id)  # pylint: disable=not-callable
                    .filter(ScrapingJob.status == "pending")
                    .label("pending_jobs"),
                    func.avg(ScrapingJob.processing_time_ms).label("avg_duration"),
                    func.sum(ScrapingJob.output_size_bytes).label("total_content_size"),
                    func.count(ScrapingJob.id)
                    .filter(ScrapingJob.output_size_bytes.isnot(None))
                    .label("total_processed"),
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
                cutoff_date = datetime.now(UTC) - timedelta(days=days)

                # Delete old completed jobs and their associated data
                deleted_count = session.execute(
                    select(func.count(ScrapingJob.id)).where(  # pylint: disable=not-callable
                        and_(
                            ScrapingJob.status.in_(["completed", "failed"]),
                            ScrapingJob.completed_at < cutoff_date,
                        )
                    )
                ).scalar()

                session.execute(
                    update(ScrapingJob)
                    .where(
                        and_(
                            ScrapingJob.status.in_(["completed", "failed"]),
                            ScrapingJob.completed_at < cutoff_date,
                        )
                    )
                    .values(status="cancelled")  # Soft delete by changing status
                )

                logger.info("Cleaned up old jobs", deleted_count=deleted_count, days=days)
                return deleted_count

        except SQLAlchemyError as e:
            logger.error("Failed to cleanup old jobs", error=str(e))
            raise DatabaseError(f"Job cleanup failed: {e}") from e
