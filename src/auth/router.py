"""Authentication router with comprehensive endpoints following FastAPI patterns."""

from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import AuthenticationCredential, RegistrationCredential

from ..constants import AUTH_CONSTANTS, OAUTH_REDIRECT_URI_BASE
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

logger = structlog.get_logger(__name__)

# Rate limiter for authentication endpoints
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=Token)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def login_for_access_token(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument  # pylint: disable=unused-argument
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_service: DatabaseService = Depends(get_database_service),
) -> Token:
    """Authenticate user and return JWT tokens."""
    # Use existing database session pattern
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Authenticate user and get user data
        authenticated_user = auth_service.authenticate_user(form_data.username, form_data.password)  # pylint: disable=assignment-from-none
        if authenticated_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # At this point, authenticated_user is guaranteed not to be None

        if not authenticated_user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

        # Create access token
        access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security_manager.create_access_token(
            data={
                "sub": authenticated_user.username,
                "user_id": authenticated_user.id,
                "scopes": form_data.scopes,
            },
            expires_delta=access_token_expires,
        )

        # Create refresh token
        refresh_token = security_manager.create_refresh_token(
            data={"sub": authenticated_user.username, "user_id": authenticated_user.id}
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
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
    user_create: UserCreate,
    db_service: DatabaseService = Depends(get_database_service),
) -> User:
    """Register new user account."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Check if username already exists
        if auth_service.get_user_by_username(user_create.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered"
            )

        # Check if email already exists
        if auth_service.get_user_by_email(user_create.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
            )

        # Create user
        user = auth_service.create_user(user_create)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user"
            )
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
        user = auth_service.get_user_by_username(token_data.username)  # pylint: disable=assignment-from-none
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
        if (
            user_update.email
            and user_update.email != current_user.email
            and auth_service.get_user_by_email(user_update.email)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
            )

        updated_user = auth_service.update_user(current_user.id, user_update)  # pylint: disable=assignment-from-none
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
        if not auth_service.authenticate_user(
            current_user.username, password_change.current_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
            )

        # Change password
        if not auth_service.change_password(current_user.id, password_change.new_password):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password",
            )

        return {"message": "Password changed successfully"}


@router.post("/password-reset")
@limiter.limit(auth_config.PASSWORD_RESET_RATE_LIMIT)
def request_password_reset(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
    password_reset: PasswordReset,
    db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Request password reset (sends email with reset token)."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        # Check if user exists (we don't use result to avoid user enumeration)
        _ = auth_service.get_user_by_email(password_reset.email)  # pylint: disable=assignment-from-none

        # Always return success to prevent email enumeration
        # In production, this would send an email with reset token
        return {"message": "If email exists, password reset instructions have been sent"}


@router.post("/password-reset/confirm")
def confirm_password_reset(
    _password_reset_confirm: PasswordResetConfirm,
    _db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Confirm password reset with token."""
    # Password reset token validation will be implemented in future release
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
        return auth_service.list_users(_skip=skip, _limit=limit)


@router.get("/users/{user_id}", response_model=User, dependencies=[Depends(get_current_superuser)])
def get_user(
    user_id: str,
    db_service: DatabaseService = Depends(get_database_service),
) -> User:
    """Get user by ID (admin only)."""
    with db_service.get_session() as session:
        auth_service = AuthService(session)

        user = auth_service.get_user_by_id(user_id)  # pylint: disable=assignment-from-none
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

        if not auth_service.deactivate_user(user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return {"message": "User deactivated successfully"}


# OAuth2 SSO Helper Functions
def _validate_oauth_callback_parameters(
    provider: OAuthProvider, oauth_callback: OAuthCallback
) -> None:
    """Validate OAuth callback parameters and handle errors."""
    # Step 1: Validate OAuth error responses
    if oauth_callback.error:
        error_detail = oauth_callback.error_description or oauth_callback.error
        logger.warning(
            "OAuth callback received error",
            provider=provider.value,
            error=oauth_callback.error,
            error_description=oauth_callback.error_description,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authorization failed: {error_detail}",
        )

    # Step 2: Validate provider consistency (CSRF protection)
    if provider != oauth_callback.provider:
        logger.warning(
            "OAuth callback provider mismatch",
            url_provider=provider.value,
            callback_provider=oauth_callback.provider.value,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider mismatch - possible CSRF attack",
        )

    # Step 3: Validate required OAuth callback parameters
    if not oauth_callback.code:
        logger.warning("OAuth callback missing authorization code", provider=provider.value)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code in OAuth callback",
        )

    if not oauth_callback.state:
        logger.warning("OAuth callback missing state parameter", provider=provider.value)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing state parameter in OAuth callback",
        )


