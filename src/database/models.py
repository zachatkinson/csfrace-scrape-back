"""SQLAlchemy models for scraping operations data persistence.

This module defines the database schema for storing scraping jobs, results, and metadata
following CLAUDE.md standards with proper relationships and constraints.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Import enums from common status module
from ..common.status import JobPriority, JobStatus

# pylint: disable=too-few-public-methods  # SQLAlchemy models often have minimal methods
# pylint: disable=too-many-instance-attributes  # Database models need many fields
# pylint: disable=broad-exception-caught  # Acceptable for database event handlers
# pylint: disable=unused-argument  # SQLAlchemy event handlers have required signatures
# pylint: disable=import-outside-toplevel  # Conditional imports for database setup
# pylint: disable=redefined-outer-name  # SQLAlchemy events pattern
# pylint: disable=reimported  # Event module reimport for database functions


# Re-export enums for convenience (allows importing from models module)
__all__ = [
    "Base",
    "ScrapingJob",
    "ContentResult",
    "JobLog",
    "SystemMetrics",
    "WebAuthnCredential",
    "WebAuthnChallenge",
    "AccountLockout",
    "RevokedToken",
    "JobStatus",
    "JobPriority",
    "create_database_engine",
]


class Base(DeclarativeBase):
    """Base class for all database models."""


class ScrapingJob(Base):
    """Model for individual scraping jobs.

    Represents a single URL to be scraped with all associated metadata,
    configuration, and status tracking.
    """

    __tablename__ = "jobs"

    # Primary identification - match actual database schema
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    job_type: Mapped[str] = mapped_column(String, nullable=False, default="single")
    target_format: Mapped[str] = mapped_column(String, nullable=False, default="html")

    # Job management
    status: Mapped[str] = mapped_column(
        String,
        default="pending",
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

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

    # Batch grouping
    batch_id: Mapped[str | None] = mapped_column(String)

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

    @property
    def priority_enum(self) -> JobPriority:
        """Return priority as enum instance."""
        return JobPriority(self.priority)

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
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
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
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
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


class SystemMetrics(Base):
    """Model for system-wide metrics and performance data.

    Stores aggregated metrics for monitoring system health,
    performance trends, and capacity planning.
    """

    __tablename__ = "system_metrics"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
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


class WebAuthnCredential(Base):
    """Model for storing WebAuthn/FIDO2 credentials for passwordless authentication.

    Stores public key credentials for WebAuthn authentication following FIDO2 standards
    with proper security, performance indexing, and audit trails.
    """

    __tablename__ = "webauthn_credentials"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_id: Mapped[str] = mapped_column(
        String(1024), nullable=False, unique=True, index=True
    )  # Base64url-encoded credential ID

    # User association
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # References User.id from auth system

    # Credential data
    public_key: Mapped[str] = mapped_column(Text, nullable=False)  # Base64url-encoded public key
    sign_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Device information
    device_name: Mapped[str | None] = mapped_column(String(255))
    device_type: Mapped[str | None] = mapped_column(String(100))  # platform, cross-platform, etc.

    # Attestation data (optional, for security auditing)
    attestation_object: Mapped[str | None] = mapped_column(Text)  # Base64url-encoded
    attestation_format: Mapped[str | None] = mapped_column(
        String(50)
    )  # packed, tpm, android-key, etc.

    # Security and audit information
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    backup_eligible: Mapped[bool | None] = mapped_column(Boolean)  # From authenticator flags
    backup_state: Mapped[bool | None] = mapped_column(Boolean)  # From authenticator flags
    user_verified: Mapped[bool | None] = mapped_column(Boolean)  # Last authentication verification

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Geographic and network information (for security monitoring)
    registration_ip: Mapped[str | None] = mapped_column(String(45))  # IPv4 or IPv6
    registration_user_agent: Mapped[str | None] = mapped_column(Text)
    last_used_ip: Mapped[str | None] = mapped_column(String(45))
    last_used_user_agent: Mapped[str | None] = mapped_column(Text)

    # Additional security metadata
    security_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # When credential was revoked

    def __repr__(self) -> str:
        """String representation of the WebAuthn credential."""
        return (
            f"<WebAuthnCredential(id={self.id}, user_id='{self.user_id}', "
            f"device_name='{self.device_name}', is_active={self.is_active})>"
        )

    @property
    def is_revoked(self) -> bool:
        """Check if credential has been revoked."""
        return self.revoked_at is not None

    def revoke(self) -> None:
        """Mark credential as revoked."""
        self.is_active = False
        self.revoked_at = datetime.now(UTC)


class WebAuthnChallenge(Base):
    """Model for storing WebAuthn challenges during authentication flows.

    Temporary storage for challenges during registration and authentication
    with automatic cleanup and security validation.
    """

    __tablename__ = "webauthn_challenges"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )  # Unique challenge identifier

    # Challenge data
    challenge: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )  # Base64url-encoded challenge
    user_id: Mapped[str | None] = mapped_column(
        String(255), index=True
    )  # For user-specific challenges
    challenge_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'registration' or 'authentication'

    # Security context
    origin: Mapped[str | None] = mapped_column(String(255))  # Expected origin
    rp_id: Mapped[str | None] = mapped_column(String(255))  # Relying party ID
    user_verification: Mapped[str | None] = mapped_column(
        String(50)
    )  # required, preferred, discouraged

    # Network information for security validation
    client_ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Challenge lifecycle
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # When challenge was consumed

    # Additional context data
    context_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    def __repr__(self) -> str:
        """String representation of the WebAuthn challenge."""
        return (
            f"<WebAuthnChallenge(id={self.id}, type='{self.challenge_type}', "
            f"user_id='{self.user_id}', expires_at='{self.expires_at}')>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if challenge has expired."""
        return datetime.now(UTC) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if challenge has been used."""
        return self.used_at is not None

    def mark_used(self) -> None:
        """Mark challenge as used."""
        self.used_at = datetime.now(UTC)


class AccountLockout(Base):
    """Model for tracking account lockouts and failed login attempts - SOLID Single Responsibility Principle."""

    __tablename__ = "account_lockouts"

    # Primary key - unique lockout record ID
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="Unique lockout record identifier"
    )

    # User identification
    user_id: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False, comment="User ID who is locked out"
    )

    username: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="Username for quick lookups and audit trail",
    )

    # Lockout tracking
    failed_attempts: Mapped[int] = mapped_column(
        Integer, default=0, comment="Current number of consecutive failed login attempts"
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, comment="Current lockout status"
    )

    lockout_reason: Mapped[str | None] = mapped_column(
        String(100),
        comment="Reason for lockout (failed_attempts, suspicious_activity, admin_action)",
    )

    # Timing information
    first_failed_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Timestamp of first failed attempt in current sequence"
    )

    last_failed_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Timestamp of most recent failed attempt"
    )

    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Timestamp when account was locked"
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        comment="Timestamp when lockout expires (NULL for permanent)",
    )

    unlocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Timestamp when account was unlocked"
    )

    # Security audit trail
    client_ip: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        comment="IP address of failed login attempts",
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text, comment="User agent of failed login attempts"
    )

    unlocked_by: Mapped[str | None] = mapped_column(
        String(100), comment="Admin user who unlocked the account manually"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Record creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Last update timestamp",
    )

    @classmethod
    def create_lockout_record(
        cls,
        user_id: str,
        username: str,
        lockout_reason: str,
        failed_attempts: int = 0,
        client_ip: str | None = None,
        user_agent: str | None = None,
        lockout_duration_minutes: int | None = None,
    ) -> "AccountLockout":
        """Factory method for creating lockout records - SOLID Factory Pattern.

        Args:
            user_id: User identifier
            username: Username for audit trail
            lockout_reason: Reason for lockout
            failed_attempts: Number of failed attempts
            client_ip: IP address of attempts
            user_agent: User agent of attempts
            lockout_duration_minutes: Duration in minutes (None for permanent)

        Returns:
            AccountLockout instance ready for database insertion
        """
        now = datetime.now(UTC)
        locked_until = None
        if lockout_duration_minutes is not None:
            locked_until = now + timedelta(minutes=lockout_duration_minutes)

        return cls(
            user_id=user_id,
            username=username,
            failed_attempts=failed_attempts,
            is_locked=True,
            lockout_reason=lockout_reason,
            first_failed_attempt_at=now,
            last_failed_attempt_at=now,
            locked_at=now,
            locked_until=locked_until,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    @classmethod
    def create_failed_attempt_record(
        cls,
        user_id: str,
        username: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> "AccountLockout":
        """Factory method for creating failed attempt tracking records - SOLID Factory Pattern.

        Args:
            user_id: User identifier
            username: Username for audit trail
            client_ip: IP address of failed attempt
            user_agent: User agent of failed attempt

        Returns:
            AccountLockout instance for tracking failed attempts
        """
        now = datetime.now(UTC)

        return cls(
            user_id=user_id,
            username=username,
            failed_attempts=1,
            is_locked=False,
            lockout_reason=None,
            first_failed_attempt_at=now,
            last_failed_attempt_at=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    def unlock_account(self, unlocked_by: str | None = None) -> None:
        """Unlock the account - SOLID Single Responsibility.

        Args:
            unlocked_by: Admin user performing the unlock
        """
        self.is_locked = False
        self.unlocked_at = datetime.now(UTC)
        self.unlocked_by = unlocked_by
        self.updated_at = datetime.now(UTC)

    def increment_failed_attempts(
        self, client_ip: str | None = None, user_agent: str | None = None
    ) -> None:
        """Increment failed attempt counter - SOLID Single Responsibility.

        Args:
            client_ip: IP address of failed attempt
            user_agent: User agent of failed attempt
        """
        self.failed_attempts += 1
        self.last_failed_attempt_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

        # Update security audit trail
        if client_ip:
            self.client_ip = client_ip
        if user_agent:
            self.user_agent = user_agent

    def reset_failed_attempts(self) -> None:
        """Reset failed attempt counter after successful login - SOLID Single Responsibility."""
        self.failed_attempts = 0
        self.first_failed_attempt_at = None
        self.last_failed_attempt_at = None
        self.updated_at = datetime.now(UTC)

    @property
    def is_lockout_expired(self) -> bool:
        """Check if lockout period has expired - SOLID Single Responsibility."""
        if not self.is_locked or not self.locked_until:
            return False
        return datetime.now(UTC) >= self.locked_until

    @property
    def lockout_remaining_minutes(self) -> int | None:
        """Get remaining lockout time in minutes - SOLID Single Responsibility."""
        if not self.is_locked or not self.locked_until:
            return None

        remaining = self.locked_until - datetime.now(UTC)
        if remaining.total_seconds() <= 0:
            return 0

        return int(remaining.total_seconds() / 60)


class RevokedToken(Base):
    """Model for tracking revoked JWT tokens - SOLID Single Responsibility Principle.

    This table provides a secure token revocation mechanism by maintaining a blacklist
    of revoked tokens. Follows security best practices for JWT invalidation.
    """

    __tablename__ = "revoked_tokens"

    # Primary key - using token JTI (JWT ID) for unique identification
    jti: Mapped[str] = mapped_column(
        String(100), primary_key=True, comment="JWT ID claim - unique identifier for each token"
    )

    # Token metadata for security and auditing
    user_id: Mapped[str | None] = mapped_column(
        String(50), index=True, comment="User who owned the token (for bulk revocation)"
    )

    token_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="access",
        comment="Token type: access, refresh, or reset",
    )

    # Security timestamps - DRY principle with consistent datetime handling
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="When token was originally issued"
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,  # Indexed for cleanup operations
        comment="When token naturally expires",
    )

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="When token was revoked",
    )

    # Revocation context for security auditing
    revocation_reason: Mapped[str | None] = mapped_column(
        String(100), comment="Reason for revocation: logout, password_change, admin_action, etc."
    )

    revoked_by: Mapped[str | None] = mapped_column(
        String(50), comment="Who/what revoked the token (user_id, admin_id, or system)"
    )

    # Additional context for security analysis
    client_ip: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        comment="IP address when token was revoked",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500), comment="User agent when token was revoked"
    )

    def __repr__(self) -> str:
        """String representation following DRY patterns from other models."""
        return (
            f"<RevokedToken(jti='{self.jti}', user_id='{self.user_id}', "
            f"type='{self.token_type}', revoked_at='{self.revoked_at}')>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if revoked token has naturally expired - DRY property pattern."""
        return datetime.now(UTC) > self.expires_at

    @classmethod
    def create_revocation_record(
        cls,
        jti: str,
        user_id: str | None,
        token_type: str,
        issued_at: datetime,
        expires_at: datetime,
        reason: str | None = None,
        revoked_by: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> "RevokedToken":
        """Factory method for creating revocation records - SOLID Factory Pattern.

        Args:
            jti: JWT ID claim
            user_id: Token owner user ID
            token_type: access, refresh, or reset
            issued_at: When token was issued
            expires_at: When token expires
            reason: Reason for revocation
            revoked_by: Who revoked the token
            client_ip: Client IP address
            user_agent: Client user agent

        Returns:
            New RevokedToken instance
        """
        return cls(
            jti=jti,
            user_id=user_id,
            token_type=token_type,
            issued_at=issued_at,
            expires_at=expires_at,
            revocation_reason=reason,
            revoked_by=revoked_by,
            client_ip=client_ip,
            user_agent=user_agent,
        )


# PostgreSQL enum metadata event listener (SQLAlchemy best practice)
@event.listens_for(Base.metadata, "before_create")
def _create_enums_before_tables(target, connection, **kw):  # noqa: ARG001
    """Create PostgreSQL enum types before table creation.

    This event listener follows SQLAlchemy best practices for PostgreSQL enum handling
    by ensuring enum types exist before any table creation attempts.

    Args:
        target: SQLAlchemy metadata object (required by event listener protocol)
        connection: Database connection (used for enum creation)
        **kw: Additional SQLAlchemy event arguments (required by protocol)
    """
    # Lazy import to avoid circular dependencies
    from .utils import create_postgresql_enums, get_standard_enum_definitions

    create_postgresql_enums(connection, get_standard_enum_definitions())


# Database configuration and utilities
def create_database_engine(echo: bool = False):
    """Create SQLAlchemy engine optimized for PostgreSQL 17.6.

    Args:
        echo: Whether to echo SQL statements (for debugging)

    Returns:
        SQLAlchemy Engine instance configured for PostgreSQL 17.6+
    """
    from sqlalchemy import event

    from .utils import get_database_url

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
            # Use cursor for SQL commands - psycopg connection doesn't have execute method
            with dbapi_connection.cursor() as cursor:
                cursor.execute("CLOSE ALL")  # Close cursors
                cursor.execute("RESET ALL")  # Reset session variables
                cursor.execute("DISCARD TEMP")  # Clean up temp tables
        dbapi_connection.rollback()  # Ensure clean transaction state

    return engine
