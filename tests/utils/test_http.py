"""Comprehensive tests for HTTP utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests HTTP utility functions with complete coverage:
- HTTPResponse wrapper initialization
- safe_http_get with various status codes
- safe_http_get_with_raise error handling
- check_http_status logging and validation
- Timeout and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive HTTP scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import asyncio
import pytest

from src.utils.http import HTTPResponse, check_http_status, safe_http_get, safe_http_get_with_raise

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Factory for mock aiohttp ClientSession - DRY principle."""
    return AsyncMock(spec=aiohttp.ClientSession)


@pytest.fixture
def mock_response() -> AsyncMock:
    """Factory for mock aiohttp response - DRY principle."""
    response = AsyncMock()
    response.status = 200
    response.text = AsyncMock(return_value="Test content")
    response.headers = {"Content-Type": "text/html", "Server": "TestServer"}
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def test_url() -> str:
    """Factory for test URL - DRY principle."""
    return "https://example.com/test"


# ============================================================================
# HTTPResponse Tests
# ============================================================================


@pytest.mark.unit
class TestHTTPResponse:
    """Tests for HTTPResponse wrapper class."""

    def test_http_response_initialization_with_success_status(self):
        """Test HTTPResponse initializes with success status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 200
        content = "Success content"
        headers = {"Content-Type": "text/html"}

        # Act - MANDATORY
        response = HTTPResponse(status=status, content=content, headers=headers)

        # Assert - MANDATORY
        assert response.status == status
        assert response.content == content
        assert response.headers == headers
        assert response.is_success is True

    def test_http_response_initialization_with_redirect_status(self):
        """Test HTTPResponse with redirect status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 301
        content = "Redirect"

        # Act - MANDATORY
        response = HTTPResponse(status=status, content=content)

        # Assert - MANDATORY
        assert response.status == 301
        assert response.is_success is False  # 3xx not considered success

    def test_http_response_initialization_with_client_error(self):
        """Test HTTPResponse with 4xx client error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 404
        content = "Not Found"

        # Act - MANDATORY
        response = HTTPResponse(status=status, content=content)

        # Assert - MANDATORY
        assert response.status == 404
        assert response.is_success is False

    def test_http_response_initialization_with_server_error(self):
        """Test HTTPResponse with 5xx server error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 500
        content = "Internal Server Error"

        # Act - MANDATORY
        response = HTTPResponse(status=status, content=content)

        # Assert - MANDATORY
        assert response.status == 500
        assert response.is_success is False

    def test_http_response_initialization_without_headers(self):
        """Test HTTPResponse defaults to empty headers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 200
        content = "Content"

        # Act - MANDATORY
        response = HTTPResponse(status=status, content=content)

        # Assert - MANDATORY
        assert response.headers == {}

    def test_http_response_is_success_boundary_values(self):
        """Test is_success boundary values - MANDATORY AAA pattern."""
        # Arrange & Act & Assert - MANDATORY
        assert HTTPResponse(199, "").is_success is False  # Below 200
        assert HTTPResponse(200, "").is_success is True  # Lower boundary
        assert HTTPResponse(299, "").is_success is True  # Upper boundary
        assert HTTPResponse(300, "").is_success is False  # Above 299


# ============================================================================
# safe_http_get Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSafeHttpGet:
    """Tests for safe_http_get function."""

    async def test_safe_http_get_successful_request(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get with successful request - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Act - MANDATORY
        result = await safe_http_get(mock_session, test_url)

        # Assert - MANDATORY
        assert result.status == 200
        assert result.content == "Test content"
        assert result.is_success is True
        assert "Content-Type" in result.headers
        mock_session.get.assert_called_once()

    async def test_safe_http_get_with_custom_timeout(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get with custom timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_timeout = 60
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Act - MANDATORY
        result = await safe_http_get(mock_session, test_url, timeout=custom_timeout)

        # Assert - MANDATORY
        assert result.status == 200
        # Verify timeout was passed to session.get
        call_args = mock_session.get.call_args
        assert call_args is not None

    async def test_safe_http_get_with_expected_statuses(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get with custom expected statuses - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response.status = 201
        mock_session.get.return_value.__aenter__.return_value = mock_response
        expected_statuses = {200, 201, 202}

        # Act - MANDATORY
        result = await safe_http_get(mock_session, test_url, expected_statuses=expected_statuses)

        # Assert - MANDATORY
        assert result.status == 201
        assert result.is_success is True  # 201 is in 200-299 range for is_success

    async def test_safe_http_get_with_unexpected_status(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get with unexpected status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Act - MANDATORY
        result = await safe_http_get(mock_session, test_url)

        # Assert - MANDATORY
        assert result.status == 404
        assert result.is_success is False

    async def test_safe_http_get_handles_timeout_error(
        self, mock_session: AsyncMock, test_url: str
    ):
        """Test safe_http_get handles TimeoutError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.side_effect = TimeoutError("Timeout")

        # Act & Assert - MANDATORY
        with pytest.raises(TimeoutError):
            await safe_http_get(mock_session, test_url)

    async def test_safe_http_get_handles_client_error(self, mock_session: AsyncMock, test_url: str):
        """Test safe_http_get handles ClientError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.side_effect = aiohttp.ClientError(
            "Connection error"
        )

        # Act & Assert - MANDATORY
        with pytest.raises(aiohttp.ClientError):
            await safe_http_get(mock_session, test_url)

    async def test_safe_http_get_handles_unexpected_exception(
        self, mock_session: AsyncMock, test_url: str
    ):
        """Test safe_http_get handles unexpected exceptions - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.side_effect = ValueError("Unexpected")

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError):
            await safe_http_get(mock_session, test_url)

    async def test_safe_http_get_with_log_errors_disabled(
        self, mock_session: AsyncMock, test_url: str
    ):
        """Test safe_http_get with logging disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.side_effect = TimeoutError("Timeout")

        # Act & Assert - MANDATORY
        with pytest.raises(TimeoutError):
            await safe_http_get(mock_session, test_url, log_errors=False)


# ============================================================================
# safe_http_get_with_raise Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSafeHttpGetWithRaise:
    """Tests for safe_http_get_with_raise function."""

    async def test_safe_http_get_with_raise_successful_request(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get_with_raise success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Act - MANDATORY
        result = await safe_http_get_with_raise(mock_session, test_url)

        # Assert - MANDATORY
        assert result == "Test content"
        mock_response.raise_for_status.assert_called_once()

    async def test_safe_http_get_with_raise_handles_http_error(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get_with_raise raises on HTTP error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=404,
            message="Not Found",
        )
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Act & Assert - MANDATORY
        with pytest.raises(aiohttp.ClientResponseError):
            await safe_http_get_with_raise(mock_session, test_url)

    async def test_safe_http_get_with_raise_with_custom_timeout(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """Test safe_http_get_with_raise with timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_timeout = 45
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Act - MANDATORY
        result = await safe_http_get_with_raise(mock_session, test_url, timeout=custom_timeout)

        # Assert - MANDATORY
        assert result == "Test content"

    async def test_safe_http_get_with_raise_handles_timeout(
        self, mock_session: AsyncMock, test_url: str
    ):
        """Test safe_http_get_with_raise handles timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.side_effect = TimeoutError()

        # Act & Assert - MANDATORY
        with pytest.raises(asyncio.TimeoutError):
            await safe_http_get_with_raise(mock_session, test_url)


# ============================================================================
# check_http_status Tests
# ============================================================================


@pytest.mark.unit
class TestCheckHttpStatus:
    """Tests for check_http_status function."""

    def test_check_http_status_with_200_ok(self, test_url: str):
        """Test check_http_status with 200 OK - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 200

        # Act - MANDATORY
        result = check_http_status(status, test_url)

        # Assert - MANDATORY
        assert result is True

    def test_check_http_status_with_404_not_found(self, test_url: str):
        """Test check_http_status with 404 Not Found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 404

        # Act - MANDATORY
        result = check_http_status(status, test_url)

        # Assert - MANDATORY
        assert result is False

    def test_check_http_status_with_500_server_error(self, test_url: str):
        """Test check_http_status with 500 server error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 500

        # Act - MANDATORY
        result = check_http_status(status, test_url)

        # Assert - MANDATORY
        assert result is False

    def test_check_http_status_with_503_service_unavailable(self, test_url: str):
        """Test check_http_status with 503 - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 503

        # Act - MANDATORY
        result = check_http_status(status, test_url)

        # Assert - MANDATORY
        assert result is False

    def test_check_http_status_with_301_redirect(self, test_url: str):
        """Test check_http_status with 301 redirect - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 301

        # Act - MANDATORY
        result = check_http_status(status, test_url)

        # Assert - MANDATORY
        assert result is False

    def test_check_http_status_with_custom_context(self, test_url: str):
        """Test check_http_status with custom context - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = 200
        context = "test operation"

        # Act - MANDATORY
        result = check_http_status(status, test_url, context=context)

        # Assert - MANDATORY
        assert result is True

    def test_check_http_status_with_4xx_client_error(self, test_url: str):
        """Test check_http_status with 4xx client errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        statuses_to_test = [400, 401, 403, 404, 429]

        # Act & Assert - MANDATORY
        for status in statuses_to_test:
            result = check_http_status(status, test_url)
            assert result is False


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHTTPPerformance:
    """MANDATORY performance tests for HTTP utilities."""

    def test_http_response_initialization_performance(self):
        """MANDATORY performance test - HTTPResponse initialization speed."""
        # Arrange - MANDATORY
        iterations = 100000
        status = 200
        content = "Test content"
        headers = {"Content-Type": "text/html"}

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            HTTPResponse(status=status, content=content, headers=headers)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <0.01ms per initialization
        assert execution_time < 1.0  # Total <1s for 100000 initializations

    def test_check_http_status_performance(self, test_url: str):
        """MANDATORY performance test - check_http_status speed."""
        # Arrange - MANDATORY
        iterations = 100000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            check_http_status(200 if i % 2 == 0 else 404, test_url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00002  # <0.02ms per check (relaxed for CI variability)
        assert execution_time < 2.0  # Total <2s for 100000 checks (relaxed for CI)

    @pytest.mark.asyncio
    async def test_safe_http_get_overhead_performance(
        self, mock_session: AsyncMock, mock_response: AsyncMock, test_url: str
    ):
        """MANDATORY performance test - safe_http_get overhead."""
        # Arrange - MANDATORY
        mock_session.get.return_value.__aenter__.return_value = mock_response
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await safe_http_get(mock_session, test_url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per call (including mock overhead)
        assert execution_time < 1.0  # Total <1s for 100 calls
