"""Comprehensive tests for authentication service - MANDATORY TEST_BUILDING.md compliance.

This module tests authentication service functionality with complete coverage:
- AuthenticationService initialization
- BasicAuthStrategy HTTP basic auth
- BasicAuthStrategy WordPress form login
- BearerTokenStrategy authentication
- Authentication validation
- Strategy configuration
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive authentication scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.core.exceptions import FetchError
from src.utils.session.authentication_service import (
    AuthenticationService,
    BasicAuthStrategy,
    BearerTokenStrategy,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


def _create_async_context_manager(response: AsyncMock) -> MagicMock:
    """Helper to create proper async context manager for aiohttp responses."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


@pytest.fixture
def mock_session() -> AsyncMock:
    """Factory for mock aiohttp session - DRY principle."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.headers = {}
    return session


@pytest.fixture
def wordpress_login_html() -> str:
    """Factory for WordPress login HTML - DRY principle."""
    return """
    <html>
        <body>
            <form id="loginform" action="/wp-login.php" method="post">
                <input type="text" name="log" />
                <input type="password" name="pwd" />
                <input type="hidden" name="redirect_to" value="" />
                <input type="hidden" name="testcookie" value="1" />
                <input type="submit" name="wp-submit" value="Log In" />
            </form>
        </body>
    </html>
    """


@pytest.fixture
def successful_login_response() -> AsyncMock:
    """Factory for successful login response - DRY principle."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.url = MagicMock()
    response.url.__str__ = MagicMock(return_value="http://example.com/wp-admin/")
    return response


