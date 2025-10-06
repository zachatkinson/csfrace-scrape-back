"""Comprehensive tests for enhanced session manager - MANDATORY TEST_BUILDING.md compliance.

This module tests enhanced session manager functionality with complete coverage:
- SessionConfig initialization and validation
- EnhancedSessionManager initialization
- Session creation and management
- URL validation
- Authentication integration
- Cookie persistence integration
- Async context manager support
- Request making
- Metrics and monitoring
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive session manager scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from src.core.exceptions import ConfigurationError
from src.utils.session_manager import EnhancedSessionManager, SessionConfig, create_session

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def valid_base_url() -> str:
    """Factory for valid base URL - DRY principle."""
    return "https://example.com"


@pytest.fixture
def basic_session_config() -> SessionConfig:
    """Factory for basic session config - DRY principle."""
    return SessionConfig()


@pytest.fixture
def authenticated_session_config(tmp_path: Path) -> SessionConfig:
    """Factory for authenticated session config - DRY principle."""
    return SessionConfig(
        username="test_user",
        password="test_password",
        auth_type="basic",
        cookie_jar_path=tmp_path / "cookies.json",
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """Factory for mock ClientSession - DRY principle."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.request = AsyncMock()
    session.close = AsyncMock()
    return session


# ============================================================================
# SessionConfig Tests
# ============================================================================


