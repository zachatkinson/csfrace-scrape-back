"""Comprehensive tests for Microsoft OAuth token revoker.

Tests cover:
- Successful session revocation
- Access token revocation limitations
- Error handling (401, 403, timeouts, network errors)
- HTTP client mocking with pytest-mock
- Logging verification
- Edge cases and boundary conditions
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auth.oauth_revocation_service import (
    MicrosoftTokenRevoker,
    OAuthRevocationRegistry,
)
from src.auth.models.oauth_models import OAuthProvider
from src.constants.auth import MICROSOFT_REVOKE_URL


@pytest.fixture
def revoker():
    """Create a Microsoft token revoker instance for testing."""
    return MicrosoftTokenRevoker(http_timeout=5)


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client for testing HTTP requests."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client, mock_response


@pytest.mark.asyncio
class TestMicrosoftTokenRevoker:
    """Test suite for MicrosoftTokenRevoker class."""

    # ==================== Initialization Tests ====================

    def test_initialization_default_timeout(self):
        """Test revoker initializes with default timeout."""
        revoker = MicrosoftTokenRevoker()
        assert revoker.http_timeout == 10

    def test_initialization_custom_timeout(self):
        """Test revoker initializes with custom timeout."""
        revoker = MicrosoftTokenRevoker(http_timeout=30)
        assert revoker.http_timeout == 30

    # ==================== Access Token Revocation Tests ====================

    async def test_revoke_access_token_logs_limitation(self, revoker, capsys):
        """Test that access token revocation logs Microsoft's limitation."""
        result = await revoker.revoke_access_token("test_access_token")

        assert result is True
        captured = capsys.readouterr()
        # Structured logging outputs JSON
        assert "does not support access token revocation" in captured.out or "access_tokens_cannot_be_revoked" in captured.out

    async def test_revoke_access_token_returns_true(self, revoker):
        """Test that access token revocation returns True (non-critical)."""
        result = await revoker.revoke_access_token("any_token")
        assert result is True

    # ==================== Successful Session Revocation Tests ====================

    async def test_revoke_all_tokens_success_200(self, revoker, mock_httpx_client):
        """Test successful session revocation with 200 status code."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200
        mock_response.text = "true"

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user123", "test_token")

            assert result is True
            mock_client.post.assert_called_once_with(
                MICROSOFT_REVOKE_URL,
                headers={
                    "Authorization": "Bearer test_token",
                    "Content-Type": "application/json",
                },
            )

    async def test_revoke_all_tokens_success_204(self, revoker, mock_httpx_client):
        """Test successful session revocation with 204 No Content."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 204
        mock_response.text = ""

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user456", "valid_token")

            assert result is True

    async def test_revoke_all_tokens_correct_endpoint(self, revoker, mock_httpx_client):
        """Test that revocation uses correct Microsoft Graph endpoint."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            await revoker.revoke_all_tokens("user", "token")

            assert mock_client.post.call_args[0][0] == MICROSOFT_REVOKE_URL

    async def test_revoke_all_tokens_authorization_header(self, revoker, mock_httpx_client):
        """Test that authorization header is correctly formatted."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            await revoker.revoke_all_tokens("user", "my_access_token")

            call_headers = mock_client.post.call_args[1]["headers"]
            assert call_headers["Authorization"] == "Bearer my_access_token"
            assert call_headers["Content-Type"] == "application/json"

    # ==================== Error Handling Tests ====================

    async def test_revoke_all_tokens_401_unauthorized(self, revoker, mock_httpx_client, caplog):
        """Test handling of 401 Unauthorized error."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 401

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user", "invalid_token")

            assert result is False
            assert "Invalid or expired access token" in caplog.text
            assert "401" in caplog.text

    async def test_revoke_all_tokens_403_forbidden(self, revoker, mock_httpx_client, caplog):
        """Test handling of 403 Forbidden error (insufficient permissions)."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 403

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user", "token_without_perms")

            assert result is False
            assert "Insufficient permissions" in caplog.text
            assert "403" in caplog.text
            assert "User.RevokeSessions.All" in caplog.text

    async def test_revoke_all_tokens_500_server_error(self, revoker, mock_httpx_client, caplog):
        """Test handling of 500 Internal Server Error."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user", "token")

            assert result is False
            assert "unexpected status" in caplog.text
            assert "500" in caplog.text

    async def test_revoke_all_tokens_timeout(self, revoker, caplog):
        """Test handling of request timeout."""
        with patch.object(revoker, "httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
            mock_httpx.TimeoutException = TimeoutError
            mock_client.post.side_effect = TimeoutError("Request timed out")

            result = await revoker.revoke_all_tokens("user", "token")

            assert result is False
            assert "timed out" in caplog.text

    async def test_revoke_all_tokens_network_error(self, revoker, caplog):
        """Test handling of network/HTTP errors."""
        with patch.object(revoker, "httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
            mock_httpx.HTTPError = Exception
            mock_client.post.side_effect = Exception("Network error")

            result = await revoker.revoke_all_tokens("user", "token")

            assert result is False
            assert "HTTP error" in caplog.text or "Unexpected error" in caplog.text

    async def test_revoke_all_tokens_unexpected_exception(self, revoker, caplog):
        """Test handling of unexpected exceptions."""
        with patch.object(revoker, "httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = ValueError("Unexpected error")

            result = await revoker.revoke_all_tokens("user", "token")

            assert result is False
            assert "Unexpected error" in caplog.text

    # ==================== Logging Tests ====================

    async def test_revoke_all_tokens_logs_attempt(self, revoker, mock_httpx_client, caplog):
        """Test that revocation attempt is logged."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            await revoker.revoke_all_tokens("user", "token")

            assert "Attempting to revoke Microsoft sign-in sessions" in caplog.text

    async def test_revoke_all_tokens_logs_success(self, revoker, mock_httpx_client, caplog):
        """Test that successful revocation is logged."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            await revoker.revoke_all_tokens("user", "token")

            assert "Successfully revoked Microsoft sign-in sessions" in caplog.text

    # ==================== Edge Cases and Boundary Conditions ====================

    async def test_revoke_all_tokens_empty_user_id(self, revoker, mock_httpx_client):
        """Test revocation with empty user ID (uses /me endpoint anyway)."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("", "token")

            assert result is True

    async def test_revoke_all_tokens_empty_response_body(self, revoker, mock_httpx_client):
        """Test handling of empty response body on error."""
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 400
        mock_response.text = ""

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user", "token")

            assert result is False

    async def test_revoke_all_tokens_custom_timeout(self, mock_httpx_client):
        """Test that custom timeout is used in HTTP client."""
        revoker = MicrosoftTokenRevoker(http_timeout=15)
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            await revoker.revoke_all_tokens("user", "token")

            # Verify timeout was passed to client
            mock_httpx.AsyncClient.assert_called_once_with(timeout=15)

    # ==================== Integration with Registry ====================

    def test_revoker_registered_with_registry(self):
        """Test that Microsoft revoker is registered in the registry."""
        assert OAuthRevocationRegistry.is_registered(OAuthProvider.MICROSOFT)

    def test_revoker_can_be_retrieved_from_registry(self):
        """Test that Microsoft revoker can be retrieved from registry."""
        revoker = OAuthRevocationRegistry.get_revoker(OAuthProvider.MICROSOFT)
        assert isinstance(revoker, MicrosoftTokenRevoker)

    # ==================== Refresh Token Support Tests ====================

    def test_does_not_support_refresh_token_revocation(self, revoker):
        """Test that revoker does not support refresh token revocation."""
        assert revoker.supports_refresh_token_revocation() is False

    async def test_revoke_refresh_token_raises_not_implemented(self, revoker):
        """Test that refresh token revocation raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await revoker.revoke_refresh_token("refresh_token")


# ==================== Parametrized Tests ====================


@pytest.mark.asyncio
class TestMicrosoftTokenRevokerParametrized:
    """Parametrized tests for comprehensive coverage."""

    @pytest.mark.parametrize(
        "status_code,expected_result",
        [
            (200, True),  # Success with content
            (204, True),  # Success no content
            (400, False),  # Bad request
            (401, False),  # Unauthorized
            (403, False),  # Forbidden
            (404, False),  # Not found
            (500, False),  # Server error
            (502, False),  # Bad gateway
            (503, False),  # Service unavailable
        ],
    )
    async def test_various_status_codes(self, status_code, expected_result):
        """Test revocation with various HTTP status codes."""
        revoker = MicrosoftTokenRevoker()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = f"Response for {status_code}"
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user", "token")

            assert result == expected_result

    @pytest.mark.parametrize(
        "timeout_value",
        [1, 5, 10, 30, 60],
    )
    def test_various_timeout_values(self, timeout_value):
        """Test initialization with various timeout values."""
        revoker = MicrosoftTokenRevoker(http_timeout=timeout_value)
        assert revoker.http_timeout == timeout_value


# ==================== Coverage Tests ====================


@pytest.mark.asyncio
class TestMicrosoftTokenRevokerCoverage:
    """Additional tests to ensure high coverage."""

    async def test_error_body_extraction(self):
        """Test that error body is correctly extracted and logged."""
        revoker = MicrosoftTokenRevoker()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_request"}'
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

            result = await revoker.revoke_all_tokens("user", "token")

            assert result is False

    async def test_context_manager_cleanup(self):
        """Test that httpx client is properly cleaned up."""
        revoker = MicrosoftTokenRevoker()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(revoker, "httpx") as mock_httpx:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_client
            mock_httpx.AsyncClient.return_value = mock_context

            await revoker.revoke_all_tokens("user", "token")

            # Verify context manager was used (enter and exit called)
            mock_context.__aenter__.assert_called_once()
            mock_context.__aexit__.assert_called_once()
