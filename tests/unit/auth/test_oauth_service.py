"""Unit tests for OAuth service - following CLAUDE.md IDT and SOLID principles."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from src.auth.models import OAuthProvider, OAuthUserInfo, SSOLoginResponse
from src.auth.oauth_service import (
    GitHubOAuthProvider,
    GoogleOAuthProvider,
    MicrosoftOAuthProvider,
    OAuthProviderFactory,
    OAuthProviderInterface,
    OAuthService,
)
from src.auth.service import AuthService
from src.constants import OAUTH_CONSTANTS


class TestOAuthProviderFactory:
    """Test OAuth provider factory - Open/Closed Principle testing."""

    def test_factory_creates_google_provider(self):
        """Test factory creates Google OAuth provider."""
        provider = OAuthProviderFactory.create_provider(OAuthProvider.GOOGLE)
        assert isinstance(provider, GoogleOAuthProvider)
        assert provider.client_id == OAUTH_CONSTANTS.OAUTH_GOOGLE_CLIENT_ID
        assert provider.client_secret == OAUTH_CONSTANTS.OAUTH_GOOGLE_CLIENT_SECRET

    def test_factory_creates_github_provider(self):
        """Test factory creates GitHub OAuth provider."""
        provider = OAuthProviderFactory.create_provider(OAuthProvider.GITHUB)
        assert isinstance(provider, GitHubOAuthProvider)
        assert provider.client_id == OAUTH_CONSTANTS.OAUTH_GITHUB_CLIENT_ID
        assert provider.client_secret == OAUTH_CONSTANTS.OAUTH_GITHUB_CLIENT_SECRET

    def test_factory_creates_microsoft_provider(self):
        """Test factory creates Microsoft OAuth provider."""
        provider = OAuthProviderFactory.create_provider(OAuthProvider.MICROSOFT)
        assert isinstance(provider, MicrosoftOAuthProvider)
        assert provider.client_id == OAUTH_CONSTANTS.OAUTH_MICROSOFT_CLIENT_ID
        assert provider.client_secret == OAUTH_CONSTANTS.OAUTH_MICROSOFT_CLIENT_SECRET

    def test_factory_raises_for_unsupported_provider(self):
        """Test factory raises error for unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported OAuth provider"):
            # Create a fake enum value that doesn't exist
            fake_provider = "unsupported_provider"
            OAuthProviderFactory.create_provider(fake_provider)


