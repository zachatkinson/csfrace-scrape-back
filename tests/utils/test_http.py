"""Unit tests for HTTP utilities module."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from src.utils.http import (
    HTTPResponse,
    check_http_status,
    safe_http_get,
    safe_http_get_with_raise,
)


class TestHTTPResponse:
    """Test HTTPResponse wrapper class."""

    def test_http_response_initialization(self):
        """Test HTTPResponse initialization."""
        response = HTTPResponse(200, "Success", {"Content-Type": "text/html"})

        assert response.status == 200
        assert response.content == "Success"
        assert response.headers["Content-Type"] == "text/html"
        assert response.is_success is True

    def test_http_response_success_status(self):
        """Test success status detection."""
        success_codes = [200, 201, 204, 299]
        for code in success_codes:
            response = HTTPResponse(code, "")
            assert response.is_success is True

    def test_http_response_failure_status(self):
        """Test failure status detection."""
        failure_codes = [199, 300, 400, 404, 500]
        for code in failure_codes:
            response = HTTPResponse(code, "")
            assert response.is_success is False

    def test_http_response_default_headers(self):
        """Test HTTPResponse with default headers."""
        response = HTTPResponse(200, "Content")
        assert response.headers == {}


@pytest.mark.asyncio
class TestHTTPUtilities:
    """Test HTTP utility functions."""

    @pytest.fixture
    def mock_session(self):
        """Mock aiohttp session."""
        return AsyncMock(spec=aiohttp.ClientSession)

    @pytest.fixture
    def mock_response(self):
        """Mock aiohttp response."""
        response = AsyncMock()
        response.status = 200
        response.text = AsyncMock(return_value="Sample content")
        response.headers = {"Content-Type": "text/html"}
        response.raise_for_status = AsyncMock()
        return response

    async def test_safe_http_get_success(self, mock_session, mock_response):
        """Test successful HTTP GET request."""
        mock_session.get.return_value.__aenter__.return_value = mock_response

        result = await safe_http_get(mock_session, "https://example.com")

        assert isinstance(result, HTTPResponse)
        assert result.status == 200
        assert result.content == "Sample content"
        assert result.headers["Content-Type"] == "text/html"
        assert result.is_success is True

    async def test_safe_http_get_with_timeout(self, mock_session, mock_response):
        """Test HTTP GET request with custom timeout."""
        mock_session.get.return_value.__aenter__.return_value = mock_response

        await safe_http_get(mock_session, "https://example.com", timeout=60)

        # Verify timeout was passed correctly
        mock_session.get.assert_called_once()
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"].total == 60

    async def test_safe_http_get_expected_statuses(self, mock_session):
        """Test HTTP GET with custom expected status codes."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not found")
        mock_response.headers = {}

        mock_session.get.return_value.__aenter__.return_value = mock_response

        result = await safe_http_get(
            mock_session, "https://example.com", expected_statuses={404, 200}
        )

        assert result.status == 404
        assert result.content == "Not found"
        assert result.is_success is False

    async def test_safe_http_get_unexpected_status(self, mock_session):
        """Test HTTP GET with unexpected status code."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server error")
        mock_response.headers = {}

        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Should still return response even with unexpected status
        result = await safe_http_get(mock_session, "https://example.com")

        assert result.status == 500
        assert result.content == "Server error"
        assert result.is_success is False

    async def test_safe_http_get_timeout_error(self, mock_session):
        """Test HTTP GET with timeout error."""
        mock_session.get.side_effect = aiohttp.ServerTimeoutError("Timeout")

        with pytest.raises(aiohttp.ServerTimeoutError):
            await safe_http_get(mock_session, "https://slow-site.com")

    async def test_safe_http_get_client_error(self, mock_session):
        """Test HTTP GET with client error."""
        mock_session.get.side_effect = aiohttp.ClientError("Connection failed")

        with pytest.raises(aiohttp.ClientError):
            await safe_http_get(mock_session, "https://unreachable.com")

    async def test_safe_http_get_no_logging(self, mock_session):
        """Test HTTP GET with logging disabled."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Error")
        mock_response.headers = {}

        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Should work without logging
        result = await safe_http_get(mock_session, "https://example.com", log_errors=False)
        assert result.status == 500

    async def test_safe_http_get_with_raise_success(self, mock_session, mock_response):
        """Test safe_http_get_with_raise on success."""
        mock_session.get.return_value.__aenter__.return_value = mock_response

        content = await safe_http_get_with_raise(mock_session, "https://example.com")

        assert content == "Sample content"
        mock_response.raise_for_status.assert_called_once()

    async def test_safe_http_get_with_raise_http_error(self, mock_session):
        """Test safe_http_get_with_raise with HTTP error."""
        mock_response = AsyncMock()
        # Create a proper side effect function that can be awaited
        def raise_error():
            raise aiohttp.ClientResponseError(
                request_info=None, history=None, status=404
            )
        mock_response.raise_for_status = raise_error

        # Set up proper async context manager
        context_manager = AsyncMock()
        context_manager.__aenter__.return_value = mock_response
        context_manager.__aexit__.return_value = None
        mock_session.get.return_value = context_manager

        with pytest.raises(aiohttp.ClientResponseError):
            await safe_http_get_with_raise(mock_session, "https://example.com")

    async def test_safe_http_get_with_raise_timeout(self, mock_session, mock_response):
        """Test safe_http_get_with_raise with custom timeout."""
        mock_session.get.return_value.__aenter__.return_value = mock_response

        await safe_http_get_with_raise(mock_session, "https://example.com", timeout=45)

        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"].total == 45


class TestHTTPStatusChecker:
    """Test HTTP status checking utility."""

    def test_check_http_status_success(self):
        """Test HTTP status check for successful response."""
        result = check_http_status(200, "https://example.com")
        assert result is True

    def test_check_http_status_not_found(self):
        """Test HTTP status check for 404."""
        result = check_http_status(404, "https://example.com")
        assert result is False

    def test_check_http_status_server_error(self):
        """Test HTTP status check for server error."""
        result = check_http_status(500, "https://example.com")
        assert result is False

    def test_check_http_status_client_error(self):
        """Test HTTP status check for client error."""
        result = check_http_status(400, "https://example.com")
        assert result is False

    def test_check_http_status_redirect(self):
        """Test HTTP status check for redirect."""
        result = check_http_status(301, "https://example.com")
        assert result is False

    def test_check_http_status_with_context(self):
        """Test HTTP status check with custom context."""
        # Should not raise exceptions, just log appropriately
        result = check_http_status(200, "https://example.com", "custom request")
        assert result is True

        result = check_http_status(404, "https://example.com", "custom request")
        assert result is False


class TestHTTPUtilitiesIntegration:
    """Integration tests for HTTP utilities."""

    def test_http_response_and_status_checker_integration(self):
        """Test that HTTPResponse and status checker work together."""
        # Test successful response
        success_response = HTTPResponse(200, "Success", {"Content-Type": "text/html"})
        assert success_response.is_success is True
        assert check_http_status(success_response.status, "https://example.com") is True
        
        # Test error response
        error_response = HTTPResponse(404, "Not Found", {})
        assert error_response.is_success is False
        assert check_http_status(error_response.status, "https://example.com") is False
        
        # Test server error
        server_error = HTTPResponse(500, "Internal Error", {})
        assert server_error.is_success is False
        assert check_http_status(server_error.status, "https://example.com") is False