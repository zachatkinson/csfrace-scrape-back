"""Authentication router with comprehensive endpoints following FastAPI patterns."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..constants import AUTH_CONSTANTS
from ..database.service import DatabaseService
from .config import auth_config
from .dependencies import get_current_active_user, get_current_superuser, get_database_service
from .models import (
    OAuthCallback,
    OAuthProvider,
    PasskeyAuthenticationRequest,
    PasskeyAuthenticationResponse,
    PasskeyCredentialRequest,
    PasskeyRegistrationRequest,
    PasskeyRegistrationResponse,
    PasskeySummary,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
    SSOLoginRequest,
    SSOLoginResponse,
    Token,
    User,
    UserCreate,
    UserUpdate,
)
from .oauth_service import OAuthService
from .security import security_manager
from .service import AuthService
from .webauthn_service import PasskeyManager, WebAuthnService

# Rate limiter for authentication endpoints
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=Token)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def login_for_access_token(
    _request,  # Required for rate limiting
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_service: DatabaseService = Depends(get_database_service),
) -> Token:
    """Authenticate user and return JWT tokens."""
    # Use existing database session pattern
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Authenticate user
        user = auth_service.authenticate_user(form_data.username, form_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

        # Create access token
        access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security_manager.create_access_token(
            data={"sub": user.username, "user_id": user.id, "scopes": form_data.scopes},
            expires_delta=access_token_expires,
        )

        # Create refresh token
        refresh_token = security_manager.create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )

        return Token(
            access_token=access_token,
            token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
            expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )


@router.post("/register", response_model=User)
@limiter.limit(auth_config.REGISTER_RATE_LIMIT)
def register_user(
    _request,  # Required for rate limiting
    user_create: UserCreate,
    db_service: DatabaseService = Depends(get_database_service),
) -> User:
    """Register new user account."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Check if username already exists
        existing_user = auth_service.get_user_by_username(user_create.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered"
            )

        # Check if email already exists
        existing_email = auth_service.get_user_by_email(user_create.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
            )

        # Create user
        user = auth_service.create_user(user_create)
        return user


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    refresh_token: str, db_service: DatabaseService = Depends(get_database_service)
) -> Token:
    """Refresh access token using refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verify refresh token
    token_data = security_manager.verify_token(refresh_token)
    if token_data is None or token_data.username is None:
        raise credentials_exception

    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Get user
        user = auth_service.get_user_by_username(token_data.username)
        if user is None or not user.is_active:
            raise credentials_exception

        # Create new access token
        access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security_manager.create_access_token(
            data={"sub": user.username, "user_id": user.id}, expires_delta=access_token_expires
        )

        return Token(
            access_token=access_token,
            token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
            expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )


@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    """Get current user information."""
    return current_user


@router.put("/me", response_model=User)
def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> User:
    """Update current user information."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Check if email is being changed and already exists
        if user_update.email and user_update.email != current_user.email:
            existing_email = auth_service.get_user_by_email(user_update.email)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
                )

        updated_user = auth_service.update_user(current_user.id, user_update)
        if not updated_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return updated_user


@router.post("/change-password")
def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Change user password."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Authenticate current password
        user_in_db = auth_service.authenticate_user(
            current_user.username, password_change.current_password
        )
        if not user_in_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
            )

        # Change password
        success = auth_service.change_password(current_user.id, password_change.new_password)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password",
            )

        return {"message": "Password changed successfully"}


