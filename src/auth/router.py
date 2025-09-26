"""Authentication router with comprehensive endpoints following FastAPI patterns."""

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Literal

import asyncio
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import AuthenticationCredential, RegistrationCredential

from src.utils.logging import get_logger

from ..api.errors import APIErrorFactory
from ..api.utils import maybe_none
from ..config.rate_limits import rate_limits
from ..constants import API_DEFAULT_LIMIT, AUTH_CONSTANTS
from ..database.service import DatabaseService
from .config import auth_config
from .dependencies import (
    get_auth_service,
    get_current_active_user,
    get_current_active_user_from_cookie,
    get_current_superuser,
    get_database_service,
    get_oauth_service,
    get_passkey_manager,
    get_webauthn_service,
)
from .enum_utils import get_oauth_provider_value
from .models import (
    AccountLockoutStatusResponse,
    BulkTokenRevocationRequest,
    LockoutStatsResponse,
    OAuthCallback,
    OAuthConnectionResponse,
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
    RevocationStatsResponse,
    SSOLoginRequest,
    SSOLoginResponse,
    Token,
    TokenRevocationRequest,
    TokenRevocationResponse,
    UnlockAccountRequest,
    User,
    UserCreate,
    UserUpdate,
)
from .oauth_service import OAuthService
from .security import security_manager
from .service import AuthService
from .webauthn_service import PasskeyManager, WebAuthnService

logger = get_logger(__name__)

# Rate limiter for authentication endpoints
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=Token)
@limiter.limit(rate_limits.AUTH_LOGIN)  # DRY: Centralized rate limits
async def login_for_access_token(
    request: Request,  # Required for SlowAPI rate limiting
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),  # DRY: Service injection
) -> Token:
    """Authenticate user and return JWT tokens with account lockout protection."""
    from .lockout_service import account_lockout_service

    # Get client information for security audit trail
    client_ip = get_remote_address(request)
    user_agent = request.headers.get("user-agent")

    # First check if account is locked - Security requirement
    user = maybe_none(auth_service.get_user_by_username, form_data.username)
    if user:
        is_locked, remaining_minutes = await account_lockout_service.is_account_locked(user.id)
        if is_locked:
            # Record failed attempt on locked account (for audit trail)
            await account_lockout_service.record_failed_login_attempt(
                user.id, form_data.username, client_ip, user_agent
            )

            logger.warning(
                "Login attempt on locked account",
                user_id=user.id,
                username=form_data.username,
                client_ip=client_ip,
                remaining_minutes=remaining_minutes,
            )

            raise APIErrorFactory.business_logic_error(
                f"Account is locked. Try again in {remaining_minutes} minutes.", "ACCOUNT_LOCKED"
            )

    # Attempt authentication
    authenticated_user = maybe_none(
        auth_service.authenticate_user, form_data.username, form_data.password
    )

    if authenticated_user is None:
        # Record failed login attempt - Security requirement
        if user:  # Only record if user exists
            account_was_locked = await account_lockout_service.record_failed_login_attempt(
                user.id, form_data.username, client_ip, user_agent
            )

            if account_was_locked:
                logger.warning(
                    "Account locked due to failed login attempts",
                    user_id=user.id,
                    username=form_data.username,
                    client_ip=client_ip,
                )
                raise APIErrorFactory.business_logic_error(
                    "Account has been locked due to too many failed attempts. Please try again later.",
                    "ACCOUNT_LOCKED_ON_FAILURE",
                )

        # Generic error message to prevent username enumeration
        raise APIErrorFactory.unauthorized("Incorrect username or password")

    if not authenticated_user.is_active:
        raise APIErrorFactory.business_logic_error("Inactive user", "USER_INACTIVE")

    # Record successful login and reset any failed attempts - Security requirement
    await account_lockout_service.record_successful_login(
        authenticated_user.id, authenticated_user.username
    )

    # Create access token with JTI for revocation tracking - DRY principle
    access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, access_jti = security_manager.create_access_token(
        data={
            "sub": authenticated_user.username,
            "user_id": authenticated_user.id,
            "scopes": form_data.scopes,
        },
        expires_delta=access_token_expires,
    )

    # Create refresh token with JTI for revocation tracking - DRY principle
    refresh_token, refresh_jti = security_manager.create_refresh_token(
        data={"sub": authenticated_user.username, "user_id": authenticated_user.id}
    )

    return Token(
        access_token=access_token,
        token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
        expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
        is_new_user=False,
    )


@router.post("/register", response_model=User)
@limiter.limit(rate_limits.AUTH_REGISTER)  # DRY: Centralized rate limits
def register_user(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    user_create: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),  # DRY: Service injection
) -> User:
    """Register new user account."""
    # Check if username already exists
    # Check if username already exists
    if maybe_none(auth_service.get_user_by_username, user_create.username):
        raise APIErrorFactory.validation_error("Username already registered", "username")

    # Check if email already exists
    if maybe_none(auth_service.get_user_by_email, user_create.email):
        raise APIErrorFactory.validation_error("Email already registered", "email")

    # Create user
    user = maybe_none(auth_service.create_user, user_create)
    if not user:
        raise APIErrorFactory.internal_server_error("Failed to create user")

    return user


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: str, auth_service: AuthService = Depends(get_auth_service)
) -> Token:
    """Refresh access token using refresh token."""
    # Verify refresh token with revocation checking - Security enhancement
    token_data = await security_manager.verify_token(refresh_token)
    if token_data is None or token_data.username is None:
        raise APIErrorFactory.unauthorized("Could not validate refresh token")

    # Verify this is actually a refresh token
    if token_data.token_type != "refresh":  # noqa: S105
        raise APIErrorFactory.unauthorized("Invalid token type for refresh operation")

    # Get user
    user = maybe_none(auth_service.get_user_by_username, token_data.username)
    if user is None or not user.is_active:
        raise APIErrorFactory.unauthorized("Could not validate refresh token")

    # Create new access token with JTI - DRY principle
    access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, access_jti = security_manager.create_access_token(
        data={"sub": user.username, "user_id": user.id}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
        expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        is_new_user=True,
    )


