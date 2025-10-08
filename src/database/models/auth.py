"""Authentication and user management database models.

This module contains all models related to user authentication, authorization,
and account management. Follows Single Responsibility Principle by focusing
only on auth domain.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from .jobs import ScrapingJob

# Note: ScrapingJob relationship uses string-based forward reference
# No import needed due to SQLAlchemy's lazy evaluation
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.logging_hierarchy import get_database_logger

from .base import Base

logger = get_database_logger()


class User(Base):
    """User model for authentication and authorization.

    Follows best practices for user management with support for:
    - OAuth SSO providers (Google, GitHub, Microsoft, Facebook, Apple)
    - Traditional username/password authentication
    - WebAuthn/passkeys for passwordless auth
    - Account status tracking and security features
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # User credentials
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Nullable for OAuth users

    # Profile information
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Security tracking
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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
    linked_accounts: Mapped[list["LinkedAccount"]] = relationship(
        "LinkedAccount", back_populates="user", cascade="all, delete-orphan"
    )
    webauthn_credentials: Mapped[list["WebAuthnCredential"]] = relationship(
        "WebAuthnCredential", back_populates="user", cascade="all, delete-orphan"
    )
    scraping_jobs: Mapped[list["ScrapingJob"]] = relationship(
        "ScrapingJob", back_populates="user"
    )  # No cascade delete - preserve jobs when user is deleted
    user_settings: Mapped["UserSettings | None"] = relationship(
        "UserSettings", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of user."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserSettings(Base):
    """User-specific application settings.

    Stores personalized configuration for each user including:
    - Job execution defaults (priority, timeout, retries)
    - Display preferences (UI settings, pagination)
    - API configuration (endpoints, timeouts)
    - Notification preferences
    """

    __tablename__ = "user_settings"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Foreign key to user (one-to-one relationship)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    # Job Defaults
    default_priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    job_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # seconds

    # API Configuration
    api_url: Mapped[str] = mapped_column(
        String(255), default="http://localhost:8000", nullable=False
    )
    api_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # seconds
    refresh_interval: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # seconds
    retry_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    enable_caching: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Display Options
    dark_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_job_ids: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    compact_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    jobs_per_page: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="auto", nullable=False)

    # Notification Settings
    completion_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    browser_notifications: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Additional settings stored as JSON for flexibility
    custom_settings: Mapped[dict[str, Any] | None] = mapped_column(JSON, server_default="{}")

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
    user: Mapped["User"] = relationship("User", back_populates="user_settings")

    def __repr__(self) -> str:
        """String representation of user settings."""
        return f"<UserSettings(id={self.id}, user_id='{self.user_id}')>"


class LinkedAccount(Base):
    """OAuth linked account model for SSO providers.

    Tracks OAuth accounts linked to users for multiple provider support.
    Allows users to sign in with multiple OAuth providers.

    OAuth Token Storage:
    - access_token: Encrypted OAuth access token (nullable for providers without tokens)
    - refresh_token: Encrypted OAuth refresh token (nullable if not provided)
    - token_expires_at: Token expiration timestamp for refresh logic
    - token_scopes: Comma-separated OAuth scopes granted by user (for revocation tracking)

    Security Note:
    All tokens (access_token, refresh_token) should be encrypted using
    TokenEncryptionService before storage to comply with security best practices.
    """

    __tablename__ = "linked_accounts"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )

    # OAuth provider information
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # google, github, microsoft, etc.
    provider_account_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Provider's user ID

    # OAuth tokens (encrypted in production using TokenEncryptionService)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    token_scopes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Comma-separated OAuth scopes for revocation tracking"
    )

    # Provider data
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # Unique constraint: One provider account per user
    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider", "provider_account_id", name="uq_user_provider_account"
        ),
    )

    # Relationship back to user
    user: Mapped["User"] = relationship("User", back_populates="linked_accounts")

    def __repr__(self) -> str:
        """String representation of linked account."""
        return (
            f"<LinkedAccount(id={self.id}, provider='{self.provider}', user_id='{self.user_id}')>"
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
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )  # Foreign key to users table

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

    # Relationship back to user
    user: Mapped["User"] = relationship("User", back_populates="webauthn_credentials")

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
    """Model for tracking account lockouts and failed login attempts.

    Follows Single Responsibility Principle for account security management.
    """

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
        """Factory method for creating lockout records.

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
        """Factory method for creating failed attempt tracking records.

        Args:
            user_id: User identifier
            username: Username for audit trail
            client_ip: IP address of failed attempt
            user_agent: User agent of failed attempt

        Returns:
            AccountLockout instance for tracking failed attempts (starts at 0, will be incremented)
        """
        now = datetime.now(UTC)

        return cls(
            user_id=user_id,
            username=username,
            failed_attempts=0,  # Start at 0, will be incremented by calling code
            is_locked=False,
            lockout_reason=None,
            first_failed_attempt_at=now,
            last_failed_attempt_at=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    def unlock_account(self, unlocked_by: str | None = None) -> None:
        """Unlock the account.

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
        """Increment failed attempt counter.

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
        """Reset failed attempt counter after successful login."""
        self.failed_attempts = 0
        self.first_failed_attempt_at = None
        self.last_failed_attempt_at = None
        self.updated_at = datetime.now(UTC)

    @property
    def is_lockout_expired(self) -> bool:
        """Check if lockout period has expired."""
        if not self.is_locked or not self.locked_until:
            return False
        return datetime.now(UTC) >= self.locked_until

    @property
    def lockout_remaining_minutes(self) -> int | None:
        """Get remaining lockout time in minutes."""
        if not self.is_locked or not self.locked_until:
            return None

        remaining = self.locked_until - datetime.now(UTC)
        if remaining.total_seconds() <= 0:
            return 0

        return int(remaining.total_seconds() / 60)


class RevokedToken(Base):
    """Model for tracking revoked JWT tokens.

    Provides a secure token revocation mechanism by maintaining a blacklist
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

    # Security timestamps
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
        """Check if revoked token has naturally expired."""
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
        """Factory method for creating revocation records.

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
