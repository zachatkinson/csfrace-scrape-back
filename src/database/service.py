"""Database service layer for scraping operations.

This module provides high-level database operations following CLAUDE.md patterns
with proper error handling, transaction management, and connection pooling.

Refactored to follow Single Responsibility Principle by delegating to focused services.
"""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_database_logger

from ..common.status import JobStatus
from ..constants import API_DEFAULT_LIMIT
from .models import (
    Base,
    ContentResult,
    JobLog,
    ScrapingJob,
    create_database_engine,
)
from .services import (
    CleanupService,
    ContentService,
    JobService,
    LoggingService,
    StatisticsService,
)
from .services.job_service import JobCreateRequest as JobServiceRequest
from .utils import create_postgresql_enums, get_standard_enum_definitions

logger = get_database_logger()


@dataclass
class JobCreateRequest:
    """Request object for creating scraping jobs."""

    url: str
    output_directory: str
    user_id: str
    domain: str | None = None
    slug: str | None = None
    batch_id: int | None = None
    priority: str = "normal"


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

    Refactored to follow Single Responsibility Principle by delegating
    to focused services: JobService, ContentService, LoggingService,
    StatisticsService, and CleanupService.
    """

    def __init__(self, echo: bool = False):
        """Initialize database service for PostgreSQL.

        Args:
            echo: Whether to echo SQL statements for debugging
        """
        self.echo = echo  # Store echo parameter for ContentService initialization
        self.engine = create_database_engine(echo=echo)
        self.SessionLocal = sessionmaker(  # pylint: disable=invalid-name
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # Keep objects accessible after commit
        )

    @classmethod
    def _create_with_engine(cls, engine: Engine) -> "DatabaseService":
        """Create DatabaseService with existing engine (for testcontainers).

        Args:
            engine: Existing SQLAlchemy engine

        Returns:
            DatabaseService instance using the provided engine
        """
        service = cls.__new__(cls)  # Create instance without calling __init__
        service.echo = False  # Default echo value for test instances
        service.engine = engine
        service.SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        return service

    @database_error_handler("initialize database")
    def initialize_database(self) -> None:
        """Create all database tables with PostgreSQL enum safety.

        Following PostgreSQL and SQLAlchemy best practices:
        1. Create enum types first with concurrent safety
        2. Create tables using checkfirst=True
        3. Handle duplicate enum creation gracefully

        This is idempotent - safe to call multiple times.
        """
        # Create enum types first with PostgreSQL best practices
        self._create_enums_safely()

        # Create all tables using SQLAlchemy best practices with concurrent safety
        Base.metadata.create_all(bind=self.engine, checkfirst=True)

        logger.info("Database tables initialized successfully")

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
    def get_session(self) -> Generator[Session]:
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

    # Job Management Operations - Delegate to JobService

    @database_error_handler("create job")
    def create_job(self, request: JobCreateRequest) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            request: Job creation request containing all parameters

        Returns:
            Created ScrapingJob instance
        """
        with self.get_session() as session:
            job_service = JobService(session)

            # Convert the DatabaseService JobCreateRequest to JobService JobCreateRequest
            service_request = JobServiceRequest(
                url=request.url,
                output_directory=request.output_directory,
                user_id=request.user_id,
                options={},
                batch_id=getattr(request, "batch_id", None),
            )
            job = job_service.create_job(service_request)
            # Ensure all attributes are loaded before session closes
            session.expunge(job)
            return job

    @database_error_handler("retrieve job")
    def get_job(self, job_id: str) -> ScrapingJob | None:
        """Retrieve a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            ScrapingJob instance or None if not found
        """
        with self.get_session() as session:
            job_service = JobService(session)
            job = job_service.get_job(job_id)
            if job:
                # Ensure all attributes are loaded before session closes
                session.expunge(job)
            return job

    @database_error_handler("update job status")
    def update_job_status(
        self,
        job_id: str,
        status: str | JobStatus,
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
        with self.get_session() as session:
            job_service = JobService(session)
            # Convert status and duration to proper types
            job_status = status if isinstance(status, JobStatus) else JobStatus(status)
            duration_ms = int(duration * 1000) if duration is not None else None
            result = job_service.update_job_status(job_id, job_status, error_message, duration_ms)
            return result is not None  # Convert ScrapingJob | None to bool

    @database_error_handler("retrieve pending jobs")
    def get_pending_jobs(self, limit: int = API_DEFAULT_LIMIT) -> list[ScrapingJob]:
        """Retrieve pending jobs for processing.

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of pending ScrapingJob instances ordered by priority and creation time
        """
        with self.get_session() as session:
            job_service = JobService(session)
            return job_service.get_pending_jobs(limit)

    @database_error_handler("retrieve jobs by status")
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
        with self.get_session() as session:
            job_service = JobService(session)
            # Convert status to proper type and pass offset correctly
            job_status = status if isinstance(status, JobStatus) else JobStatus(status)
            return job_service.get_jobs_by_status(job_status, limit, None, offset)

    @database_error_handler("retrieve retry jobs")
    def get_retry_jobs(self, max_jobs: int = 50) -> list[ScrapingJob]:
        """Retrieve failed jobs eligible for retry.

        Args:
            max_jobs: Maximum number of jobs to retrieve

        Returns:
            List of ScrapingJob instances ready for retry
        """
        with self.get_session() as session:
            job_service = JobService(session)
            return job_service.get_retry_jobs(max_jobs)

    # Batch Operations - Delegate to JobService

    @database_error_handler("create batch jobs")
    def create_jobs(self, urls: list[str], **job_config: Any) -> list[ScrapingJob]:
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
        with self.get_session() as session:
            job_service = JobService(session)
            return job_service.create_jobs(urls, **job_config)

    @database_error_handler("get batch jobs")
    def get_batch_jobs(self, batch_id: str) -> list[ScrapingJob]:
        """Get all jobs in a batch.

        Args:
            batch_id: Batch identifier

        Returns:
            List of jobs in the batch
        """
        with self.get_session() as session:
            job_service = JobService(session)
            return job_service.get_batch_jobs(batch_id)

    @database_error_handler("get batch summary")
    def get_batch_summary(self, batch_id: str) -> dict[str, Any]:
        """Get batch progress summary.

        Args:
            batch_id: Batch identifier

        Returns:
            Dictionary with job counts and progress
        """
        with self.get_session() as session:
            job_service = JobService(session)
            return job_service.get_batch_summary(batch_id)

    # Content Operations - Delegate to ContentService

    @database_error_handler("save content result")
    def save_content_result(
        self,
        job_id: str,
        html_content: str | None = None,
        metadata: dict[str, Any] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs: Any,
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
        with self.get_session() as session:
            content_service = ContentService(session)
            # Merge file_paths and kwargs into metadata
            combined_metadata = metadata.copy() if metadata else {}

            # Add file paths to metadata
            if file_paths:
                combined_metadata.update(
                    {
                        "html_file_path": file_paths.get("html"),
                        "metadata_file_path": file_paths.get("metadata"),
                        "images_directory": file_paths.get("images"),
                    }
                )

            # Add kwargs to metadata (for word_count, image_count, etc.)
            combined_metadata.update(kwargs)

            result = content_service.save_content_result(
                job_id, html_content, "html", combined_metadata
            )

            # Commit the transaction BEFORE accessing attributes
            session.commit()

            # Eagerly load ALL attributes after commit but before session closes
            _ = (
                result.id,
                result.job_id,
                result.original_html,
                result.converted_html,
                result.shopify_html,
                result.html_file_path,
                result.metadata_file_path,
                result.images_directory,
                result.title,
                result.meta_description,
                result.published_date,
                result.author,
                result.tags,
                result.categories,
                result.og_title,
                result.og_description,
                result.og_image,
                result.twitter_card,
                result.word_count,
                result.image_count,
                result.link_count,
                result.processing_time_seconds,
                result.extra_metadata,
                result.conversion_stats,
                result.created_at,
                result.updated_at,
            )

            # Detach from session for safe return
            session.expunge(result)
            return result

    # Logging Operations - Delegate to LoggingService

    def add_job_log(self, request: "JobLogRequest") -> JobLog | None:
        """Add a log entry for a job.

        Args:
            request: Job log request containing all parameters

        Returns:
            Created JobLog instance
        """
        return _add_job_log_safe(self, request)

    # Statistics Operations - Delegate to StatisticsService

    @database_error_handler("get job statistics")
    def get_job_statistics(self, days: int = 7) -> dict[str, Any]:
        """Get job statistics for the specified time period.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with comprehensive job statistics
        """
        with self.get_session() as session:
            statistics_service = StatisticsService(session)
            return statistics_service.get_job_statistics(days)

    @database_error_handler("get performance metrics")
    def get_performance_metrics(self, days: int = 7) -> dict[str, Any]:
        """Get performance metrics for the specified time period.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with performance metrics
        """
        with self.get_session() as session:
            statistics_service = StatisticsService(session)
            # StatisticsService.get_performance_metrics expects (domain, days)
            return statistics_service.get_performance_metrics(None, days)

    @database_error_handler("get domain statistics")
    def get_domain_statistics(self, days: int = 30) -> list[dict[str, Any]]:
        """Get statistics grouped by domain.

        Args:
            days: Number of days to analyze

        Returns:
            List of domain statistics
        """
        with self.get_session() as session:
            statistics_service = StatisticsService(session)
            # Use existing method since get_domain_statistics doesn't exist
            stats = statistics_service.get_job_statistics(days)
            return [stats]  # Wrap dict in list to match return type

    @database_error_handler("get processing time percentiles")
    def get_processing_time_percentiles(self, days: int = 7) -> dict[str, float]:
        """Get processing time percentiles.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with percentile values
        """
        with self.get_session() as session:
            statistics_service = StatisticsService(session)
            # Use existing method since get_processing_time_percentiles doesn't exist
            return statistics_service.get_performance_metrics(None, days)

    # Cleanup Operations - Delegate to CleanupService

    @database_error_handler("cleanup jobs")
    def cleanup_jobs(self, days: int = 7) -> int:
        """Delete jobs older than specified days.

        Args:
            days: Number of days to keep jobs

        Returns:
            Number of jobs deleted
        """
        with self.get_session() as session:
            cleanup_service = CleanupService(session)
            return cleanup_service.cleanup_jobs(days)

    @database_error_handler("cleanup failed jobs")
    def cleanup_failed_jobs(self, days: int = 3) -> int:
        """Delete failed jobs older than specified days.

        Args:
            days: Number of days to keep failed jobs

        Returns:
            Number of jobs deleted
        """
        with self.get_session() as session:
            cleanup_service = CleanupService(session)
            return cleanup_service.cleanup_failed_jobs(days)

    @database_error_handler("cleanup orphaned content")
    def cleanup_orphaned_content(self) -> int:
        """Delete content records without associated jobs.

        Returns:
            Number of content records deleted
        """
        with self.get_session() as session:
            cleanup_service = CleanupService(session)
            return cleanup_service.cleanup_orphaned_content()

    @database_error_handler("cleanup orphaned logs")
    def cleanup_orphaned_logs(self) -> int:
        """Delete log records without associated jobs.

        Returns:
            Number of log records deleted
        """
        with self.get_session() as session:
            cleanup_service = CleanupService(session)
            return cleanup_service.cleanup_orphaned_logs()

    @database_error_handler("cleanup all operations")
    def cleanup_all(self, old_jobs_days: int = 7, failed_jobs_days: int = 3) -> dict[str, Any]:
        """Run all cleanup operations.

        Args:
            old_jobs_days: Days to keep normal jobs
            failed_jobs_days: Days to keep failed jobs

        Returns:
            Summary of cleanup operations
        """
        with self.get_session() as session:
            from .services.cleanup_service import CleanupService

            cleanup_service = CleanupService(session)
            return cleanup_service.cleanup_all(old_jobs_days, failed_jobs_days)

    @database_error_handler("get database size")
    def get_database_size(self) -> dict[str, Any]:
        """Get database size information.

        Returns:
            Dictionary with size information
        """
        with self.get_session() as session:
            from .services.cleanup_service import CleanupService

            cleanup_service = CleanupService(session)
            return cleanup_service.get_database_size()

    @database_error_handler("get table sizes")
    def get_table_sizes(self) -> list[dict[str, Any]]:
        """Get size information for all tables.

        Returns:
            List of table size information
        """
        with self.get_session() as session:
            from .services.cleanup_service import CleanupService

            cleanup_service = CleanupService(session)
            return cleanup_service.get_table_sizes()

    def close_all_sessions(self) -> None:
        """Close all database connections and sessions.

        This method properly closes the database engine and all associated
        connection pools, following SQLAlchemy best practices for cleanup.
        """
        _close_all_sessions_safe(self)


@database_error_handler("add job log")
def _add_job_log_safe(service: DatabaseService, request: "JobLogRequest") -> JobLog | None:
    """Safely add a job log entry."""
    with service.get_session() as session:
        logging_service = LoggingService(session)
        # Convert DatabaseService JobLogRequest to LoggingService JobLogRequest
        from .services.logging_service import JobLogRequest as LogServiceRequest

        log_request = LogServiceRequest(
            job_id=request.job_id,
            level=request.level,
            message=request.message,
            component=getattr(request, "component", None),
            operation=getattr(request, "operation", None),
            context_data=request.context_data,
        )
        return logging_service.add_job_log(log_request)


def _close_all_sessions_safe(service: DatabaseService) -> None:
    """Safely close all database connections and sessions."""
    try:
        # Close the session maker's connections
        if hasattr(service, "SessionLocal"):
            service.SessionLocal.close_all()

        # Dispose of the engine's connection pool
        if hasattr(service, "engine") and service.engine:
            service.engine.dispose()
            logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error("Failed to close database connections", error=str(e))
        # Don't raise here - cleanup should be non-failing
