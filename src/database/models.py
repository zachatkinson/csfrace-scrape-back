"""SQLAlchemy models for scraping operations data persistence.

This module defines the database schema for storing scraping jobs, results, and metadata
following CLAUDE.md standards with proper relationships and constraints.
"""

from datetime import datetime, timezone
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
)
from sqlalchemy import (
    Enum as SQLEnum,
)
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
    slug: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # Job management
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )
    priority: Mapped[JobPriority] = mapped_column(
        SQLEnum(JobPriority), default=JobPriority.NORMAL, nullable=False
    )

    # Timing information
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Execution tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=CONSTANTS.MAX_RETRIES, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=CONSTANTS.DEFAULT_TIMEOUT, nullable=False
    )

    # Output configuration
    output_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    custom_slug: Mapped[Optional[str]] = mapped_column(String(255))
    skip_existing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Results and errors
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_type: Mapped[Optional[str]] = mapped_column(String(255))
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Performance metrics (Unix timestamps)
    start_time: Mapped[Optional[float]] = mapped_column()
    end_time: Mapped[Optional[float]] = mapped_column()
    duration_seconds: Mapped[Optional[float]] = mapped_column()
    content_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    images_downloaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Configuration (JSON field for flexibility)
    converter_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    processing_options: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # Archive information
    archive_path: Mapped[Optional[str]] = mapped_column(String(1024))
    archive_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batches.id"), index=True)
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
    def duration(self) -> Optional[float]:
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
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Batch status and timing
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Configuration
    max_concurrent: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
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
    summary_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    batch_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

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
    original_html: Mapped[Optional[str]] = mapped_column(Text)
    converted_html: Mapped[Optional[str]] = mapped_column(Text)
    shopify_html: Mapped[Optional[str]] = mapped_column(Text)

    # File locations
    html_file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    metadata_file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    images_directory: Mapped[Optional[str]] = mapped_column(String(1024))

    # Metadata
    title: Mapped[Optional[str]] = mapped_column(String(500))
    meta_description: Mapped[Optional[str]] = mapped_column(Text)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON)
    categories: Mapped[Optional[list[str]]] = mapped_column(JSON)

    # SEO and social metadata
    og_title: Mapped[Optional[str]] = mapped_column(String(500))
    og_description: Mapped[Optional[str]] = mapped_column(Text)
    og_image: Mapped[Optional[str]] = mapped_column(String(1024))
    twitter_card: Mapped[Optional[str]] = mapped_column(String(50))

    # Processing statistics
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    image_count: Mapped[Optional[int]] = mapped_column(Integer)
    link_count: Mapped[Optional[int]] = mapped_column(Integer)
    processing_time_seconds: Mapped[Optional[float]] = mapped_column()

    # Additional metadata (JSON for flexibility)
    extra_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    conversion_stats: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Contextual information
    component: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # html_processor, image_downloader, etc.
    operation: Mapped[Optional[str]] = mapped_column(String(100))  # fetch, process, save, etc.

    # Additional context data (JSON for structured logging)
    context_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # Exception information (for errors)
    exception_type: Mapped[Optional[str]] = mapped_column(String(255))
    exception_traceback: Mapped[Optional[str]] = mapped_column(Text)

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
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Metric values
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    numeric_value: Mapped[Optional[float]] = mapped_column()
    string_value: Mapped[Optional[str]] = mapped_column(String(500))
    json_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # Categorization
    component: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)

    # Tags for flexible querying (JSON array)
    tags: Mapped[Optional[dict[str, str]]] = mapped_column(JSON)

    def __repr__(self) -> str:
        """String representation of the metrics entry."""
        return (
            f"<SystemMetrics(id={self.id}, type='{self.metric_type}', name='{self.metric_name}')>"
        )


# Database configuration and utilities
def get_database_url() -> str:
    """Generate PostgreSQL database URL from environment variables.

    Returns:
        PostgreSQL database URL string for PostgreSQL 17.6+
    """
    import os

    # Get database configuration from environment variables with secure defaults
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")
    database = os.getenv("DATABASE_NAME", "scraper_db")
    username = os.getenv("DATABASE_USER", "scraper_user")
    password = os.getenv("DATABASE_PASSWORD", "scraper_password")

    return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"


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
