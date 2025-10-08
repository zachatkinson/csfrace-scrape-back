"""Comprehensive tests for AppleTokenRevoker.

Tests cover:
- Successful token revocation (access and refresh)
- Error handling (network errors, invalid tokens)
- All abstract interface methods
- Target: 80%+ code coverage
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.auth.oauth_revocation_service import (
    AppleTokenRevoker,
    TokenRevocationFailedError,
)


class TestAppleTokenRevoker:
    """Test suite for AppleTokenRevoker."""

    @pytest.fixture
    def sample_access_token(self) -> str:
        """Sample Apple access token for testing."""
        return "a12345678901234567890123456789012"

    @pytest.fixture
    def sample_refresh_token(self) -> str:
        """Sample Apple refresh token for testing."""
        return "r98765432109876543210987654321098"

    @pytest.fixture
    def apple_revoker(self) -> AppleTokenRevoker:
        """Create an AppleTokenRevoker instance."""
        return AppleTokenRevoker(http_timeout=10)

    # Initialization Tests

    def test_initialization(self, apple_revoker: AppleTokenRevoker) -> None:
        """Test Apple token revoker initialization."""
        assert apple_revoker is not None
        assert apple_revoker.http_timeout == 10
        assert apple_revoker.revoke_url is not None
        assert apple_revoker.client_id is not None
        assert apple_revoker.client_secret is not None

    def test_supports_refresh_token_revocation(self, apple_revoker: AppleTokenRevoker) -> None:
        """Test that Apple supports refresh token revocation."""
        assert apple_revoker.supports_refresh_token_revocation() is True

    # revoke_access_token Tests

    @pytest.mark.asyncio
    async def test_revoke_access_token_success(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test successful Apple access token revocation."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_access_token(sample_access_token)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_access_token_empty_token(
        self, apple_revoker: AppleTokenRevoker
    ) -> None:
        """Test revocation with empty token raises error."""
        with pytest.raises(TokenRevocationFailedError) as exc_info:
            await apple_revoker.revoke_access_token("")

        assert "Access token cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_access_token_non_200_status(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation with non-200 status returns False."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_access_token(sample_access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_access_token_timeout(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation handles timeout gracefully."""
        # Mock httpx.AsyncClient to raise TimeoutException
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = apple_revoker.httpx.TimeoutException("Timeout")

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_access_token(sample_access_token)

        assert result is False  # Non-critical failure

    @pytest.mark.asyncio
    async def test_revoke_access_token_http_error(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation handles HTTP errors gracefully."""
        # Mock httpx.AsyncClient to raise HTTPError
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = apple_revoker.httpx.HTTPError("HTTP error")

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_access_token(sample_access_token)

        assert result is False  # Non-critical failure

    @pytest.mark.asyncio
    async def test_revoke_access_token_unexpected_error(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation handles unexpected errors gracefully."""
        # Mock httpx.AsyncClient to raise unexpected error
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = Exception("Unexpected error")

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_access_token(sample_access_token)

        assert result is False  # Graceful degradation

    # revoke_all_tokens Tests

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_success(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test revoking all tokens for a user succeeds."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_all_tokens("user123", sample_access_token)

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_failure(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test revoking all tokens handles failure gracefully."""
        # Mock httpx.AsyncClient to return non-200
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_all_tokens("user123", sample_access_token)

        assert result is False

    # revoke_refresh_token Tests

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_success(
        self, apple_revoker: AppleTokenRevoker, sample_refresh_token: str
    ) -> None:
        """Test successful Apple refresh token revocation."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_refresh_token(sample_refresh_token)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_empty_token(
        self, apple_revoker: AppleTokenRevoker
    ) -> None:
        """Test revocation with empty refresh token raises error."""
        with pytest.raises(TokenRevocationFailedError) as exc_info:
            await apple_revoker.revoke_refresh_token("")

        assert "Refresh token cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_non_200_status(
        self, apple_revoker: AppleTokenRevoker, sample_refresh_token: str
    ) -> None:
        """Test refresh token revocation with non-200 status returns False."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_refresh_token(sample_refresh_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_error_handling(
        self, apple_revoker: AppleTokenRevoker, sample_refresh_token: str
    ) -> None:
        """Test refresh token revocation handles errors gracefully."""
        # Mock httpx.AsyncClient to raise error
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = Exception("Network error")

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await apple_revoker.revoke_refresh_token(sample_refresh_token)

        assert result is False  # Graceful degradation

    # Edge Cases

    @pytest.mark.asyncio
    async def test_revoke_access_token_whitespace_only(
        self, apple_revoker: AppleTokenRevoker
    ) -> None:
        """Test revocation with whitespace-only token raises error."""
        with pytest.raises(TokenRevocationFailedError):
            await apple_revoker.revoke_access_token("   ")

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_whitespace_only(
        self, apple_revoker: AppleTokenRevoker
    ) -> None:
        """Test revocation with whitespace-only refresh token raises error."""
        with pytest.raises(TokenRevocationFailedError):
            await apple_revoker.revoke_refresh_token("   ")

    @pytest.mark.asyncio
    async def test_revoke_access_token_parameters(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test that correct parameters are sent to Apple."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        await apple_revoker.revoke_access_token(sample_access_token)

        # Verify parameters
        call_args = mock_client.post.call_args
        data = call_args[1]["data"]
        assert data["client_id"] == apple_revoker.client_id
        assert data["client_secret"] == apple_revoker.client_secret
        assert data["token"] == sample_access_token
        assert data["token_type_hint"] == "access_token"

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_parameters(
        self, apple_revoker: AppleTokenRevoker, sample_refresh_token: str
    ) -> None:
        """Test that correct parameters are sent for refresh token."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        await apple_revoker.revoke_refresh_token(sample_refresh_token)

        # Verify parameters
        call_args = mock_client.post.call_args
        data = call_args[1]["data"]
        assert data["token"] == sample_refresh_token
        assert data["token_type_hint"] == "refresh_token"

    @pytest.mark.asyncio
    async def test_revoke_access_token_headers(
        self, apple_revoker: AppleTokenRevoker, sample_access_token: str
    ) -> None:
        """Test that correct headers are sent to Apple."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        apple_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        await apple_revoker.revoke_access_token(sample_access_token)

        # Verify headers
        call_args = mock_client.post.call_args
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
