"""Comprehensive tests for enhanced session manager with authentication and persistence.

This test module ensures the session manager meets CLAUDE.md requirements for
production-ready session handling, authentication, and cookie persistence.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from src.core.exceptions import ConfigurationError, FetchError
from src.utils.session_manager import (
    EnhancedSessionManager,
    PersistentCookieJar,
    SessionConfig,
    create_session,
)


class TestSessionConfig:
    """Test suite for SessionConfig validation and defaults."""

    def test_session_config_defaults(self):
        """Test SessionConfig uses proper defaults."""
        config = SessionConfig()

        assert config.max_concurrent_connections == 10  # From CONSTANTS.MAX_CONCURRENT
        assert config.connection_timeout == 30.0  # From CONSTANTS.DEFAULT_TIMEOUT
        assert config.total_timeout == 30.0
        assert config.read_timeout == 30.0
        assert config.keepalive_timeout == 30.0
        assert config.save_cookies is True
        assert config.load_cookies is True
        assert config.auth_type == "basic"
        assert config.verify_ssl is True
        assert config.max_redirects == 10

    def test_session_config_validation(self):
        """Test SessionConfig parameter validation."""
        # Invalid max_concurrent_connections
        with pytest.raises(ValueError, match="max_concurrent_connections must be at least 1"):
            SessionConfig(max_concurrent_connections=0)

        # Invalid connection_timeout
        with pytest.raises(ValueError, match="connection_timeout must be positive"):
            SessionConfig(connection_timeout=0)

        # Invalid total_timeout
        with pytest.raises(ValueError, match="total_timeout must be positive"):
            SessionConfig(total_timeout=-1)

        # Invalid auth_type
        with pytest.raises(ValueError, match="auth_type must be"):
            SessionConfig(auth_type="invalid")

        # Basic auth with missing credentials
        with pytest.raises(ValueError, match="Both username and password required"):
            SessionConfig(auth_type="basic", username="user")

        # Bearer auth without token
        with pytest.raises(ValueError, match="bearer_token required"):
            SessionConfig(auth_type="bearer")

    def test_session_config_valid_auth_configurations(self):
        """Test valid authentication configurations."""
        # Basic auth with both credentials
        config = SessionConfig(auth_type="basic", username="user", password="pass")
        assert config.username == "user"
        assert config.password == "pass"

        # Bearer auth with token
        config = SessionConfig(auth_type="bearer", bearer_token="token123")
        assert config.bearer_token == "token123"

        # Custom auth (no validation required)
        config = SessionConfig(auth_type="custom")
        assert config.auth_type == "custom"


class TestPersistentCookieJar:
    """Test suite for persistent cookie storage."""

    def test_cookie_jar_initialization(self, tmp_path):
        """Test cookie jar initialization."""
        cookie_path = tmp_path / "test_cookies.json"
        jar = PersistentCookieJar(cookie_path)

        assert jar.file_path == cookie_path
        assert jar.cookies == {}
        assert cookie_path.parent.exists()

    def test_save_and_load_cookies(self, tmp_path):
        """Test cookie save and load functionality."""
        cookie_path = tmp_path / "test_cookies.json"
        jar = PersistentCookieJar(cookie_path)

        # Create mock cookies with get method
        cookie1 = Mock()
        cookie1.get.side_effect = lambda key, default=None: {
            "name": "session_id",
            "value": "abc123",
            "domain": "example.com",
            "path": "/",
            "expires": None,
            "secure": True,
            "httponly": True,
        }.get(key, default)

        cookie2 = Mock()
        cookie2.get.side_effect = lambda key, default=None: {
            "name": "preferences",
            "value": "theme=dark",
            "domain": ".example.com",
            "path": "/",
            "expires": None,
            "secure": False,
            "httponly": False,
        }.get(key, default)

        # Create mock aiohttp cookie jar
        mock_cookie_jar = Mock()
        mock_cookie_jar.__iter__ = Mock(return_value=iter([cookie1, cookie2]))

        # Save cookies
        jar.save_cookies(mock_cookie_jar)

        # Verify file was created
        assert cookie_path.exists()

        # Load cookies and verify
        loaded_cookies = jar.load_cookies()

        assert "example.com" in loaded_cookies
        assert "session_id" in loaded_cookies["example.com"]
        assert loaded_cookies["example.com"]["session_id"]["value"] == "abc123"
        assert loaded_cookies["example.com"]["session_id"]["secure"] is True

        assert ".example.com" in loaded_cookies
        assert "preferences" in loaded_cookies[".example.com"]
        assert loaded_cookies[".example.com"]["preferences"]["value"] == "theme=dark"

    def test_load_nonexistent_cookies(self, tmp_path):
        """Test loading cookies when file doesn't exist."""
        cookie_path = tmp_path / "nonexistent.json"
        jar = PersistentCookieJar(cookie_path)

        cookies = jar.load_cookies()
        assert cookies == {}

    def test_load_invalid_cookie_file(self, tmp_path):
        """Test loading cookies from corrupted file."""
        cookie_path = tmp_path / "invalid.json"
        cookie_path.write_text("invalid json content")

        jar = PersistentCookieJar(cookie_path)
        cookies = jar.load_cookies()
        assert cookies == {}

    def test_expired_cookie_filtering(self, tmp_path):
        """Test filtering of expired cookies during load."""
        import time

        cookie_path = tmp_path / "test_cookies.json"

        # Create cookie data with expired and valid cookies
        cookie_data = {
            "example.com": {
                "expired_cookie": {
                    "name": "expired_cookie",
                    "value": "old_value",
                    "expires": time.time() - 3600,  # Expired 1 hour ago
                },
                "valid_cookie": {
                    "name": "valid_cookie",
                    "value": "current_value",
                    "expires": time.time() + 3600,  # Expires in 1 hour
                },
            }
        }

        with open(cookie_path, "w") as f:
            json.dump(cookie_data, f)

        jar = PersistentCookieJar(cookie_path)
        loaded_cookies = jar.load_cookies()

        # Only valid cookie should be loaded
        assert "example.com" in loaded_cookies
        assert "valid_cookie" in loaded_cookies["example.com"]
        assert "expired_cookie" not in loaded_cookies["example.com"]


