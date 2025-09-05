"""Rate limiting configuration following DRY principles.

Centralizes all rate limit definitions to eliminate magic strings
scattered across the codebase and provide single source of truth.
"""

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


# Global instance
rate_limits = RateLimits()