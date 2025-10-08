"""OAuth authentication Pydantic models following SOLID principles."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class OAuthProvider(str, Enum):
    """OAuth2 provider enumeration - DRY principle for provider constants."""

    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    FACEBOOK = "facebook"
    APPLE = "apple"

    def __str__(self) -> str:
        """Return the provider value for string conversion."""
        return self.value


class OAuthUserInfo(BaseModel):
    """OAuth2 user information model - Single Responsibility for OAuth data."""

    # Note: Removed use_enum_values=True to preserve enum types internally
    # This prevents the "'str' object has no attribute 'value'" error
    model_config = ConfigDict()

    provider: OAuthProvider
    provider_id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None
    access_token: str | None = None  # OAuth access token for storage and revocation


class OAuthCallback(BaseModel):
    """OAuth2 callback model for authorization code flow - Interface Segregation."""

    code: str
    state: str
    provider: OAuthProvider
    error: str | None = None
    error_description: str | None = None


class SSOLoginRequest(BaseModel):
    """SSO login initiation request with DRY validation."""

    # Note: Removed use_enum_values=True to preserve enum types internally
    # This prevents the "'str' object has no attribute 'value'" error
    model_config = ConfigDict()

    provider: OAuthProvider
    redirect_uri: str | None = None

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, v: str | None) -> str | None:
        """DRY: Centralized URI validation."""
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError("Redirect URI must be HTTP or HTTPS")
        return v


class SSOLoginResponse(BaseModel):
    """SSO login response model - Consistent interface."""

    model_config = ConfigDict(use_enum_values=True)

    authorization_url: str
    state: str
    provider: OAuthProvider


class LinkedAccount(BaseModel):
    """Linked OAuth account model for users with multiple providers."""

    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    provider: OAuthProvider
    provider_id: str
    provider_email: EmailStr
    linked_at: datetime
    is_primary: bool = False


class OAuthConnectionResponse(BaseModel):
    """OAuth connection response model for API responses - Single Responsibility."""

    model_config = ConfigDict(use_enum_values=True)

    provider: OAuthProvider
    connected: bool
    email: EmailStr | None = None
    name: str | None = None
    linked_at: datetime | None = None
    is_primary: bool = False