@router.post("/password-reset")
@limiter.limit(auth_config.PASSWORD_RESET_RATE_LIMIT)
def request_password_reset(
    _request,  # Required for rate limiting
    password_reset: PasswordReset,
    db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Request password reset (sends email with reset token)."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Check if user exists
        _user = auth_service.get_user_by_email(password_reset.email)

        # Always return success to prevent email enumeration
        # In production, this would send an email with reset token
        return {"message": "If email exists, password reset instructions have been sent"}


@router.post("/password-reset/confirm")
def confirm_password_reset(
    _password_reset_confirm: PasswordResetConfirm,
    _db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Confirm password reset with token."""
    # TODO: Implement password reset token validation
    # This would validate the reset token and change the password

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset confirmation not yet implemented",
    )


# Admin endpoints
@router.get("/users", response_model=list[User], dependencies=[Depends(get_current_superuser)])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service),
) -> list[User]:
    """List all users with pagination (admin only)."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)
        return auth_service.list_users(skip=skip, limit=limit)


@router.get("/users/{user_id}", response_model=User, dependencies=[Depends(get_current_superuser)])
def get_user(
    user_id: str,
    db_service: DatabaseService = Depends(get_database_service),
) -> User:
    """Get user by ID (admin only)."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        user = auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return user


@router.delete("/users/{user_id}", dependencies=[Depends(get_current_superuser)])
def deactivate_user(
    user_id: str,
    db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Deactivate user account (admin only)."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        success = auth_service.deactivate_user(user_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return {"message": "User deactivated successfully"}


# OAuth2 SSO Endpoints
@router.post("/oauth/login", response_model=SSOLoginResponse)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def initiate_oauth_login(
    _request,  # Required for rate limiting
    sso_request: SSOLoginRequest,
    db_service: DatabaseService = Depends(get_database_service),
) -> SSOLoginResponse:
    """Initiate OAuth2 SSO login flow - Following FastAPI official patterns."""
    with db_service.get_session() as session:
        oauth_service = OAuthService(session)
        return oauth_service.initiate_oauth_login(
            provider=sso_request.provider, redirect_uri=sso_request.redirect_uri
        )


@router.post("/oauth/{provider}/callback", response_model=Token)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def handle_oauth_callback(
    _request,  # Required for rate limiting
    provider: OAuthProvider,
    oauth_callback: OAuthCallback,
    db_service: DatabaseService = Depends(get_database_service),
) -> Token:
    """Handle OAuth2 callback and return JWT tokens - Async OAuth per FastAPI docs."""
    if oauth_callback.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {oauth_callback.error_description or oauth_callback.error}",
        )

    # Validate provider consistency
    if provider != oauth_callback.provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Provider mismatch in callback"
        )

    with db_service.get_session() as session:
        _oauth_service = OAuthService(session)
        _auth_service = AuthService(session)

        # Handle OAuth callback (this would normally be async but using sync for consistency)
        # In a real implementation, you'd use async/await here per FastAPI OAuth patterns
        try:
            # For now, create a placeholder response - full implementation needs async
            # TODO: Implement actual OAuth callback handling

            # Create placeholder user for demonstration
            # In real implementation: user, is_new = await oauth_service.handle_oauth_callback(...)

            # For now, return a basic token (should be replaced with actual OAuth flow)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="OAuth callback handling not fully implemented - requires async database operations",
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OAuth authentication failed: {str(e)}",
            )


@router.get("/oauth/providers", response_model=list[str])
def list_oauth_providers() -> list[str]:
    """List available OAuth2 providers - Simple endpoint per REST principles."""
    return [provider.value for provider in OAuthProvider]


# WebAuthn/Passkeys Endpoints - Passwordless Authentication
@router.post("/passkeys/register/begin", response_model=PasskeyRegistrationResponse)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def begin_passkey_registration(
    _request,  # Required for rate limiting
    passkey_request: PasskeyRegistrationRequest,
    current_user: User = Depends(get_current_active_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> PasskeyRegistrationResponse:
    """Begin WebAuthn/Passkeys registration - Following FIDO2 standards."""
    with db_service.get_session() as session:
        webauthn_service = WebAuthnService(session)
        passkey_manager = PasskeyManager(webauthn_service)

        try:
            registration_data = passkey_manager.start_passkey_registration(
                user=current_user, device_name=passkey_request.device_name or "Default Device"
            )

            return PasskeyRegistrationResponse(
                public_key=registration_data["publicKey"],
                challenge_key=registration_data["challengeKey"],
                device_name=registration_data["deviceName"],
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate passkey registration: {str(e)}",
            )


@router.post("/passkeys/register/complete", response_model=dict[str, str])
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def complete_passkey_registration(
    _request,  # Required for rate limiting
    _credential_request: PasskeyCredentialRequest,
    _current_user: User = Depends(get_current_active_user),
    _db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Complete WebAuthn/Passkeys registration - Store credential."""
    # TODO: Implement actual credential verification and storage
    # This requires proper WebAuthn library integration with database
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Passkey registration completion not yet implemented - requires database integration",
    )


@router.post("/passkeys/authenticate/begin", response_model=PasskeyAuthenticationResponse)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def begin_passkey_authentication(
    _request,  # Required for rate limiting
    auth_request: PasskeyAuthenticationRequest,
    db_service: DatabaseService = Depends(get_database_service),
) -> PasskeyAuthenticationResponse:
    """Begin WebAuthn/Passkeys authentication - Supports usernameless login."""
    with db_service.get_session() as session:
        webauthn_service = WebAuthnService(session)
        passkey_manager = PasskeyManager(webauthn_service)

        try:
            # Get user if username provided, otherwise None for usernameless auth
            user = None
            if auth_request.username:
                auth_service = AuthService(session)
                user = auth_service.get_user_by_username(auth_request.username)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                    )

            authentication_data = passkey_manager.start_passkey_authentication(user)

            return PasskeyAuthenticationResponse(
                public_key=authentication_data["publicKey"],
                challenge_key=authentication_data["challengeKey"],
            )

        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate passkey authentication: {str(e)}",
            )


@router.post("/passkeys/authenticate/complete", response_model=Token)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def complete_passkey_authentication(
    _request,  # Required for rate limiting
    _credential_request: PasskeyCredentialRequest,
    _db_service: DatabaseService = Depends(get_database_service),
) -> Token:
    """Complete WebAuthn/Passkeys authentication and return JWT token."""
    # TODO: Implement actual credential verification and JWT token generation
    # This requires proper WebAuthn library integration with database
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Passkey authentication completion not yet implemented - requires database integration",
    )


@router.get("/passkeys/summary", response_model=PasskeySummary)
def get_passkey_summary(
    current_user: User = Depends(get_current_active_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> PasskeySummary:
    """Get user's passkey summary for dashboard - User management."""
    with db_service.get_session() as session:
        webauthn_service = WebAuthnService(session)
        passkey_manager = PasskeyManager(webauthn_service)

        try:
            summary_data = passkey_manager.get_passkey_summary(current_user)

            return PasskeySummary(
                total_passkeys=summary_data["total_passkeys"],
                active_passkeys=summary_data["active_passkeys"],
                last_used=summary_data["last_used"],
                devices=summary_data["devices"],
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get passkey summary: {str(e)}",
            )


@router.delete("/passkeys/{credential_id}")
def revoke_passkey(
    credential_id: str,
    current_user: User = Depends(get_current_active_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Revoke a WebAuthn/Passkey credential - Security operation."""
    with db_service.get_session() as session:
        webauthn_service = WebAuthnService(session)

        try:
            success = webauthn_service.revoke_credential(current_user, credential_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Passkey not found or already revoked",
                )

            return {"message": "Passkey revoked successfully"}

        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to revoke passkey: {str(e)}",
            )


# TODO: Add rate limit exception handler when implementing rate limiting middleware
# router.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
