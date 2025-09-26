"""Service registration for dependency injection container.

This module configures all application services with proper lifetimes
and dependencies for the DI container.
"""

from __future__ import annotations

from src.utils.logging import get_logger

from ..auth.oauth_service import OAuthService
from ..auth.service import AuthService
from ..auth.webauthn_service import PasskeyManager, WebAuthnService
from ..caching.manager import CacheManager
from ..database.service import DatabaseService
from ..database.services.cleanup_service import CleanupService
from ..database.services.content_service import ContentService
from ..database.services.job_service import JobService
from ..database.services.logging_service import LoggingService
from ..database.services.statistics_service import StatisticsService
from .container import container

logger = get_logger(__name__)


def configure_services() -> None:
    """Configure all application services in the DI container."""

    logger.info("Configuring dependency injection services")

    # Database services
    from ..database.service import DatabaseService
    from ..database.services.cleanup_service import CleanupService
    from ..database.services.content_service import ContentService
    from ..database.services.job_service import JobService
    from ..database.services.logging_service import LoggingService
    from ..database.services.statistics_service import StatisticsService

    container.register_singleton(DatabaseService)
    container.register_transient(JobService)
    container.register_transient(ContentService)
    container.register_transient(LoggingService)
    container.register_transient(StatisticsService)
    container.register_transient(CleanupService)

    # Auth services
    from ..auth.oauth_service import OAuthService
    from ..auth.service import AuthService
    from ..auth.webauthn_service import PasskeyManager, WebAuthnService

    container.register_transient(AuthService)
    container.register_transient(OAuthService)
    container.register_transient(WebAuthnService)
    container.register_transient(PasskeyManager)

    # Caching services
    from ..caching.manager import CacheManager

    container.register_singleton(CacheManager)

    # Register cleanup handlers
    # TODO: DatabaseService doesn't have close_all_sessions method
    # container.register_cleanup(DatabaseService, lambda db: db.close_all_sessions())
    container.register_cleanup(DatabaseService, lambda db: None)  # Placeholder  # noqa: ARG005
    container.register_cleanup(
        CacheManager,
        lambda cache: None,  # noqa: ARG005
    )  # CacheManager has its own cleanup

    logger.info("Dependency injection services configured")


def get_database_service() -> DatabaseService:
    """Get database service from container."""
    return container.resolve(DatabaseService)


def get_job_service() -> JobService:
    """Get job service from container."""
    return container.resolve(JobService)


def get_content_service() -> ContentService:
    """Get content service from container."""
    return container.resolve(ContentService)


def get_logging_service() -> LoggingService:
    """Get logging service from container."""
    return container.resolve(LoggingService)


def get_statistics_service() -> StatisticsService:
    """Get statistics service from container."""
    return container.resolve(StatisticsService)


def get_cleanup_service() -> CleanupService:
    """Get cleanup service from container."""
    return container.resolve(CleanupService)


def get_auth_service() -> AuthService:
    """Get auth service from container."""
    return container.resolve(AuthService)


def get_oauth_service() -> OAuthService:
    """Get OAuth service from container."""
    return container.resolve(OAuthService)


def get_webauthn_service() -> WebAuthnService:
    """Get WebAuthn service from container."""
    return container.resolve(WebAuthnService)


def get_passkey_manager() -> PasskeyManager:
    """Get passkey manager from container."""
    return container.resolve(PasskeyManager)


def get_cache_manager() -> CacheManager:
    """Get cache manager from container."""
    return container.resolve(CacheManager)
