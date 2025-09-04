"""OAuth2 SSO service with SOLID principles and DRY validation."""

import secrets
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from ..constants import (
    OAUTH_CONSTANTS,
    OAUTH_GITHUB_CLIENT_ID,
    OAUTH_GITHUB_CLIENT_SECRET,
    OAUTH_GOOGLE_CLIENT_ID,
    OAUTH_GOOGLE_CLIENT_SECRET,
    OAUTH_MICROSOFT_CLIENT_ID,
    OAUTH_MICROSOFT_CLIENT_SECRET,
    OAUTH_REDIRECT_URI_BASE,
)
from .models import LinkedAccount, OAuthProvider, OAuthUserInfo, SSOLoginResponse, User
from .service import AuthService


class OAuthProviderInterface(ABC):
    """Interface Segregation: Abstract OAuth provider interface."""

    @abstractmethod
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate authorization URL for OAuth flow."""
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange authorization code for access token."""
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user information using access token."""
        pass


class GoogleOAuthProvider(OAuthProviderInterface):
    """Google OAuth2 provider implementation - Single Responsibility with DRY constants."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_base_url = OAUTH_CONSTANTS.GOOGLE_AUTHORIZATION_URL
        self.token_url = OAUTH_CONSTANTS.GOOGLE_TOKEN_URL
        self.user_info_url = OAUTH_CONSTANTS.GOOGLE_USER_INFO_URL
        self.scope = OAUTH_CONSTANTS.GOOGLE_SCOPES

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scope),
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.authorization_base_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange Google authorization code for access token."""
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            response = await client.post(self.token_url, data=token_data)
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch Google user information."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(self.user_info_url, headers=headers)
            response.raise_for_status()

            user_data = response.json()
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


class OAuthProviderFactory:
    """Factory pattern for OAuth providers - Open/Closed Principle."""

    @staticmethod
    def create_provider(provider: OAuthProvider) -> OAuthProviderInterface:
        """Create OAuth provider instance based on type."""
        if provider == OAuthProvider.GOOGLE:
            return GoogleOAuthProvider(
                client_id=OAUTH_GOOGLE_CLIENT_ID, client_secret=OAUTH_GOOGLE_CLIENT_SECRET
            )
        elif provider == OAuthProvider.GITHUB:
            return GitHubOAuthProvider(
                client_id=OAUTH_GITHUB_CLIENT_ID, client_secret=OAUTH_GITHUB_CLIENT_SECRET
            )
        elif provider == OAuthProvider.MICROSOFT:
            return MicrosoftOAuthProvider(
                client_id=OAUTH_MICROSOFT_CLIENT_ID, client_secret=OAUTH_MICROSOFT_CLIENT_SECRET
            )
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")


class OAuthService:
    """OAuth2 service with dependency injection - Dependency Inversion Principle."""

    def __init__(self, db_session: Session, auth_service: AuthService | None = None):
        """Dependency injection for database and auth services."""
        self.db_session = db_session
        self.auth_service = auth_service or AuthService(db_session)
        self.provider_factory = OAuthProviderFactory()

    def initiate_oauth_login(
        self, provider: OAuthProvider, redirect_uri: str | None = None
    ) -> SSOLoginResponse:
        """Initiate OAuth login flow - generates authorization URL."""
        oauth_provider = self.provider_factory.create_provider(provider)

        # Generate secure state parameter using DRY constant
        state = secrets.token_urlsafe(OAUTH_CONSTANTS.STATE_TOKEN_LENGTH)

        # Use default redirect URI if not provided
        if redirect_uri is None:
            redirect_uri = f"{OAUTH_REDIRECT_URI_BASE}/auth/oauth/{provider.value}/callback"

        authorization_url = oauth_provider.get_authorization_url(state, redirect_uri)

        # TODO: Store state in cache/session for validation
        # self._store_oauth_state(state, provider, redirect_uri)

        return SSOLoginResponse(authorization_url=authorization_url, state=state, provider=provider)

    async def handle_oauth_callback(
        self, provider: OAuthProvider, code: str, state: str, redirect_uri: str
    ) -> tuple[str, bool]:
        """Handle OAuth callback and return access token and whether user is new."""
        # TODO: Validate state parameter
        # self._validate_oauth_state(state, provider)

        oauth_provider = self.provider_factory.create_provider(provider)

        # Exchange code for access token
        access_token = await oauth_provider.exchange_code_for_token(code, redirect_uri)

        # Get user information
        oauth_user_info = await oauth_provider.get_user_info(access_token)

        # Find or create user
        user, is_new_user = self._find_or_create_user(oauth_user_info)

        # Link account if not already linked
        self._link_oauth_account(user.id, oauth_user_info)

        return access_token, is_new_user

    def _find_or_create_user(self, oauth_user_info: OAuthUserInfo) -> tuple[User, bool]:
        """Find existing user or create new one from OAuth info."""
        # Try to find user by email first
        existing_user = self.auth_service.get_user_by_email(oauth_user_info.email)

        if existing_user:
            return existing_user, False

        # Create new user from OAuth info
        from .models import UserCreate

        user_create = UserCreate(
            username=oauth_user_info.email.split("@")[0],  # Use email prefix as username
            email=oauth_user_info.email,
            password=secrets.token_urlsafe(32),  # Random password for OAuth users
            full_name=oauth_user_info.name,
        )

        new_user = self.auth_service.create_user(user_create)
        return new_user, True

    def _link_oauth_account(self, user_id: str, oauth_user_info: OAuthUserInfo) -> LinkedAccount:
        """Link OAuth account to user."""
        # TODO: Implement database storage for linked accounts
        # This would create/update a linked_accounts table entry
        linked_account = LinkedAccount(
            user_id=user_id,
            provider=oauth_user_info.provider,
            provider_id=oauth_user_info.provider_id,
            provider_email=oauth_user_info.email,
            linked_at=datetime.now(UTC),
            is_primary=False,  # Could be True if this is the primary login method
        )

        # TODO: Store in database
        # self.db_session.add(linked_account_db_model)
        # self.db_session.commit()

        return linked_account
