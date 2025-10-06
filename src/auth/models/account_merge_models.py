"""Account merge models following SOLID principles - Single Responsibility.

Models for handling account merging when a user attempts to link an OAuth provider
that's already associated with a different account.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .oauth_models import OAuthProvider


class DuplicateAccountInfo(BaseModel):
    """Information about the duplicate account that would be merged - Read-only model."""

    user_id: str = Field(..., description="ID of the duplicate user account")
    username: str = Field(..., description="Username of the duplicate account")
    email: str = Field(..., description="Email of the duplicate account")
    created_at: datetime = Field(..., description="When the duplicate account was created")
    linked_providers: list[OAuthProvider] = Field(
        default_factory=list, description="OAuth providers linked to duplicate account"
    )


class AccountMergeDetection(BaseModel):
    """Response when account merge is detected - Single Responsibility for detection info."""

    merge_required: bool = Field(
        True, description="Indicates that account merge is required to proceed"
    )
    message: str = Field(..., description="Human-readable message explaining the merge requirement")
    current_account: DuplicateAccountInfo = Field(
        ..., description="Information about the current logged-in account"
    )
    duplicate_account: DuplicateAccountInfo = Field(
        ..., description="Information about the account that would be merged"
    )
    provider_to_link: OAuthProvider = Field(
        ..., description="The OAuth provider that triggered the merge detection"
    )
    merge_token: str = Field(..., description="Temporary token to authorize the merge operation")


class AccountMergeRequest(BaseModel):
    """Request to merge accounts - Single Responsibility for merge request validation."""

    merge_token: str = Field(..., description="Token from merge detection response")
    confirm_merge: bool = Field(
        ..., description="User confirmation to proceed with merge (must be True)"
    )


class AccountMergeResult(BaseModel):
    """Result of account merge operation - Single Responsibility for merge result info."""

    success: bool = Field(..., description="Whether the merge was successful")
    message: str = Field(..., description="Human-readable result message")
    merged_user_id: str = Field(..., description="ID of the user account that was kept (target)")
    deleted_user_id: str | None = Field(
        None, description="ID of the user account that was deleted (source)"
    )
    transferred_providers: list[OAuthProvider] = Field(
        default_factory=list, description="OAuth providers transferred to the merged account"
    )
    merge_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the merge was completed"
    )


class MergeAuditLog(BaseModel):
    """Audit log entry for account merge - Single Responsibility for audit tracking."""

    target_user_id: str = Field(..., description="User account that was kept")
    source_user_id: str = Field(..., description="User account that was merged/deleted")
    initiated_by_user_id: str = Field(..., description="User who initiated the merge")
    trigger_provider: OAuthProvider = Field(
        ..., description="OAuth provider that triggered the merge"
    )
    transferred_providers: list[OAuthProvider] = Field(
        default_factory=list, description="Providers transferred during merge"
    )
    merge_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When merge occurred"
    )
    client_ip: str | None = Field(None, description="IP address of merge request")
    user_agent: str | None = Field(None, description="User agent of merge request")