async def _process_oauth_token_exchange(
    provider: OAuthProvider, oauth_callback: OAuthCallback, oauth_service: OAuthService
) -> tuple[str, bool]:
    """Process OAuth token exchange and return access token."""
    # Build redirect URI for token exchange (must match the one used in authorization)
    redirect_uri = f"{OAUTH_REDIRECT_URI_BASE}/auth/oauth/{provider.value}/callback"

    # Handle OAuth callback and get user information
    return await oauth_service.handle_oauth_callback(
        provider=provider,
        code=oauth_callback.code,
        state=oauth_callback.state,
        redirect_uri=redirect_uri,
    )


def _create_jwt_tokens_for_user(user: User) -> Token:
    """Create JWT access and refresh tokens for authenticated user."""
    access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_access_token = security_manager.create_access_token(
        data={"sub": user.username, "user_id": user.id, "scopes": []},
        expires_delta=access_token_expires,
    )

    jwt_refresh_token = security_manager.create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )

    return Token(
        access_token=jwt_access_token,
        token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
        expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        refresh_token=jwt_refresh_token,
    )


# OAuth2 SSO Endpoints
@router.post("/oauth/login", response_model=SSOLoginResponse)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def initiate_oauth_login(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
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
async def handle_oauth_callback(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
    provider: OAuthProvider,
    oauth_callback: OAuthCallback,
    db_service: DatabaseService = Depends(get_database_service),
) -> Token:
    """Handle OAuth2 callback and return JWT tokens following OAuth2 Authorization Code Flow.

    This endpoint implements the OAuth2 Authorization Code Flow callback handling
    according to RFC 6749 and FastAPI security best practices.
    """
    # Validate OAuth callback parameters
    _validate_oauth_callback_parameters(provider, oauth_callback)

    # Process OAuth callback with database session
    with db_service.get_session() as session:
        oauth_service = OAuthService(session)
        auth_service = AuthService(session)

        try:
            logger.info(
                "Processing OAuth callback",
                provider=provider.value,
                code_present=bool(oauth_callback.code),
                state_present=bool(oauth_callback.state),
            )

            # Exchange authorization code for access token
            access_token, is_new_user = await _process_oauth_token_exchange(
                provider, oauth_callback, oauth_service
            )

            # Get user information and retrieve user from database
            user_info = await oauth_service._get_cached_user_info(access_token)  # pylint: disable=protected-access
            user = auth_service.get_user_by_email(user_info.email)  # pylint: disable=assignment-from-none

            if not user:
                logger.error("User not found after OAuth callback processing")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User account creation or retrieval failed",
                )

            # Log successful OAuth authentication
            logger.info(
                "OAuth authentication successful",
                provider=provider.value,
                user_id=user.id,
                email=user.email,
                is_new_user=is_new_user,
            )

            # Generate and return JWT tokens
            return _create_jwt_tokens_for_user(user)

        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except ValueError as e:
            # Handle validation errors from OAuth service
            logger.warning("OAuth callback validation error", provider=provider.value, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth validation failed: {str(e)}",
            ) from e
        except Exception as e:
            # Handle unexpected errors with structured logging
            logger.error(
                "Unexpected error in OAuth callback",
                provider=provider.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OAuth authentication failed due to internal error",
            ) from e


@router.get("/oauth/providers", response_model=list[str])
def list_oauth_providers() -> list[str]:
    """List available OAuth2 providers - Simple endpoint per REST principles."""
    return [provider.value for provider in OAuthProvider]


# WebAuthn/Passkeys Endpoints - Passwordless Authentication
@router.post("/passkeys/register/begin", response_model=PasskeyRegistrationResponse)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def begin_passkey_registration(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
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
            ) from e


