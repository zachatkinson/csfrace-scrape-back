"""Authentication configuration following security best practices."""

from datetime import timedelta
from typing import Literal

from pydantic import Field, field_validator

from src.core.logging_hierarchy import get_core_logger

from ..constants import PASSWORD_CONTEXT_DEPRECATED
from .base import BaseConfig, SecurityMixin

logger = get_core_logger()


class AuthConfig(BaseConfig, SecurityMixin):
    """Authentication configuration with environment variable support."""

    # JWT Configuration - SECURE, no insecure defaults
    SECRET_KEY: str = Field(..., description="Application secret key for JWT signing")
    ALGORITHM: str = Field("HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        720, ge=1, le=1440, description="Access token expiration in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        7, ge=1, le=365, description="Refresh token expiration in days"
    )

    # Password Configuration
    PWD_CONTEXT_SCHEMES: list[str] = Field(["bcrypt"], description="Password hashing schemes")
    PWD_CONTEXT_DEPRECATED: str = Field(
        PASSWORD_CONTEXT_DEPRECATED, description="Deprecated password schemes"
    )

    # Rate Limiting - configurable for different environments
    AUTH_RATE_LIMIT: str = Field("5/minute", description="Login attempts rate limit")
    REGISTER_RATE_LIMIT: str = Field("3/hour", description="Registration attempts rate limit")
    PASSWORD_RESET_RATE_LIMIT: str = Field(
        "3/hour", description="Password reset attempts rate limit"
    )

    # Security Headers - configurable for different environments
    SECURE_COOKIES: bool = Field(True, description="Use secure cookies in production")
    SAME_SITE_COOKIES: Literal["strict", "lax", "none"] = Field(
        "strict", description="SameSite cookie policy"
    )

    # OAuth2 Configuration (optional)
    GOOGLE_CLIENT_ID: str | None = Field(None, description="Google OAuth client ID")
    GOOGLE_CLIENT_SECRET: str | None = Field(None, description="Google OAuth client secret")
    GITHUB_CLIENT_ID: str | None = Field(None, description="GitHub OAuth client ID")
    GITHUB_CLIENT_SECRET: str | None = Field(None, description="GitHub OAuth client secret")
    MICROSOFT_CLIENT_ID: str | None = Field(None, description="Microsoft OAuth client ID")
    MICROSOFT_CLIENT_SECRET: str | None = Field(None, description="Microsoft OAuth client secret")

    # WebAuthn Configuration
    WEBAUTHN_RP_ID: str | None = Field(None, description="WebAuthn Relying Party ID (domain)")
    WEBAUTHN_RP_NAME: str = Field("CSFrace Scraper", description="WebAuthn Relying Party name")
    WEBAUTHN_ORIGIN: str | None = Field(None, description="WebAuthn origin URL")

    # Account Security
    MAX_LOGIN_ATTEMPTS: int = Field(5, ge=1, le=20, description="Max failed login attempts")
    LOCKOUT_DURATION_MINUTES: int = Field(15, ge=1, le=1440, description="Account lockout duration")

    @field_validator("SAME_SITE_COOKIES", mode="before")
    @classmethod
    def validate_same_site(cls, v: str) -> str:
        """Validate SameSite cookie policy."""
        if v.lower() not in ("strict", "lax", "none"):
            raise ValueError("SAME_SITE_COOKIES must be 'strict', 'lax', or 'none'")
        return v.lower()

    @property
    def access_token_expire_delta(self) -> timedelta:
        """Get access token expiration timedelta."""
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

    @property
    def refresh_token_expire_delta(self) -> timedelta:
        """Get refresh token expiration timedelta."""
        return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)

    @property
    def lockout_duration_delta(self) -> timedelta:
        """Get lockout duration timedelta."""
        return timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)

    def has_oauth_provider(self, provider: str) -> bool:
        """Check if OAuth provider is configured."""
        provider_configs = {
            "google": (self.GOOGLE_CLIENT_ID, self.GOOGLE_CLIENT_SECRET),
            "github": (self.GITHUB_CLIENT_ID, self.GITHUB_CLIENT_SECRET),
            "microsoft": (self.MICROSOFT_CLIENT_ID, self.MICROSOFT_CLIENT_SECRET),
        }

        if provider not in provider_configs:
            return False

        client_id, client_secret = provider_configs[provider]
        return bool(client_id and client_secret)

    def get_enabled_oauth_providers(self) -> list[str]:
        """Get list of enabled OAuth providers."""
        providers = []
        for provider in ["google", "github", "microsoft"]:
            if self.has_oauth_provider(provider):
                providers.append(provider)
        return providers