@pytest.mark.unit
class TestSessionConfig:
    """Tests for SessionConfig dataclass."""

    def test_initialization_defaults(self) -> None:
        """Test SessionConfig initialization with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        config = SessionConfig()

        # Assert - MANDATORY
        assert config.max_concurrent_connections == 10
        assert config.connection_timeout == 30.0
        assert config.total_timeout == 30.0
        assert config.save_cookies is True
        assert config.auth_type == "basic"

    def test_initialization_custom_values(self) -> None:
        """Test SessionConfig with custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        config = SessionConfig(
            max_concurrent_connections=20,
            connection_timeout=60.0,
            username="user",
            password="pass",
        )

        # Assert - MANDATORY
        assert config.max_concurrent_connections == 20
        assert config.connection_timeout == 60.0
        assert config.username == "user"
        assert config.password == "pass"

    def test_validation_max_concurrent_connections_negative(self) -> None:
        """Test validation for negative max_concurrent_connections - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="max_concurrent_connections must be at least 1"):
            SessionConfig(max_concurrent_connections=0)

    def test_validation_connection_timeout_negative(self) -> None:
        """Test validation for negative connection_timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="connection_timeout must be positive"):
            SessionConfig(connection_timeout=-1.0)

    def test_validation_total_timeout_negative(self) -> None:
        """Test validation for negative total_timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="total_timeout must be positive"):
            SessionConfig(total_timeout=-1.0)

    def test_validation_invalid_auth_type(self) -> None:
        """Test validation for invalid auth_type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="auth_type must be"):
            SessionConfig(auth_type="invalid")

    def test_validation_basic_auth_missing_username(self) -> None:
        """Test validation for basic auth missing username - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Both username and password required"):
            SessionConfig(auth_type="basic", password="pass")

    def test_validation_basic_auth_missing_password(self) -> None:
        """Test validation for basic auth missing password - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Both username and password required"):
            SessionConfig(auth_type="basic", username="user")

    def test_validation_bearer_auth_missing_token(self) -> None:
        """Test validation for bearer auth missing token - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="bearer_token required"):
            SessionConfig(auth_type="bearer")


# ============================================================================
# EnhancedSessionManager Tests
# ============================================================================


@pytest.mark.unit
class TestEnhancedSessionManager:
    """Tests for EnhancedSessionManager class."""

    def test_initialization_basic(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test EnhancedSessionManager initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (using fixtures)
        # Act - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)

        # Assert - MANDATORY
        assert manager.base_url == valid_base_url
        assert manager.domain == "example.com"
        assert manager._session is None
        assert manager.cookie_persistence is None

    def test_initialization_with_authentication(
        self, valid_base_url: str, authenticated_session_config: SessionConfig
    ) -> None:
        """Test initialization with authentication - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (using fixtures)
        # Act - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, authenticated_session_config)

        # Assert - MANDATORY
        assert manager.auth_service.has_strategy is True
        assert manager.cookie_persistence is not None

    def test_validate_url_valid_https(self) -> None:
        """Test _validate_url() with valid HTTPS URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager.__new__(EnhancedSessionManager)
        url = "https://example.com"

        # Act - MANDATORY
        validated = manager._validate_url(url)

        # Assert - MANDATORY
        assert validated == url

    def test_validate_url_adds_https_prefix(self) -> None:
        """Test _validate_url() adds https prefix - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager.__new__(EnhancedSessionManager)
        url = "example.com"

        # Act - MANDATORY
        validated = manager._validate_url(url)

        # Assert - MANDATORY
        assert validated == "https://example.com"

    def test_validate_url_invalid_empty(self) -> None:
        """Test _validate_url() with empty URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager.__new__(EnhancedSessionManager)

        # Act & Assert - MANDATORY
        with pytest.raises(ConfigurationError, match="URL must be a non-empty string"):
            manager._validate_url("")

    def test_validate_url_invalid_netloc(self) -> None:
        """Test _validate_url() with invalid netloc - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager.__new__(EnhancedSessionManager)

        # Act & Assert - MANDATORY
        with pytest.raises(ConfigurationError, match="Invalid URL"):
            manager._validate_url("not-a-url")

    @pytest.mark.asyncio
    async def test_get_session_creates_session(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test get_session() creates session - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)

        # Act - MANDATORY
        session = await manager.get_session()

        # Assert - MANDATORY
        assert session is not None
        assert isinstance(session, aiohttp.ClientSession)
        assert manager._session is session

    @pytest.mark.asyncio
    async def test_get_session_returns_existing_session(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test get_session() returns existing session - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)
        session1 = await manager.get_session()

        # Act - MANDATORY
        session2 = await manager.get_session()

        # Assert - MANDATORY
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_close_session(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test close() closes session - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)
        session = await manager.get_session()

        # Act - MANDATORY
        await manager.close()

        # Assert - MANDATORY
        assert session.closed

    @pytest.mark.asyncio
    async def test_async_context_manager(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test async context manager support - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)

        # Act - MANDATORY
        async with manager as session:
            # Assert - MANDATORY
            assert session is not None
            assert isinstance(session, aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_make_request_absolute_url(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test make_request() with absolute URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)
        url = "https://example.com/path"

        # Mock session
        with patch.object(manager, "get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.request = AsyncMock(return_value="response")
            mock_get_session.return_value = mock_session

            # Act - MANDATORY
            result = await manager.make_request("GET", url)

            # Assert - MANDATORY
            mock_session.request.assert_called_once_with("GET", url)

    @pytest.mark.asyncio
    async def test_make_request_relative_url(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test make_request() with relative URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)
        relative_url = "/api/endpoint"

        # Mock session
        with patch.object(manager, "get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.request = AsyncMock(return_value="response")
            mock_get_session.return_value = mock_session

            # Act - MANDATORY
            await manager.make_request("GET", relative_url)

            # Assert - MANDATORY
            expected_url = "https://example.com/api/endpoint"
            mock_session.request.assert_called_once_with("GET", expected_url)

    @pytest.mark.asyncio
    async def test_validate_authentication(
        self, valid_base_url: str, authenticated_session_config: SessionConfig
    ) -> None:
        """Test validate_authentication() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, authenticated_session_config)
        session = await manager.get_session()

        # Mock authentication validation
        with patch.object(manager.auth_service, "validate_authentication", return_value=True):
            # Act - MANDATORY
            result = await manager.validate_authentication()

            # Assert - MANDATORY
            assert result is True

    def test_is_authenticated_property(
        self, valid_base_url: str, authenticated_session_config: SessionConfig
    ) -> None:
        """Test is_authenticated property - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, authenticated_session_config)
        manager.auth_service._is_authenticated = True

        # Act & Assert - MANDATORY
        assert manager.is_authenticated is True

    def test_metrics_property(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test metrics property - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config, session_name="test")

        # Act - MANDATORY
        metrics = manager.metrics

        # Assert - MANDATORY
        assert metrics["domain"] == "example.com"
        assert metrics["session_name"] == "test"
        assert "is_authenticated" in metrics
        assert "config" in metrics

    @pytest.mark.asyncio
    async def test_create_session_utility_function(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test create_session() utility function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        manager = await create_session(valid_base_url, basic_session_config)

        # Assert - MANDATORY
        assert isinstance(manager, EnhancedSessionManager)
        assert manager._session is not None


# ============================================================================
# Integration Scenario Tests
# ============================================================================


@pytest.mark.unit
class TestSessionManagerIntegration:
    """Integration scenario tests for session manager."""

    @pytest.mark.asyncio
    async def test_session_with_cookie_persistence(
        self, valid_base_url: str, tmp_path: Path
    ) -> None:
        """Test session with cookie persistence - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cookie_file = tmp_path / "test_cookies.json"
        config = SessionConfig(cookie_jar_path=cookie_file, save_cookies=True, load_cookies=True)
        manager = EnhancedSessionManager(valid_base_url, config)

        # Act - MANDATORY
        session = await manager.get_session()

        # Add a test cookie to the session
        from http.cookies import SimpleCookie

        cookie = SimpleCookie()
        cookie["test_cookie"] = "test_value"
        cookie["test_cookie"]["domain"] = "example.com"
        session.cookie_jar.update_cookies(cookie)

        await manager.close()

        # Assert - MANDATORY
        assert cookie_file.exists()
        # Verify cookie was saved
        import json

        with open(cookie_file) as f:
            saved_cookies = json.load(f)
            assert "example.com" in saved_cookies
            assert "test_cookie" in saved_cookies["example.com"]

    @pytest.mark.asyncio
    async def test_session_lifecycle(
        self, valid_base_url: str, basic_session_config: SessionConfig
    ) -> None:
        """Test complete session lifecycle - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager(valid_base_url, basic_session_config)

        # Act - MANDATORY
        # Create session
        session = await manager.get_session()
        assert not session.closed

        # Close session
        await manager.close()

        # Assert - MANDATORY
        assert session.closed


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestEnhancedSessionManagerPerformance:
    """MANDATORY performance tests for session manager operations."""

    def test_initialization_performance(self, valid_base_url: str) -> None:
        """MANDATORY performance test - manager initialization speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            EnhancedSessionManager(valid_base_url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per creation
        assert execution_time < 1.0  # Total <1s for 1000 creations

    def test_url_validation_performance(self) -> None:
        """MANDATORY performance test - URL validation speed."""
        # Arrange - MANDATORY
        manager = EnhancedSessionManager.__new__(EnhancedSessionManager)
        iterations = 10000
        url = "https://example.com"

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            manager._validate_url(url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per validation
        assert execution_time < 1.0  # Total <1s for 10000 validations

    def test_config_validation_performance(self) -> None:
        """MANDATORY performance test - config validation speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            SessionConfig(
                max_concurrent_connections=10,
                connection_timeout=30.0,
                total_timeout=30.0,
            )

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per validation
        assert execution_time < 1.0  # Total <1s for 1000 validations
