"""Authentication Pydantic models following FastAPI official patterns with DRY and SOLID principles."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..constants import AUTH_CONSTANTS


class PasswordValidatorMixin:
    """DRY principle: Shared password validation logic."""

    @staticmethod
    def validate_password_strength(password: str) -> str:
        """Centralized password validation to eliminate code duplication."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain number")
        return password


class Token(BaseModel):
    """JWT token response model - Single Responsibility Principle."""

    access_token: str
    token_type: str = AUTH_CONSTANTS.BEARER_TOKEN_TYPE
    expires_in: int  # seconds until expiration
    refresh_token: str | None = None


class TokenData(BaseModel):
    """JWT token payload data - Interface Segregation Principle."""

    username: str | None = None
    user_id: str | None = None
    scopes: list[str] = []


class User(BaseModel):
    """User model for authentication - Single Responsibility."""

    id: str
    username: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    last_login: datetime | None = None


class UserInDB(User):
    """User model with hashed password for database storage - Liskov Substitution."""

    hashed_password: str


class UserCreate(BaseModel, PasswordValidatorMixin):
    """User creation request model with DRY validation."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """DRY: Use shared password validation."""
        return cls.validate_password_strength(v)


class UserLogin(BaseModel):
    """User login request model - Single Responsibility."""

    username: str
    password: str


class PasswordReset(BaseModel):
    """Password reset request model - Single Responsibility."""

    email: EmailStr


class PasswordResetConfirm(BaseModel, PasswordValidatorMixin):
    """Password reset confirmation model with DRY validation."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """DRY: Use shared password validation."""
        return cls.validate_password_strength(v)


class UserUpdate(BaseModel):
    """User update request model - Open/Closed Principle."""

    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class PasswordChange(BaseModel, PasswordValidatorMixin):
    """Password change request model with DRY validation."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """DRY: Use shared password validation."""
        return cls.validate_password_strength(v)


class OAuthProvider(str, Enum):
    """OAuth2 provider enumeration - DRY principle for provider constants."""

    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"

    def __str__(self) -> str:
        """Return the provider value for string conversion."""
        return self.value


class OAuthUserInfo(BaseModel):
    """OAuth2 user information model - Single Responsibility for OAuth data."""

    model_config = ConfigDict(use_enum_values=True)

    provider: OAuthProvider
    provider_id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None


class OAuthCallback(BaseModel):
    """OAuth2 callback model for authorization code flow - Interface Segregation."""

    code: str
    state: str
    provider: OAuthProvider
    error: str | None = None
    error_description: str | None = None


class SSOLoginRequest(BaseModel):
    """SSO login initiation request with DRY validation."""

    model_config = ConfigDict(use_enum_values=True)

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


class PasskeyRegistrationRequest(BaseModel):
    """Passkey registration initiation request - Single Responsibility."""

    device_name: str | None = Field(default="Default Device", max_length=100)

    @field_validator("device_name")
    @classmethod
    def validate_device_name(cls, v: str | None) -> str | None:
        """DRY: Validate device name format."""
        if v is None:
            return v
        # Basic sanitization - no special characters that could cause issues
        if any(char in v for char in ["<", ">", '"', "'", "&"]):
            raise ValueError("Device name contains invalid characters")
        return v.strip()


class PasskeyRegistrationResponse(BaseModel):
    """Passkey registration response - Interface Segregation."""

    public_key: dict
    challenge_key: str
    device_name: str


class PasskeyAuthenticationRequest(BaseModel):
    """Passkey authentication request - Single Responsibility."""

    username: str | None = None  # Optional for usernameless/discoverable auth


class PasskeyAuthenticationResponse(BaseModel):
    """Passkey authentication response - Consistent interface."""

    public_key: dict
    challenge_key: str


class PasskeyCredentialRequest(BaseModel):
    """Passkey credential operation request - DRY validation."""

    challenge_key: str
    credential_response: dict
    device_name: str | None = None

    @field_validator("challenge_key")
    @classmethod
    def validate_challenge_key(cls, v: str) -> str:
        """DRY: Validate challenge key format."""
        if len(v) < 10:
            raise ValueError("Challenge key too short")
        return v

    @field_validator("credential_response")
    @classmethod
    def validate_credential_response(cls, v: dict) -> dict:
        """DRY: Validate credential response structure."""
        required_fields = ["id", "type", "response"]
        if not all(field in v for field in required_fields):
            raise ValueError(f"Credential response missing required fields: {required_fields}")
        return v


class PasskeySummary(BaseModel):
    """Passkey summary for user dashboard - Single Responsibility."""

    total_passkeys: int
    active_passkeys: int
    last_used: datetime | None = None
    devices: list[dict]


class PasskeyDevice(BaseModel):
    """Individual passkey device information - Interface Segregation."""

    id: str
    name: str
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool = True


class WebAuthnRegistrationStart(BaseModel):
    """WebAuthn registration start request model - Single Responsibility."""

    device_name: str | None = Field(default="Default Device", max_length=255)

    @field_validator("device_name")
    @classmethod
    def validate_device_name(cls, v: str | None) -> str:
        """DRY: Validate and sanitize device name."""
        if not v or not v.strip():
            return "Default Device"
        return v.strip()


class WebAuthnRegistrationComplete(BaseModel):
    """WebAuthn registration completion request model - Interface Segregation."""

    challengeKey: str = Field(min_length=1, max_length=200)
    credential: dict
    deviceName: str | None = Field(default="Default Device", max_length=255)


class WebAuthnAuthenticationStart(BaseModel):
    """WebAuthn authentication start request model - Single Responsibility."""

    username: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        """DRY: Validate and sanitize username."""
        if not v or not v.strip():
            return None
        return v.strip()


class WebAuthnAuthenticationComplete(BaseModel):
    """WebAuthn authentication completion request model - Interface Segregation."""

    challengeKey: str = Field(min_length=1, max_length=200)
    credential: dict


class WebAuthnCredentialResponse(BaseModel):
    """WebAuthn credential response model for API responses - Single Responsibility."""

    credential_id: str
    user_id: str
    device_name: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool = True
    usage_count: int = Field(ge=0)


class WebAuthnChallenge(BaseModel):
    """WebAuthn challenge model for secure operations - Security focused."""

    challenge: str
    user_id: str | None = None
    challenge_type: str  # 'registration' or 'authentication'
    created_at: datetime
    expires_at: datetime

    @field_validator("challenge_type")
    @classmethod
    def validate_challenge_type(cls, v: str) -> str:
        """DRY: Validate challenge type."""
        valid_types = ["registration", "authentication"]
        if v not in valid_types:
            raise ValueError(f"Challenge type must be one of {valid_types}")
        return v


# FastAPI Response Models - Following Official Best Practices
class MessageResponse(BaseModel):
    """Standard message response model for simple operations."""

    message: str
    status: str = "success"


class StatusResponse(BaseModel):
    """Standard status response model for health checks."""

    status: str


# Type Aliases for Path Parameters - FastAPI Best Practices
UserIdPath = Annotated[str, Field(min_length=1, max_length=50, description="User ID")]
JobIdPath = Annotated[str, Field(min_length=1, max_length=50, description="Job ID")]
BatchIdPath = Annotated[str, Field(min_length=1, max_length=50, description="Batch ID")]
CredentialIdPath = Annotated[
    str, Field(min_length=1, max_length=100, description="WebAuthn Credential ID")
]
