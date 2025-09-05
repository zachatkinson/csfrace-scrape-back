"""FastAPI dependencies for authentication following official patterns."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..database.service import DatabaseService
from .models import TokenData, User
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


def get_current_user(
    token: str = Depends(oauth2_scheme), db_service: DatabaseService = Depends(get_database_service)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verify token
    token_data: TokenData | None = security_manager.verify_token(token)
    if token_data is None or token_data.username is None:
        raise credentials_exception

    # Get user from database using existing session pattern
    with db_service.get_session() as session:
        auth_service = AuthService(session)
        user = auth_service.get_user_by_username(token_data.username)  # pylint: disable=assignment-from-none
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

        token_data = security_manager.verify_token(token)
        if token_data is None:
            raise credentials_exception

        # Check if user has required scopes
        if not all(scope in token_data.scopes for scope in required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )

        return token_data

    return check_scopes


def get_webauthn_service(
    db_service: DatabaseService = Depends(get_database_service),
) -> WebAuthnService:
    """Get WebAuthn service instance with database dependency."""
    with db_service.get_session() as session:
        return WebAuthnService(db_session=session)


def get_passkey_manager(
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> PasskeyManager:
    """Get PasskeyManager instance with WebAuthn service dependency."""
    return PasskeyManager(webauthn_service)