@router.post("/passkeys/register/complete", response_model=dict[str, str])
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def complete_passkey_registration(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
    credential_request: PasskeyCredentialRequest,
    current_user: User = Depends(get_current_active_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> dict[str, str]:
    """Complete WebAuthn/Passkeys registration following FIDO2 standards."""
    with db_service.get_session() as session:
        webauthn_service = WebAuthnService(session)

        try:
            logger.info(
                "Processing passkey registration completion",
                user_id=current_user.id,
                challenge_key=credential_request.challenge_key,
                device_name=credential_request.device_name,
            )

            # Convert credential response to WebAuthn format
            credential_response = credential_request.credential_response

            # Validate required fields are present
            required_fields = ["id", "rawId", "response", "type"]
            if not all(field in credential_response for field in required_fields):
                logger.warning(
                    "Invalid credential response format",
                    user_id=current_user.id,
                    missing_fields=[f for f in required_fields if f not in credential_response],
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid credential response format",
                )

            # Create RegistrationCredential object
            registration_credential = RegistrationCredential(
                id=credential_response["id"],
                raw_id=base64url_to_bytes(credential_response["rawId"]),
                response=credential_response["response"],
                type=credential_response["type"],
            )

            # Verify and store the credential
            webauthn_credential = webauthn_service.verify_registration_response(
                credential=registration_credential,
                challenge_key=credential_request.challenge_key,
                device_name=credential_request.device_name,
            )

            logger.info(
                "Passkey registration completed successfully",
                user_id=current_user.id,
                credential_id=webauthn_credential.credential_id,
                device_name=webauthn_credential.metadata.device_name,
            )

            return {
                "message": "Passkey registered successfully",
                "credential_id": webauthn_credential.credential_id,
                "device_name": webauthn_credential.metadata.device_name or "Default Device",
            }

        except ValueError as e:
            # Handle WebAuthn validation errors
            logger.warning(
                "Passkey registration validation failed",
                user_id=current_user.id,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Passkey registration failed: {str(e)}",
            ) from e
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                "Unexpected error in passkey registration",
                user_id=current_user.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Passkey registration failed due to internal error",
            ) from e


@router.post("/passkeys/authenticate/begin", response_model=PasskeyAuthenticationResponse)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def begin_passkey_authentication(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
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
                user = auth_service.get_user_by_username(auth_request.username)  # pylint: disable=assignment-from-none
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
            ) from e


@router.post("/passkeys/authenticate/complete", response_model=Token)
@limiter.limit(auth_config.AUTH_RATE_LIMIT)
def complete_passkey_authentication(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
    credential_request: PasskeyCredentialRequest,
    db_service: DatabaseService = Depends(get_database_service),
) -> Token:
    """Complete WebAuthn/Passkeys authentication following FIDO2 standards and return JWT token."""
    with db_service.get_session() as session:
        webauthn_service = WebAuthnService(session)

        try:
            logger.info(
                "Processing passkey authentication completion",
                challenge_key=credential_request.challenge_key,
            )

            # Convert credential response to WebAuthn format
            credential_response = credential_request.credential_response

            # Validate required fields for authentication
            required_fields = ["id", "rawId", "response", "type"]
            if not all(field in credential_response for field in required_fields):
                logger.warning(
                    "Invalid authentication credential response format",
                    missing_fields=[f for f in required_fields if f not in credential_response],
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid authentication credential response format",
                )

            # Create AuthenticationCredential object
            authentication_credential = AuthenticationCredential(
                id=credential_response["id"],
                raw_id=base64url_to_bytes(credential_response["rawId"]),
                response=credential_response["response"],
                type=credential_response["type"],
            )

            # Verify authentication and get user
            user, webauthn_credential = webauthn_service.verify_authentication_response(
                credential=authentication_credential,
                challenge_key=credential_request.challenge_key,
            )

            logger.info(
                "Passkey authentication completed successfully",
                user_id=user.id,
                credential_id=webauthn_credential.credential_id,
                device_name=webauthn_credential.metadata.device_name,
            )

            # Generate JWT tokens for authenticated user
            access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
            jwt_access_token = security_manager.create_access_token(
                data={"sub": user.username, "user_id": user.id, "scopes": []},
                expires_delta=access_token_expires,
            )

            # Create refresh token
            jwt_refresh_token = security_manager.create_refresh_token(
                data={"sub": user.username, "user_id": user.id}
            )

            # Return JWT tokens following FastAPI Token model
            return Token(
                access_token=jwt_access_token,
                token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
                expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
                refresh_token=jwt_refresh_token,
            )

        except ValueError as e:
            # Handle WebAuthn validation errors
            logger.warning(
                "Passkey authentication validation failed",
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Passkey authentication failed: {str(e)}",
            ) from e
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                "Unexpected error in passkey authentication",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Passkey authentication failed due to internal error",
            ) from e


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
            ) from e


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
            ) from e


# Rate limit exception handler will be added when implementing rate limiting middleware
# router.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
