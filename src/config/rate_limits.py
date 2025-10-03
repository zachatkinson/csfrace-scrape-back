"""Rate limiting configuration following DRY principles.

Centralizes all rate limit definitions to eliminate magic strings
scattered across the codebase and provide single source of truth.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimits:  # pylint: disable=too-many-instance-attributes,invalid-name  # Intentional: centralizes all rate limits to eliminate magic strings
    """Centralized rate limiting configuration."""

    # Authentication endpoints
    AUTH_LOGIN: str = "5/minute"  # Login attempts
    AUTH_REGISTER: str = "3/minute"  # User registration
    AUTH_PASSWORD_RESET: str = "2/minute"  # Password reset requests
    AUTH_OAUTH: str = "10/minute"  # OAuth operations
    AUTH_PASSKEY: str = "10/minute"  # WebAuthn/Passkey operations
    AUTH_SENSITIVE_OPERATION: str = "3/minute"  # Sensitive operations like token revocation

    # API endpoints
    JOB_CREATION: str = "20/hour"  # Job creation
    BATCH_CREATION: str = "10/hour"  # Batch creation (more restrictive)

    # Admin endpoints (more permissive)
    ADMIN_OPERATIONS: str = "100/hour"

    # Development/Testing (more permissive)
    DEVELOPMENT: str = "1000/hour"


def get_rate_limits() -> RateLimits:
    """Get rate limits based on environment.

    Returns test-friendly rate limits in test environment,
    development-friendly rate limits in development environment,
    production rate limits otherwise.
    """
    # Check for testing environment first
    if os.getenv("TESTING") == "true":
        # Test-friendly rate limits - much higher to avoid interference
        return RateLimits(
            AUTH_LOGIN="1000/minute",
            AUTH_REGISTER="1000/minute",
            AUTH_PASSWORD_RESET="1000/minute",
            AUTH_OAUTH="1000/minute",
            AUTH_PASSKEY="1000/minute",
            AUTH_SENSITIVE_OPERATION="1000/minute",
            JOB_CREATION="1000/hour",
            BATCH_CREATION="1000/hour",  # High enough for test suites
            ADMIN_OPERATIONS="1000/hour",
            DEVELOPMENT="1000/hour",
        )

    # Check for development environment
    if os.getenv("ENVIRONMENT") == "development":
        # Development-friendly rate limits - realistic but not overbearing
        return RateLimits(
            AUTH_LOGIN="30/minute",  # 5 → 30 (realistic for login testing)
            AUTH_REGISTER="15/minute",  # 3 → 15 (enough for registration testing)
            AUTH_PASSWORD_RESET="10/minute",  # 2 → 10 (reasonable for password reset testing)
            AUTH_OAUTH="50/minute",  # 10 → 50 (sufficient for OAuth flow testing)
            AUTH_PASSKEY="50/minute",  # 10 → 50 (good for passkey testing)
            AUTH_SENSITIVE_OPERATION="20/minute",  # 3 → 20 (safe but not restrictive)
            JOB_CREATION="100/hour",  # 20 → 100 (allows good job testing without abuse)
            BATCH_CREATION="50/hour",  # 10 → 50 (reasonable batch testing)
            ADMIN_OPERATIONS="200/hour",  # 100 → 200 (admin operations need more headroom)
            DEVELOPMENT="500/hour",  # 1000 → 500 (general development usage)
        )

    # Production rate limits
    return RateLimits()


# Global instance - will be initialized when first accessed
_rate_limits_instance = None  # pylint: disable=invalid-name


def get_rate_limits_instance() -> RateLimits:
    """Get the global rate limits instance, creating if needed."""
    global _rate_limits_instance  # pylint: disable=global-statement
    if _rate_limits_instance is None:
        _rate_limits_instance = get_rate_limits()
    return _rate_limits_instance


# Global rate limits instance
rate_limits = get_rate_limits_instance()
