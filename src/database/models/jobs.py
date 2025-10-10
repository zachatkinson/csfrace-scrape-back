"""Job-related database models.

This module contains models for scraping jobs, content results, and job logs.
Follows Single Responsibility Principle by focusing only on job domain.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from .auth import User

# Note: User relationship uses string-based forward reference
# No import needed due to SQLAlchemy's lazy evaluation
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.logging_hierarchy import get_database_logger

from ...common.status import JobStatus
from .base import Base

logger = get_database_logger()


class ScrapingJob(Base):
    """Model for individual scraping jobs.

    Represents a single URL to be scraped with all associated metadata,
    configuration, and status tracking.
    """

    __tablename__ = "jobs"

    # Primary identification - match actual database schema (UUID type)
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    # User association - REQUIRED for all jobs
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Domain extracted from source_url for efficient querying and analytics
    domain: Mapped[str] = mapped_column(
        String(253),  # RFC 2181 compliant maximum domain length
        nullable=False,
        index=True,  # Performance optimization for domain-based queries
        comment="Extracted domain from source_url for efficient statistics and filtering",
    )

    target_format: Mapped[str] = mapped_column(String, nullable=False, default="html")

    # Job management
    status: Mapped[str] = mapped_column(
        String,
        default="pending",
        nullable=False,
        index=True,
    )
    # priority: Removed - YAGNI (not used for filtering, ordering, or queue processing)

    # Execution tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Configuration and options (includes metadata)
    options: Mapped[dict[str, Any] | None] = mapped_column(JSON, server_default="{}")

    # Results and errors
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timing information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Performance metrics
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    download_size_bytes: Mapped[int | None] = mapped_column(Integer)
    output_size_bytes: Mapped[int | None] = mapped_column(Integer)

    # Progress tracking (0-100)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Batch grouping (foreign key exists at database level)
    batch_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="scraping_jobs")
    content_results: Mapped[list["ContentResult"]] = relationship(
        "ContentResult", back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    job_logs: Mapped[list["JobLog"]] = relationship(
        "JobLog", back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        """String representation of the job."""
        return (
            f"<ScrapingJob(id={self.id}, source_url='{self.source_url}', status='{self.status}')>"
        )

    @property
    def status_enum(self) -> JobStatus:
        """Return status as enum instance."""
        return JobStatus(self.status)

    # priority_enum property removed - field no longer exists

    @property
    def is_finished(self) -> bool:
        """Check if job is in a finished state."""
        return self.status in {"completed", "failed", "cancelled"}

    @property
    def duration(self) -> float | None:
        """Calculate job duration from start and completion times."""
        if self.started_at is not None and self.completed_at is not None:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == "failed" and self.retry_count < self.max_retries


class ContentResult(Base):
    """Model for storing converted content results.

    Stores the actual converted HTML content, extracted metadata,
    and file locations for each successful scraping job.
    """

    __tablename__ = "content_results"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
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
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Log entry details
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # INFO, WARN, ERROR, DEBUG
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
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
        return (
            f"<JobLog(id={self.id}, job_id={self.job_id}, "
            f"level='{self.level}', timestamp='{self.timestamp}')>"
        )