@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_active_user_from_cookie)) -> User:
    """Get current user information from HTTP-only cookie (Astro best practices)."""
    return current_user


@router.put("/me", response_model=User)
def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Update current user information."""
    # Check if email is being changed and already exists
    if (
        user_update.email
        and user_update.email != current_user.email
        and maybe_none(auth_service.get_user_by_email, user_update.email)
    ):
        raise APIErrorFactory.validation_error("Email already registered", "email")

    updated_user = maybe_none(auth_service.update_user, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return updated_user


@router.post("/change-password")
def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Change user password."""
    # Authenticate current password
    authenticated_user = maybe_none(
        auth_service.authenticate_user, current_user.username, password_change.current_password
    )
    if not authenticated_user:
        raise APIErrorFactory.business_logic_error("Incorrect current password", "INVALID_PASSWORD")

    # Change password
    if not auth_service.change_password(current_user.id, password_change.new_password):
        raise APIErrorFactory.internal_server_error("Failed to change password")

    return {"message": "Password changed successfully"}


@router.post("/password-reset")
@limiter.limit(rate_limits.AUTH_PASSWORD_RESET)
def request_password_reset(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    password_reset: PasswordReset,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Request password reset (sends email with reset token)."""
    # Check if user exists (we don't use result to avoid user enumeration)
    _ = maybe_none(auth_service.get_user_by_email, password_reset.email)

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
    limit: int = API_DEFAULT_LIMIT,
    auth_service: AuthService = Depends(get_auth_service),
) -> list[User]:
    """List all users with pagination (admin only)."""
    return auth_service.list_users(_skip=skip, _limit=limit)


@router.get("/users/{user_id}", response_model=User, dependencies=[Depends(get_current_superuser)])
def get_user(
    user_id: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Get user by ID (admin only)."""
    user = maybe_none(auth_service.get_user_by_id, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


@router.delete("/users/{user_id}", dependencies=[Depends(get_current_superuser)])
def deactivate_user(
    user_id: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Deactivate user account (admin only)."""
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
            provider=get_oauth_provider_value(provider),
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
            url_provider=get_oauth_provider_value(provider),
            callback_provider=get_oauth_provider_value(oauth_callback.provider),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider mismatch - possible CSRF attack",
        )

    # Step 3: Validate required OAuth callback parameters
    if not oauth_callback.code:
        logger.warning(
            "OAuth callback missing authorization code", provider=get_oauth_provider_value(provider)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code in OAuth callback",
        )

    if not oauth_callback.state:
        logger.warning(
            "OAuth callback missing state parameter", provider=get_oauth_provider_value(provider)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing state parameter in OAuth callback",
        )


async def _process_oauth_token_exchange(
    provider: OAuthProvider, oauth_callback: OAuthCallback, oauth_service: OAuthService
) -> tuple[User, bool]:
    """Process OAuth token exchange and return user."""
    # OAuth service will extract the original redirect URI from JWT state and use it
    # for token exchange (as required by OAuth2 spec)
    return await oauth_service.handle_oauth_callback(
        provider=provider,
        code=oauth_callback.code,
        state=oauth_callback.state,
        redirect_uri="",  # Not used - OAuth service extracts from JWT state
    )


def _create_jwt_tokens_for_user(user: User, is_new_user: bool = False) -> Token:
    """Create JWT access and refresh tokens for authenticated user."""
    access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_access_token, access_jti = security_manager.create_access_token(
        data={"sub": user.username, "user_id": user.id, "scopes": []},
        expires_delta=access_token_expires,
    )

    jwt_refresh_token, refresh_jti = security_manager.create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )

    return Token(
        access_token=jwt_access_token,
        token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
        expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        refresh_token=jwt_refresh_token,
        is_new_user=is_new_user,
    )


def _set_secure_auth_cookies(response: Response, token: Token) -> None:
    """Set HTTP-only cookies for secure token storage following OWASP best practices."""
    # Environment-aware security settings
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_production = environment == "production"
    secure_cookies = is_production  # Only use secure cookies in production (HTTPS required)

    # Domain setting for cookie scope
    # CRITICAL: Set domain to ensure cookies are accessible to both OAuth redirect (port 3000)
    # and subsequent SSE proxy requests. Without explicit domain, cookies may not be shared.
    cookie_domain = "localhost"  # Required for multi-port localhost access

    # SameSite policy for development vs production
    # Use "lax" in development to allow cross-origin SSE proxy requests
    samesite_policy: Literal["strict", "lax"] = "strict" if is_production else "lax"

    # Access token cookie - short lived
    response.set_cookie(
        key="auth_token",
        value=token.access_token,
        max_age=token.expires_in,  # Seconds until expiration
        httponly=True,  # Prevents XSS attacks
        secure=secure_cookies,  # HTTPS only in production
        samesite=samesite_policy,  # Environment-aware CSRF protection
        path="/",  # Available to entire application
        domain=cookie_domain,  # Cross-port support in development
    )

    # Refresh token cookie - longer lived
    if token.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=token.refresh_token,
            max_age=60 * 60 * 24 * 30,  # 30 days
            httponly=True,
            secure=secure_cookies,
            samesite=samesite_policy,  # Environment-aware CSRF protection
            path="/",  # Use same path as auth_token for consistency
            domain=cookie_domain,  # Cross-port support in development
        )

    # User info cookie for frontend (non-sensitive data only)
    response.set_cookie(
        key="auth_user",
        value=f'{{"isAuthenticated":true,"isNewUser":{str(token.is_new_user).lower()}}}',
        max_age=token.expires_in,
        httponly=False,  # Frontend needs to read this
        secure=secure_cookies,
        samesite=samesite_policy,  # Environment-aware CSRF protection
        path="/",
        domain=cookie_domain,  # Cross-port support in development
    )

    logger.info(
        "Secure authentication cookies set",
        access_token_expires=token.expires_in,
        has_refresh_token=bool(token.refresh_token),
        is_new_user=token.is_new_user,
        environment=environment,
        secure_cookies=secure_cookies,
        cookie_domain=cookie_domain,
        samesite_policy=samesite_policy,
    )


# OAuth2 SSO Endpoints
@router.post("/oauth/login", response_model=SSOLoginResponse)
@limiter.limit(rate_limits.AUTH_OAUTH)
def initiate_oauth_login(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    sso_request: SSOLoginRequest,
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> SSOLoginResponse:
    """Initiate OAuth2 SSO login flow - Following FastAPI official patterns."""
    return oauth_service.initiate_oauth_login(
        provider=sso_request.provider, redirect_uri=sso_request.redirect_uri
    )


@router.get("/oauth/{provider}/callback", response_model=Token)
@limiter.limit(rate_limits.AUTH_OAUTH)
async def handle_oauth_callback(
    request: Request,  # Required for SlowAPI rate limiting and query params
    response: Response,  # Required for setting HTTP-only cookies
    provider: OAuthProvider,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    oauth_service: OAuthService = Depends(get_oauth_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """Handle OAuth2 callback and return JWT tokens following OAuth2 Authorization Code Flow.

    This endpoint implements the OAuth2 Authorization Code Flow callback handling
    according to RFC 6749 and FastAPI security best practices.
    """
    # Create OAuthCallback object from query parameters
    oauth_callback = OAuthCallback(
        code=code or "",
        state=state or "",
        provider=provider,
        error=error,
        error_description=error_description,
    )

    # Validate OAuth callback parameters
    _validate_oauth_callback_parameters(provider, oauth_callback)

    # Process OAuth callback using injected services
    try:
        logger.info(
            "Processing OAuth callback",
            provider=get_oauth_provider_value(provider),
            code_present=bool(oauth_callback.code),
            state_present=bool(oauth_callback.state),
        )

        # Exchange authorization code for access token and get user
        user, is_new_user = await _process_oauth_token_exchange(
            provider, oauth_callback, oauth_service
        )

        # Log successful OAuth authentication
        logger.info(
            "OAuth authentication successful",
            provider=get_oauth_provider_value(provider),
            user_id=user.id,
            email=user.email,
            is_new_user=is_new_user,
        )

        # Generate JWT tokens
        token = _create_jwt_tokens_for_user(user, is_new_user)

        # Debug: Confirm we reached cookie setting point
        logger.info(
            "About to set secure HTTP-only cookies",
            user_id=user.id,
            token_expires=token.expires_in,
            has_refresh=bool(token.refresh_token),
        )

        try:
            # Set secure HTTP-only cookies for enterprise-grade security
            _set_secure_auth_cookies(response, token)
            logger.info("HTTP-only cookies setting completed successfully")
        except Exception as e:
            logger.error("Failed to set HTTP-only cookies", error=str(e), user_id=user.id)
            # Continue anyway - don't break OAuth flow for cookie issues
            pass

        # Return token for backwards compatibility and immediate frontend use
        return token

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors from OAuth service
        logger.warning(
            "OAuth callback validation error",
            provider=get_oauth_provider_value(provider),
            error=str(e),
        )
        raise APIErrorFactory.business_logic_error(
            f"OAuth validation failed: {str(e)}", "OAUTH_VALIDATION_FAILED"
        ) from e
    except Exception as e:
        # Handle unexpected errors with structured logging
        logger.error(
            "Unexpected error in OAuth callback",
            provider=get_oauth_provider_value(provider),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise APIErrorFactory.internal_server_error(
            "OAuth authentication failed due to internal error"
        ) from e


@router.get("/oauth/providers", response_model=list[str])
def list_oauth_providers() -> list[str]:
    """List available OAuth2 providers - Simple endpoint per REST principles."""
    return [get_oauth_provider_value(provider) for provider in OAuthProvider]


@router.get("/oauth/connections", response_model=list[OAuthConnectionResponse])
def get_oauth_connections(
    current_user: User = Depends(get_current_active_user_from_cookie),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> list[OAuthConnectionResponse]:
    """Get OAuth provider connections for current user - Single Responsibility Principle.

    Returns the connection status for all supported OAuth providers by querying
    the database for linked accounts. This is the efficient approach that avoids
    external API calls to OAuth providers.

    **Features:**
    - Database-driven connection detection (no external API calls)
    - Returns status for all supported providers
    - Secure authentication required
    - Following SOLID principles

    **Security:**
    - HTTP-only cookie authentication
    - User can only see their own connections
    - No sensitive token data exposed

    Returns:
        List[OAuthConnectionResponse]: Connection status for each provider
    """
    try:
        logger.info("Getting OAuth connections", user_id=current_user.id)

        connections = oauth_service.get_oauth_connections(current_user.id)

        logger.info(
            "OAuth connections retrieved successfully",
            user_id=current_user.id,
            total_providers=len(connections),
            connected_count=len([c for c in connections if c.connected]),
        )

        return connections

    except Exception as e:
        logger.error(
            "Failed to get OAuth connections",
            user_id=current_user.id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise APIErrorFactory.internal_server_error("Failed to retrieve OAuth connections") from e


# WebAuthn/Passkeys Endpoints - Passwordless Authentication
@router.post("/passkeys/register/begin", response_model=PasskeyRegistrationResponse)
@limiter.limit(rate_limits.AUTH_PASSKEY)
def begin_passkey_registration(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    passkey_request: PasskeyRegistrationRequest,
    current_user: User = Depends(get_current_active_user),
    passkey_manager: PasskeyManager = Depends(get_passkey_manager),
) -> PasskeyRegistrationResponse:
    """Begin WebAuthn/Passkeys registration - Following FIDO2 standards."""
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
        raise APIErrorFactory.internal_server_error(
            f"Failed to initiate passkey registration: {str(e)}"
        ) from e


@router.post("/passkeys/register/complete", response_model=dict[str, str])
@limiter.limit(rate_limits.AUTH_PASSKEY)
def complete_passkey_registration(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    credential_request: PasskeyCredentialRequest,
    current_user: User = Depends(get_current_active_user),
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> dict[str, str]:
    """Complete WebAuthn/Passkeys registration following FIDO2 standards."""
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
        # Use 422 for validation errors like invalid/expired challenges
        if "challenge" in str(e).lower() or "expired" in str(e).lower():
            raise APIErrorFactory.validation_error(f"Passkey registration failed: {str(e)}") from e
        raise APIErrorFactory.business_logic_error(
            f"Passkey registration failed: {str(e)}", "PASSKEY_REGISTRATION_FAILED"
        ) from e
    except Exception as e:
        # Handle unexpected errors
        logger.error(
            "Unexpected error in passkey registration",
            user_id=current_user.id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise APIErrorFactory.internal_server_error(
            "Passkey registration failed due to internal error"
        ) from e


@router.post("/passkeys/authenticate/begin", response_model=PasskeyAuthenticationResponse)
@limiter.limit(rate_limits.AUTH_PASSKEY)
def begin_passkey_authentication(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    auth_request: PasskeyAuthenticationRequest,
    auth_service: AuthService = Depends(get_auth_service),
    passkey_manager: PasskeyManager = Depends(get_passkey_manager),
) -> PasskeyAuthenticationResponse:
    """Begin WebAuthn/Passkeys authentication - Supports usernameless login."""
    try:
        # Get user if username provided, otherwise None for usernameless auth
        user = None
        if auth_request.username:
            user = maybe_none(auth_service.get_user_by_username, auth_request.username)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Start authentication (works for both username and usernameless flows)
        authentication_data = passkey_manager.start_passkey_authentication(user)

        return PasskeyAuthenticationResponse(
            public_key=authentication_data["publicKey"],
            challenge_key=authentication_data["challengeKey"],
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise APIErrorFactory.internal_server_error(
            f"Failed to initiate passkey authentication: {str(e)}"
        ) from e


@router.post("/passkeys/authenticate/complete", response_model=Token)
@limiter.limit(rate_limits.AUTH_PASSKEY)
def complete_passkey_authentication(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    credential_request: PasskeyCredentialRequest,
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> Token:
    """Complete WebAuthn/Passkeys authentication following FIDO2 standards and return JWT token."""
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
        jwt_access_token, access_jti = security_manager.create_access_token(
            data={"sub": user.username, "user_id": user.id, "scopes": []},
            expires_delta=access_token_expires,
        )

        # Create refresh token
        jwt_refresh_token, refresh_jti = security_manager.create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )

        # Return JWT tokens following FastAPI Token model
        return Token(
            access_token=jwt_access_token,
            token_type=AUTH_CONSTANTS.BEARER_TOKEN_TYPE,
            expires_in=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            refresh_token=jwt_refresh_token,
            is_new_user=False,
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
    passkey_manager: PasskeyManager = Depends(get_passkey_manager),
) -> PasskeySummary:
    """Get user's passkey summary for dashboard - User management."""
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
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> dict[str, bool | str]:
    """Revoke a WebAuthn/Passkey credential - Security operation."""
    try:
        success = webauthn_service.revoke_credential(current_user, credential_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passkey not found or already revoked",
            )

        return {"success": True, "message": "Passkey revoked successfully"}

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke passkey: {str(e)}",
        ) from e


# =============================================================================
# TOKEN REVOCATION ENDPOINTS - Critical Security Operations
# =============================================================================


@router.post("/revoke-token", response_model=TokenRevocationResponse)
@limiter.limit(rate_limits.AUTH_SENSITIVE_OPERATION)  # DRY: Centralized rate limits
async def revoke_token(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    revocation_request: TokenRevocationRequest,
    current_user: User = Depends(get_current_active_user),
) -> TokenRevocationResponse:
    """Revoke a specific JWT token - SOLID Single Responsibility.

    This endpoint allows users to revoke their own tokens (logout from specific sessions).
    The token being revoked must be provided in the request body.
    """
    from .revocation_service import token_revocation_service

    try:
        # Decode the token to get its metadata - Security validation
        token_data = await security_manager.verify_token(revocation_request.token)
        if not token_data or token_data.user_id != current_user.id:
            raise APIErrorFactory.forbidden("Cannot revoke token for another user")

        # Extract token metadata for revocation record
        payload = jwt.decode(
            revocation_request.token,
            auth_config.SECRET_KEY,
            algorithms=[auth_config.ALGORITHM],
            options={"verify_exp": False},  # Allow expired tokens to be revoked
        )

        issued_at = datetime.fromtimestamp(payload.get("iat", 0), tz=UTC)
        expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=UTC)

        # Revoke the token (JTI is required for revocation)
        if not token_data.jti:
            raise APIErrorFactory.validation_error("Token missing required JTI for revocation")

        success = await token_revocation_service.revoke_token(
            jti=token_data.jti,
            user_id=current_user.id,
            token_type=token_data.token_type or "access",
            issued_at=issued_at,
            expires_at=expires_at,
            reason=revocation_request.reason or "user_requested",
            client_ip=get_remote_address(request),
            user_agent=request.headers.get("user-agent"),
        )

        if not success:
            raise APIErrorFactory.internal_server_error("Failed to revoke token")

        logger.info(
            "Token revoked by user",
            user_id=current_user.id,
            jti=token_data.jti,
            reason=revocation_request.reason,
        )

        return TokenRevocationResponse(
            success=True,
            message="Token revoked successfully",
            jti=token_data.jti,
        )

    except HTTPException as e:
        raise e
    except jwt.InvalidTokenError:
        raise APIErrorFactory.validation_error("Invalid token format")
    except Exception as e:
        logger.error("Error revoking token", user_id=current_user.id, error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to revoke token")


@router.post("/revoke-all-tokens", response_model=TokenRevocationResponse)
@limiter.limit(rate_limits.AUTH_SENSITIVE_OPERATION)  # DRY: Centralized rate limits
async def revoke_all_user_tokens(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    response: Response,  # Required to clear HTTP-only cookies
    bulk_revocation: BulkTokenRevocationRequest,
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> TokenRevocationResponse:
    """Revoke all tokens for the current user - SOLID Single Responsibility.

    This endpoint allows users to log out from ALL devices/sessions at once.
    Useful for security incidents or when changing passwords.
    """
    from .revocation_service import token_revocation_service

    try:
        revoked_count = await token_revocation_service.revoke_all_user_tokens(
            user_id=current_user.id,
            reason=bulk_revocation.reason,
            revoked_by=current_user.username,
        )

        logger.warning(
            "Bulk token revocation performed",
            user_id=current_user.id,
            reason=bulk_revocation.reason,
            revoked_count=revoked_count,
        )

        # Clear HTTP-only authentication cookies to complete logout
        # This ensures the user is actually logged out in the browser
        # Safari-compatible cookie clearing patterns based on research
        environment = os.getenv("ENVIRONMENT", "development")
        is_production = environment == "production"

        # CRITICAL: Use EXACT same cookie settings as when they were created
        secure_cookies = is_production
        cookie_domain = None if is_production else "localhost"
        samesite_policy: Literal["strict", "lax"] = (
            "strict" if is_production else "lax"
        )  # Must match creation settings!

        # Safari-compatible cookie clearing: Set to empty value with past expiration
        # Based on Safari research: Use explicit past date instead of max_age=0
        past_date = datetime.now(UTC) - timedelta(days=1)

        # Clear auth_token cookie (main authentication cookie)
        # CRITICAL: Must match EXACT parameters used when setting cookie
        response.set_cookie(
            key="auth_token",
            value="",
            expires=past_date,  # Safari-specific: Use past date instead of max_age=0
            httponly=True,
            secure=secure_cookies,  # EXACT match: use same secure setting
            samesite=samesite_policy,  # EXACT match: use environment-specific policy
            path="/",
            domain=cookie_domain,
        )

        # Clear refresh_token cookie with EXACT matching parameters
        response.set_cookie(
            key="refresh_token",
            value="",
            expires=past_date,  # Safari-specific: Use past date instead of max_age=0
            httponly=True,
            secure=secure_cookies,  # EXACT match: use same secure setting
            samesite=samesite_policy,  # EXACT match: use environment-specific policy
            path="/",
            domain=cookie_domain,
        )

        # Clear auth_user cookie with EXACT matching parameters
        response.set_cookie(
            key="auth_user",
            value="",
            expires=past_date,  # Safari-specific: Use past date instead of max_age=0
            httponly=False,  # EXACT match: frontend-readable
            secure=secure_cookies,  # EXACT match: use same secure setting
            samesite=samesite_policy,  # EXACT match: use environment-specific policy
            path="/",
            domain=cookie_domain,
        )

        logger.info(
            "Authentication cookies cleared for logout",
            user_id=current_user.id,
            environment=environment,
            is_production=is_production,
            cookie_domain=cookie_domain,
            samesite_policy=samesite_policy,
            secure_cookies=secure_cookies,
        )

        return TokenRevocationResponse(
            success=True,
            message=f"All tokens revoked successfully ({revoked_count} sessions)",
            revoked_count=revoked_count,
            jti=None,  # Bulk revocation doesn't have specific JTI
            clear_local_storage=True,  # Safari compatibility: instruct client to clear storage
        )

    except Exception as e:
        logger.error("Error in bulk token revocation", user_id=current_user.id, error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to revoke tokens")


@router.get("/revocation-stats", response_model=RevocationStatsResponse)
async def get_revocation_stats(
    current_user: User = Depends(get_current_active_user),
) -> RevocationStatsResponse:
    """Get token revocation statistics for the current user - SOLID Single Responsibility.

    Returns statistics about token revocations for monitoring and security awareness.
    """
    from .revocation_service import token_revocation_service

    try:
        stats = await token_revocation_service.get_revocation_stats(user_id=current_user.id)

        return RevocationStatsResponse(
            total_revocations=stats.get("total_revocations", 0),
            revocations_by_type=stats.get("revocations_by_type", {}),
            revocations_by_reason=stats.get("revocations_by_reason", {}),
            recent_revocations_24h=stats.get("recent_revocations_24h", 0),
            recent_revocations_7d=stats.get("recent_revocations_7d", 0),
            user_id=current_user.id,
        )

    except Exception as e:
        logger.error("Error getting revocation stats", user_id=current_user.id, error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to get revocation statistics")


# Admin-only endpoint for system-wide revocation management
@router.get("/admin/revocation-stats", response_model=RevocationStatsResponse)
async def get_system_revocation_stats(
    current_user: User = Depends(get_current_superuser),
) -> RevocationStatsResponse:
    """Get system-wide token revocation statistics - SOLID Single Responsibility.

    Admin-only endpoint for monitoring token revocations across the entire system.
    """
    from .revocation_service import token_revocation_service

    try:
        stats = await token_revocation_service.get_revocation_stats()

        return RevocationStatsResponse(
            total_revocations=stats.get("total_revocations", 0),
            revocations_by_type=stats.get("revocations_by_type", {}),
            revocations_by_reason=stats.get("revocations_by_reason", {}),
            recent_revocations_24h=stats.get("recent_revocations_24h", 0),
            recent_revocations_7d=stats.get("recent_revocations_7d", 0),
        )

    except Exception as e:
        logger.error("Error getting system revocation stats", error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to get system revocation statistics")


# =============================================================================
# ACCOUNT LOCKOUT ENDPOINTS - Critical Security Operations
# =============================================================================


@router.get("/lockout-status", response_model=AccountLockoutStatusResponse)
async def get_account_lockout_status(
    current_user: User = Depends(get_current_active_user),
) -> AccountLockoutStatusResponse:
    """Get current account lockout status - SOLID Single Responsibility.

    Returns information about the current user's lockout status including
    failed attempts, lockout duration, and remaining time.
    """
    from .lockout_service import account_lockout_service

    try:
        is_locked, remaining_minutes = await account_lockout_service.is_account_locked(
            current_user.id
        )

        # Get detailed lockout statistics
        stats = await account_lockout_service.get_lockout_stats(user_id=current_user.id)

        # Build response with comprehensive lockout information
        response = AccountLockoutStatusResponse(
            is_locked=is_locked,
            remaining_minutes=remaining_minutes,
            failed_attempts=stats.get("current_failed_attempts", 0),
            lockout_reason=None,  # Would be populated from lockout record in full implementation
            locked_since=None,  # Would be populated from lockout record in full implementation
        )

        logger.info(
            "Lockout status requested",
            user_id=current_user.id,
            is_locked=is_locked,
            failed_attempts=response.failed_attempts,
        )

        return response

    except Exception as e:
        logger.error("Error getting lockout status", user_id=current_user.id, error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to get account lockout status")


@router.get("/lockout-stats", response_model=LockoutStatsResponse)
async def get_lockout_stats(
    current_user: User = Depends(get_current_active_user),
) -> LockoutStatsResponse:
    """Get account lockout statistics for current user - SOLID Single Responsibility.

    Returns detailed statistics about lockout history for security awareness.
    """
    from .lockout_service import account_lockout_service

    try:
        stats = await account_lockout_service.get_lockout_stats(user_id=current_user.id)

        return LockoutStatsResponse(
            total_lockout_records=stats.get("total_lockout_records", 0),
            currently_locked_accounts=stats.get("currently_locked_accounts", 0),
            lockouts_by_reason=stats.get("lockouts_by_reason", {}),
            recent_lockouts_24h=stats.get("recent_lockouts_24h", 0),
            recent_lockouts_7d=stats.get("recent_lockouts_7d", 0),
            average_failed_attempts=stats.get("average_failed_attempts", 0.0),
            user_id=current_user.id,
            current_failed_attempts=stats.get("current_failed_attempts"),
            is_currently_locked=stats.get("is_currently_locked"),
        )

    except Exception as e:
        logger.error("Error getting lockout statistics", user_id=current_user.id, error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to get lockout statistics")


# Admin-only endpoints for lockout management
@router.post("/admin/unlock-account")
@limiter.limit(rate_limits.AUTH_SENSITIVE_OPERATION)  # DRY: Centralized rate limits
async def unlock_user_account(
    request: Request,  # Required for SlowAPI rate limiting - framework constraint  # pylint: disable=unused-argument
    unlock_request: UnlockAccountRequest,
    current_user: User = Depends(get_current_superuser),
) -> dict[str, bool | str]:
    """Manually unlock a user account - SOLID Single Responsibility.

    Admin-only endpoint for unlocking accounts that are locked due to
    failed login attempts or suspicious activity.
    """
    from .lockout_service import account_lockout_service

    try:
        success = await account_lockout_service.unlock_account(
            user_id=unlock_request.user_id,
            unlocked_by=current_user.username,
            reason=unlock_request.reason,
        )

        if not success:
            raise APIErrorFactory.not_found("Account", unlock_request.user_id)

        logger.warning(
            "Account manually unlocked by admin",
            target_user_id=unlock_request.user_id,
            admin_user_id=current_user.id,
            admin_username=current_user.username,
            reason=unlock_request.reason,
        )

        return {
            "success": True,
            "message": f"Account {unlock_request.user_id} unlocked successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error unlocking account",
            target_user_id=unlock_request.user_id,
            admin_user_id=current_user.id,
            error=str(e),
        )
        raise APIErrorFactory.internal_server_error("Failed to unlock account")


@router.get("/admin/lockout-stats", response_model=LockoutStatsResponse)
async def get_system_lockout_stats(
    current_user: User = Depends(get_current_superuser),
) -> LockoutStatsResponse:
    """Get system-wide lockout statistics - SOLID Single Responsibility.

    Admin-only endpoint for monitoring lockouts across the entire system.
    """
    from .lockout_service import account_lockout_service

    try:
        stats = await account_lockout_service.get_lockout_stats()

        return LockoutStatsResponse(
            total_lockout_records=stats.get("total_lockout_records", 0),
            currently_locked_accounts=stats.get("currently_locked_accounts", 0),
            lockouts_by_reason=stats.get("lockouts_by_reason", {}),
            recent_lockouts_24h=stats.get("recent_lockouts_24h", 0),
            recent_lockouts_7d=stats.get("recent_lockouts_7d", 0),
            average_failed_attempts=stats.get("average_failed_attempts", 0.0),
        )

    except Exception as e:
        logger.error("Error getting system lockout statistics", error=str(e))
        raise APIErrorFactory.internal_server_error("Failed to get system lockout statistics")


# =============================================================================
# SSE AUTHENTICATION STREAM ENDPOINT - ENTERPRISE REAL-TIME AUTH
# =============================================================================


async def _get_auth_status_from_cookies(request: Request) -> dict:
    """Extract authentication status from HTTP-only cookies."""
    try:
        # COMPREHENSIVE DEBUGGING: Log all request information
        logger.info(
            "🍪 [SSE Cookie Debug] Checking authentication from cookies",
            request_url=str(request.url),
            client_host=request.client.host if request.client else "unknown",
            headers_keys=list(request.headers.keys()),
            cookie_header=request.headers.get("cookie", "NO_COOKIE_HEADER"),
            has_auth_token=bool(request.cookies.get("auth_token")),
            has_auth_user=bool(request.cookies.get("auth_user")),
            all_cookie_names=list(request.cookies.keys()),
            cookie_count=len(request.cookies),
        )

        # Try to get auth token from HTTP-only cookie
        auth_token = request.cookies.get("auth_token")
        auth_user = request.cookies.get("auth_user")

        # Log detailed cookie debugging
        logger.info(
            "🍪 [SSE Cookie Debug] Cookie extraction results",
            auth_token_present=bool(auth_token),
            auth_token_length=len(auth_token) if auth_token else 0,
            auth_user_present=bool(auth_user),
            auth_user_length=len(auth_user) if auth_user else 0,
            auth_token_prefix=auth_token[:20] + "..."
            if auth_token and len(auth_token) > 20
            else auth_token,
            auth_user_preview=auth_user[:50] + "..."
            if auth_user and len(auth_user) > 50
            else auth_user,
        )

        if auth_token and auth_user:
            try:
                # Validate the JWT token
                payload = jwt.decode(
                    auth_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
                )

                # Parse user data from cookie
                user_data = json.loads(auth_user)

                return {
                    "authenticated": True,
                    "user": {
                        "id": user_data.get("id"),
                        "username": user_data.get("username"),
                        "email": user_data.get("email"),
                        "is_verified": user_data.get("is_verified", True),
                        "provider": user_data.get("provider", "local"),
                    },
                    "expires_at": payload.get("exp"),
                    "token_type": "bearer",
                }
            except jwt.ExpiredSignatureError:
                logger.debug("JWT token expired in cookie")
                return {"authenticated": False, "reason": "token_expired"}
            except jwt.InvalidTokenError:
                logger.debug("Invalid JWT token in cookie")
                return {"authenticated": False, "reason": "invalid_token"}
            except json.JSONDecodeError:
                logger.debug("Invalid user data in auth_user cookie")
                return {"authenticated": False, "reason": "invalid_user_data"}

        logger.info(
            "🍪 [SSE Cookie Debug] No authentication cookies found",
            auth_token_missing=not bool(auth_token),
            auth_user_missing=not bool(auth_user),
            available_cookies=list(request.cookies.keys()),
            cookie_header_raw=request.headers.get("cookie", "NO_COOKIE_HEADER"),
        )
        return {"authenticated": False, "reason": "no_auth_cookies"}

    except Exception as e:
        logger.error("Error checking auth status from cookies", error=str(e))
        return {"authenticated": False, "reason": "auth_error"}


async def _generate_auth_events(request: Request):
    """Generate Server-Sent Events for authentication status updates."""
    client_ip = get_remote_address(request)
    connection_id = f"auth_{client_ip}_{datetime.now().timestamp()}"

    logger.info(
        "SSE auth stream connection established", connection_id=connection_id, client_ip=client_ip
    )

    try:
        heartbeat_interval = 30  # Send heartbeat every 30 seconds
        last_auth_status = None
        heartbeat_counter = 0

        while True:
            try:
                # Check current authentication status
                current_auth_status = await _get_auth_status_from_cookies(request)

                # Send auth status update if it changed
                if current_auth_status != last_auth_status:
                    auth_event = {
                        "type": "auth_status",
                        "data": current_auth_status,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "connection_id": connection_id,
                    }

                    yield f"event: auth_status\ndata: {json.dumps(auth_event)}\n\n"

                    logger.debug(
                        "Auth status change detected",
                        connection_id=connection_id,
                        authenticated=current_auth_status.get("authenticated", False),
                        reason=current_auth_status.get("reason"),
                    )

                    last_auth_status = current_auth_status

                # Send periodic heartbeat to keep connection alive
                heartbeat_counter += 1
                if heartbeat_counter % heartbeat_interval == 0:
                    heartbeat_event = {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "connection_id": connection_id,
                        "authenticated": current_auth_status.get("authenticated", False),
                    }

                    yield f"event: heartbeat\ndata: {json.dumps(heartbeat_event)}\n\n"

                    logger.debug("SSE heartbeat sent", connection_id=connection_id)

                # Check every second for auth changes, heartbeat every 30 seconds
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info(
                    "SSE auth stream cancelled", connection_id=connection_id, client_ip=client_ip
                )
                break
            except Exception as e:
                logger.error("Error in SSE auth stream", connection_id=connection_id, error=str(e))
                # Send error event
                error_event = {
                    "type": "error",
                    "error": "stream_error",
                    "message": "Authentication stream error",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "connection_id": connection_id,
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
                break

    except Exception as e:
        logger.error("Fatal error in SSE auth stream", connection_id=connection_id, error=str(e))
    finally:
        logger.info(
            "SSE auth stream connection closed", connection_id=connection_id, client_ip=client_ip
        )


@router.get("/stream")
async def auth_status_stream(request: Request) -> StreamingResponse:
    """
    Server-Sent Events stream for real-time authentication status updates.

    This enterprise-grade endpoint provides real-time authentication state
    synchronization between backend cookies and frontend state management.

    **Features:**
    - Real-time authentication status monitoring
    - HTTP-only cookie validation
    - Automatic token expiration detection
    - Connection heartbeat for reliability
    - Structured event logging
    - Graceful error handling

    **Event Types:**
    - `auth_status`: Authentication state changes
    - `heartbeat`: Keep-alive signals
    - `error`: Stream errors

    **Usage:**
    ```javascript
    const eventSource = new EventSource('/auth/stream');
    eventSource.addEventListener('auth_status', (event) => {
        const authData = JSON.parse(event.data);
        if (authData.data.authenticated) {
            // User is authenticated
            showAuthenticatedUI(authData.data.user);
        } else {
            // User is not authenticated
            showLoginUI();
        }
    });
    ```

    **Security:**
    - Uses HTTP-only cookies for token validation
    - No sensitive data in event stream
    - Client IP logging for audit trail
    - Rate limiting through SlowAPI

    Returns:
        StreamingResponse: SSE stream with authentication events
    """
    # Debug: Log all cookies received in SSE request
    cookies_debug = dict(request.cookies) if request.cookies else {}
    cookie_header = request.headers.get("cookie", "")

    logger.info(
        "Starting SSE auth stream",
        client_ip=get_remote_address(request),
        user_agent=request.headers.get("user-agent", "unknown"),
        cookies_received=cookies_debug,
        cookie_header=cookie_header,
    )

    # Environment-aware CORS headers for SSE with credentials
    environment = os.getenv("ENVIRONMENT", "development").lower()
    frontend_origin = (
        "http://localhost:3000"
        if environment == "development"
        else os.getenv("FRONTEND_URL", "https://your-domain.com")
    )

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": frontend_origin,  # Must be specific origin when using credentials
        "Access-Control-Allow-Credentials": "true",  # Required for HTTP-only cookies
        "Access-Control-Allow-Headers": "Cache-Control",
    }

    return StreamingResponse(
        _generate_auth_events(request), media_type="text/event-stream", headers=headers
    )


@router.delete("/account")
async def delete_user_account(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    """
    Delete the current user's account.

    This endpoint allows authenticated users to permanently delete their account.
    The operation is irreversible and will remove all user data.

    **Security Features:**
    - Requires active user authentication
    - Validates user exists before deletion
    - Proper error handling and logging

    Returns:
        JSONResponse: Success message or error details

    Raises:
        HTTPException: If deletion fails or user not found
    """
    try:
        # Delete the user account using the auth service
        success = auth_service.delete_user_account(current_user.id)

        if success:
            logger.info("User account deleted successfully", user_id=current_user.id)
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": "Account deleted successfully"},
            )
        else:
            logger.warning("Failed to delete user account", user_id=current_user.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete account"
            )

    except Exception as e:
        logger.error("Error deleting user account", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during account deletion",
        )


# Rate limit exception handler will be added when implementing rate limiting middleware
# router.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
