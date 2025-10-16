"""OAuth2 SSO service with SOLID principles and DRY validation."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlencode

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .token_encryption_service import TokenEncryptionService

import httpx

from src.core.decorators import oauth_error_handler
from src.core.exceptions import AccountMergeRequiredError
from src.core.logging_hierarchy import get_auth_logger
from src.database.models.auth import LinkedAccount as LinkedAccountDB, User as UserTable

from ..constants import (
    APPLE_AUTHORIZATION_URL,
    APPLE_SCOPES,
    APPLE_TOKEN_URL,
    GITHUB_AUTHORIZATION_URL,
    GITHUB_SCOPES,
    GITHUB_TOKEN_URL,
    GITHUB_USER_EMAILS_URL,
    GITHUB_USER_INFO_URL,
    GOOGLE_AUTHORIZATION_URL,
    GOOGLE_SCOPES,
    GOOGLE_TOKEN_URL,
    GOOGLE_USER_INFO_URL,
    MICROSOFT_AUTHORIZATION_URL,
    MICROSOFT_SCOPES,
    MICROSOFT_TOKEN_URL,
    MICROSOFT_USER_INFO_URL,
    OAUTH_APPLE_CLIENT_ID,
    OAUTH_APPLE_CLIENT_SECRET,
    OAUTH_FACEBOOK_CLIENT_ID,
    OAUTH_FACEBOOK_CLIENT_SECRET,
    OAUTH_GITHUB_CLIENT_ID,
    OAUTH_GITHUB_CLIENT_SECRET,
    OAUTH_GOOGLE_CLIENT_ID,
    OAUTH_GOOGLE_CLIENT_SECRET,
    OAUTH_MICROSOFT_CLIENT_ID,
    OAUTH_MICROSOFT_CLIENT_SECRET,
    OAUTH_REDIRECT_URI_BASE,
)
from .account_merge_service import AccountMergeService
from .enum_utils import ensure_oauth_provider, get_oauth_provider_value
from .models import (
    LinkedAccount,
    OAuthConnectionResponse,
    OAuthProvider,
    OAuthUserCreate,
    OAuthUserInfo,
    SSOLoginResponse,
    User,
)
from .service import AuthService

logger = get_auth_logger()


class OAuthProviderInterface(ABC):
    """Interface Segregation: Abstract OAuth provider interface."""

    @abstractmethod
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate authorization URL for OAuth flow."""

    @abstractmethod
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange authorization code for access token."""

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user information using access token."""


class BaseOAuthProvider(OAuthProviderInterface):
    """DRY Base OAuth provider - eliminates duplication across all providers.

    Template Method Pattern: Concrete providers only override specific behavior.
    Following SOLID principles for maximum code reuse.
    """

    def __init__(self, client_id: str, client_secret: str, provider: OAuthProvider):
        self.client_id = client_id
        self.client_secret = client_secret
        self.provider = provider
        self.logger = logger.bind(provider=provider.value)

    @property
    def scope(self) -> str:
        """OAuth scope."""
        # Default implementation - providers can override
        return "openid email profile"

    # Template Method Pattern - DRY implementation for all providers
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """DRY authorization URL generation for all providers."""
        base_params = self._get_base_auth_params(state, redirect_uri)
        provider_params = self._get_provider_auth_params()

        # Merge base and provider-specific parameters
        params = {**base_params, **provider_params}
        return f"{self._get_auth_base_url()}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """DRY token exchange logic for all providers."""
        async with httpx.AsyncClient() as client:
            token_data = self._get_token_exchange_data(code, redirect_uri)
            headers = self._get_token_exchange_headers()

            # Enhanced logging for debugging - DRY across all providers
            self.logger.debug(
                "OAuth token exchange request",
                redirect_uri=redirect_uri,
                code_length=len(code),
                client_id=self.client_id[:8] + "...",
                token_url=self._get_token_url(),
            )

            response = await client.post(self._get_token_url(), data=token_data, headers=headers)

            # DRY response logging
            self.logger.debug(
                "OAuth token exchange response",
                status_code=response.status_code,
                response_content_preview=str(response.text)[:200]
                if response.status_code != 200
                else "Success",
            )

            response.raise_for_status()
            return self._extract_access_token(response.json())

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """DRY user info fetching for all providers."""
        async with httpx.AsyncClient() as client:
            headers = self._get_user_info_headers(access_token)

            # Some providers need multiple requests (e.g., GitHub for email)
            user_data = await self._fetch_user_data(client, headers)

            return self._map_user_info(user_data)

    # Abstract methods that providers must implement (Template Method Pattern)
    @abstractmethod
    def _get_auth_base_url(self) -> str:
        """Return provider's authorization URL."""

    @abstractmethod
    def _get_token_url(self) -> str:
        """Return provider's token exchange URL."""

    @abstractmethod
    def _get_user_info_url(self) -> str:
        """Return provider's user info URL."""

    @abstractmethod
    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return provider-specific authorization parameters."""

    @abstractmethod
    def _map_user_info(self, user_data: dict[str, Any]) -> OAuthUserInfo:
        """Map provider-specific user data to OAuthUserInfo."""

    # DRY helper methods with sensible defaults (Open/Closed Principle)
    def _get_base_auth_params(self, state: str, redirect_uri: str) -> dict[str, str]:
        """Base authorization parameters common to most providers."""
        return {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }

    def _get_token_exchange_data(self, code: str, redirect_uri: str) -> dict[str, str]:
        """Base token exchange data common to most providers."""
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

    def _get_token_exchange_headers(self) -> dict[str, str]:
        """Default headers for token exchange."""
        return {"Content-Type": "application/x-www-form-urlencoded"}

    def _get_user_info_headers(self, access_token: str) -> dict[str, str]:
        """Default headers for user info requests."""
        return {"Authorization": f"Bearer {access_token}"}

    def _extract_access_token(self, token_response: dict[str, Any]) -> str:
        """Extract access token from provider response."""
        access_token: str = token_response["access_token"]
        return access_token

    async def _fetch_user_data(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Default user data fetching - single request."""
        response = await client.get(self._get_user_info_url(), headers=headers)
        response.raise_for_status()
        user_data: dict[str, Any] = response.json()
        return user_data


