"""Authentication configuration following security best practices."""

import os
from datetime import timedelta

from pydantic import field_validator
from pydantic_settings import BaseSettings

from ..constants import AUTH_CONSTANTS


class AuthConfig(BaseSettings):
    """Authentication configuration with environment variable support."""

    # JWT Configuration
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password Configuration
    PWD_CONTEXT_SCHEMES: list[str] = ["bcrypt"]
    PWD_CONTEXT_DEPRECATED: str = AUTH_CONSTANTS.PASSWORD_CONTEXT_DEPRECATED

    # Rate Limiting
    AUTH_RATE_LIMIT: str = "5/minute"  # Login attempts
    REGISTER_RATE_LIMIT: str = "3/hour"  # Registration attempts
    PASSWORD_RESET_RATE_LIMIT: str = "3/hour"  # noqa: S105

    # Security Headers
    SECURE_COOKIES: bool = True
    SAME_SITE_COOKIES: str = "strict"

    # OAuth2 Configuration (will be populated later)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    MICROSOFT_CLIENT_ID: str | None = None
    MICROSOFT_CLIENT_SECRET: str | None = None

    # WebAuthn Configuration
    WEBAUTHN_RP_ID: str | None = None  # Relying Party ID (usually domain)
    WEBAUTHN_RP_NAME: str = "CSFrace Scraper"
    WEBAUTHN_ORIGIN: str | None = None

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v):
        """Ensure SECRET_KEY is properly configured."""
        if not v:
            raise ValueError("SECRET_KEY must be set. Generate one with: openssl rand -hex 32")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @property
    def access_token_expire_delta(self) -> timedelta:
        """Get access token expiration timedelta."""
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

    @property
    def refresh_token_expire_delta(self) -> timedelta:
        """Get refresh token expiration timedelta."""
        return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)

    model_config = {"env_prefix": "AUTH_", "case_sensitive": False}


# Global auth config instance
auth_config = AuthConfig()