class TestGoogleOAuthProvider:
    """Test Google OAuth provider - Single Responsibility testing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = GoogleOAuthProvider("test_client_id", "test_client_secret")

    def test_google_provider_initialization(self):
        """Test Google provider initializes with correct URLs from constants."""
        assert self.provider.client_id == "test_client_id"
        assert self.provider.client_secret == "test_client_secret"
        assert self.provider.authorization_base_url == OAUTH_CONSTANTS.GOOGLE_AUTHORIZATION_URL
        assert self.provider.token_url == OAUTH_CONSTANTS.GOOGLE_TOKEN_URL
        assert self.provider.user_info_url == OAUTH_CONSTANTS.GOOGLE_USER_INFO_URL
        assert self.provider.scope == OAUTH_CONSTANTS.GOOGLE_SCOPES

    def test_google_get_authorization_url(self):
        """Test Google authorization URL generation."""
        state = "test_state"
        redirect_uri = "https://myapp.com/callback"

        auth_url = self.provider.get_authorization_url(state, redirect_uri)

        assert OAUTH_CONSTANTS.GOOGLE_AUTHORIZATION_URL in auth_url
        assert "client_id=test_client_id" in auth_url
        assert f"state={state}" in auth_url
        from urllib.parse import unquote

        assert redirect_uri in unquote(auth_url)
        assert "scope=openid+email+profile" in auth_url
        assert "response_type=code" in auth_url
        assert "access_type=offline" in auth_url
        assert "prompt=consent" in auth_url

    @pytest.mark.asyncio
    async def test_google_exchange_code_for_token(self):
        """Test Google code exchange for access token."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"access_token": "test_access_token"}

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            token = await self.provider.exchange_code_for_token("test_code", "https://callback.com")

            assert token == "test_access_token"

    @pytest.mark.asyncio
    async def test_google_get_user_info(self):
        """Test Google user info retrieval."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "id": "google_user_123",
                "email": "user@gmail.com",
                "name": "John Doe",
                "picture": "https://example.com/avatar.jpg",
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            user_info = await self.provider.get_user_info("test_access_token")

            assert isinstance(user_info, OAuthUserInfo)
            assert user_info.provider == OAuthProvider.GOOGLE
            assert user_info.provider_id == "google_user_123"
            assert user_info.email == "user@gmail.com"
            assert user_info.name == "John Doe"
            assert user_info.avatar_url == "https://example.com/avatar.jpg"


class TestGitHubOAuthProvider:
    """Test GitHub OAuth provider - Single Responsibility testing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = GitHubOAuthProvider("github_client_id", "github_client_secret")

    def test_github_provider_initialization(self):
        """Test GitHub provider initializes with correct URLs from constants."""
        assert self.provider.authorization_base_url == OAUTH_CONSTANTS.GITHUB_AUTHORIZATION_URL
        assert self.provider.token_url == OAUTH_CONSTANTS.GITHUB_TOKEN_URL
        assert self.provider.user_info_url == OAUTH_CONSTANTS.GITHUB_USER_INFO_URL
        assert self.provider.user_emails_url == OAUTH_CONSTANTS.GITHUB_USER_EMAILS_URL
        assert self.provider.scope == OAUTH_CONSTANTS.GITHUB_SCOPES

    def test_github_get_authorization_url(self):
        """Test GitHub authorization URL generation."""
        state = "github_state"
        redirect_uri = "https://app.com/github/callback"

        auth_url = self.provider.get_authorization_url(state, redirect_uri)

        assert OAUTH_CONSTANTS.GITHUB_AUTHORIZATION_URL in auth_url
        assert "client_id=github_client_id" in auth_url
        assert f"state={state}" in auth_url
        assert "scope=user%3Aemail" in auth_url
        assert "allow_signup=true" in auth_url

    @pytest.mark.asyncio
    async def test_github_get_user_info_with_primary_email(self):
        """Test GitHub user info retrieval with primary email."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock user profile response
            mock_user_response = Mock()
            mock_user_response.raise_for_status.return_value = None
            mock_user_response.json.return_value = {
                "id": 12345,
                "login": "octocat",
                "name": "The Octocat",
                "avatar_url": "https://github.com/images/error/octocat_happy.gif",
                "email": None,  # GitHub often doesn't include email in user endpoint
            }

            # Mock emails response
            mock_emails_response = Mock()
            mock_emails_response.raise_for_status.return_value = None
            mock_emails_response.json.return_value = [
                {"email": "secondary@example.com", "primary": False},
                {"email": "octocat@github.com", "primary": True},
            ]

            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get = AsyncMock(
                side_effect=[mock_user_response, mock_emails_response]
            )

            user_info = await self.provider.get_user_info("github_access_token")

            assert user_info.provider == OAuthProvider.GITHUB
            assert user_info.provider_id == "12345"
            assert user_info.email == "octocat@github.com"  # Primary email
            assert user_info.name == "The Octocat"
            assert user_info.avatar_url == "https://github.com/images/error/octocat_happy.gif"


class TestMicrosoftOAuthProvider:
    """Test Microsoft OAuth provider - Single Responsibility testing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = MicrosoftOAuthProvider("ms_client_id", "ms_client_secret")

    def test_microsoft_provider_initialization(self):
        """Test Microsoft provider initializes with correct URLs from constants."""
        assert self.provider.authorization_base_url == OAUTH_CONSTANTS.MICROSOFT_AUTHORIZATION_URL
        assert self.provider.token_url == OAUTH_CONSTANTS.MICROSOFT_TOKEN_URL
        assert self.provider.user_info_url == OAUTH_CONSTANTS.MICROSOFT_USER_INFO_URL
        assert self.provider.scope == OAUTH_CONSTANTS.MICROSOFT_SCOPES

    def test_microsoft_get_authorization_url(self):
        """Test Microsoft authorization URL generation."""
        state = "ms_state"
        redirect_uri = "https://app.com/ms/callback"

        auth_url = self.provider.get_authorization_url(state, redirect_uri)

        assert OAUTH_CONSTANTS.MICROSOFT_AUTHORIZATION_URL in auth_url
        assert "client_id=ms_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "response_mode=query" in auth_url
        assert "scope=openid+profile+email+User.Read" in auth_url

    @pytest.mark.asyncio
    async def test_microsoft_get_user_info(self):
        """Test Microsoft user info retrieval."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "id": "microsoft_user_456",
                "displayName": "Jane Microsoft",
                "mail": "jane@company.com",
                "userPrincipalName": "jane@company.onmicrosoft.com",
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            user_info = await self.provider.get_user_info("ms_access_token")

            assert user_info.provider == OAuthProvider.MICROSOFT
            assert user_info.provider_id == "microsoft_user_456"
            assert user_info.email == "jane@company.com"  # Prefers 'mail' over 'userPrincipalName'
            assert user_info.name == "Jane Microsoft"
            assert user_info.avatar_url is None  # Microsoft doesn't provide direct avatar URL


class TestOAuthService:
    """Test OAuth service - Dependency Inversion Principle testing."""

    def setup_method(self):
        """Set up test fixtures with dependency injection."""
        self.mock_db_session = Mock(spec=Session)
        self.mock_auth_service = Mock(spec=AuthService)
        self.oauth_service = OAuthService(self.mock_db_session, self.mock_auth_service)

    def test_oauth_service_initialization(self):
        """Test OAuth service initializes with injected dependencies."""
        assert self.oauth_service.db_session == self.mock_db_session
        assert self.oauth_service.auth_service == self.mock_auth_service
        assert hasattr(self.oauth_service, "provider_factory")

    def test_oauth_service_default_auth_service(self):
        """Test OAuth service creates default auth service if not provided."""
        service = OAuthService(self.mock_db_session)
        assert service.db_session == self.mock_db_session
        assert hasattr(service, "auth_service")

    @patch("src.auth.oauth_service.secrets.token_urlsafe")
    @patch("src.auth.oauth_service.OAuthProviderFactory.create_provider")
    def test_initiate_oauth_login(self, mock_create_provider, mock_token_urlsafe):
        """Test OAuth login initiation - generates authorization URL with secure state."""
        # Mock dependencies
        mock_token_urlsafe.return_value = "secure_random_state_123"
        mock_provider = Mock()
        mock_provider.get_authorization_url.return_value = (
            "https://oauth.provider.com/authorize?params"
        )
        mock_create_provider.return_value = mock_provider

        # Test initiate login
        response = self.oauth_service.initiate_oauth_login(OAuthProvider.GOOGLE)

        # Verify state token generation uses DRY constant
        mock_token_urlsafe.assert_called_once_with(OAUTH_CONSTANTS.STATE_TOKEN_LENGTH)

        # Verify response
        assert isinstance(response, SSOLoginResponse)
        assert response.authorization_url == "https://oauth.provider.com/authorize?params"
        assert response.state == "secure_random_state_123"
        assert response.provider == OAuthProvider.GOOGLE

    def test_initiate_oauth_login_with_custom_redirect_uri(self):
        """Test OAuth login initiation with custom redirect URI."""
        with (
            patch("src.auth.oauth_service.secrets.token_urlsafe") as mock_token,
            patch("src.auth.oauth_service.OAuthProviderFactory.create_provider") as mock_factory,
        ):
            mock_token.return_value = "state_456"
            mock_provider = Mock()
            mock_provider.get_authorization_url.return_value = "https://auth.url"
            mock_factory.return_value = mock_provider

            custom_redirect = "https://myapp.com/custom/callback"
            response = self.oauth_service.initiate_oauth_login(
                OAuthProvider.GITHUB, redirect_uri=custom_redirect
            )

            # Verify custom redirect URI is used
            mock_provider.get_authorization_url.assert_called_once_with(
                "state_456", custom_redirect
            )

    def test_initiate_oauth_login_uses_default_redirect_uri(self):
        """Test OAuth login initiation uses default redirect URI when none provided."""
        with (
            patch("src.auth.oauth_service.secrets.token_urlsafe") as mock_token,
            patch("src.auth.oauth_service.OAuthProviderFactory.create_provider") as mock_factory,
        ):
            mock_token.return_value = "default_state"
            mock_provider = Mock()
            mock_provider.get_authorization_url.return_value = "https://default.auth.url"
            mock_factory.return_value = mock_provider

            response = self.oauth_service.initiate_oauth_login(OAuthProvider.MICROSOFT)

            # Verify default redirect URI pattern is used
            expected_redirect = (
                f"{OAUTH_CONSTANTS.OAUTH_REDIRECT_URI_BASE}/auth/oauth/microsoft/callback"
            )
            mock_provider.get_authorization_url.assert_called_once_with(
                "default_state", expected_redirect
            )


class TestOAuthProviderInterface:
    """Test OAuth provider interface - Interface Segregation Principle."""

    def test_oauth_provider_interface_is_abstract(self):
        """Test OAuth provider interface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OAuthProviderInterface()

    def test_oauth_provider_interface_defines_required_methods(self):
        """Test OAuth provider interface defines all required abstract methods."""
        abstract_methods = OAuthProviderInterface.__abstractmethods__
        expected_methods = {"get_authorization_url", "exchange_code_for_token", "get_user_info"}
        assert abstract_methods == expected_methods

    def test_concrete_providers_implement_interface(self):
        """Test all concrete providers properly implement the interface."""
        providers = [
            GoogleOAuthProvider("client", "secret"),
            GitHubOAuthProvider("client", "secret"),
            MicrosoftOAuthProvider("client", "secret"),
        ]

        for provider in providers:
            assert isinstance(provider, OAuthProviderInterface)
            assert hasattr(provider, "get_authorization_url")
            assert hasattr(provider, "exchange_code_for_token")
            assert hasattr(provider, "get_user_info")

            # Verify methods are callable
            assert callable(provider.get_authorization_url)
            assert callable(provider.exchange_code_for_token)
            assert callable(provider.get_user_info)