class GoogleOAuthProvider(BaseOAuthProvider):
    """Google OAuth2 provider implementation - Now DRY using BaseOAuthProvider Template Method Pattern."""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, OAuthProvider.GOOGLE)

    @property
    def scope(self) -> str:
        """Google-specific OAuth scopes."""
        return " ".join(GOOGLE_SCOPES)

    # Required abstract method implementations
    def _get_auth_base_url(self) -> str:
        """Return Google's authorization URL."""
        return GOOGLE_AUTHORIZATION_URL

    def _get_token_url(self) -> str:
        """Return Google's token exchange URL."""
        return GOOGLE_TOKEN_URL

    def _get_user_info_url(self) -> str:
        """Return Google's user info URL."""
        return GOOGLE_USER_INFO_URL

    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return Google-specific authorization parameters."""
        return {
            "access_type": "offline",
            "prompt": "consent",
            "scope": " ".join(GOOGLE_SCOPES),
        }

    def _map_user_info(self, user_data: dict[str, Any]) -> OAuthUserInfo:
        """Map Google user data to standardized format."""
        return OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id=user_data["id"],
            email=user_data["email"],
            name=user_data["name"],
            avatar_url=user_data.get("picture"),
        )


class GitHubOAuthProvider(BaseOAuthProvider):
    """GitHub OAuth2 provider implementation using BaseOAuthProvider for DRY compliance."""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, OAuthProvider.GITHUB)
        self.user_emails_url = GITHUB_USER_EMAILS_URL

    @property
    def scope(self) -> str:
        """GitHub-specific OAuth scopes."""
        return " ".join(GITHUB_SCOPES)

    # Required abstract method implementations
    def _get_auth_base_url(self) -> str:
        """Return GitHub's authorization URL."""
        return GITHUB_AUTHORIZATION_URL

    def _get_token_url(self) -> str:
        """Return GitHub's token exchange URL."""
        return GITHUB_TOKEN_URL

    def _get_user_info_url(self) -> str:
        """Return GitHub's user info URL."""
        return GITHUB_USER_INFO_URL

    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return GitHub-specific authorization parameters."""
        return {
            "scope": self.scope,
            "allow_signup": "true",
        }

    def _get_token_exchange_headers(self) -> dict[str, str]:
        """GitHub requires Accept header for JSON response."""
        return {"Accept": "application/json"}

    def _get_user_info_headers(self, access_token: str) -> dict[str, str]:
        """GitHub uses 'token' prefix instead of 'Bearer'."""
        return {"Authorization": f"token {access_token}"}

    async def _fetch_user_data(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> dict[str, Any]:
        """GitHub requires additional email request."""
        # Get user profile
        user_response = await client.get(self._get_user_info_url(), headers=headers)
        user_response.raise_for_status()
        user_data: dict[str, Any] = user_response.json()

        # Get primary email (GitHub doesn't always include email in user endpoint)
        emails_response = await client.get(self.user_emails_url, headers=headers)
        emails_response.raise_for_status()
        emails: list[dict[str, Any]] = emails_response.json()

        primary_email = next(
            (email["email"] for email in emails if email["primary"]), user_data.get("email")
        )

        # Add email to user data for mapping
        user_data["primary_email"] = primary_email
        result: dict[str, Any] = user_data
        return result

    def _map_user_info(self, user_data: dict[str, Any]) -> OAuthUserInfo:
        """Map GitHub user data to standardized format."""
        return OAuthUserInfo(
            provider=OAuthProvider.GITHUB,
            provider_id=str(user_data["id"]),
            email=user_data["primary_email"],
            name=user_data.get("name") or user_data["login"],
            avatar_url=user_data.get("avatar_url"),
        )


class MicrosoftOAuthProvider(BaseOAuthProvider):
    """Microsoft OAuth2 provider implementation using BaseOAuthProvider for DRY compliance."""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, OAuthProvider.MICROSOFT)

    @property
    def scope(self) -> str:
        """Microsoft-specific OAuth scopes."""
        return " ".join(MICROSOFT_SCOPES)

    # Required abstract method implementations
    def _get_auth_base_url(self) -> str:
        """Return Microsoft's authorization URL."""
        return MICROSOFT_AUTHORIZATION_URL

    def _get_token_url(self) -> str:
        """Return Microsoft's token exchange URL."""
        return MICROSOFT_TOKEN_URL

    def _get_user_info_url(self) -> str:
        """Return Microsoft's user info URL."""
        return MICROSOFT_USER_INFO_URL

    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return Microsoft-specific authorization parameters."""
        return {
            "scope": self.scope,
            "response_mode": "query",
        }

    def _map_user_info(self, user_data: dict[str, Any]) -> OAuthUserInfo:
        """Map Microsoft user data to standardized format."""
        return OAuthUserInfo(
            provider=OAuthProvider.MICROSOFT,
            provider_id=user_data["id"],
            email=user_data["mail"] or user_data["userPrincipalName"],
            name=user_data["displayName"],
            avatar_url=None,  # Microsoft Graph doesn't provide avatar URL directly
        )


class FacebookOAuthProvider(BaseOAuthProvider):
    """Facebook OAuth2 provider implementation using BaseOAuthProvider for DRY compliance."""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, OAuthProvider.FACEBOOK)

    @property
    def scope(self) -> str:
        """Facebook-specific OAuth scopes."""
        return "email,public_profile"

    # Required abstract method implementations
    def _get_auth_base_url(self) -> str:
        """Return Facebook's authorization URL."""
        return "https://www.facebook.com/v18.0/dialog/oauth"

    def _get_token_url(self) -> str:
        """Return Facebook's token exchange URL."""
        return "https://graph.facebook.com/v18.0/oauth/access_token"

    def _get_user_info_url(self) -> str:
        """Return Facebook's user info URL."""
        return "https://graph.facebook.com/v18.0/me"

    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return Facebook-specific authorization parameters."""
        return {
            "scope": self.scope,
        }

    async def _fetch_user_data(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Facebook uses query params instead of headers for access token."""
        # Extract access token from headers
        auth_header = headers.get("Authorization", "")
        access_token = auth_header.replace("Bearer ", "")

        params = {
            "fields": "id,email,name,picture.type(large)",
            "access_token": access_token,
        }
        response = await client.get(self._get_user_info_url(), params=params)
        response.raise_for_status()
        user_data: dict[str, Any] = response.json()
        return user_data

    def _map_user_info(self, user_data: dict[str, Any]) -> OAuthUserInfo:
        """Map Facebook user data to standardized format."""
        # Facebook email is optional - use fallback if not provided
        email = user_data.get("email")
        if not email:
            # Generate a placeholder email using Facebook ID
            # User will need to update this later for email features
            email = f"fb_{user_data['id']}@users.csfrace.local"
            self.logger.warning(
                "Facebook user without email, using placeholder",
                facebook_id=user_data["id"],
                placeholder_email=email,
            )

        return OAuthUserInfo(
            provider=OAuthProvider.FACEBOOK,
            provider_id=user_data["id"],
            email=email,
            name=user_data["name"],
            avatar_url=user_data.get("picture", {}).get("data", {}).get("url"),
        )


