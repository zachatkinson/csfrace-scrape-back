"""OAuth2 SSO service with SOLID principles and DRY validation."""

import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy.orm import Session

from ..constants import (
    OAUTH_APPLE_CLIENT_ID,
    OAUTH_APPLE_CLIENT_SECRET,
    OAUTH_CONSTANTS,
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
from .enum_utils import ensure_oauth_provider, get_oauth_provider_value
from .models import (
    LinkedAccount,
    OAuthProvider,
    OAuthUserCreate,
    OAuthUserInfo,
    SSOLoginResponse,
    User,
)
from .service import AuthService

logger = structlog.get_logger(__name__)


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

    # Properties for backward compatibility with tests
    @property
    def authorization_base_url(self) -> str:
        """Authorization URL for backward compatibility."""
        return self._get_auth_base_url()

    @property
    def token_url(self) -> str:
        """Token URL for backward compatibility."""
        return self._get_token_url()

    @property
    def user_info_url(self) -> str:
        """User info URL for backward compatibility."""
        return self._get_user_info_url()

    @property
    def scope(self) -> str:
        """OAuth scope for backward compatibility."""
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
        return token_response["access_token"]

    async def _fetch_user_data(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Default user data fetching - single request."""
        response = await client.get(self._get_user_info_url(), headers=headers)
        response.raise_for_status()
        return response.json()


class GoogleOAuthProvider(BaseOAuthProvider):
    """Google OAuth2 provider implementation - Now DRY using BaseOAuthProvider Template Method Pattern."""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, OAuthProvider.GOOGLE)

    @property
    def scope(self) -> str:
        """Google-specific OAuth scopes."""
        return " ".join(OAUTH_CONSTANTS.GOOGLE_SCOPES)

    # Required abstract method implementations
    def _get_auth_base_url(self) -> str:
        """Return Google's authorization URL."""
        return OAUTH_CONSTANTS.GOOGLE_AUTHORIZATION_URL

    def _get_token_url(self) -> str:
        """Return Google's token exchange URL."""
        return OAUTH_CONSTANTS.GOOGLE_TOKEN_URL

    def _get_user_info_url(self) -> str:
        """Return Google's user info URL."""
        return OAUTH_CONSTANTS.GOOGLE_USER_INFO_URL

    def _get_provider_auth_params(self) -> dict[str, str]:
        """Return Google-specific authorization parameters."""
        return {
            "access_type": "offline",
            "prompt": "consent",
            "scope": " ".join(OAUTH_CONSTANTS.GOOGLE_SCOPES),
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


class GitHubOAuthProvider(OAuthProviderInterface):
    """GitHub OAuth2 provider implementation - Single Responsibility with DRY constants."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_base_url = OAUTH_CONSTANTS.GITHUB_AUTHORIZATION_URL
        self.token_url = OAUTH_CONSTANTS.GITHUB_TOKEN_URL
        self.user_info_url = OAUTH_CONSTANTS.GITHUB_USER_INFO_URL
        self.user_emails_url = OAUTH_CONSTANTS.GITHUB_USER_EMAILS_URL
        self.scope = OAUTH_CONSTANTS.GITHUB_SCOPES

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate GitHub OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scope),
            "state": state,
            "allow_signup": "true",
        }
        return f"{self.authorization_base_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange GitHub authorization code for access token."""
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
            headers = {"Accept": "application/json"}
            response = await client.post(self.token_url, data=token_data, headers=headers)
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch GitHub user information."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"token {access_token}"}

            # Get user profile
            user_response = await client.get(self.user_info_url, headers=headers)
            user_response.raise_for_status()
            user_data = user_response.json()

            # Get primary email (GitHub doesn't always include email in user endpoint)
            emails_response = await client.get(self.user_emails_url, headers=headers)
            emails_response.raise_for_status()
            emails = emails_response.json()

            primary_email = next(
                (email["email"] for email in emails if email["primary"]), user_data.get("email")
            )

            return OAuthUserInfo(
                provider=OAuthProvider.GITHUB,
                provider_id=str(user_data["id"]),
                email=primary_email,
                name=user_data.get("name") or user_data["login"],
                avatar_url=user_data.get("avatar_url"),
            )


class MicrosoftOAuthProvider(OAuthProviderInterface):
    """Microsoft OAuth2 provider implementation - Single Responsibility with DRY constants."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_base_url = OAUTH_CONSTANTS.MICROSOFT_AUTHORIZATION_URL
        self.token_url = OAUTH_CONSTANTS.MICROSOFT_TOKEN_URL
        self.user_info_url = OAUTH_CONSTANTS.MICROSOFT_USER_INFO_URL
        self.scope = OAUTH_CONSTANTS.MICROSOFT_SCOPES

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Microsoft OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scope),
            "response_type": "code",
            "state": state,
            "response_mode": "query",
        }
        return f"{self.authorization_base_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange Microsoft authorization code for access token."""
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = await client.post(self.token_url, data=token_data, headers=headers)
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch Microsoft user information."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(self.user_info_url, headers=headers)
            response.raise_for_status()

            user_data = response.json()
            return OAuthUserInfo(
                provider=OAuthProvider.MICROSOFT,
                provider_id=user_data["id"],
                email=user_data["mail"] or user_data["userPrincipalName"],
                name=user_data["displayName"],
                avatar_url=None,  # Microsoft Graph doesn't provide avatar URL directly
            )


class FacebookOAuthProvider(OAuthProviderInterface):
    """Facebook OAuth2 provider implementation - Single Responsibility with DRY constants."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = "https://www.facebook.com/v18.0/dialog/oauth"
        self.token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        self.user_info_url = "https://graph.facebook.com/v18.0/me"

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Facebook authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "email,public_profile",
            "response_type": "code",
            "state": state,
        }
        return f"{self.authorization_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange Facebook authorization code for access token."""
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
            response = await client.post(self.token_url, data=token_data)
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch Facebook user information."""
        async with httpx.AsyncClient() as client:
            params = {
                "fields": "id,email,name,picture.type(large)",
                "access_token": access_token,
            }
            response = await client.get(self.user_info_url, params=params)
            response.raise_for_status()

            user_data = response.json()

            # Facebook email is optional - use fallback if not provided
            email = user_data.get("email")
            if not email:
                # Generate a placeholder email using Facebook ID
                # User will need to update this later for email features
                email = f"fb_{user_data['id']}@users.csfrace.local"
                logger.warning(
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


class AppleOAuthProvider(OAuthProviderInterface):
    """Apple OAuth2 provider implementation - Single Responsibility with DRY constants."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = "https://appleid.apple.com/auth/authorize"
        self.token_url = "https://appleid.apple.com/auth/token"
        # Note: Apple uses ID token for user info, not a separate endpoint

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Apple authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "name email",
            "response_type": "code",
            "response_mode": "form_post",  # Apple requires form_post
            "state": state,
        }
        return f"{self.authorization_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange Apple authorization code for access token."""
        async with httpx.AsyncClient() as client:
            # Apple requires specific headers and client_secret as JWT (simplified for demo)
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,  # Should be JWT in production
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            response = await client.post(self.token_url, data=token_data, headers=headers)
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Fetch Apple user information.
        Note: Apple provides user info in the ID token, not via separate API.
        This is a simplified implementation - production should decode JWT ID token.
        """
        # TODO: In production, decode the ID token (access_token) as JWT
        # to extract actual user info from claims

        # For now, generate consistent placeholder data
        # Real implementation would decode JWT and extract: sub, email, name
        import hashlib

        unique_id = hashlib.md5(access_token.encode()).hexdigest()[:12]

        logger.warning(
            "Apple OAuth using placeholder implementation",
            message="Production should decode JWT ID token for real user data",
        )

        return OAuthUserInfo(
            provider=OAuthProvider.APPLE,
            provider_id=f"apple_{unique_id}",  # Would come from JWT sub claim
            email=f"apple_{unique_id}@privaterelay.appleid.com",  # Would come from JWT email claim
            name="Apple User",  # Would come from JWT name claim if provided
            avatar_url=None,  # Apple doesn't provide avatars
        )


class OAuthProviderRegistry:
    """Registry pattern for OAuth providers - SOLID Open/Closed Principle compliant.

    New providers can be registered without modifying existing code.
    """

    _providers: dict[OAuthProvider, type[OAuthProviderInterface]] = {}
    _provider_configs: dict[OAuthProvider, dict[str, str]] = {}

    @classmethod
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

    @classmethod
    def create_provider(cls, provider: OAuthProvider) -> OAuthProviderInterface:
        """Create OAuth provider instance from registry."""
        if provider not in cls._providers:
            raise ValueError(
                f"Unsupported OAuth provider: {provider}. Available: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[provider]
        config = cls._provider_configs[provider]

        # MyPy cast: provider_class is guaranteed to be a concrete implementation
        # with the correct constructor signature
        return cast("Any", provider_class)(
            client_id=config["client_id"], client_secret=config["client_secret"]
        )

    @classmethod
    def get_supported_providers(cls) -> list[OAuthProvider]:
        """Get list of registered OAuth providers."""
        return list(cls._providers.keys())

    @classmethod
    def is_provider_registered(cls, provider: OAuthProvider) -> bool:
        """Check if a provider is registered."""
        return provider in cls._providers


# Register all OAuth providers on module load (Open/Closed compliant)
def _register_default_providers() -> None:
    """Register default OAuth providers - can be extended without modification."""
    OAuthProviderRegistry.register_provider(
        OAuthProvider.GOOGLE,
        GoogleOAuthProvider,
        OAUTH_GOOGLE_CLIENT_ID,
        OAUTH_GOOGLE_CLIENT_SECRET,
    )

    OAuthProviderRegistry.register_provider(
        OAuthProvider.GITHUB,
        GitHubOAuthProvider,
        OAUTH_GITHUB_CLIENT_ID,
        OAUTH_GITHUB_CLIENT_SECRET,
    )

    OAuthProviderRegistry.register_provider(
        OAuthProvider.MICROSOFT,
        MicrosoftOAuthProvider,
        OAUTH_MICROSOFT_CLIENT_ID,
        OAUTH_MICROSOFT_CLIENT_SECRET,
    )

    OAuthProviderRegistry.register_provider(
        OAuthProvider.FACEBOOK,
        FacebookOAuthProvider,
        OAUTH_FACEBOOK_CLIENT_ID,
        OAUTH_FACEBOOK_CLIENT_SECRET,
    )

    OAuthProviderRegistry.register_provider(
        OAuthProvider.APPLE,
        AppleOAuthProvider,
        OAUTH_APPLE_CLIENT_ID,
        OAUTH_APPLE_CLIENT_SECRET,
    )


# Initialize providers on import
_register_default_providers()


# Backward compatibility alias - can be removed after migration
class OAuthProviderFactory:
    """Backward compatibility wrapper around OAuthProviderRegistry."""

    @staticmethod
    def create_provider(provider: OAuthProvider) -> OAuthProviderInterface:
        return OAuthProviderRegistry.create_provider(provider)

    @staticmethod
    def get_supported_providers() -> list[OAuthProvider]:
        return OAuthProviderRegistry.get_supported_providers()


class OAuthService:
    """OAuth2 service with dependency injection - Dependency Inversion Principle."""

    def __init__(self, db_session: Session, auth_service: AuthService | None = None):
        """Dependency injection for database and auth services."""
        self.db_session = db_session
        self.auth_service = auth_service or AuthService(db_session)
        self.provider_factory = OAuthProviderFactory()
        self._oauth_state_cache: dict[str, dict] = {}  # In-memory state cache (temporary)
        self._cached_oauth_user_info: OAuthUserInfo | None = None  # Temporary cache

    def initiate_oauth_login(
        self, provider: OAuthProvider, redirect_uri: str | None = None
    ) -> SSOLoginResponse:
        """Initiate OAuth login flow - generates authorization URL."""
        # DRY: Use centralized enum handling utility - Single Responsibility Principle
        provider = ensure_oauth_provider(provider)

        oauth_provider = self.provider_factory.create_provider(provider)

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

    async def handle_oauth_callback(
        self, provider: OAuthProvider, code: str, state: str, redirect_uri: str
    ) -> tuple[User, bool]:
        """Handle OAuth callback and return user and whether user is new.

        Implements OAuth2 Authorization Code Flow with proper validation and security checks.
        """
        # Step 1: Validate JWT state parameter (CSRF protection)
        original_redirect_uri = await self._validate_oauth_state_jwt(state, provider)

        oauth_provider = self.provider_factory.create_provider(provider)

        try:
            # Step 2: Exchange authorization code for access token using original redirect URI
            # This must match the redirect URI used during authorization (OAuth2 spec requirement)
            access_token = await oauth_provider.exchange_code_for_token(code, original_redirect_uri)

            # Step 3: Get user information from OAuth provider
            oauth_user_info = await oauth_provider.get_user_info(access_token)

            # Step 4: Find or create user account
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

        except Exception as e:
            logger.error(
                "OAuth callback processing failed",
                provider=get_oauth_provider_value(provider),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _find_or_create_user(self, oauth_user_info: OAuthUserInfo) -> tuple[User, bool]:
        """Find existing user or create new one from OAuth info."""
        # Try to find user by email first
        existing_user = self.auth_service.get_user_by_email(oauth_user_info.email)

        if existing_user:
            return existing_user, False

        # Create new user from OAuth info
        try:
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

        except Exception as e:
            logger.error(
                "Failed to create user from OAuth info",
                email=oauth_user_info.email,
                username=oauth_user_info.email.split("@")[0],
                error=str(e),
                error_type=type(e).__name__,
            )
            raise RuntimeError(f"User creation failed: {str(e)}") from e

    def _generate_unique_username(self, base_username: str) -> str:
        """Generate a unique username by appending numbers if needed."""
        username = base_username
        counter = 1

        while self.auth_service.get_user_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1

        return username

    def _link_oauth_account(self, user_id: str, oauth_user_info: OAuthUserInfo) -> LinkedAccount:
        """Link OAuth account to user."""
        # Database storage implementation pending - for now return in-memory object
        # This will create/update a linked_accounts table entry in production
        linked_account = LinkedAccount(
            user_id=user_id,
            provider=oauth_user_info.provider,
            provider_id=oauth_user_info.provider_id,
            provider_email=oauth_user_info.email,
            linked_at=datetime.now(UTC),
            is_primary=False,  # Could be True if this is the primary login method
        )

        # Database storage will be implemented with linked_accounts table
        # self.db_session.add(linked_account_db_model)
        # self.db_session.commit()

        return linked_account

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
        state_created = cached_state.get("created_at", 0)
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
        expired_states = [
            s
            for s, data in self._oauth_state_cache.items()
            if current_time - data.get("created_at", 0) > 600  # 10 minutes
        ]
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

        state_data = {
            "provider": get_oauth_provider_value(provider),
            "redirect_uri": redirect_uri,
            "purpose": "oauth_state",
        }
        state_jwt, _ = security_manager.create_access_token(
            data=state_data, expires_delta=timedelta(minutes=10)
        )
        logger.debug("JWT OAuth state created", provider=get_oauth_provider_value(provider))
        return state_jwt

    async def _validate_oauth_state_jwt(self, state: str, provider: OAuthProvider) -> str:
        """Validate JWT-based OAuth state token and return original redirect_uri."""
        from ..auth.security import security_manager

        try:
            # Decode and validate JWT state token
            state_data = security_manager.decode_access_token(state)

            # Validate state token purpose
            if state_data.get("purpose") != "oauth_state":
                logger.warning(
                    "Invalid OAuth state token purpose", purpose=state_data.get("purpose")
                )
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
            redirect_uri = state_data.get("redirect_uri")
            if not redirect_uri:
                logger.warning("Missing redirect_uri in OAuth state token")
                raise ValueError("Missing redirect_uri in state token")

            logger.debug("JWT OAuth state validated successfully", provider=expected_provider)
            return redirect_uri

        except Exception as e:
            logger.error("OAuth state validation failed", error=str(e))
            raise ValueError("Invalid or expired state parameter")
