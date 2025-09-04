"""SQLAlchemy models for scraping operations data persistence.

This module defines the database schema for storing scraping jobs, results, and metadata
following CLAUDE.md standards with proper relationships and constraints.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..constants import CONSTANTS


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class JobStatus(Enum):
    """Status enumeration for scraping jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class JobPriority(Enum):
    """Priority levels for job scheduling."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ScrapingJob(Base):
    """Model for individual scraping jobs.

    Represents a single URL to be scraped with all associated metadata,
    configuration, and status tracking.
    """

    __tablename__ = "scraping_jobs"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)

    # Job management - Using PostgreSQL native enums for better concurrent handling
    status: Mapped[JobStatus] = mapped_column(
        PostgreSQLEnum(JobStatus, name="jobstatus", create_type=False),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority: Mapped[JobPriority] = mapped_column(
        PostgreSQLEnum(JobPriority, name="jobpriority", create_type=False),
        default=JobPriority.NORMAL,
        nullable=False,
    )

    # Timing information
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Execution tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=CONSTANTS.MAX_RETRIES, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=CONSTANTS.DEFAULT_TIMEOUT, nullable=False
    )

    # Output configuration
    output_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    custom_slug: Mapped[str | None] = mapped_column(String(255))
    skip_existing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Results and errors
    error_message: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(255))
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Performance metrics (Unix timestamps)
    start_time: Mapped[float | None] = mapped_column()
    end_time: Mapped[float | None] = mapped_column()
    duration_seconds: Mapped[float | None] = mapped_column()
    content_size_bytes: Mapped[int | None] = mapped_column(Integer)
    images_downloaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Configuration (JSON field for flexibility)
    converter_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    processing_options: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Archive information
    archive_path: Mapped[str | None] = mapped_column(String(1024))
    archive_size_bytes: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), index=True
    )
    batch: Mapped[Optional["Batch"]] = relationship("Batch", back_populates="jobs")

    content_results: Mapped[list["ContentResult"]] = relationship(
        "ContentResult", back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    job_logs: Mapped[list["JobLog"]] = relationship(
        "JobLog", back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        """String representation of the job."""
        return f"<ScrapingJob(id={self.id}, url='{self.url}', status='{self.status.value}')>"

    @property
    def is_finished(self) -> bool:
        """Check if job is in a finished state."""
        return self.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == JobStatus.FAILED and self.retry_count < self.max_retries

    @property
    def duration(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time


class Batch(Base):
    """Model for batch processing operations.

    Represents a collection of related scraping jobs processed together,
    with shared configuration and progress tracking.
    """

    __tablename__ = "batches"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Batch status and timing - Using PostgreSQL native enum for consistency
    status: Mapped[JobStatus] = mapped_column(
        PostgreSQLEnum(JobStatus, name="jobstatus", create_type=False),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Configuration
    max_concurrent: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    continue_on_error: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    output_base_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    create_archives: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cleanup_after_archive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Progress tracking
    total_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Summary data (JSON for flexibility)
    summary_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    batch_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Relationships
    jobs: Mapped[list[ScrapingJob]] = relationship(
        "ScrapingJob", back_populates="batch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the batch."""
        return f"<Batch(id={self.id}, name='{self.name}', status='{self.status.value}')>"

    @property
    def success_rate(self) -> float:
        """Calculate batch success rate."""
        if self.total_jobs is None or self.total_jobs == 0:
            return 0.0
        if self.completed_jobs is None:
            return 0.0
        return self.completed_jobs / self.total_jobs


class ContentResult(Base):
    """Model for storing converted content results.

    Stores the actual converted HTML content, extracted metadata,
    and file locations for each successful scraping job.
    """

    __tablename__ = "content_results"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Content storage
    original_html: Mapped[str | None] = mapped_column(Text)
    converted_html: Mapped[str | None] = mapped_column(Text)
    shopify_html: Mapped[str | None] = mapped_column(Text)

    # File locations
    html_file_path: Mapped[str | None] = mapped_column(String(1024))
    metadata_file_path: Mapped[str | None] = mapped_column(String(1024))
    images_directory: Mapped[str | None] = mapped_column(String(1024))

    # Metadata
    title: Mapped[str | None] = mapped_column(String(500))
    meta_description: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[datetime | None] = mapped_column(DateTime)
    author: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    categories: Mapped[list[str] | None] = mapped_column(JSON)

    # SEO and social metadata
    og_title: Mapped[str | None] = mapped_column(String(500))
    og_description: Mapped[str | None] = mapped_column(Text)
    og_image: Mapped[str | None] = mapped_column(String(1024))
    twitter_card: Mapped[str | None] = mapped_column(String(50))

    # Processing statistics
    word_count: Mapped[int | None] = mapped_column(Integer)
    image_count: Mapped[int | None] = mapped_column(Integer)
    link_count: Mapped[int | None] = mapped_column(Integer)
    processing_time_seconds: Mapped[float | None] = mapped_column()

    # Additional metadata (JSON for flexibility)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    conversion_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    job: Mapped[ScrapingJob] = relationship("ScrapingJob", back_populates="content_results")

    def __repr__(self) -> str:
        """String representation of the content result."""
        return f"<ContentResult(id={self.id}, job_id={self.job_id}, title='{self.title}')>"


