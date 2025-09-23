"""FastAPI dependencies for authentication following official patterns."""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

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


# Service injection patterns (DRY principle)
def get_auth_service(db_service: DatabaseService = Depends(get_database_service)) -> AuthService:
    """Get auth service with injected database session - eliminates boilerplate."""
    with db_service.get_session() as session:
        return AuthService(session)


def get_oauth_service(db_service: DatabaseService = Depends(get_database_service)) -> OAuthService:
    """Get OAuth service with injected database session - eliminates boilerplate."""
    with db_service.get_session() as session:
        return OAuthService(session)


def get_webauthn_service(
    db_service: DatabaseService = Depends(get_database_service),
) -> WebAuthnService:
    """Get WebAuthn service with injected database session - eliminates boilerplate."""
    with db_service.get_session() as session:
        return WebAuthnService(session)


def get_passkey_manager(
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> PasskeyManager:
    """Get passkey manager instance - eliminates boilerplate."""
    return PasskeyManager(webauthn_service)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db_service: DatabaseService = Depends(get_database_service)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verify token
    token_data: TokenData | None = await security_manager.verify_token(token)
    if token_data is None or token_data.username is None:
        raise credentials_exception

    # Get user from database using existing session pattern
    with db_service.get_session() as session:
        auth_service = AuthService(session)
        # Use maybe_none wrapper (DRY principle) to handle assignment-from-none
        from ..api.utils import maybe_none  # pylint: disable=import-outside-toplevel

        user = maybe_none(auth_service.get_user_by_username, token_data.username)
        if user is None:
            raise credentials_exception

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user (not disabled)."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def get_current_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    """Get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user


def require_scopes(*required_scopes: str):
    """Dependency factory for scope-based authorization."""

    async def check_scopes(token: str = Depends(oauth2_scheme)) -> TokenData:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        token_data = await security_manager.verify_token(token)
        if token_data is None:
            raise credentials_exception

        # Check if user has required scopes
        if not all(scope in token_data.scopes for scope in required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )

        return token_data

    return check_scopes


async def get_current_user_from_cookie(
    request: Request, db_service: DatabaseService = Depends(get_database_service)
) -> User:
    """Get current authenticated user from HTTP-only cookie (for Astro best practices)."""
    import structlog

    logger = structlog.get_logger(__name__)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Debug: Log all cookies received
    all_cookies = dict(request.cookies) if request.cookies else {}
    logger.info(
        "Cookie authentication attempt",
        cookies_received=all_cookies,
        has_auth_token=bool(request.cookies.get("auth_token")),
    )

    # Try to get auth token from HTTP-only cookie
    auth_token = request.cookies.get("auth_token")
    if not auth_token:
        logger.warning("No auth_token cookie found")
        raise credentials_exception

    try:
        # Debug: Log token details (first/last 10 chars only for security)
        token_preview = (
            f"{auth_token[:10]}...{auth_token[-10:]}" if len(auth_token) > 20 else "short_token"
        )
        logger.info(
            "Attempting JWT decode",
            token_preview=token_preview,
            secret_key_length=len(auth_config.SECRET_KEY),
            algorithm=auth_config.ALGORITHM,
        )

        # Verify JWT token from cookie
        payload = jwt.decode(auth_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        username: str = payload.get("sub")
        logger.info("JWT decode successful", username=username, payload_keys=list(payload.keys()))

        if username is None:
            logger.warning("No username (sub) in JWT payload")
            raise credentials_exception

        token_data = TokenData(username=username)
    except jwt.ExpiredSignatureError as e:
        logger.warning("JWT token expired", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("JWT token invalid", error=str(e), error_type=type(e).__name__)
        raise credentials_exception

    # Get user from database
    with db_service.get_session() as session:
        auth_service = AuthService(session)
        from ..api.utils import maybe_none  # pylint: disable=import-outside-toplevel

        user = maybe_none(auth_service.get_user_by_username, token_data.username)
        if user is None:
            logger.warning("User not found in database", username=token_data.username)
            raise credentials_exception

        logger.info(
            "Cookie authentication successful",
            user_id=user.id,
            username=user.username,
            is_active=user.is_active,
        )

    return user


def get_current_active_user_from_cookie(
    current_user: User = Depends(get_current_user_from_cookie),
) -> User:
    """Get current active user from cookie (not disabled)."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user
