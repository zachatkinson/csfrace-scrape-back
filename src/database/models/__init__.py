"""Database models package.

This package contains domain-focused database models following Single Responsibility Principle.
Models are organized by domain for better maintainability and testability.

Domains:
- Base: Shared components (Base class, event handlers)
- Jobs: Job-related models (ScrapingJob, ContentResult, JobLog)
- Auth: Authentication models (User, UserSettings, LinkedAccount, WebAuthn*, AccountLockout, RevokedToken)
- Metrics: System monitoring models (SystemMetrics)
- Engine: Database engine configuration utilities
"""

# Import base components
# Import enums from common status module for convenience
from ...common.status import JobPriority, JobStatus

# Import domain models
from .auth import (
    AccountLockout,
    LinkedAccount,
    RevokedToken,
    User,
    UserSettings,
    WebAuthnChallenge,
    WebAuthnCredential,
)
from .base import Base
from .engine import create_database_engine
from .jobs import ContentResult, JobLog, ScrapingJob
from .metrics import SystemMetrics

__all__ = [
    # Base components
    "Base",
    "create_database_engine",
    # Job domain models
    "ScrapingJob",
    "ContentResult",
    "JobLog",
    # Auth domain models
    "User",
    "UserSettings",
    "LinkedAccount",
    "WebAuthnCredential",
    "WebAuthnChallenge",
    "AccountLockout",
    "RevokedToken",
    # Metrics domain models
    "SystemMetrics",
    # Enums
    "JobStatus",
    "JobPriority",
]