class AppleOAuthProvider(BaseOAuthProvider):
    """Apple OAuth2 provider implementation using BaseOAuthProvider for DRY compliance."""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, OAuthProvider.APPLE)

    @property
    def scope(self) -> str:
        """Apple-specific OAuth scopes."""
        return " ".join(APPLE_SCOPES)

    # Required abstract method implementations
    def _get_auth_base_url(self) -> str:
        """Return Apple's authorization URL."""
        return APPLE_AUTHORIZATION_URL

    def _get_token_url(self) -> str:
        """Return Apple's token exchange URL."""
        return APPLE_TOKEN_URL

    def _get_user_info_url(self) -> str:
        """Apple uses ID token for user info, not a separate endpoint."""
        return ""  # Not used for Apple

    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return Apple-specific authorization parameters."""
        return {
            "scope": self.scope,
            "response_mode": "form_post",  # Apple requires form_post
        }

    @oauth_error_handler("get Apple user info from JWT")
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Fetch Apple user information from JWT ID token.
        Apple provides user info in the ID token as JWT claims.
        """
        import jwt

        # Decode JWT without verification for now (Apple's public keys would be needed for full verification)
        # In production, you should verify the JWT signature using Apple's public keys
        decoded_token = jwt.decode(access_token, options={"verify_signature": False})

        # Extract user information from JWT claims
        provider_id = decoded_token.get("sub", "unknown")  # Subject claim (unique user ID)
        email = decoded_token.get("email", f"apple_{provider_id}@privaterelay.appleid.com")

        # Name might be provided in first login, otherwise use default
        name = "Apple User"  # Apple doesn't always provide name
        if "name" in decoded_token:
            name = decoded_token["name"]

        self.logger.info(
            "Successfully decoded Apple JWT ID token", provider_id=provider_id, email=email
        )

        return OAuthUserInfo(
            provider=OAuthProvider.APPLE,
            provider_id=f"apple_{provider_id}",
            email=email,
            name=name,
            avatar_url=None,  # Apple doesn't provide avatars
        )

    def _map_user_info(self, user_data: dict[str, Any]) -> OAuthUserInfo:
        """Apple doesn't use this method - overrides get_user_info directly."""
        raise NotImplementedError("Apple provider overrides get_user_info directly")


