"""Rate limiting configuration following DRY principles.

Centralizes all rate limit definitions to eliminate magic strings
scattered across the codebase and provide single source of truth.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimits:
    """Centralized rate limiting configuration."""
    
    # Authentication endpoints
    AUTH_LOGIN: str = "5/minute"  # Login attempts
    AUTH_REGISTER: str = "3/minute"  # User registration  
    AUTH_PASSWORD_RESET: str = "2/minute"  # Password reset requests
    AUTH_OAUTH: str = "10/minute"  # OAuth operations
    AUTH_PASSKEY: str = "10/minute"  # WebAuthn/Passkey operations
    
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
    production rate limits otherwise.
    """
    if os.getenv("TESTING") == "true":
        # Test-friendly rate limits - much higher to avoid interference
        return RateLimits(
            AUTH_LOGIN="1000/minute",
            AUTH_REGISTER="1000/minute", 
            AUTH_PASSWORD_RESET="1000/minute",
            AUTH_OAUTH="1000/minute",
            AUTH_PASSKEY="1000/minute",
            JOB_CREATION="1000/hour",
            BATCH_CREATION="1000/hour",  # High enough for test suites
            ADMIN_OPERATIONS="1000/hour",
            DEVELOPMENT="1000/hour"
        )
    else:
        # Production rate limits
        return RateLimits()


# Global instance - will be initialized when first accessed
_rate_limits_instance = None

def get_rate_limits_instance() -> RateLimits:
    """Get the global rate limits instance, creating if needed."""
    global _rate_limits_instance
    if _rate_limits_instance is None:
        _rate_limits_instance = get_rate_limits()
    return _rate_limits_instance

# For backward compatibility
rate_limits = get_rate_limits_instance()