class TestOAuthCallbackHandling:
    """Test OAuth2 callback handling functionality - comprehensive security validation."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        return Mock(spec=Session)

    @pytest.fixture
    def oauth_service(self, mock_db_session):
        """Create OAuth service instance for testing."""
        return OAuthService(mock_db_session)

    @pytest.fixture
    def sample_oauth_user_info(self):
        """Sample OAuth user information for testing."""
        return OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id="123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
        )

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        from datetime import UTC, datetime

        from src.auth.models import User

        return User(
            id="user123",
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            is_superuser=False,
            created_at=datetime.now(UTC),
        )

    def test_oauth_state_storage_and_retrieval(self, oauth_service):
        """Test OAuth state storage and retrieval for CSRF protection."""
        provider = OAuthProvider.GOOGLE
        state = "test_state_123"
        redirect_uri = "https://example.com/callback"

        # Store state
        oauth_service._store_oauth_state(state, provider, redirect_uri)

        # Verify state is stored
        assert state in oauth_service._oauth_state_cache
        cached_data = oauth_service._oauth_state_cache[state]
        assert cached_data["provider"] == provider
        assert cached_data["redirect_uri"] == redirect_uri
        assert "created_at" in cached_data

    def test_oauth_state_cleanup_expired_states(self, oauth_service):
        """Test automatic cleanup of expired OAuth states."""
        import time

        provider = OAuthProvider.GOOGLE
        old_state = "old_state_123"
        new_state = "new_state_456"
        redirect_uri = "https://example.com/callback"

        # Manually add an old state (simulate expired)
        oauth_service._oauth_state_cache[old_state] = {
            "provider": provider,
            "redirect_uri": redirect_uri,
            "created_at": time.time() - 700,  # 700 seconds ago (>10 minutes)
        }

        # Store a new state (should trigger cleanup)
        oauth_service._store_oauth_state(new_state, provider, redirect_uri)

        # Old state should be cleaned up
        assert old_state not in oauth_service._oauth_state_cache
        assert new_state in oauth_service._oauth_state_cache

    @pytest.mark.asyncio
    async def test_validate_oauth_state_success(self, oauth_service):
        """Test successful OAuth state validation."""
        provider = OAuthProvider.GOOGLE
        state = "valid_state_123"
        redirect_uri = "https://example.com/callback"

        # Store state first
        oauth_service._store_oauth_state(state, provider, redirect_uri)

        # Should validate successfully and clean up state
        await oauth_service._validate_oauth_state(state, provider)

        # State should be removed after validation (one-time use)
        assert state not in oauth_service._oauth_state_cache

    @pytest.mark.asyncio
    async def test_validate_oauth_state_missing_state(self, oauth_service):
        """Test OAuth state validation with missing state parameter."""
        provider = OAuthProvider.GOOGLE

        with pytest.raises(ValueError, match="Missing state parameter"):
            await oauth_service._validate_oauth_state("", provider)

    @pytest.mark.asyncio
    async def test_validate_oauth_state_invalid_state(self, oauth_service):
        """Test OAuth state validation with invalid state."""
        provider = OAuthProvider.GOOGLE
        invalid_state = "nonexistent_state"

        with pytest.raises(ValueError, match="Invalid or expired state parameter"):
            await oauth_service._validate_oauth_state(invalid_state, provider)

    @pytest.mark.asyncio
    async def test_validate_oauth_state_provider_mismatch(self, oauth_service):
        """Test OAuth state validation with provider mismatch."""
        stored_provider = OAuthProvider.GOOGLE
        callback_provider = OAuthProvider.GITHUB
        state = "test_state_123"
        redirect_uri = "https://example.com/callback"

        # Store state for Google
        oauth_service._store_oauth_state(state, stored_provider, redirect_uri)

        # Try to validate with GitHub provider
        with pytest.raises(ValueError, match="State parameter provider mismatch"):
            await oauth_service._validate_oauth_state(state, callback_provider)

    @pytest.mark.asyncio
    async def test_validate_oauth_state_expired(self, oauth_service):
        """Test OAuth state validation with expired state."""
        import time

        provider = OAuthProvider.GOOGLE
        state = "expired_state_123"
        redirect_uri = "https://example.com/callback"

        # Manually add expired state
        oauth_service._oauth_state_cache[state] = {
            "provider": provider,
            "redirect_uri": redirect_uri,
            "created_at": time.time() - 700,  # 700 seconds ago (>10 minutes)
        }

        with pytest.raises(ValueError, match="Expired state parameter"):
            await oauth_service._validate_oauth_state(state, provider)

        # Expired state should be cleaned up
        assert state not in oauth_service._oauth_state_cache

    @pytest.mark.asyncio
    async def test_get_cached_user_info_success(self, oauth_service, sample_oauth_user_info):
        """Test successful retrieval of cached OAuth user info."""
        # Cache user info
        oauth_service._cached_oauth_user_info = sample_oauth_user_info

        # Retrieve cached info
        result = await oauth_service.get_cached_user_info("dummy_token")

        assert result == sample_oauth_user_info
        assert result.email == "test@example.com"
        assert result.provider == OAuthProvider.GOOGLE

    @pytest.mark.asyncio
    async def test_get_cached_user_info_no_cache(self, oauth_service):
        """Test cached user info retrieval when no cache exists."""
        with pytest.raises(ValueError, match="No cached OAuth user information available"):
            await oauth_service.get_cached_user_info("dummy_token")

    @pytest.mark.asyncio
    @patch("src.auth.oauth_service.OAuthProviderFactory.create_provider")
    @patch.object(OAuthService, "_find_or_create_user")
    @patch.object(OAuthService, "_link_oauth_account")
    async def test_handle_oauth_callback_success(
        self,
        mock_link_account,
        mock_find_user,
        mock_create_provider,
        oauth_service,
        sample_oauth_user_info,
        sample_user,
    ):
        """Test successful OAuth callback handling."""
        # Mock provider and its methods
        mock_provider = AsyncMock()
        mock_provider.exchange_code_for_token.return_value = "access_token_123"
        mock_provider.get_user_info.return_value = sample_oauth_user_info
        mock_create_provider.return_value = mock_provider

        # Mock user operations
        mock_find_user.return_value = (sample_user, True)  # New user
        mock_linked_account = Mock(id="link123")
        mock_link_account.return_value = mock_linked_account

        # Store valid state
        provider = OAuthProvider.GOOGLE
        state = "valid_state_123"
        code = "auth_code_123"
        redirect_uri = "https://example.com/callback"
        oauth_service._store_oauth_state(state, provider, redirect_uri)

        # Handle callback
        access_token, is_new_user = await oauth_service.handle_oauth_callback(
            provider, code, state, redirect_uri
        )

        # Verify results
        assert access_token == "access_token_123"
        assert is_new_user is True
        assert oauth_service._cached_oauth_user_info == sample_oauth_user_info

        # Verify all methods were called correctly
        mock_provider.exchange_code_for_token.assert_called_once_with(code, redirect_uri)
        mock_provider.get_user_info.assert_called_once_with("access_token_123")
        mock_find_user.assert_called_once_with(sample_oauth_user_info)
        mock_link_account.assert_called_once_with(sample_user.id, sample_oauth_user_info)

    @pytest.mark.asyncio
    @patch("src.auth.oauth_service.OAuthProviderFactory.create_provider")
    async def test_handle_oauth_callback_invalid_state(self, mock_create_provider, oauth_service):
        """Test OAuth callback handling with invalid state."""
        provider = OAuthProvider.GOOGLE
        state = "invalid_state_123"
        code = "auth_code_123"
        redirect_uri = "https://example.com/callback"

        # Don't store the state (making it invalid)

        with pytest.raises(ValueError, match="Invalid or expired state parameter"):
            await oauth_service.handle_oauth_callback(provider, code, state, redirect_uri)

    @pytest.mark.asyncio
    @patch("src.auth.oauth_service.OAuthProviderFactory.create_provider")
    async def test_handle_oauth_callback_token_exchange_failure(
        self, mock_create_provider, oauth_service
    ):
        """Test OAuth callback handling when token exchange fails."""
        # Mock provider that fails token exchange
        mock_provider = AsyncMock()
        mock_provider.exchange_code_for_token.side_effect = Exception("Token exchange failed")
        mock_create_provider.return_value = mock_provider

        # Store valid state
        provider = OAuthProvider.GOOGLE
        state = "valid_state_123"
        code = "invalid_code_123"
        redirect_uri = "https://example.com/callback"
        oauth_service._store_oauth_state(state, provider, redirect_uri)

        with pytest.raises(Exception, match="Token exchange failed"):
            await oauth_service.handle_oauth_callback(provider, code, state, redirect_uri)

    @pytest.mark.asyncio
    @patch("src.auth.oauth_service.OAuthProviderFactory.create_provider")
    async def test_handle_oauth_callback_user_info_failure(
        self, mock_create_provider, oauth_service
    ):
        """Test OAuth callback handling when user info retrieval fails."""
        # Mock provider that succeeds token exchange but fails user info
        mock_provider = AsyncMock()
        mock_provider.exchange_code_for_token.return_value = "access_token_123"
        mock_provider.get_user_info.side_effect = Exception("User info retrieval failed")
        mock_create_provider.return_value = mock_provider

        # Store valid state
        provider = OAuthProvider.GOOGLE
        state = "valid_state_123"
        code = "auth_code_123"
        redirect_uri = "https://example.com/callback"
        oauth_service._store_oauth_state(state, provider, redirect_uri)

        with pytest.raises(Exception, match="User info retrieval failed"):
            await oauth_service.handle_oauth_callback(provider, code, state, redirect_uri)