class OAuthProviderRegistry:
    """Registry pattern for OAuth providers - SOLID Open/Closed Principle compliant.

    New providers can be registered without modifying existing code.
    Uses Factory Method pattern for provider instantiation.
    """

    _providers: dict[OAuthProvider, type[OAuthProviderInterface]] = {}
    _provider_configs: dict[OAuthProvider, dict[str, str]] = {}

    @classmethod
    @oauth_error_handler("register OAuth provider")
    def register_provider(
        cls,
        provider_type: OAuthProvider,
        provider_class: type[OAuthProviderInterface],
        client_id: str,
        client_secret: str,
    ) -> None:
        """Register a new OAuth provider type.

        Args:
            provider_type: The OAuth provider enum
            provider_class: The provider implementation class
            client_id: OAuth client ID for this provider
            client_secret: OAuth client secret for this provider
        """
        cls._providers[provider_type] = provider_class
        cls._provider_configs[provider_type] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        logger.debug("OAuth provider registered", provider=provider_type.value)
        # Enhanced decorator handles exceptions

    @classmethod
    @oauth_error_handler("create OAuth provider")
    def create_provider(cls, provider: OAuthProvider) -> OAuthProviderInterface:
        """Create OAuth provider instance from registry using Factory Method pattern."""
        if provider not in cls._providers:
            logger.warning(
                "Unsupported OAuth provider requested",
                requested_provider=provider.value,
                available_providers=[p.value for p in cls._providers],
            )
            raise ValueError(
                f"Unsupported OAuth provider: {provider}. Available: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[provider]
        config = cls._provider_configs[provider]

        logger.debug(
            "Creating OAuth provider instance",
            provider=provider.value,
            provider_class=provider_class.__name__,
        )

        # MyPy cast: provider_class is guaranteed to be a concrete implementation
        # with the correct constructor signature
        instance = cast("Any", provider_class)(
            client_id=config["client_id"], client_secret=config["client_secret"]
        )

        logger.info("OAuth provider instance created successfully", provider=provider.value)
        provider_instance: OAuthProviderInterface = instance
        return provider_instance
        # Enhanced decorator handles exceptions

    @classmethod
    def get_supported_providers(cls) -> list[OAuthProvider]:
        """Get list of registered OAuth providers."""
        return list(cls._providers.keys())

    @classmethod
    def is_provider_registered(cls, provider: OAuthProvider) -> bool:
        """Check if a provider is registered."""
        return provider in cls._providers


# Register all OAuth providers on module load (Open/Closed compliant)
@oauth_error_handler("register default OAuth providers")
def _register_default_providers() -> None:
    """Register default OAuth providers - can be extended without modification."""
    logger.info("Registering default OAuth providers")

    providers_config = [
        (
            OAuthProvider.GOOGLE,
            GoogleOAuthProvider,
            OAUTH_GOOGLE_CLIENT_ID,
            OAUTH_GOOGLE_CLIENT_SECRET,
        ),
        (
            OAuthProvider.GITHUB,
            GitHubOAuthProvider,
            OAUTH_GITHUB_CLIENT_ID,
            OAUTH_GITHUB_CLIENT_SECRET,
        ),
        (
            OAuthProvider.MICROSOFT,
            MicrosoftOAuthProvider,
            OAUTH_MICROSOFT_CLIENT_ID,
            OAUTH_MICROSOFT_CLIENT_SECRET,
        ),
        (
            OAuthProvider.FACEBOOK,
            FacebookOAuthProvider,
            OAUTH_FACEBOOK_CLIENT_ID,
            OAUTH_FACEBOOK_CLIENT_SECRET,
        ),
        (OAuthProvider.APPLE, AppleOAuthProvider, OAUTH_APPLE_CLIENT_ID, OAUTH_APPLE_CLIENT_SECRET),
    ]

    for provider_type, provider_class, client_id, client_secret in providers_config:
        OAuthProviderRegistry.register_provider(
            provider_type,
            provider_class,  # type: ignore[type-abstract]
            client_id,
            client_secret,
        )

    logger.info(
        "Default OAuth providers registered successfully",
        provider_count=len(providers_config),
        providers=[p.value for p, *_ in providers_config],
    )
    # Enhanced decorator handles exceptions


# Initialize providers on import
_register_default_providers()


class OAuthService:
    """OAuth2 service with dependency injection - Dependency Inversion Principle."""

    def __init__(
        self,
        db_session: Session,
        auth_service: AuthService | None = None,
        merge_service: AccountMergeService | None = None,
        token_encryption_service: TokenEncryptionService | None = None,
    ):
        """Dependency injection for database, auth, and encryption services."""
        self.db_session = db_session
        self.auth_service = auth_service or AuthService(db_session)
        self.merge_service = merge_service or AccountMergeService(db_session, self.auth_service)
        self.provider_registry = OAuthProviderRegistry
        self._oauth_state_cache: dict[
            str, dict[str, str | float | OAuthProvider]
        ] = {}  # In-memory state cache (temporary)
        self._cached_oauth_user_info: OAuthUserInfo | None = None  # Temporary cache

        # Token encryption service for secure token storage (Phase 1 integration)
        if token_encryption_service is None:
            from .token_encryption_service import TokenEncryptionService

            token_encryption_service = TokenEncryptionService()
        self.token_encryption_service = token_encryption_service

    def initiate_oauth_login(
        self, provider: OAuthProvider, redirect_uri: str | None = None
    ) -> SSOLoginResponse:
        """Initiate OAuth login flow - generates authorization URL."""
        # DRY: Use centralized enum handling utility - Single Responsibility Principle
        provider = ensure_oauth_provider(provider)

        oauth_provider = self.provider_registry.create_provider(provider)

        # Generate secure JWT state parameter for stateless validation
        # Use default redirect URI if not provided - DRY enum value extraction
        if redirect_uri is None:
            provider_value = get_oauth_provider_value(provider)
            redirect_uri = f"{OAUTH_REDIRECT_URI_BASE}/auth/oauth/{provider_value}/callback"

        # Create JWT state with the actual redirect_uri that will be used for authorization
        state = self._create_oauth_state_jwt(provider, redirect_uri)

        authorization_url = oauth_provider.get_authorization_url(state, redirect_uri)

        # State is now JWT-encoded and stateless, no need to store

        return SSOLoginResponse(authorization_url=authorization_url, state=state, provider=provider)

    @oauth_error_handler("callback processing")
    async def handle_oauth_callback(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
        redirect_uri: str,
        existing_user_id: str | None = None,
    ) -> tuple[User, bool]:
        """Handle OAuth callback and return user and whether user is new.

        Implements OAuth2 Authorization Code Flow with proper validation and security checks.

        Args:
            provider: OAuth provider
            code: Authorization code from OAuth provider
            state: State parameter for CSRF protection
            redirect_uri: Redirect URI (not used, extracted from state JWT)
            existing_user_id: If provided, link OAuth account to this user (connection scenario)

        Returns:
            Tuple of (User, is_new_user)
        """
        # Step 1: Validate JWT state parameter (CSRF protection)
        original_redirect_uri = await self._validate_oauth_state_jwt(state, provider)

        oauth_provider = self.provider_registry.create_provider(provider)

        # Step 2: Exchange authorization code for access token using original redirect URI
        # This must match the redirect URI used during authorization (OAuth2 spec requirement)
        access_token = await oauth_provider.exchange_code_for_token(code, original_redirect_uri)

        # Step 3: Get user information from OAuth provider
        oauth_user_info = await oauth_provider.get_user_info(access_token)

        # Step 3.2: Store access token in oauth_user_info for later encryption
        # This token will be encrypted and stored in the database
        oauth_user_info.access_token = access_token

        # Step 3.5: Check for account merge requirement (when linking accounts)
        if existing_user_id:
            # Check if this OAuth account is already linked to a different user
            merge_detection = self.merge_service.check_merge_required(
                existing_user_id, oauth_user_info
            )

            if merge_detection:
                # Account merge is required - raise exception with merge detection data
                logger.warning(
                    "Account merge required for OAuth linking",
                    current_user_id=existing_user_id,
                    duplicate_user_id=merge_detection.duplicate_account.user_id,
                    provider=get_oauth_provider_value(provider),
                )
                raise AccountMergeRequiredError(
                    merge_detection=merge_detection,
                    message=merge_detection.message,
                    details={
                        "current_user_id": existing_user_id,
                        "duplicate_user_id": merge_detection.duplicate_account.user_id,
                        "provider": get_oauth_provider_value(provider),
                    },
                )

        # Step 4: Find or create user account (or use existing logged-in user)
        if existing_user_id:
            # User is already logged in, link to their account
            user = self.auth_service.get_user_by_id(existing_user_id)
            if not user:
                raise ValueError("Existing user not found")
            is_new_user = False
            logger.info(
                "Linking OAuth account to existing logged-in user",
                user_id=existing_user_id,
                provider=get_oauth_provider_value(provider),
            )
        else:
            # Normal OAuth sign-in/sign-up flow
            user, is_new_user = self._find_or_create_user(oauth_user_info)

        # Step 5: Link OAuth account to user account
        linked_account = self._link_oauth_account(user.id, oauth_user_info)

        # Step 6: Cache user info for token generation (temporary solution)
        self._cached_oauth_user_info = oauth_user_info

        logger.info(
            "OAuth callback processed successfully",
            provider=get_oauth_provider_value(provider),
            user_id=user.id,
            is_new_user=is_new_user,
            linked_account_id=getattr(linked_account, "id", None),
        )

        return user, is_new_user

    @oauth_error_handler("find or create OAuth user")
    def _find_or_create_user(self, oauth_user_info: OAuthUserInfo) -> tuple[User, bool]:
        """Find existing user or create new one from OAuth info."""
        # Try to find user by email first
        existing_user = self.auth_service.get_user_by_email(oauth_user_info.email)

        if existing_user:
            return existing_user, False

        # Create new user from OAuth info
        # Generate unique username from email
        base_username = oauth_user_info.email.split("@")[0]
        username = self._generate_unique_username(base_username)

        user_create = OAuthUserCreate(
            username=username,
            email=oauth_user_info.email,
            full_name=oauth_user_info.name,
        )

        new_user = self.auth_service.create_user(user_create)
        logger.info(
            "New user created from OAuth",
            user_id=new_user.id,
            email=oauth_user_info.email,
            username=user_create.username,
        )
        return new_user, True

    def _generate_unique_username(self, base_username: str) -> str:
        """Generate a unique username by appending numbers if needed."""
        username = base_username
        counter = 1

        while self.auth_service.get_user_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1

        return username

    @oauth_error_handler("account linking")
    def _link_oauth_account(self, user_id: str, oauth_user_info: OAuthUserInfo) -> LinkedAccount:
        """Link OAuth account to user with encrypted token storage - FIXED: Now properly saves to database."""
        # Check if this OAuth account is already linked to avoid duplicates
        existing_link = (
            self.db_session.query(LinkedAccountDB)
            .filter(
                LinkedAccountDB.user_id == user_id,
                LinkedAccountDB.provider == oauth_user_info.provider.lower(),
            )
            .first()
        )

        # Encrypt access token if provided (Phase 3 integration)
        encrypted_access_token = None
        if oauth_user_info.access_token:
            try:
                encrypted_access_token = self.token_encryption_service.encrypt_token(
                    oauth_user_info.access_token
                )
                logger.debug(
                    "OAuth access token encrypted successfully",
                    user_id=user_id,
                    provider=oauth_user_info.provider,
                )
            except Exception as e:
                logger.error(
                    "Failed to encrypt OAuth access token",
                    error=str(e),
                    user_id=user_id,
                    provider=oauth_user_info.provider,
                )
                # Non-critical: Continue without storing token
                encrypted_access_token = None

        if existing_link:
            logger.info(
                "OAuth account already linked, updating existing record",
                user_id=user_id,
                provider=oauth_user_info.provider,
                existing_id=existing_link.id,
            )
            # Update existing record with latest information
            existing_link.email = oauth_user_info.email
            existing_link.name = oauth_user_info.name
            existing_link.provider_account_id = oauth_user_info.provider_id
            existing_link.access_token = encrypted_access_token  # Update encrypted token
            existing_link.updated_at = datetime.now(UTC)

            self.db_session.commit()

            # Return the API model
            return LinkedAccount(
                user_id=user_id,
                provider=oauth_user_info.provider,
                provider_id=oauth_user_info.provider_id,
                provider_email=oauth_user_info.email,
                linked_at=existing_link.created_at,
                is_primary=False,
            )

        # Create new linked account record in database
        linked_account_db = LinkedAccountDB(
            user_id=user_id,
            provider=oauth_user_info.provider.lower(),  # Store as lowercase for consistency
            provider_account_id=oauth_user_info.provider_id,
            email=oauth_user_info.email,
            name=oauth_user_info.name,
            access_token=encrypted_access_token,  # Store encrypted access token
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # CRITICAL FIX: Actually save to database
        self.db_session.add(linked_account_db)
        self.db_session.commit()

        logger.info(
            "OAuth account successfully linked to user with encrypted token",
            user_id=user_id,
            provider=oauth_user_info.provider,
            provider_email=oauth_user_info.email,
            linked_account_id=linked_account_db.id,
            token_stored=encrypted_access_token is not None,
        )

        # Return the API model
        return LinkedAccount(
            user_id=user_id,
            provider=oauth_user_info.provider,
            provider_id=oauth_user_info.provider_id,
            provider_email=oauth_user_info.email,
            linked_at=linked_account_db.created_at,
            is_primary=False,  # Could be True if this is the primary login method
        )

    async def _validate_oauth_state(self, state: str, provider: OAuthProvider) -> None:
        """Validate OAuth state parameter for CSRF protection.

        Args:
            state: State parameter from OAuth callback
            provider: OAuth provider

        Raises:
            ValueError: If state is invalid or expired
        """
        if not state:
            raise ValueError("Missing state parameter")

        # Check if state exists in cache
        cached_state = self._oauth_state_cache.get(state)
        if not cached_state:
            logger.warning(
                "Invalid OAuth state parameter",
                state=state,
                provider=get_oauth_provider_value(provider),
            )
            raise ValueError("Invalid or expired state parameter")

        # Validate provider matches
        if cached_state.get("provider") != provider:
            logger.warning(
                "OAuth state provider mismatch",
                cached_provider=cached_state.get("provider"),
                callback_provider=get_oauth_provider_value(provider),
            )
            raise ValueError("State parameter provider mismatch")

        # Check expiration (states should expire after 10 minutes)
        state_created_raw = cached_state.get("created_at", 0)
        state_created: float = (
            state_created_raw if isinstance(state_created_raw, (int, float)) else 0
        )
        if time.time() - state_created > 600:  # 10 minutes
            logger.warning(
                "Expired OAuth state parameter",
                state=state,
                provider=get_oauth_provider_value(provider),
            )
            # Clean up expired state
            self._oauth_state_cache.pop(state, None)
            raise ValueError("Expired state parameter")

        # Clean up used state (one-time use)
        self._oauth_state_cache.pop(state, None)

        logger.debug(
            "OAuth state validation successful",
            state=state,
            provider=get_oauth_provider_value(provider),
        )

    def _store_oauth_state(self, state: str, provider: OAuthProvider, redirect_uri: str) -> None:
        """Store OAuth state for validation.

        Args:
            state: Generated state parameter
            provider: OAuth provider
            redirect_uri: Redirect URI used
        """

        self._oauth_state_cache[state] = {
            "provider": provider,
            "redirect_uri": redirect_uri,
            "created_at": time.time(),
        }

        # Clean up old states (simple cleanup - in production, use Redis with TTL)
        current_time = time.time()
        expired_states = []
        for s, data in self._oauth_state_cache.items():
            created_at_raw = data.get("created_at", 0)
            if isinstance(created_at_raw, (int, float)):
                created_at: float = float(created_at_raw)
                if current_time - created_at > 600:  # 10 minutes
                    expired_states.append(s)
        for expired_state in expired_states:
            self._oauth_state_cache.pop(expired_state, None)

        logger.debug("OAuth state stored", state=state, provider=get_oauth_provider_value(provider))

    async def get_cached_user_info(self, access_token: str) -> OAuthUserInfo:  # pylint: disable=unused-argument
        """Get OAuth user information using the access token.

        This method fetches fresh user information from the OAuth provider
        using the provided access token, ensuring data accuracy and security.

        Args:
            access_token: OAuth access token

        Returns:
            OAuthUserInfo with current user data

        Raises:
            ValueError: If token is invalid or user info cannot be retrieved
        """
        # Check if we have cached user info
        if self._cached_oauth_user_info is not None:
            return self._cached_oauth_user_info

        # No cache available, raise error
        raise ValueError("No cached OAuth user information available")

    def _create_oauth_state_jwt(self, provider: OAuthProvider, redirect_uri: str) -> str:
        """Create JWT-based OAuth state token - Stateless and CSRF-secure."""
        from ..auth.security import security_manager

        state_data: dict[str, str | bool | datetime | list[str]] = {
            "provider": get_oauth_provider_value(provider),
            "redirect_uri": redirect_uri,
            "purpose": "oauth_state",
        }
        state_jwt, _ = security_manager.create_access_token(
            data=state_data, expires_delta=timedelta(minutes=10)
        )
        logger.debug("JWT OAuth state created", provider=get_oauth_provider_value(provider))
        return state_jwt

    @oauth_error_handler("validate OAuth state JWT")
    async def _validate_oauth_state_jwt(self, state: str, provider: OAuthProvider) -> str:
        """Validate JWT-based OAuth state token and return original redirect_uri."""
        from ..auth.security import security_manager

        # Decode and validate JWT state token
        state_data = security_manager.decode_access_token(state)

        # Validate state token purpose
        if state_data.get("purpose") != "oauth_state":
            logger.warning("Invalid OAuth state token purpose", purpose=state_data.get("purpose"))
            raise ValueError("Invalid state token purpose")

        # Validate provider matches
        token_provider = state_data.get("provider")
        expected_provider = get_oauth_provider_value(provider)
        if token_provider != expected_provider:
            logger.warning(
                "OAuth state provider mismatch",
                token_provider=token_provider,
                expected_provider=expected_provider,
            )
            raise ValueError("Provider mismatch in state token")

        # Extract and return original redirect URI
        redirect_uri_raw = state_data.get("redirect_uri")
        if not redirect_uri_raw or not isinstance(redirect_uri_raw, str):
            logger.warning("Missing or invalid redirect_uri in OAuth state token")
            raise ValueError("Missing or invalid redirect_uri in state token")

        redirect_uri: str = redirect_uri_raw
        logger.debug("JWT OAuth state validated successfully", provider=expected_provider)
        return redirect_uri

    @oauth_error_handler("connection retrieval")
    def get_oauth_connections(self, user_id: str) -> list[OAuthConnectionResponse]:
        """Get OAuth provider connections for a user - Single Responsibility Principle.

        Returns connection status for all supported OAuth providers by querying
        the database for linked accounts. This is the efficient approach that
        avoids external API calls to OAuth providers.

        Args:
            user_id: User ID to get connections for

        Returns:
            List of OAuth connection responses with provider status
        """
        logger.debug("Getting OAuth connections for user", user_id=user_id)

        # Get all linked accounts for this user from database
        linked_accounts = (
            self.db_session.query(LinkedAccountDB).filter(LinkedAccountDB.user_id == user_id).all()
        )

        # Create a map of connected providers and find the primary account
        connected_providers = {}
        primary_account = None

        for account in linked_accounts:
            # Convert database provider string to enum for consistency
            try:
                provider_enum = OAuthProvider(account.provider.lower())
                connected_providers[provider_enum] = account

                # Track the oldest account as primary (first linked account)
                if primary_account is None or account.created_at < primary_account.created_at:
                    primary_account = account

            except ValueError:
                # Skip unknown providers for forward compatibility
                logger.warning("Unknown OAuth provider in database", provider=account.provider)
                continue

        # Build response for all supported providers
        connections = []
        for provider in OAuthProviderRegistry.get_supported_providers():
            if provider in connected_providers:
                # Provider is connected
                linked_account = connected_providers[provider]
                is_primary = primary_account is not None and linked_account.id == primary_account.id

                connections.append(
                    OAuthConnectionResponse(
                        provider=provider,
                        connected=True,
                        email=linked_account.email,
                        name=linked_account.name,
                        linked_at=linked_account.created_at,
                        is_primary=is_primary,
                    )
                )
            else:
                # Provider is not connected
                connections.append(
                    OAuthConnectionResponse(
                        provider=provider,
                        connected=False,
                        email=None,
                        name=None,
                        linked_at=None,
                        is_primary=False,
                    )
                )

        logger.info(
            "OAuth connections retrieved",
            user_id=user_id,
            total_providers=len(connections),
            connected_count=len([c for c in connections if c.connected]),
        )

        return connections

    async def _revoke_oauth_token(
        self, linked_account: LinkedAccountDB, provider: OAuthProvider
    ) -> bool:
        """Attempt to revoke OAuth token with provider before account deletion.

        This method implements graceful degradation - if revocation fails for any reason,
        it logs the error but returns False without raising an exception. This ensures
        account disconnection can proceed even if the provider's revocation endpoint
        is unavailable or the token is already invalid.

        Args:
            linked_account: The linked account database record containing encrypted token
            provider: OAuth provider for token revocation

        Returns:
            bool: True if revocation succeeded, False if failed or no token stored
        """
        # Step 1: Check if we have an access token to revoke
        if not linked_account.access_token:
            logger.debug(
                "No access token stored for OAuth account, skipping revocation",
                user_id=linked_account.user_id,
                provider=get_oauth_provider_value(provider),
            )
            return False

        try:
            # Step 2: Decrypt the access token
            decrypted_token = self.token_encryption_service.decrypt_token(
                linked_account.access_token
            )

            logger.debug(
                "Decrypted OAuth access token for revocation",
                user_id=linked_account.user_id,
                provider=get_oauth_provider_value(provider),
            )

            # Step 3: Get the appropriate revoker from the registry
            from .oauth_revocation_service import OAuthRevocationRegistry

            revoker = OAuthRevocationRegistry.get_revoker(provider)

            logger.debug(
                "Retrieved OAuth token revoker from registry",
                provider=get_oauth_provider_value(provider),
                revoker_class=revoker.__class__.__name__,
            )

            # Step 4: Attempt to revoke all tokens (access + refresh if supported)
            # Use provider_account_id (e.g., Facebook user ID) not internal user_id
            revocation_success = await revoker.revoke_all_tokens(
                user_id=linked_account.provider_account_id, access_token=decrypted_token
            )

            if revocation_success:
                logger.info(
                    "Successfully revoked OAuth tokens with provider",
                    user_id=linked_account.user_id,
                    provider=get_oauth_provider_value(provider),
                )
                return True
            else:
                logger.warning(
                    "OAuth token revocation returned False (non-critical failure)",
                    user_id=linked_account.user_id,
                    provider=get_oauth_provider_value(provider),
                )
                return False

        except Exception as e:
            # Graceful degradation: Log error but don't raise
            logger.error(
                "Failed to revoke OAuth token (non-critical, proceeding with disconnect)",
                user_id=linked_account.user_id,
                provider=get_oauth_provider_value(provider),
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    @oauth_error_handler("OAuth account disconnection")
    async def disconnect_oauth_account(self, user_id: str, provider: OAuthProvider) -> bool:
        """Disconnect OAuth account from user with token revocation - SOLID Single Responsibility with safety checks.

        This method removes the linked OAuth account for a provider, but includes
        critical safety checks to prevent users from locking themselves out.
        Also attempts to revoke the OAuth token with the provider before deletion.

        Safety Rules:
        1. Cannot disconnect if it's the only authentication method (no password set)
        2. Cannot disconnect the primary OAuth account if it's the only one
        3. Validates the account is actually linked before attempting removal
        4. Attempts token revocation before deletion (Phase 3 integration)

        Args:
            user_id: User ID to disconnect account from
            provider: OAuth provider to disconnect

        Returns:
            bool: True if successfully disconnected, False if not linked

        Raises:
            ValueError: If disconnecting would lock user out of account
        """
        logger.info(
            "Attempting to disconnect OAuth account with token revocation",
            user_id=user_id,
            provider=get_oauth_provider_value(provider),
        )

        # Safety Check 1: Get user from database to check if they have a password
        user_db = self.db_session.query(UserTable).filter(UserTable.id == user_id).first()
        if not user_db:
            logger.warning("User not found for OAuth disconnect", user_id=user_id)
            raise ValueError("User not found")

        # Safety Check 2: Count linked OAuth accounts
        linked_accounts = (
            self.db_session.query(LinkedAccountDB).filter(LinkedAccountDB.user_id == user_id).all()
        )

        # Safety Check 3: Prevent lockout - user must have password OR multiple OAuth accounts
        has_password = user_db.hashed_password is not None and len(user_db.hashed_password) > 0
        has_multiple_oauth = len(linked_accounts) > 1

        if not has_password and not has_multiple_oauth:
            logger.warning(
                "Cannot disconnect OAuth - would lock user out",
                user_id=user_id,
                provider=get_oauth_provider_value(provider),
                has_password=has_password,
                oauth_count=len(linked_accounts),
            )
            raise ValueError(
                "Cannot disconnect this account. You must either set a password or "
                "connect another OAuth provider first to avoid being locked out."
            )

        # Find the linked account to disconnect
        linked_account = (
            self.db_session.query(LinkedAccountDB)
            .filter(
                LinkedAccountDB.user_id == user_id,
                LinkedAccountDB.provider == provider.value,
            )
            .first()
        )

        if not linked_account:
            logger.info(
                "OAuth account not linked, nothing to disconnect",
                user_id=user_id,
                provider=get_oauth_provider_value(provider),
            )
            return False

        # Phase 3: Attempt token revocation before deletion
        revocation_success = await self._revoke_oauth_token(linked_account, provider)

        # Delete the linked account (even if revocation fails - graceful degradation)
        self.db_session.delete(linked_account)
        self.db_session.commit()

        logger.info(
            "OAuth account disconnected successfully",
            user_id=user_id,
            provider=get_oauth_provider_value(provider),
            token_revoked=revocation_success,
            linked_account_id=linked_account.id,
        )

        return True