@pytest.fixture
def failed_login_response() -> AsyncMock:
    """Factory for failed login response - DRY principle."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.url = MagicMock()
    response.url.__str__ = MagicMock(return_value="http://example.com/wp-login.php?error=1")
    return response


# ============================================================================
# BasicAuthStrategy Tests
# ============================================================================


@pytest.mark.unit
class TestBasicAuthStrategy:
    """Tests for BasicAuthStrategy class."""

    def test_initialization(self) -> None:
        """Test BasicAuthStrategy initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        username = "test_user"
        password = "test_password"

        # Act - MANDATORY
        strategy = BasicAuthStrategy(username, password)

        # Assert - MANDATORY
        assert strategy.username == username
        assert strategy.password == password

    @pytest.mark.asyncio
    async def test_authenticate_wordpress_form_success(
        self,
        mock_session: AsyncMock,
        wordpress_login_html: str,
        successful_login_response: AsyncMock,
    ) -> None:
        """Test authenticate() with WordPress form success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")
        base_url = "http://example.com"

        # Mock login page response
        login_page_response = AsyncMock()
        login_page_response.status = 200
        login_page_response.text = AsyncMock(return_value=wordpress_login_html)

        # Configure mock session with proper async context managers
        mock_session.get = MagicMock(
            return_value=_create_async_context_manager(login_page_response)
        )
        mock_session.post = MagicMock(
            return_value=_create_async_context_manager(successful_login_response)
        )

        # Act - MANDATORY
        result = await strategy.authenticate(mock_session, base_url)

        # Assert - MANDATORY
        assert result is True
        mock_session.get.assert_called_once()
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_http_basic_auth_fallback(self, mock_session: AsyncMock) -> None:
        """Test authenticate() HTTP basic auth fallback - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")
        base_url = "http://example.com"

        # Mock WordPress form login failure (404)
        login_page_response = AsyncMock()
        login_page_response.status = 404

        # Mock successful HTTP basic auth
        basic_auth_response = AsyncMock()
        basic_auth_response.status = 200

        mock_session.get = MagicMock(
            side_effect=[
                _create_async_context_manager(login_page_response),  # WordPress form fails
                _create_async_context_manager(basic_auth_response),  # HTTP basic succeeds
            ]
        )

        # Act - MANDATORY
        result = await strategy.authenticate(mock_session, base_url)

        # Assert - MANDATORY
        assert result is True

    @pytest.mark.asyncio
    async def test_extract_login_form_data(self, wordpress_login_html: str) -> None:
        """Test _extract_login_form_data() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("testuser", "testpass")
        base_url = "http://example.com"

        # Act - MANDATORY
        form_data = strategy._extract_login_form_data(wordpress_login_html, base_url)

        # Assert - MANDATORY
        assert form_data is not None
        assert form_data["log"] == "testuser"
        assert form_data["pwd"] == "testpass"
        assert form_data["wp-submit"] == "Log In"
        # HTML fixture has empty redirect_to value which overrides base_url
        assert form_data["redirect_to"] == ""
        assert form_data["testcookie"] == "1"

    @pytest.mark.asyncio
    async def test_extract_login_form_data_no_form(self) -> None:
        """Test _extract_login_form_data() with no form - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")
        html_without_form = "<html><body>No login form here</body></html>"

        # Act - MANDATORY
        form_data = strategy._extract_login_form_data(html_without_form, "http://example.com")

        # Assert - MANDATORY
        assert form_data is None

    @pytest.mark.asyncio
    async def test_try_wordpress_form_login_network_error(self, mock_session: AsyncMock) -> None:
        """Test _try_wordpress_form_login() with network error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")

        # Configure mock to raise error within context manager
        error_response = AsyncMock()
        error_response.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
        mock_session.get = MagicMock(return_value=error_response)

        # Act - MANDATORY
        # _try_wordpress_form_login catches exceptions and returns False
        result = await strategy._try_wordpress_form_login(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is False

    @pytest.mark.asyncio
    async def test_try_http_basic_auth_success(self, mock_session: AsyncMock) -> None:
        """Test _try_http_basic_auth() success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")
        response = AsyncMock()
        response.status = 200
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act - MANDATORY
        result = await strategy._try_http_basic_auth(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is True

    @pytest.mark.asyncio
    async def test_try_http_basic_auth_failure(self, mock_session: AsyncMock) -> None:
        """Test _try_http_basic_auth() failure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")
        response = AsyncMock()
        response.status = 401
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act - MANDATORY
        result = await strategy._try_http_basic_auth(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# BearerTokenStrategy Tests
# ============================================================================


@pytest.mark.unit
class TestBearerTokenStrategy:
    """Tests for BearerTokenStrategy class."""

    def test_initialization(self) -> None:
        """Test BearerTokenStrategy initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        token = "test_bearer_token"

        # Act - MANDATORY
        strategy = BearerTokenStrategy(token)

        # Assert - MANDATORY
        assert strategy.token == token

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_session: AsyncMock) -> None:
        """Test authenticate() success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BearerTokenStrategy("valid_token")
        response = AsyncMock()
        response.status = 200
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act - MANDATORY
        result = await strategy.authenticate(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is True
        assert mock_session.headers["Authorization"] == "Bearer valid_token"

    @pytest.mark.asyncio
    async def test_authenticate_unauthorized(self, mock_session: AsyncMock) -> None:
        """Test authenticate() with 401 response - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BearerTokenStrategy("invalid_token")
        response = AsyncMock()
        response.status = 401
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act & Assert - MANDATORY
        # 401 status raises FetchError (authentication failure, not network error)
        with pytest.raises(FetchError, match="Bearer token authentication failed - unauthorized"):
            await strategy.authenticate(mock_session, "http://example.com")

    @pytest.mark.asyncio
    async def test_authenticate_other_error(self, mock_session: AsyncMock) -> None:
        """Test authenticate() with other HTTP error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BearerTokenStrategy("token")
        response = AsyncMock()
        response.status = 500
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act & Assert - MANDATORY
        # 500 status raises FetchError (server error, not network error)
        with pytest.raises(FetchError, match="Bearer token validation failed - status 500"):
            await strategy.authenticate(mock_session, "http://example.com")

    @pytest.mark.asyncio
    async def test_authenticate_network_error(self, mock_session: AsyncMock) -> None:
        """Test authenticate() with network error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = BearerTokenStrategy("token")

        # Configure mock to raise error within context manager
        error_response = AsyncMock()
        error_response.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Network failure"))
        mock_session.get = MagicMock(return_value=error_response)

        # Act & Assert - MANDATORY
        # ClientError is caught by @network_error_handler decorator and converted to RuntimeError
        with pytest.raises(
            RuntimeError, match="Network operation failed: perform bearer authentication"
        ):
            await strategy.authenticate(mock_session, "http://example.com")


# ============================================================================
# AuthenticationService Tests
# ============================================================================


