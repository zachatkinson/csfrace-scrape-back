"""Authentication router with comprehensive endpoints following FastAPI patterns."""

from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticationCredential,
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    RegistrationCredential,
)

from src.core.decorators import auth_error_handler, oauth_error_handler
from src.core.exceptions import AccountMergeRequiredError
from src.core.logging_hierarchy import get_auth_logger

from ..api.errors import APIErrorFactory
from ..api.utils import maybe_none
from ..config.rate_limits import rate_limits
from ..constants import API_DEFAULT_LIMIT
from ..database.service import DatabaseService
from .dependencies import (
    get_auth_service,
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
    AccountMergeRequest,
    AccountMergeResult,
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
from .services import CookieService, OAuthValidationService, SSEAuthService, TokenService
from .webauthn_service import PasskeyManager, WebAuthnService

# from .config import auth_config  # type: ignore[import-not-found]


# Temporary auth config until config.py is available
class AuthConfig:
    SECRET_KEY = "your-secret-key-here"  # noqa: S105
    ALGORITHM = "HS256"


auth_config = AuthConfig()

logger = get_auth_logger()

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
                    "Account locked due to too many failed attempts. Try again later.",
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

    # Create JWT tokens using TokenService - DRY principle
    return TokenService.create_tokens_for_user(
        user=authenticated_user, is_new_user=False, scopes=form_data.scopes
    )


@router.post("/register", response_model=User)
@limiter.limit(rate_limits.AUTH_REGISTER)  # DRY: Centralized rate limits
def register_user(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
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
    user: User | None = maybe_none(auth_service.create_user, user_create)
    if not user:
        raise APIErrorFactory.internal_server_error("Failed to create user")

    return user


@router.post("/refresh", response_model=Token)
@auth_error_handler("refresh access token")
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

    # Create new access token using TokenService - DRY principle
    return TokenService.create_access_token_only(user=user)


@router.post("/logout")
@auth_error_handler("logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> dict[str, str]:
    """
    Logout user by clearing HTTP-only authentication cookies.

    This endpoint clears the auth_token, refresh_token, and auth_user cookies,
    effectively logging out the user. Works with httpOnly cookies for security.

    Returns:
        dict: Success message confirming logout
    """
    # Initialize cookie service
    cookie_service = CookieService()

    # Clear all authentication cookies
    cookie_service.clear_auth_cookies(response)

    logger.info(
        "User logged out successfully", user_id=current_user.id, username=current_user.username
    )

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_active_user_from_cookie)) -> User:
    """Get current user information from HTTP-only cookie (Astro best practices)."""
    return current_user


@router.put("/me", response_model=User)
def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user_from_cookie),
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

    updated_user: User | None = maybe_none(auth_service.update_user, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return updated_user


@router.post("/change-password")
def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user_from_cookie),
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
    if not auth_service.change_password(
        current_user.id, password_change.current_password, password_change.new_password
    ):
        raise APIErrorFactory.internal_server_error("Failed to change password")

    return {"message": "Password changed successfully"}


