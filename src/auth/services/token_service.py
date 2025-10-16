"""JWT token creation and management service following SOLID principles."""

from datetime import timedelta
from typing import TYPE_CHECKING

from src.config.settings import ConfigManager
from src.core.logging_hierarchy import get_auth_logger

from ...constants import BEARER_TOKEN_TYPE
from ..models import Token, User
from ..security import security_manager

if TYPE_CHECKING:
    from src.config.auth import AuthConfig


def _get_auth_config() -> "AuthConfig":
    """Get authentication configuration from settings."""
    try:
        settings = ConfigManager.get_config()
        return settings.auth
    except RuntimeError:
        # Fallback for testing or early initialization
        from src.config.auth import AuthConfig

        return AuthConfig()


auth_config = _get_auth_config()

logger = get_auth_logger()


class TokenService:
    """Service for JWT token creation and management - SOLID Single Responsibility."""

    @staticmethod
    def create_tokens_for_user(
        user: User, is_new_user: bool = False, scopes: list[str] | None = None
    ) -> Token:
        """Create JWT access and refresh tokens for authenticated user.

        Args:
            user: Authenticated user
            is_new_user: Whether this is a newly created user
            scopes: Token scopes (defaults to empty list)

        Returns:
            Token object with access and refresh tokens
        """
        scopes = scopes or []

        # Create access token with JTI for revocation tracking
        access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token, access_jti = security_manager.create_access_token(
            data={"sub": user.username, "user_id": user.id, "scopes": scopes},
            expires_delta=access_token_expires,
        )

        # Create refresh token with JTI for revocation tracking
        refresh_token, refresh_jti = security_manager.create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )

        return Token(
            access_token=access_token,
            token_type=BEARER_TOKEN_TYPE,
            expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            refresh_token=refresh_token,
            is_new_user=is_new_user,
        )

    @staticmethod
    def create_access_token_only(user: User) -> Token:
        """Create only access token (for refresh operations).

        Args:
            user: Authenticated user

        Returns:
            Token object with only access token
        """
        access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token, access_jti = security_manager.create_access_token(
            data={"sub": user.username, "user_id": user.id}, expires_delta=access_token_expires
        )

        return Token(
            access_token=access_token,
            token_type=BEARER_TOKEN_TYPE,
            expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            is_new_user=False,  # Refresh tokens are for existing sessions
        )
