"""SQLAlchemy models for scraping operations data persistence.

This module has been refactored following Single Responsibility Principle.
The original monolithic module has been split into focused domain modules.

Import the unified models from the models package for backward compatibility.
"""

# Import all models from the new package structure for backward compatibility
from .models import (
    AccountLockout,
    Base,
    ContentResult,
    JobLog,
    JobPriority,
    JobStatus,
    LinkedAccount,
    RevokedToken,
    ScrapingJob,
    SystemMetrics,
    User,
    UserSettings,
    WebAuthnChallenge,
    WebAuthnCredential,
    create_database_engine,
)

# Export all models for backward compatibility
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
    "User",
    "UserSettings",
    "LinkedAccount",
    "JobStatus",
    "JobPriority",
    "create_database_engine",
]