@router.post("/password-reset")
@limiter.limit(rate_limits.AUTH_PASSWORD_RESET)
def request_password_reset(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
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
    return auth_service.list_users(skip=skip, limit=limit)


@router.get("/users/{user_id}", response_model=User, dependencies=[Depends(get_current_superuser)])
def get_user(
    user_id: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Get user by ID (admin only)."""
    user: User | None = maybe_none(auth_service.get_user_by_id, user_id)
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


# OAuth2 SSO Endpoints
@router.post("/oauth/login", response_model=SSOLoginResponse)
@limiter.limit(rate_limits.AUTH_OAUTH)
def initiate_oauth_login(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    sso_request: SSOLoginRequest,
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> SSOLoginResponse:
    """Initiate OAuth2 SSO login flow - Following FastAPI official patterns."""
    return oauth_service.initiate_oauth_login(
        provider=sso_request.provider, redirect_uri=sso_request.redirect_uri
    )


@router.get("/oauth/providers", response_model=list[str])
def list_oauth_providers() -> list[str]:
    """List available OAuth2 providers - Simple endpoint per REST principles."""
    return [get_oauth_provider_value(provider) for provider in OAuthProvider]


@router.get("/oauth/connections", response_model=list[OAuthConnectionResponse])
@oauth_error_handler("OAuth connections retrieval")
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
    logger.info("Getting OAuth connections", user_id=current_user.id)

    connections = oauth_service.get_oauth_connections(current_user.id)

    logger.info(
        "OAuth connections retrieved successfully",
        user_id=current_user.id,
        total_providers=len(connections),
        connected_count=len([c for c in connections if c.connected]),
    )

    return connections


@router.get("/oauth/{provider}")
@limiter.limit(rate_limits.AUTH_OAUTH)
@oauth_error_handler("OAuth login initiation")
def initiate_oauth_login_redirect(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    provider: OAuthProvider,
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """Initiate OAuth2 login flow with direct redirect - Browser convenience.

    This GET endpoint provides a simpler alternative to the POST /oauth/login endpoint,
    allowing direct browser navigation (e.g., window.location.href = '/auth/oauth/github').

    Uses the same redirect_uri configuration as the main OAuth flow (OAUTH_REDIRECT_URI_BASE).

    Args:
        provider: OAuth provider (google, github, microsoft, facebook, apple)
        oauth_service: OAuth service dependency

    Returns:
        RedirectResponse: Redirects browser to OAuth provider's authorization page

    Example:
        Navigate to: https://localhost/auth/oauth/github
        Redirects to: https://github.com/login/oauth/authorize?client_id=...
    """
    logger.info(
        "Initiating OAuth login via redirect",
        provider=get_oauth_provider_value(provider),
    )

    # Get authorization URL from OAuth service (uses default redirect_uri from config)
    sso_response = oauth_service.initiate_oauth_login(provider=provider, redirect_uri=None)

    # Redirect user to OAuth provider's authorization page
    return RedirectResponse(url=sso_response.authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/oauth/{provider}/callback", response_model=None)
@limiter.limit(rate_limits.AUTH_OAUTH)
@oauth_error_handler("OAuth callback processing")
async def handle_oauth_callback(
    request: Request,  # Required for SlowAPI rate limiting and query params
    response: Response,  # Not used but kept for compatibility
    provider: OAuthProvider,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    oauth_service: OAuthService = Depends(get_oauth_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> RedirectResponse | JSONResponse:
    """Handle OAuth2 callback and return JWT tokens following OAuth2 Authorization Code Flow.

    This endpoint implements the OAuth2 Authorization Code Flow callback handling
    according to RFC 6749 and FastAPI security best practices.

    Supports two scenarios:
    1. User signing in/up with OAuth (no existing session)
    2. Logged-in user connecting a new OAuth provider (existing session)
    """
    # Check if user is already logged in (linking scenario)
    existing_user_id: str | None = None
    try:
        # Try to get current user from cookie without raising error
        auth_token = request.cookies.get("auth_token")
        if auth_token:
            payload = jwt.decode(
                auth_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
            )
            username: str | None = payload.get("sub")
            if username:
                existing_user = auth_service.get_user_by_username(username)
                if existing_user:
                    existing_user_id = existing_user.id
                    logger.info(
                        "User already logged in, will link OAuth account",
                        user_id=existing_user_id,
                        provider=get_oauth_provider_value(provider),
                    )
    except Exception:
        # User not logged in, proceed with normal OAuth flow
        pass

    # Create OAuthCallback object from query parameters
    oauth_callback = OAuthCallback(
        code=code or "",
        state=state or "",
        provider=provider,
        error=error,
        error_description=error_description,
    )

    # Validate OAuth callback parameters using service
    OAuthValidationService.validate_callback_parameters(provider, oauth_callback)

    # Process OAuth callback using injected services
    logger.info(
        "Processing OAuth callback",
        provider=get_oauth_provider_value(provider),
        code_present=bool(oauth_callback.code),
        state_present=bool(oauth_callback.state),
        linking_to_existing_user=existing_user_id is not None,
    )

    # Exchange authorization code for access token and get user
    # OAuth service will extract the original redirect URI from JWT state and use it
    # for token exchange (as required by OAuth2 spec)
    try:
        user, is_new_user = await oauth_service.handle_oauth_callback(
            provider=provider,
            code=oauth_callback.code,
            state=oauth_callback.state,
            redirect_uri="",  # Not used - OAuth service extracts from JWT state
            existing_user_id=existing_user_id,  # Pass existing user ID for linking
        )
    except AccountMergeRequiredError as e:
        # Account merge is required - return merge detection as 409 Conflict
        logger.info(
            "Account merge required",
            merge_detection=e.merge_detection.model_dump(),
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=e.merge_detection.model_dump(),
        )

    # Log successful OAuth authentication
    logger.info(
        "OAuth authentication successful",
        provider=get_oauth_provider_value(provider),
        user_id=user.id,
        email=user.email,
        is_new_user=is_new_user,
    )

    # Generate JWT tokens using TokenService
    token = TokenService.create_tokens_for_user(user, is_new_user)

    # Create JSON response with tokens and set cookies
    response = JSONResponse(
        content={
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "refresh_token": token.refresh_token,
            "is_new_user": is_new_user,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
            },
        }
    )

    # Set secure HTTP-only cookies on the response
    cookie_service = CookieService()
    cookie_service.set_auth_cookies(response, token, request)

    logger.info(
        "OAuth callback completed successfully - returning tokens with cookies",
        user_id=user.id,
        is_new_user=is_new_user,
    )

    return response


@router.post("/oauth/merge", response_model=AccountMergeResult)
@limiter.limit(rate_limits.AUTH_OAUTH)
@auth_error_handler("account merge execution")
async def execute_account_merge(
    request: Request,  # Required for SlowAPI rate limiting
    merge_request: AccountMergeRequest,
    current_user: User = Depends(get_current_active_user_from_cookie),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> AccountMergeResult:
    """Execute account merge after user confirmation.

    This endpoint handles the actual merging of two user accounts after the user
    has confirmed the merge operation. It validates the merge token, checks permissions,
    and executes the merge using the AccountMergeService.

    Args:
        request: FastAPI request object (for rate limiting)
        merge_request: Contains merge_token and confirm_merge flag
        current_user: Currently logged-in user (must be the target user)
        oauth_service: Injected OAuth service with merge service

    Returns:
        AccountMergeResult with merge details

    Raises:
        HTTPException 400: If merge token is invalid or user is not authorized
        HTTPException 422: If validation fails
    """
    logger.info(
        "Account merge requested",
        current_user_id=current_user.id,
        confirm_merge=merge_request.confirm_merge,
    )

    # Validate merge token and execute merge using AccountMergeService
    result = oauth_service.merge_service.merge_accounts(
        merge_request=merge_request,
        initiated_by_user_id=current_user.id,
    )

    logger.info(
        "Account merge completed successfully",
        result=result.model_dump(),
    )

    return result


@router.get("/providers")
def list_oauth_providers_simple(request: Request) -> dict[str, list[dict[str, str]]]:
    """List available OAuth2 providers - API contract endpoint."""
    providers = []
    for provider in OAuthProvider:
        provider_name = get_oauth_provider_value(provider)
        providers.append(
            {
                "name": provider_name,
                "display_name": provider_name.capitalize(),
                "authorization_url": str(
                    request.url_for("get_oauth_authorization_url", provider=provider_name)
                ),
            }
        )
    return {"providers": providers}


@router.get("/{provider}/authorize")
@limiter.limit(rate_limits.AUTH_OAUTH)
def get_oauth_authorization_url(
    request: Request,  # Required for SlowAPI rate limiting
    provider: OAuthProvider,
    redirect_uri: str | None = None,
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> SSOLoginResponse:
    """Get OAuth authorization URL for a specific provider - API contract endpoint."""
    return oauth_service.initiate_oauth_login(
        provider=provider, redirect_uri=redirect_uri or "http://localhost:8000/auth/oauth/callback"
    )


@router.delete("/oauth/connections/{provider}", response_model=dict[str, bool | str])
@oauth_error_handler("OAuth account disconnection")
async def disconnect_oauth_provider(
    provider: OAuthProvider,
    current_user: User = Depends(get_current_active_user_from_cookie),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> dict[str, bool | str]:
    """Disconnect OAuth provider from current user account - Single Responsibility Principle.

    Removes the linked OAuth account for the specified provider with comprehensive
    safety checks to prevent user lockout.

    **Safety Features:**
    - Cannot disconnect if it's the only authentication method (no password set)
    - Cannot disconnect if it's the only OAuth account and no password exists
    - Validates account is actually linked before attempting removal

    **Security:**
    - HTTP-only cookie authentication required
    - User can only disconnect their own accounts
    - Comprehensive audit logging

    Args:
        provider: OAuth provider to disconnect (e.g., github, google)
        current_user: Authenticated user from cookie
        oauth_service: OAuth service dependency

    Returns:
        dict with success status and confirmation message

    Raises:
        HTTPException 404: Account not connected
        HTTPException 400: Disconnection would lock user out
    """
    logger.info(
        "User requesting OAuth disconnect",
        user_id=current_user.id,
        provider=get_oauth_provider_value(provider),
    )

    try:
        success = await oauth_service.disconnect_oauth_account(current_user.id, provider)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{provider.value.capitalize()} account not connected",
            )

        logger.info(
            "OAuth account disconnected via API",
            user_id=current_user.id,
            provider=get_oauth_provider_value(provider),
        )

        return {
            "success": True,
            "message": f"{provider.value.capitalize()} account disconnected successfully",
        }
    except ValueError as e:
        # Safety check failed (would lock user out)
        logger.warning(
            "OAuth disconnect prevented by safety check",
            user_id=current_user.id,
            provider=get_oauth_provider_value(provider),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# WebAuthn/Passkeys Endpoints - Passwordless Authentication
@router.post("/passkeys/register/begin", response_model=PasskeyRegistrationResponse)
@limiter.limit(rate_limits.AUTH_PASSKEY)
@auth_error_handler("passkey registration initiation")
async def begin_passkey_registration(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    passkey_request: PasskeyRegistrationRequest,
    current_user: User = Depends(get_current_active_user_from_cookie),
    passkey_manager: PasskeyManager = Depends(get_passkey_manager),
) -> PasskeyRegistrationResponse:
    """Begin WebAuthn/Passkeys registration - Following FIDO2 standards."""
    registration_data = await passkey_manager.start_passkey_registration(
        user=current_user, device_name=passkey_request.device_name or "Default Device"
    )

    return PasskeyRegistrationResponse(
        public_key=registration_data["publicKey"],
        challenge_key=registration_data["challengeKey"],
        device_name=registration_data["deviceName"],
    )


@router.post("/passkeys/register/complete", response_model=dict[str, str])
@limiter.limit(rate_limits.AUTH_PASSKEY)
@auth_error_handler("passkey registration completion")
async def complete_passkey_registration(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    credential_request: PasskeyCredentialRequest,
    current_user: User = Depends(get_current_active_user_from_cookie),
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> dict[str, str]:
    """Complete WebAuthn/Passkeys registration following FIDO2 standards."""
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

    # Create AuthenticatorAttestationResponse from frontend data
    # Frontend sends camelCase (clientDataJSON, attestationObject)
    # Backend needs snake_case bytes (client_data_json, attestation_object)
    attestation_response = AuthenticatorAttestationResponse(
        client_data_json=base64url_to_bytes(credential_response["response"]["clientDataJSON"]),
        attestation_object=base64url_to_bytes(credential_response["response"]["attestationObject"]),
    )

    # Create RegistrationCredential object
    registration_credential = RegistrationCredential(
        id=credential_response["id"],
        raw_id=base64url_to_bytes(credential_response["rawId"]),
        response=attestation_response,
        type=credential_response["type"],
    )

    # Verify and store the credential
    webauthn_credential = await webauthn_service.verify_registration_response(
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


@router.post("/passkeys/authenticate/begin", response_model=PasskeyAuthenticationResponse)
@limiter.limit(rate_limits.AUTH_PASSKEY)
@auth_error_handler("passkey authentication initiation")
async def begin_passkey_authentication(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    auth_request: PasskeyAuthenticationRequest,
    auth_service: AuthService = Depends(get_auth_service),
    passkey_manager: PasskeyManager = Depends(get_passkey_manager),
) -> PasskeyAuthenticationResponse:
    """Begin WebAuthn/Passkeys authentication - Supports usernameless login."""
    # Get user if username provided, otherwise None for usernameless auth
    user = None
    if auth_request.username:
        user = maybe_none(auth_service.get_user_by_username, auth_request.username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Start authentication (works for both username and usernameless flows)
    authentication_data = await passkey_manager.start_passkey_authentication(user)

    return PasskeyAuthenticationResponse(
        public_key=authentication_data["publicKey"],
        challenge_key=authentication_data["challengeKey"],
    )


@router.post("/passkeys/authenticate/complete", response_model=Token)
@limiter.limit(rate_limits.AUTH_PASSKEY)
@auth_error_handler("passkey authentication completion")
async def complete_passkey_authentication(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    credential_request: PasskeyCredentialRequest,
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> JSONResponse:
    """Complete WebAuthn/Passkeys authentication following FIDO2 standards and return JWT token."""
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

    # Create AuthenticatorAssertionResponse from frontend data
    # Frontend sends camelCase (clientDataJSON, authenticatorData, signature, userHandle)
    # Backend needs snake_case bytes (client_data_json, authenticator_data, signature, user_handle)
    assertion_response = AuthenticatorAssertionResponse(
        client_data_json=base64url_to_bytes(credential_response["response"]["clientDataJSON"]),
        authenticator_data=base64url_to_bytes(credential_response["response"]["authenticatorData"]),
        signature=base64url_to_bytes(credential_response["response"]["signature"]),
        user_handle=(
            base64url_to_bytes(credential_response["response"]["userHandle"])
            if credential_response["response"].get("userHandle")
            else None
        ),
    )

    # Create AuthenticationCredential object
    authentication_credential = AuthenticationCredential(
        id=credential_response["id"],
        raw_id=base64url_to_bytes(credential_response["rawId"]),
        response=assertion_response,
        type=credential_response["type"],
    )

    # Verify authentication and get user
    user, webauthn_credential = await webauthn_service.verify_authentication_response(
        credential=authentication_credential,
        challenge_key=credential_request.challenge_key,
    )

    logger.info(
        "Passkey authentication completed successfully",
        user_id=user.id,
        credential_id=webauthn_credential.credential_id,
        device_name=webauthn_credential.metadata.device_name,
    )

    # Generate JWT tokens using TokenService
    token = TokenService.create_tokens_for_user(user, is_new_user=False, scopes=[])

    # Create JSON response and set cookies
    response = JSONResponse(
        content={
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "refresh_token": token.refresh_token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
            },
        }
    )

    # Set secure HTTP-only cookies
    cookie_service = CookieService()
    cookie_service.set_auth_cookies(response, token, request)

    return response


@router.get("/passkeys/summary", response_model=PasskeySummary)
@auth_error_handler("passkey summary retrieval")
def get_passkey_summary(
    current_user: User = Depends(get_current_active_user_from_cookie),
    passkey_manager: PasskeyManager = Depends(get_passkey_manager),
) -> PasskeySummary:
    """Get user's passkey summary for dashboard - User management."""
    summary_data = passkey_manager.get_passkey_summary(current_user)

    return PasskeySummary(
        total_passkeys=summary_data["total_passkeys"],
        active_passkeys=summary_data["active_passkeys"],
        last_used=summary_data["last_used"],
        devices=summary_data["devices"],
    )


@router.delete("/passkeys/{credential_id}")
@auth_error_handler("passkey revocation")
def revoke_passkey(
    credential_id: str,
    current_user: User = Depends(get_current_active_user_from_cookie),
    webauthn_service: WebAuthnService = Depends(get_webauthn_service),
) -> dict[str, bool | str]:
    """Revoke a WebAuthn/Passkey credential - Security operation."""
    success = webauthn_service.revoke_credential(current_user, credential_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passkey not found or already revoked",
        )

    return {"success": True, "message": "Passkey revoked successfully"}


# =============================================================================
# TOKEN REVOCATION ENDPOINTS - Critical Security Operations
# =============================================================================


@router.post("/revoke-token", response_model=TokenRevocationResponse)
@limiter.limit(rate_limits.AUTH_SENSITIVE_OPERATION)  # DRY: Centralized rate limits
@auth_error_handler("token revocation")
async def revoke_token(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    revocation_request: TokenRevocationRequest,
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> TokenRevocationResponse:
    """Revoke a specific JWT token - SOLID Single Responsibility.

    This endpoint allows users to revoke their own tokens (logout from specific sessions).
    The token being revoked must be provided in the request body.
    """
    from .revocation_service import token_revocation_service

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


@router.post("/revoke-all-tokens", response_model=TokenRevocationResponse)
@limiter.limit(rate_limits.AUTH_SENSITIVE_OPERATION)  # DRY: Centralized rate limits
@auth_error_handler("bulk token revocation")
async def revoke_all_user_tokens(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    response: Response,  # Required to clear HTTP-only cookies
    bulk_revocation: BulkTokenRevocationRequest,
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> TokenRevocationResponse:
    """Revoke all tokens for the current user - SOLID Single Responsibility.

    This endpoint allows users to log out from ALL devices/sessions at once.
    Useful for security incidents or when changing passwords.
    """
    from .revocation_service import token_revocation_service

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

    # Clear HTTP-only authentication cookies using CookieService
    cookie_service = CookieService()
    cookie_service.clear_auth_cookies(response)

    return TokenRevocationResponse(
        success=True,
        message=f"All tokens revoked successfully ({revoked_count} sessions)",
        revoked_count=revoked_count,
        jti=None,  # Bulk revocation doesn't have specific JTI
        clear_local_storage=True,  # Safari compatibility: instruct client to clear storage
    )


@router.get("/revocation-stats", response_model=RevocationStatsResponse)
@auth_error_handler("revocation stats retrieval")
async def get_revocation_stats(
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> RevocationStatsResponse:
    """Get token revocation statistics for the current user - SOLID Single Responsibility.

    Returns statistics about token revocations for monitoring and security awareness.
    """
    from .revocation_service import token_revocation_service

    stats = await token_revocation_service.get_revocation_stats(user_id=current_user.id)

    return RevocationStatsResponse(
        total_revocations=stats.get("total_revocations", 0),
        revocations_by_type=stats.get("revocations_by_type", {}),
        revocations_by_reason=stats.get("revocations_by_reason", {}),
        recent_revocations_24h=stats.get("recent_revocations_24h", 0),
        recent_revocations_7d=stats.get("recent_revocations_7d", 0),
        user_id=current_user.id,
    )


# Admin-only endpoint for system-wide revocation management
@router.get("/admin/revocation-stats", response_model=RevocationStatsResponse)
@auth_error_handler("admin revocation stats retrieval")
async def get_system_revocation_stats(
    current_user: User = Depends(get_current_superuser),
) -> RevocationStatsResponse:
    """Get system-wide token revocation statistics - SOLID Single Responsibility.

    Admin-only endpoint for monitoring token revocations across the entire system.
    """
    from .revocation_service import token_revocation_service

    stats = await token_revocation_service.get_revocation_stats()

    return RevocationStatsResponse(
        total_revocations=stats.get("total_revocations", 0),
        revocations_by_type=stats.get("revocations_by_type", {}),
        revocations_by_reason=stats.get("revocations_by_reason", {}),
        recent_revocations_24h=stats.get("recent_revocations_24h", 0),
        recent_revocations_7d=stats.get("recent_revocations_7d", 0),
    )


# =============================================================================
# ACCOUNT LOCKOUT ENDPOINTS - Critical Security Operations
# =============================================================================


@router.get("/lockout-status", response_model=AccountLockoutStatusResponse)
@auth_error_handler("lockout status retrieval")
async def get_account_lockout_status(
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> AccountLockoutStatusResponse:
    """Get current account lockout status - SOLID Single Responsibility.

    Returns information about the current user's lockout status including
    failed attempts, lockout duration, and remaining time.
    """
    from .lockout_service import account_lockout_service

    is_locked, remaining_minutes = await account_lockout_service.is_account_locked(current_user.id)

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


@router.get("/lockout-stats", response_model=LockoutStatsResponse)
@auth_error_handler("lockout stats retrieval")
async def get_lockout_stats(
    current_user: User = Depends(get_current_active_user_from_cookie),
) -> LockoutStatsResponse:
    """Get account lockout statistics for current user - SOLID Single Responsibility.

    Returns detailed statistics about lockout history for security awareness.
    """
    from .lockout_service import account_lockout_service

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


# Admin-only endpoints for lockout management
@router.post("/admin/unlock-account")
@limiter.limit(rate_limits.AUTH_SENSITIVE_OPERATION)  # DRY: Centralized rate limits
@auth_error_handler("admin account unlock")
async def unlock_user_account(
    request: Request,  # SlowAPI requirement  # pylint: disable=unused-argument
    unlock_request: UnlockAccountRequest,
    current_user: User = Depends(get_current_superuser),
) -> dict[str, bool | str]:
    """Manually unlock a user account - SOLID Single Responsibility.

    Admin-only endpoint for unlocking accounts that are locked due to
    failed login attempts or suspicious activity.
    """
    from .lockout_service import account_lockout_service

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


@router.get("/admin/lockout-stats", response_model=LockoutStatsResponse)
@auth_error_handler("admin lockout stats retrieval")
async def get_system_lockout_stats(
    current_user: User = Depends(get_current_superuser),
) -> LockoutStatsResponse:
    """Get system-wide lockout statistics - SOLID Single Responsibility.

    Admin-only endpoint for monitoring lockouts across the entire system.
    """
    from .lockout_service import account_lockout_service

    stats = await account_lockout_service.get_lockout_stats()

    return LockoutStatsResponse(
        total_lockout_records=stats.get("total_lockout_records", 0),
        currently_locked_accounts=stats.get("currently_locked_accounts", 0),
        lockouts_by_reason=stats.get("lockouts_by_reason", {}),
        recent_lockouts_24h=stats.get("recent_lockouts_24h", 0),
        recent_lockouts_7d=stats.get("recent_lockouts_7d", 0),
        average_failed_attempts=stats.get("average_failed_attempts", 0.0),
    )


# =============================================================================
# SSE AUTHENTICATION STREAM ENDPOINT - ENTERPRISE REAL-TIME AUTH
# =============================================================================


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

    # Use SSE service for auth events
    sse_service = SSEAuthService()
    headers = sse_service.get_sse_headers()

    return StreamingResponse(
        sse_service.generate_auth_events(request), media_type="text/event-stream", headers=headers
    )


@router.post("/oauth/facebook/data-deletion")
@oauth_error_handler("Facebook data deletion callback")
async def facebook_data_deletion_callback(
    request: Request,
    db_service: DatabaseService = Depends(get_database_service),
) -> JSONResponse:
    """
    Handle Facebook's data deletion callback.

    This endpoint is required by Facebook's Platform Policy for apps in Live mode.
    Facebook calls this endpoint when a user requests data deletion through Facebook.

    The signed_request contains:
    - user_id: Facebook user ID
    - algorithm: HMAC-SHA256 (verified)
    - issued_at: Request timestamp

    **Process:**
    1. Verify HMAC signature from Facebook
    2. Extract Facebook user ID from signed_request
    3. Find user in database by provider_id
    4. Delete all user data
    5. Return confirmation URL and code

    **Response Format (required by Facebook):**
    ```json
    {
        "url": "https://localhost:3000/privacy/facebook-data-deletion?code=...",
        "confirmation_code": "fb_12345678_abc123def456..."
    }
    ```

    Args:
        request: FastAPI request containing signed_request form data
        db_service: Database service for user lookup and deletion

    Returns:
        JSONResponse with confirmation URL and code

    Raises:
        HTTPException: If signature invalid or deletion fails

    @see https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
    """
    import secrets

    from src.auth.facebook_data_deletion import facebook_data_deletion_handler
    from src.constants.auth import OAUTH_REDIRECT_URI_BASE

    # Get form data from Facebook request
    form_data = await request.form()
    signed_request = form_data.get("signed_request")

    if not signed_request:
        logger.warning("Facebook data deletion request missing signed_request parameter")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing signed_request parameter",
        )

    # Ensure signed_request is a string (not UploadFile)
    if not isinstance(signed_request, str):
        logger.warning("Facebook data deletion request signed_request must be a string")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signed_request parameter type",
        )

    # Parse and verify signed request
    try:
        data = facebook_data_deletion_handler.parse_signed_request(signed_request)

        if not data:
            logger.error("Invalid signature in Facebook data deletion request")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Extract Facebook user ID
        facebook_user_id = data.get("user_id")
        if not facebook_user_id:
            logger.error("Missing user_id in Facebook signed_request", data=data)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing user_id in request",
            )

        # Find user by Facebook provider account ID
        logger.info(
            "Processing Facebook data deletion request",
            facebook_user_id=facebook_user_id,
        )

        # Query database for user with this Facebook provider account ID
        # Import database models (not Pydantic models)
        from src.database.models.auth import LinkedAccount, User as UserTable

        with db_service.get_session() as session:
            linked_account = (
                session.query(LinkedAccount)
                .filter(
                    LinkedAccount.provider == "facebook",
                    LinkedAccount.provider_account_id == facebook_user_id,
                )
                .first()
            )

            if not linked_account:
                logger.info(
                    "No user found for Facebook data deletion request",
                    facebook_user_id=facebook_user_id,
                )
                # Generate confirmation code (Facebook requirement)
                confirmation_code = f"fb_{facebook_user_id}_{secrets.token_urlsafe(16)}"
                deletion_url = (
                    f"{OAUTH_REDIRECT_URI_BASE}/privacy/"
                    f"facebook-data-deletion?code={confirmation_code}"
                )
                return JSONResponse(
                    content={"url": deletion_url, "confirmation_code": confirmation_code}
                )

            # Get the user from the linked account
            user = session.query(UserTable).filter(UserTable.id == linked_account.user_id).first()

            if user:
                # User found - delete their account
                user_id = user.id
                user_email = user.email

                # Delete the user
                session.delete(user)
                session.commit()

                logger.info(
                    "Deleted user account via Facebook data deletion callback",
                    user_id=user_id,
                    facebook_user_id=facebook_user_id,
                    email=user_email,
                )

                deletion_status = "completed"
            else:
                # User not found - they may have already deleted their account
                logger.info(
                    "User not found for Facebook data deletion",
                    facebook_user_id=facebook_user_id,
                )
                deletion_status = "not_found"

        # Generate confirmation code
        confirmation_code = facebook_data_deletion_handler.generate_confirmation_code(
            facebook_user_id
        )

        # Construct confirmation URL (required by Facebook)
        # User can visit this URL to verify their data deletion
        confirmation_url = (
            f"{OAUTH_REDIRECT_URI_BASE}/privacy/"
            f"facebook-data-deletion?code={confirmation_code}&status={deletion_status}"
        )

        logger.info(
            "Facebook data deletion request processed",
            facebook_user_id=facebook_user_id,
            confirmation_code=confirmation_code,
            status=deletion_status,
        )

        # Return response in format required by Facebook
        return JSONResponse(
            status_code=200,
            content={"url": confirmation_url, "confirmation_code": confirmation_code},
        )

    except ValueError as e:
        logger.error("Invalid signed_request format", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request format: {e}",
        )


@router.delete("/account")
@auth_error_handler("account deletion")
async def delete_user_account(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_cookie),
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
    # Delete the user account using the auth service
    success = await auth_service.delete_user_account(current_user.id)

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


# Rate limit exception handler will be added when implementing rate limiting middleware
# router.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
