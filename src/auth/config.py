"""Authentication configuration following security best practices.

This module has been refactored to use the unified configuration system.
Import the unified configuration from the config package for backward compatibility.
"""

from datetime import timedelta

# Import from unified config system
from ..config import AuthConfig as NewAuthConfig, get_settings


class AuthConfig:
    """Authentication configuration with environment variable support.

    Maintains backward compatibility while delegating to the new unified system.
    """

    def __init__(self):
        """Initialize auth configuration."""
        try:
            # Use the new unified configuration system
            settings = get_settings()
            self._config = settings.auth
        except Exception:
            # Fallback to creating a new instance if unified system fails
            self._config = NewAuthConfig()

    # JWT Configuration properties
    @property
    def SECRET_KEY(self) -> str:
        """JWT secret key."""
        return self._config.SECRET_KEY

    @property
    def ALGORITHM(self) -> str:
        """JWT algorithm."""
        return self._config.ALGORITHM

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        """Access token expiration in minutes."""
        return self._config.ACCESS_TOKEN_EXPIRE_MINUTES

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        """Refresh token expiration in days."""
        return self._config.REFRESH_TOKEN_EXPIRE_DAYS

    # Password Configuration properties
    @property
    def PWD_CONTEXT_SCHEMES(self) -> list[str]:
        """Password hashing schemes."""
        return self._config.PWD_CONTEXT_SCHEMES

    @property
    def PWD_CONTEXT_DEPRECATED(self) -> str:
        """Deprecated password schemes."""
        return self._config.PWD_CONTEXT_DEPRECATED

    # Rate Limiting properties
    @property
    def AUTH_RATE_LIMIT(self) -> str:
        """Login attempts rate limit."""
        return self._config.AUTH_RATE_LIMIT

    @property
    def REGISTER_RATE_LIMIT(self) -> str:
        """Registration attempts rate limit."""
        return self._config.REGISTER_RATE_LIMIT

    @property
    def PASSWORD_RESET_RATE_LIMIT(self) -> str:
        """Password reset attempts rate limit."""
        return self._config.PASSWORD_RESET_RATE_LIMIT

    # Security Headers properties
    @property
    def SECURE_COOKIES(self) -> bool:
        """Use secure cookies."""
        return self._config.SECURE_COOKIES

    @property
    def SAME_SITE_COOKIES(self) -> str:
        """SameSite cookie policy."""
        return self._config.SAME_SITE_COOKIES

    # OAuth2 Configuration properties
    @property
    def GOOGLE_CLIENT_ID(self) -> str | None:
        """Google OAuth client ID."""
        return self._config.GOOGLE_CLIENT_ID

    @property
    def GOOGLE_CLIENT_SECRET(self) -> str | None:
        """Google OAuth client secret."""
        return self._config.GOOGLE_CLIENT_SECRET

    @property
    def GITHUB_CLIENT_ID(self) -> str | None:
        """GitHub OAuth client ID."""
        return self._config.GITHUB_CLIENT_ID

    @property
    def GITHUB_CLIENT_SECRET(self) -> str | None:
        """GitHub OAuth client secret."""
        return self._config.GITHUB_CLIENT_SECRET

    @property
    def MICROSOFT_CLIENT_ID(self) -> str | None:
        """Microsoft OAuth client ID."""
        return self._config.MICROSOFT_CLIENT_ID

    @property
    def MICROSOFT_CLIENT_SECRET(self) -> str | None:
        """Microsoft OAuth client secret."""
        return self._config.MICROSOFT_CLIENT_SECRET

    # WebAuthn Configuration properties
    @property
    def WEBAUTHN_RP_ID(self) -> str | None:
        """WebAuthn Relying Party ID."""
        return self._config.WEBAUTHN_RP_ID

    @property
    def WEBAUTHN_RP_NAME(self) -> str:
        """WebAuthn Relying Party name."""
        return self._config.WEBAUTHN_RP_NAME

    @property
    def WEBAUTHN_ORIGIN(self) -> str | None:
        """WebAuthn origin URL."""
        return self._config.WEBAUTHN_ORIGIN

    # Account Security properties
    @property
    def MAX_LOGIN_ATTEMPTS(self) -> int:
        """Max failed login attempts."""
        return getattr(self._config, "MAX_LOGIN_ATTEMPTS", 5)

    @property
    def LOCKOUT_DURATION_MINUTES(self) -> int:
        """Account lockout duration in minutes."""
        return getattr(self._config, "LOCKOUT_DURATION_MINUTES", 15)

    # Computed properties
    @property
    def access_token_expire_delta(self) -> timedelta:
        """Get access token expiration timedelta."""
        return self._config.access_token_expire_delta

    @property
    def refresh_token_expire_delta(self) -> timedelta:
        """Get refresh token expiration timedelta."""
        return self._config.refresh_token_expire_delta

    @property
    def lockout_duration_delta(self) -> timedelta:
        """Get lockout duration timedelta."""
        return getattr(self._config, "lockout_duration_delta", timedelta(minutes=15))

    # Methods
    def has_oauth_provider(self, provider: str) -> bool:
        """Check if OAuth provider is configured."""
        return self._config.has_oauth_provider(provider)

    def get_enabled_oauth_providers(self) -> list[str]:
        """Get list of enabled OAuth providers."""
        return self._config.get_enabled_oauth_providers()


# Global auth config instance - uses unified system
try:
    auth_config = AuthConfig()  # type: ignore
except Exception:
    # Fallback if unified system is not available
    auth_config = None  # type: ignore
