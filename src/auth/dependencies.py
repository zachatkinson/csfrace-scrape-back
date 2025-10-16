"""FastAPI dependencies for authentication following official patterns."""

from collections.abc import Awaitable, Callable, Generator
from typing import TYPE_CHECKING

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

# Import configuration from centralized settings
from src.config.settings import ConfigManager

from ..api.errors import APIErrorFactory
from ..database.service import DatabaseService
from .models import TokenData, User
from .oauth_service import OAuthService
from .security import security_manager
from .service import AuthService
from .webauthn_service import PasskeyManager, WebAuthnService

if TYPE_CHECKING:
    from ..config.auth import AuthConfig


def _get_auth_config() -> "AuthConfig":
    """Get authentication configuration from centralized settings."""
    try:
        settings = ConfigManager.get_config()
        return settings.auth
    except RuntimeError:
        # Fallback for testing or early initialization
        import os

        from src.config.auth import AuthConfig

        return AuthConfig(SECRET_KEY=os.getenv("SECRET_KEY", ""))


auth_config = _get_auth_config()

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/token",
    scopes={"read": "Read access", "write": "Write access", "admin": "Admin access"},
)


def get_database_service() -> DatabaseService:
    """Get database service instance - FastAPI dependency."""
    # Each request gets a fresh database service instance
    # This is better than global state for testing and thread safety
    return DatabaseService()


# Database session dependency for proper lifecycle management
def get_db_session(
    db_service: DatabaseService = Depends(get_database_service),
) -> Generator[Session]:
    """Get database session with proper lifecycle management for FastAPI."""
    with db_service.get_session() as session:
        yield session


# Service injection patterns (DRY principle) - Fixed connection pool issue
def get_auth_service(session: Session = Depends(get_db_session)) -> AuthService:
    """Get auth service with injected database session - eliminates boilerplate."""
    return AuthService(session)


def get_oauth_service(session: Session = Depends(get_db_session)) -> OAuthService:
    """Get OAuth service with injected database session - eliminates boilerplate."""
    return OAuthService(session)


def get_webauthn_service(session: Session = Depends(get_db_session)) -> WebAuthnService:
    """Get WebAuthn service with injected database session - eliminates boilerplate."""
    return WebAuthnService(session)


def get_passkey_manager(
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> PasskeyManager:
    """Get passkey manager instance - eliminates boilerplate."""
    return PasskeyManager(webauthn_service)


async def get_current_user(
    token: str = Depends(oauth2_scheme), auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """Get current authenticated user from JWT token."""

    # Use standardized error factory for consistent API responses
    def raise_credentials_error() -> None:
        raise APIErrorFactory.unauthorized("Could not validate credentials")

    # Verify token
    token_data: TokenData | None = await security_manager.verify_token(token)
    if token_data is None or token_data.username is None:
        raise_credentials_error()

    # At this point, token_data is guaranteed to be non-None with a non-None username
    assert token_data is not None, "token_data should not be None after verification"
    assert token_data.username is not None, "username should not be None after verification"

    # Get user from database using injected auth service
    user: User | None = auth_service.get_user_by_username(token_data.username)
    if user is None:
        raise_credentials_error()

    # Type narrowing: user is guaranteed to be User here (not None)
    assert user is not None, "user should not be None after check"
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user (not disabled)."""
    if not current_user.is_active:
        raise APIErrorFactory.business_logic_error("Inactive user", "USER_INACTIVE")
    return current_user


def get_current_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    """Get current superuser."""
    if not current_user.is_superuser:
        raise APIErrorFactory.forbidden("Not enough permissions")
    return current_user


def require_scopes(*required_scopes: str) -> Callable[..., Awaitable[TokenData]]:
    """Dependency factory for scope-based authorization."""

    async def check_scopes(token: str = Depends(oauth2_scheme)) -> TokenData:
        def raise_credentials_error() -> None:
            raise APIErrorFactory.unauthorized("Could not validate credentials")

        token_data = await security_manager.verify_token(token)
        if token_data is None:
            raise_credentials_error()

        # At this point, token_data is guaranteed to be non-None
        assert token_data is not None, "token_data should not be None after verification"

        # Check if user has required scopes
        if not all(scope in token_data.scopes for scope in required_scopes):
            raise APIErrorFactory.forbidden("Not enough permissions")

        return token_data

    return check_scopes


async def get_current_user_from_cookie(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """Get current authenticated user from HTTP-only cookie (for Astro best practices)."""

    def raise_not_authenticated_error() -> None:
        raise APIErrorFactory.unauthorized("Not authenticated")

    # Try to get auth token from HTTP-only cookie
    auth_token = request.cookies.get("auth_token")
    if not auth_token:
        raise_not_authenticated_error()

    # At this point, auth_token is guaranteed to be a non-empty string
    assert auth_token is not None and auth_token != "", "auth_token should be valid after check"

    try:
        # Verify JWT token from cookie
        payload = jwt.decode(auth_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise_not_authenticated_error()

        # Type narrowing: username is guaranteed to be str here (not None)
        assert username is not None, "username should not be None after check"
        token_data = TokenData(username=username)
    except jwt.ExpiredSignatureError:
        raise APIErrorFactory.unauthorized("Token expired")
    except jwt.InvalidTokenError:
        raise_not_authenticated_error()

    # Get user from database using injected auth service
    # Type narrowing: token_data.username is guaranteed to be str here (not None)
    assert token_data.username is not None, "token_data.username should not be None after check"
    user: User | None = auth_service.get_user_by_username(token_data.username)
    if user is None:
        raise_not_authenticated_error()

    # Type narrowing: user is guaranteed to be User here (not None)
    assert user is not None, "user should not be None after check"
    return user


def get_current_active_user_from_cookie(
    current_user: User = Depends(get_current_user_from_cookie),
) -> User:
    """Get current active user from cookie (not disabled)."""
    if not current_user.is_active:
        raise APIErrorFactory.business_logic_error("Inactive user", "USER_INACTIVE")
    return current_user
