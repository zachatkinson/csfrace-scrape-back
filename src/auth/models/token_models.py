"""Authentication token Pydantic models following SOLID principles."""

from pydantic import BaseModel, Field

from ...constants import BEARER_TOKEN_TYPE


class Token(BaseModel):
    """JWT token response model - Single Responsibility Principle."""

    access_token: str
    token_type: str = BEARER_TOKEN_TYPE
    expires_in: int  # seconds until expiration
    refresh_token: str | None = None
    is_new_user: bool = Field(
        False,
        description="Indicates if this is a newly created user",
        json_schema_extra={"include_in_schema": True},
    )


class TokenData(BaseModel):
    """JWT token payload data - Interface Segregation Principle."""

    username: str | None = None
    user_id: str | None = None
    scopes: list[str] = []
    jti: str | None = None  # JWT ID for revocation tracking
    token_type: str | None = None  # Token type ('access' or 'refresh')


class TokenRevocationRequest(BaseModel):
    """Request model for token revocation - Single Responsibility."""

    token: str = Field(..., min_length=1, max_length=1000, description="JWT token to revoke")
    reason: str | None = Field(None, max_length=100, description="Reason for revocation")


class BulkTokenRevocationRequest(BaseModel):
    """Request model for bulk token revocation - Security Operations."""

    reason: str = Field(..., max_length=100, description="Reason for bulk revocation")
    revoke_all_sessions: bool = Field(True, description="Revoke all user sessions")


class TokenRevocationResponse(BaseModel):
    """Response model for token revocation operations."""

    success: bool
    message: str
    revoked_count: int = Field(default=1, description="Number of tokens revoked")
    jti: str | None = Field(None, description="JWT ID of revoked token")
    clear_local_storage: bool = Field(
        default=False,
        description="Instructs client to clear localStorage/sessionStorage for Safari compatibility",
    )


class RevocationStatsResponse(BaseModel):
    """Response model for revocation statistics - Monitoring."""

    total_revocations: int
    revocations_by_type: dict[str, int]
    revocations_by_reason: dict[str, int]
    recent_revocations_24h: int
    recent_revocations_7d: int
    user_id: str | None = None
