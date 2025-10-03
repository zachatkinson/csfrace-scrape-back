"""Security-related Pydantic models for lockouts and security operations."""

from datetime import datetime

from pydantic import BaseModel, Field


class AccountLockoutStatusResponse(BaseModel):
    """Response model for account lockout status checks - Single Responsibility."""

    is_locked: bool
    remaining_minutes: int | None = None
    failed_attempts: int = 0
    lockout_reason: str | None = None
    locked_since: datetime | None = None


class UnlockAccountRequest(BaseModel):
    """Request model for administrative account unlock - Security Operations."""

    user_id: str = Field(..., min_length=1, max_length=50, description="User ID to unlock")
    reason: str = Field(..., max_length=200, description="Reason for unlock")


class LockoutStatsResponse(BaseModel):
    """Response model for lockout statistics - Monitoring."""

    total_lockout_records: int
    currently_locked_accounts: int
    lockouts_by_reason: dict[str, int]
    recent_lockouts_24h: int
    recent_lockouts_7d: int
    average_failed_attempts: float
    user_id: str | None = None
    current_failed_attempts: int | None = None
    is_currently_locked: bool | None = None
