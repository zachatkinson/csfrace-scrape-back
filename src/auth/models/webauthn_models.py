"""WebAuthn and Passkey authentication Pydantic models following SOLID principles."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from .validation_mixins import PasswordValidatorMixin


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

    public_key: dict[str, Any]
    challenge_key: str
    device_name: str


class PasskeyAuthenticationRequest(BaseModel):
    """Passkey authentication request - Single Responsibility."""

    username: str | None = None  # Optional for usernameless/discoverable auth


class PasskeyAuthenticationResponse(BaseModel):
    """Passkey authentication response - Consistent interface."""

    public_key: dict[str, Any]
    challenge_key: str


class PasskeyCredentialRequest(BaseModel):
    """Passkey credential operation request - DRY validation."""

    challenge_key: str
    credential_response: dict[str, Any]
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
    def validate_credential_response(cls, v: dict[str, Any]) -> dict[str, Any]:
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
    devices: list[dict[str, Any]]


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
    credential: dict[str, Any]
    deviceName: str | None = Field(default="Default Device", max_length=255)


class WebAuthnAuthenticationStart(BaseModel):
    """WebAuthn authentication start request model - Single Responsibility."""

    username: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        """DRY: Validate and sanitize username."""
        if v is None:
            return None
        return PasswordValidatorMixin.validate_username(v)


class WebAuthnAuthenticationComplete(BaseModel):
    """WebAuthn authentication completion request model - Interface Segregation."""

    challengeKey: str = Field(min_length=1, max_length=200)
    credential: dict[str, Any]


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


# Type Aliases for Path Parameters - FastAPI Best Practices
CredentialIdPath = Annotated[
    str, Field(min_length=1, max_length=100, description="WebAuthn Credential ID")
]