class TestEnhancedSessionManager:
    """Test suite for EnhancedSessionManager."""

    @pytest.fixture
    def session_config(self):
        """Create test session configuration."""
        return SessionConfig(
            max_concurrent_connections=5,
            total_timeout=10.0,
            user_agent="Test Agent",
            save_cookies=False,  # Disable for most tests
        )

    def test_session_manager_initialization(self, session_config):
        """Test session manager initialization."""
        manager = EnhancedSessionManager(
            "https://example.com", config=session_config, session_name="test"
        )

        assert manager.base_url == "https://example.com"
        assert manager.domain == "example.com"
        assert manager.session_name == "test"
        assert manager.config == session_config

    def test_url_validation(self, session_config):
        """Test URL validation and normalization."""
        # Valid URLs
        manager = EnhancedSessionManager("https://example.com", session_config)
        assert manager.base_url == "https://example.com"

        # URL without protocol should get https prefix
        manager = EnhancedSessionManager("example.com", session_config)
        assert manager.base_url == "https://example.com"

        # Invalid URLs should raise error
        with pytest.raises(ConfigurationError, match="URL must be a non-empty string"):
            EnhancedSessionManager("", session_config)

        with pytest.raises(ConfigurationError, match="Invalid URL"):
            EnhancedSessionManager("not-a-url", session_config)

    @pytest.mark.asyncio
    async def test_session_creation(self, session_config):
        """Test HTTP session creation with proper configuration."""
        manager = EnhancedSessionManager("https://example.com", session_config)

        session = await manager.get_session()

        assert isinstance(session, aiohttp.ClientSession)
        assert not session.closed
        assert session.headers["User-Agent"] == "Test Agent"

        # Clean up
        await manager.close()

    @pytest.mark.asyncio
    async def test_session_reuse(self, session_config):
        """Test that get_session returns the same session instance."""
        manager = EnhancedSessionManager("https://example.com", session_config)

        session1 = await manager.get_session()
        session2 = await manager.get_session()

        assert session1 is session2

        await manager.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, session_config):
        """Test async context manager functionality."""
        async with EnhancedSessionManager("https://example.com", session_config) as session:
            assert isinstance(session, aiohttp.ClientSession)
            assert not session.closed

        # Session should be closed after context

    @pytest.mark.asyncio
    async def test_cookie_persistence_setup(self, tmp_path, session_config):
        """Test cookie persistence configuration."""
        cookie_path = tmp_path / "test_cookies.json"
        config = SessionConfig(cookie_jar_path=cookie_path, save_cookies=True, load_cookies=True)

        manager = EnhancedSessionManager("https://example.com", config)
        assert manager.persistent_jar is not None

        session = await manager.get_session()
        assert manager.cookie_jar is not None

        await manager.close()

    @pytest.mark.asyncio
    async def test_basic_auth_configuration(self):
        """Test basic authentication configuration detection."""
        config = SessionConfig(auth_type="basic", username="testuser", password="testpass")

        manager = EnhancedSessionManager("https://example.com", config)
        assert manager._has_auth_config() is True

    @pytest.mark.asyncio
    async def test_bearer_auth_configuration(self):
        """Test bearer token authentication configuration."""
        config = SessionConfig(auth_type="bearer", bearer_token="test_token_123")

        manager = EnhancedSessionManager("https://example.com", config)
        assert manager._has_auth_config() is True

    @pytest.mark.asyncio
    async def test_make_request_url_handling(self, session_config):
        """Test make_request URL handling (relative and absolute)."""
        manager = EnhancedSessionManager("https://example.com", session_config)

        with patch.object(manager, "get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Test relative URL
            await manager.make_request("GET", "/api/test")
            mock_session.request.assert_called_with("GET", "https://example.com/api/test")

            # Test absolute URL
            await manager.make_request("GET", "https://other.com/api")
            mock_session.request.assert_called_with("GET", "https://other.com/api")

    @pytest.mark.asyncio
    async def test_authentication_properties(self, session_config):
        """Test authentication state properties."""
        manager = EnhancedSessionManager("https://example.com", session_config)

        assert manager.is_authenticated is False

        # Simulate authentication
        manager._is_authenticated = True
        assert manager.is_authenticated is True

    def test_metrics_collection(self, session_config):
        """Test session metrics collection."""
        manager = EnhancedSessionManager("https://example.com", session_config, "test_session")

        metrics = manager.metrics

        assert metrics["domain"] == "example.com"
        assert metrics["session_name"] == "test_session"
        assert metrics["is_authenticated"] is False
        assert metrics["config"]["max_connections"] == 5
        assert metrics["config"]["timeout"] == 10.0

    @pytest.mark.asyncio
    async def test_session_close_with_cookie_save(self, tmp_path):
        """Test session closing with cookie persistence."""
        cookie_path = tmp_path / "test_cookies.json"
        config = SessionConfig(cookie_jar_path=cookie_path, save_cookies=True)

        manager = EnhancedSessionManager("https://example.com", config)
        session = await manager.get_session()

        # Mock cookie jar with cookies
        manager.cookie_jar = Mock()
        manager.cookie_jar.__iter__ = Mock(
            return_value=iter([{"name": "test", "value": "value", "domain": "example.com"}])
        )

        with patch.object(session, "close", new_callable=AsyncMock) as mock_close:
            await manager.close()
            mock_close.assert_called_once()


class TestSessionManagerAuthentication:
    """Test suite for authentication functionality."""

    @pytest.mark.asyncio
    async def test_wordpress_form_authentication(self):
        """Test WordPress form-based authentication."""
        config = SessionConfig(auth_type="basic", username="testuser", password="testpass")

        manager = EnhancedSessionManager("https://wordpress-site.com", config)

        # Mock session and responses
        mock_session = AsyncMock(spec=aiohttp.ClientSession)

        # Mock login page response
        mock_login_response = AsyncMock()
        mock_login_response.text.return_value = """
        <form id="loginform" action="/wp-login.php" method="post">
            <input type="hidden" name="redirect_to" value="/" />
            <input name="log" type="text" />
            <input name="pwd" type="password" />
        </form>
        """
        mock_login_response.__aenter__.return_value = mock_login_response

        # Mock login submission response
        mock_submit_response = AsyncMock()
        mock_submit_response.status = 200
        mock_submit_response.url = Mock()
        mock_submit_response.url.__str__ = Mock(return_value="https://wordpress-site.com/wp-admin/")
        mock_submit_response.__aenter__.return_value = mock_submit_response

        # Configure session mocks
        mock_session.get.return_value = mock_login_response
        mock_session.post.return_value = mock_submit_response

        manager._session = mock_session

        # Test authentication
        await manager._perform_basic_auth()

        # Verify login form was requested
        mock_session.get.assert_called_with("https://wordpress-site.com/wp-login.php")

        # Verify form was submitted with credentials
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["log"] == "testuser"
        assert call_args[1]["data"]["pwd"] == "testpass"

    @pytest.mark.asyncio
    async def test_bearer_token_authentication(self):
        """Test bearer token authentication."""
        config = SessionConfig(auth_type="bearer", bearer_token="test_bearer_token_123")

        manager = EnhancedSessionManager("https://api.example.com", config)

        # Mock session
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.headers = {}

        # Mock validation response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_session.get.return_value = mock_response

        manager._session = mock_session

        # Test bearer authentication
        await manager._perform_bearer_auth()

        # Verify authorization header was set
        assert mock_session.headers["Authorization"] == "Bearer test_bearer_token_123"

        # Verify validation request was made
        mock_session.get.assert_called_with("https://api.example.com")

    @pytest.mark.asyncio
    async def test_authentication_validation_success(self):
        """Test successful authentication validation."""
        config = SessionConfig(auth_type="basic", username="user", password="pass")
        manager = EnhancedSessionManager("https://example.com", config)
        manager._is_authenticated = True

        # Mock session with successful response using aioresponses pattern
        mock_session = AsyncMock()
        mock_response = Mock()
        mock_response.status = 200
        mock_response.content_type = "text/html"
        mock_response.text = AsyncMock(return_value="<html>Dashboard content</html>")

        # Create async context manager mock
        async def mock_get(*args, **kwargs):
            return mock_response

        mock_session.get = Mock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        manager._session = mock_session

        result = await manager.validate_authentication()
        assert result is True
        assert manager._auth_validated is True

    @pytest.mark.asyncio
    async def test_authentication_validation_failure(self):
        """Test failed authentication validation."""
        config = SessionConfig(auth_type="basic", username="user", password="pass")
        manager = EnhancedSessionManager("https://example.com", config)
        manager._is_authenticated = True

        # Mock session with login redirect response
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 302
        mock_response.headers = {"Location": "https://example.com/wp-login.php"}
        mock_response.__aenter__.return_value = mock_response
        mock_session.get.return_value = mock_response

        manager._session = mock_session

        result = await manager.validate_authentication()
        assert result is False


class TestUtilityFunctions:
    """Test suite for utility functions."""

    @pytest.mark.asyncio
    async def test_create_session_function(self):
        """Test create_session utility function."""
        with patch("src.utils.session_manager.EnhancedSessionManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager

            config = SessionConfig()
            result = await create_session("https://example.com", config, "test")

            mock_manager_class.assert_called_once_with("https://example.com", config, "test")
            mock_manager.get_session.assert_called_once()
            assert result == mock_manager


@pytest.mark.integration
class TestSessionManagerIntegration:
    """Integration tests for session manager with real HTTP scenarios."""

    @pytest.mark.asyncio
    async def test_session_with_cookies_integration(self, tmp_path):
        """Test session manager with cookie persistence in integration scenario."""
        cookie_path = tmp_path / "integration_cookies.json"
        config = SessionConfig(
            cookie_jar_path=cookie_path,
            save_cookies=True,
            load_cookies=True,
            max_concurrent_connections=2,
        )

        # First session - establish cookies
        manager1 = EnhancedSessionManager("https://httpbin.org", config, "integration_test")

        async with manager1 as session:
            # Make a request that sets cookies
            try:
                response = await session.get("/cookies/set/test_cookie/test_value")
                assert response.status in (200, 302)  # httpbin redirects after setting cookies
            except aiohttp.ClientError:
                # Skip if httpbin is not available
                pytest.skip("httpbin.org not available for integration test")

        # Verify cookie file was created
        assert cookie_path.exists()

        # Second session - should load existing cookies
        manager2 = EnhancedSessionManager("https://httpbin.org", config, "integration_test")

        async with manager2 as session:
            # Verify cookies were loaded
            assert manager2.cookie_jar is not None

    @pytest.mark.asyncio
    async def test_session_manager_error_handling(self):
        """Test session manager error handling with invalid configurations."""
        # Test with invalid URL
        with pytest.raises(ConfigurationError):
            EnhancedSessionManager("invalid-url", SessionConfig())

        # Test authentication failure scenario
        config = SessionConfig(auth_type="bearer", bearer_token="invalid_token")
        manager = EnhancedSessionManager("https://httpbin.org", config)

        # Mock failed authentication
        with patch.object(manager, "_perform_bearer_auth", side_effect=FetchError("Auth failed")):
            with pytest.raises(FetchError):
                await manager.get_session()
