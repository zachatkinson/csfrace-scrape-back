"""FastAPI dependencies for authentication following official patterns."""

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from ..api.errors import APIErrorFactory
from ..database.service import DatabaseService
from .config import auth_config
from .models import TokenData, User
from .oauth_service import OAuthService
from .security import security_manager
from .service import AuthService
from .webauthn_service import PasskeyManager, WebAuthnService

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
def get_db_session(db_service: DatabaseService = Depends(get_database_service)):
    """Get database session with proper lifecycle management for FastAPI."""
    with db_service.get_session() as session:
        yield session


# Service injection patterns (DRY principle) - Fixed connection pool issue
def get_auth_service(session=Depends(get_db_session)) -> AuthService:
    """Get auth service with injected database session - eliminates boilerplate."""
    return AuthService(session)


def get_oauth_service(session=Depends(get_db_session)) -> OAuthService:
    """Get OAuth service with injected database session - eliminates boilerplate."""
    return OAuthService(session)


def get_webauthn_service(session=Depends(get_db_session)) -> WebAuthnService:
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
    def raise_credentials_error():
        raise APIErrorFactory.unauthorized("Could not validate credentials")

    # Verify token
    token_data: TokenData | None = await security_manager.verify_token(token)
    if token_data is None or token_data.username is None:
        raise_credentials_error()

    # At this point, token_data is guaranteed to be non-None with a non-None username
    assert token_data is not None, "token_data should not be None after verification"
    assert token_data.username is not None, "username should not be None after verification"

    # Get user from database using injected auth service
    # Use maybe_none wrapper (DRY principle) to handle assignment-from-none
    # Import inside function to avoid circular dependency: auth.dependencies -> api.utils -> auth.*
    from ..api.utils import maybe_none  # pylint: disable=import-outside-toplevel

    user = maybe_none(auth_service.get_user_by_username, token_data.username)
    if user is None:
        raise_credentials_error()

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


def require_scopes(*required_scopes: str):
    """Dependency factory for scope-based authorization."""

    async def check_scopes(token: str = Depends(oauth2_scheme)) -> TokenData:
        def raise_credentials_error():
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

    def raise_not_authenticated_error():
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
        username: str = payload.get("sub")
        if username is None:
            raise_not_authenticated_error()

        token_data = TokenData(username=username)
    except jwt.ExpiredSignatureError:
        raise APIErrorFactory.unauthorized("Token expired")
    except jwt.InvalidTokenError:
        raise_not_authenticated_error()

    # Get user from database using injected auth service
    # Import inside function to avoid circular dependency: auth.dependencies -> api.utils -> auth.*
    from ..api.utils import maybe_none  # pylint: disable=import-outside-toplevel

    user = maybe_none(auth_service.get_user_by_username, token_data.username)
    if user is None:
        raise_not_authenticated_error()

    return user


def get_current_active_user_from_cookie(
    current_user: User = Depends(get_current_user_from_cookie),
) -> User:
    """Get current active user from cookie (not disabled)."""
    if not current_user.is_active:
        raise APIErrorFactory.business_logic_error("Inactive user", "USER_INACTIVE")
    return current_user