class JobLog(Base):
    """Model for detailed job execution logs.

    Stores timestamped log entries for debugging, monitoring,
    and audit trail purposes.
    """

    __tablename__ = "job_logs"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Log entry details
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # INFO, WARN, ERROR, DEBUG
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    # Contextual information
    component: Mapped[str | None] = mapped_column(
        String(100)
    )  # html_processor, image_downloader, etc.
    operation: Mapped[str | None] = mapped_column(String(100))  # fetch, process, save, etc.

    # Additional context data (JSON for structured logging)
    context_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Exception information (for errors)
    exception_type: Mapped[str | None] = mapped_column(String(255))
    exception_traceback: Mapped[str | None] = mapped_column(Text)

    # Relationships
    job: Mapped[ScrapingJob] = relationship("ScrapingJob", back_populates="job_logs")

    def __repr__(self) -> str:
        """String representation of the log entry."""
        return f"<JobLog(id={self.id}, job_id={self.job_id}, level='{self.level}', timestamp='{self.timestamp}')>"


class SystemMetrics(Base):
    """Model for system-wide metrics and performance data.

    Stores aggregated metrics for monitoring system health,
    performance trends, and capacity planning.
    """

    __tablename__ = "system_metrics"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Metric values
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    numeric_value: Mapped[float | None] = mapped_column()
    string_value: Mapped[str | None] = mapped_column(String(500))
    json_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Categorization
    component: Mapped[str | None] = mapped_column(String(100), index=True)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)

    # Tags for flexible querying (JSON array)
    tags: Mapped[dict[str, str] | None] = mapped_column(JSON)

    def __repr__(self) -> str:
        """String representation of the metrics entry."""
        return (
            f"<SystemMetrics(id={self.id}, type='{self.metric_type}', name='{self.metric_name}')>"
        )


# PostgreSQL enum metadata event listener (SQLAlchemy best practice)
from sqlalchemy import event

@event.listens_for(Base.metadata, "before_create")
def _create_enums_before_tables(target, connection, **kw):
    """Create PostgreSQL enum types before table creation.
    
    This event listener follows SQLAlchemy best practices for PostgreSQL enum handling
    by ensuring enum types exist before any table creation attempts.
    """
    enum_definitions = [
        ("jobstatus", JobStatus),
        ("jobpriority", JobPriority),
    ]
    
    for enum_name, enum_class in enum_definitions:
        try:
            # Check if enum type already exists using PostgreSQL system catalogs
            result = connection.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = :enum_name)"),
                {"enum_name": enum_name},
            ).scalar()
            
            if not result:
                # Create enum type using SQLAlchemy PostgreSQL dialect
                pg_enum = PostgreSQLEnum(enum_class, name=enum_name, create_type=True)
                pg_enum.create(connection, checkfirst=True)
            
        except Exception as e:
            # Handle concurrent enum creation gracefully (for parallel tests)
            error_msg = str(e).lower()
            if not any(phrase in error_msg for phrase in ["already exists", "duplicate key"]):
                # Only re-raise if it's not a concurrency issue
                raise


# Database configuration and utilities
def get_database_url() -> str:
    """Generate PostgreSQL database URL from environment variables.

    Returns:
        PostgreSQL database URL string for PostgreSQL 17.6+
    """
    import os

    # First check if DATABASE_URL is provided directly (Docker Compose sets this)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Replace psycopg with asyncpg for async support if needed
        if "postgresql://" in database_url:
            return database_url.replace("postgresql://", "postgresql+psycopg://")
        return database_url

    # Fallback: build from individual environment variables
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")
    database = os.getenv("DATABASE_NAME", "scraper_db")
    username = os.getenv("DATABASE_USER", "scraper_user")
    password = os.getenv("DATABASE_PASSWORD", "scraper_password")

    return f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"


def create_database_engine(echo: bool = False):
    """Create SQLAlchemy engine optimized for PostgreSQL 17.6.

    Args:
        echo: Whether to echo SQL statements (for debugging)

    Returns:
        SQLAlchemy Engine instance configured for PostgreSQL 17.6+
    """
    from sqlalchemy import event

    database_url = get_database_url()

    # PostgreSQL 17.6 optimized configuration following 2025 best practices
    engine = create_engine(
        database_url,
        echo=echo,
        # Connection pool settings optimized for concurrent web scraping
        pool_size=20,  # Base connections (increased for concurrent scraping)
        max_overflow=30,  # Additional connections under load
        pool_timeout=30,  # Timeout to get connection from pool
        pool_recycle=3600,  # Recycle connections every hour
        pool_pre_ping=True,  # Validate connections before use
        # Set isolation level directly on engine (SQLAlchemy 2.0 way)
        isolation_level="READ_COMMITTED",
        # PostgreSQL 17.6 specific optimizations
        connect_args={
            "connect_timeout": 10,  # Connection establishment timeout
            "application_name": "csfrace-scraper",  # For monitoring/debugging
        },
    )

    # PostgreSQL connection reset handler for proper resource management
    @event.listens_for(engine, "reset")
    def _reset_postgresql(dbapi_connection, _connection_record, reset_state):
        """Reset PostgreSQL connections properly following best practices."""
        if not reset_state.terminate_only:
            # Use cursor for SQL commands - psycopg2 connection doesn't have execute method
            with dbapi_connection.cursor() as cursor:
                cursor.execute("CLOSE ALL")  # Close cursors
                cursor.execute("RESET ALL")  # Reset session variables
                cursor.execute("DISCARD TEMP")  # Clean up temp tables
        dbapi_connection.rollback()  # Ensure clean transaction state

    return engine