@pytest.mark.unit
class TestAuthenticationService:
    """Tests for AuthenticationService class."""

    def test_initialization(self) -> None:
        """Test AuthenticationService initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        service = AuthenticationService()

        # Assert - MANDATORY
        assert service._strategy is None
        assert service._is_authenticated is False
        assert service._auth_validated is False

    def test_set_basic_auth(self) -> None:
        """Test set_basic_auth() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()

        # Act - MANDATORY
        service.set_basic_auth("user", "pass")

        # Assert - MANDATORY
        assert service._strategy is not None
        assert isinstance(service._strategy, BasicAuthStrategy)
        assert service._is_authenticated is False

    def test_set_bearer_auth(self) -> None:
        """Test set_bearer_auth() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()

        # Act - MANDATORY
        service.set_bearer_auth("token123")

        # Assert - MANDATORY
        assert service._strategy is not None
        assert isinstance(service._strategy, BearerTokenStrategy)
        assert service._is_authenticated is False

    def test_reset_auth_state_on_strategy_change(self) -> None:
        """Test auth state resets when strategy changes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        service._is_authenticated = True
        service._auth_validated = True

        # Act - MANDATORY
        service.set_basic_auth("new_user", "new_pass")

        # Assert - MANDATORY
        assert service._is_authenticated is False
        assert service._auth_validated is False

    @pytest.mark.asyncio
    async def test_authenticate_no_strategy(self, mock_session: AsyncMock) -> None:
        """Test authenticate() with no strategy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()

        # Act & Assert - MANDATORY
        with pytest.raises(RuntimeError, match="No authentication strategy configured"):
            await service.authenticate(mock_session, "http://example.com")

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_session: AsyncMock) -> None:
        """Test authenticate() success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        service.set_basic_auth("user", "pass")

        # Mock successful authentication
        with patch.object(service._strategy, "authenticate", return_value=True):
            # Act - MANDATORY
            result = await service.authenticate(mock_session, "http://example.com")

            # Assert - MANDATORY
            assert result is True
            assert service._is_authenticated is True

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, mock_session: AsyncMock) -> None:
        """Test authenticate() failure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        service.set_basic_auth("user", "wrong_pass")

        # Mock failed authentication
        with patch.object(service._strategy, "authenticate", return_value=False):
            # Act - MANDATORY
            result = await service.authenticate(mock_session, "http://example.com")

            # Assert - MANDATORY
            assert result is False
            assert service._is_authenticated is False

    @pytest.mark.asyncio
    async def test_validate_authentication_not_authenticated(self, mock_session: AsyncMock) -> None:
        """Test validate_authentication() when not authenticated - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()

        # Act - MANDATORY
        result = await service.validate_authentication(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_authentication_already_validated(self, mock_session: AsyncMock) -> None:
        """Test validate_authentication() when already validated - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        service._is_authenticated = True
        service._auth_validated = True

        # Act - MANDATORY
        result = await service.validate_authentication(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_authentication_performs_validation(
        self, mock_session: AsyncMock
    ) -> None:
        """Test validate_authentication() performs validation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        service._is_authenticated = True
        service._auth_validated = False

        # Mock successful validation
        response = AsyncMock()
        response.status = 200
        response.content_type = "text/html"
        response.text = AsyncMock(return_value="<html>Dashboard content</html>")
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act - MANDATORY
        result = await service.validate_authentication(mock_session, "http://example.com")

        # Assert - MANDATORY
        assert result is True
        assert service._auth_validated is True

    @pytest.mark.asyncio
    async def test_test_protected_url_redirect_to_login(self, mock_session: AsyncMock) -> None:
        """Test _test_protected_url() with redirect to login - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        response = AsyncMock()
        response.status = 302
        response.headers = {"Location": "http://example.com/wp-login.php"}
        mock_session.get = MagicMock(return_value=_create_async_context_manager(response))

        # Act - MANDATORY
        result = await service._test_protected_url(mock_session, "http://example.com/wp-admin/")

        # Assert - MANDATORY
        assert result is False  # Redirect to login indicates not authenticated

    @pytest.mark.asyncio
    async def test_check_response_content_authenticated(self) -> None:
        """Test _check_response_content() with authenticated content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        response = AsyncMock()
        response.content_type = "text/html"
        response.text = AsyncMock(return_value="<html>Dashboard</html>")

        # Act - MANDATORY
        result = await service._check_response_content(response)

        # Assert - MANDATORY
        assert result is True

    @pytest.mark.asyncio
    async def test_check_response_content_unauthenticated(self) -> None:
        """Test _check_response_content() with login page - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()
        response = AsyncMock()
        response.content_type = "text/html"
        response.text = AsyncMock(return_value="<html>wp-login form</html>")

        # Act - MANDATORY
        result = await service._check_response_content(response)

        # Assert - MANDATORY
        assert result is False

    def test_is_authenticated_property(self) -> None:
        """Test is_authenticated property - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()

        # Act & Assert - MANDATORY
        assert service.is_authenticated is False

        service._is_authenticated = True
        assert service.is_authenticated is True

    def test_has_strategy_property(self) -> None:
        """Test has_strategy property - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = AuthenticationService()

        # Act & Assert - MANDATORY
        assert service.has_strategy is False

        service.set_basic_auth("user", "pass")
        assert service.has_strategy is True


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestAuthenticationServicePerformance:
    """MANDATORY performance tests for authentication service operations."""

    def test_service_initialization_performance(self) -> None:
        """MANDATORY performance test - service creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            AuthenticationService()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_strategy_initialization_performance(self) -> None:
        """MANDATORY performance test - strategy creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            BasicAuthStrategy("user", "pass")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_extract_form_data_performance(self, wordpress_login_html: str) -> None:
        """MANDATORY performance test - form data extraction speed."""
        # Arrange - MANDATORY
        strategy = BasicAuthStrategy("user", "pass")
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            strategy._extract_login_form_data(wordpress_login_html, "http://example.com")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per extraction
        assert execution_time < 10.0  # Total <10s for 1000 extractions
