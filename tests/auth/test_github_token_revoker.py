"""Comprehensive tests for GitHubTokenRevoker.

Tests cover:
- Successful token revocation
- Error handling (network errors, invalid tokens, auth failures)
- All abstract interface methods
- Target: 80%+ code coverage
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.auth.oauth_revocation_service import (
    GitHubTokenRevoker,
    TokenRevocationFailedError,
)


class TestGitHubTokenRevoker:
    """Test suite for GitHubTokenRevoker."""

    @pytest.fixture
    def sample_access_token(self) -> str:
        """Sample GitHub access token for testing."""
        return "gho_16C7e42F292c6912E7710c838347Ae178B4a"

    @pytest.fixture
    def github_revoker(self) -> GitHubTokenRevoker:
        """Create a GitHubTokenRevoker instance."""
        return GitHubTokenRevoker(http_timeout=10)

    # Initialization Tests

    def test_initialization(self, github_revoker: GitHubTokenRevoker) -> None:
        """Test GitHub token revoker initialization."""
        assert github_revoker is not None
        assert github_revoker.http_timeout == 10
        assert github_revoker.revoke_url is not None
        assert github_revoker.client_id is not None
        assert github_revoker.client_secret is not None

    # revoke_access_token Tests

    @pytest.mark.asyncio
    async def test_revoke_access_token_success(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test successful GitHub access token revocation."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_access_token(sample_access_token)

        assert result is True
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_access_token_empty_token(
        self, github_revoker: GitHubTokenRevoker
    ) -> None:
        """Test revocation with empty token raises error."""
        with pytest.raises(TokenRevocationFailedError) as exc_info:
            await github_revoker.revoke_access_token("")

        assert "Access token cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_access_token_non_204_status(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation with non-204 status returns False."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_access_token(sample_access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_access_token_timeout(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation handles timeout gracefully."""
        # Mock httpx.AsyncClient to raise TimeoutException
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = github_revoker.httpx.TimeoutException("Timeout")

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_access_token(sample_access_token)

        assert result is False  # Non-critical failure

    @pytest.mark.asyncio
    async def test_revoke_access_token_http_error(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation handles HTTP errors gracefully."""
        # Mock httpx.AsyncClient to raise HTTPError
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = github_revoker.httpx.HTTPError("HTTP error")

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_access_token(sample_access_token)

        assert result is False  # Non-critical failure

    @pytest.mark.asyncio
    async def test_revoke_access_token_unexpected_error(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test token revocation handles unexpected errors gracefully."""
        # Mock httpx.AsyncClient to raise unexpected error
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = Exception("Unexpected error")

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_access_token(sample_access_token)

        assert result is False  # Graceful degradation

    # revoke_all_tokens Tests

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_success(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test revoking all tokens for a user succeeds."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_all_tokens("user123", sample_access_token)

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_failure(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test revoking all tokens handles failure gracefully."""
        # Mock httpx.AsyncClient to return non-204
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        result = await github_revoker.revoke_all_tokens("user123", sample_access_token)

        assert result is False

    # Edge Cases

    @pytest.mark.asyncio
    async def test_revoke_access_token_whitespace_only(
        self, github_revoker: GitHubTokenRevoker
    ) -> None:
        """Test revocation with whitespace-only token raises error."""
        with pytest.raises(TokenRevocationFailedError):
            await github_revoker.revoke_access_token("   ")

    @pytest.mark.asyncio
    async def test_revoke_access_token_url_construction(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test that URL is correctly constructed with client_id."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        await github_revoker.revoke_access_token(sample_access_token)

        # Verify URL includes client_id
        call_args = mock_client.request.call_args
        url = call_args[0][0]
        assert github_revoker.client_id in url
        assert url.endswith("/grant")

    @pytest.mark.asyncio
    async def test_revoke_access_token_headers(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test that correct headers are sent to GitHub."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        await github_revoker.revoke_access_token(sample_access_token)

        # Verify headers
        call_args = mock_client.request.call_args
        headers = call_args[1]["headers"]
        assert headers["Accept"] == "application/vnd.github+json"
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"

    @pytest.mark.asyncio
    async def test_revoke_access_token_basic_auth(
        self, github_revoker: GitHubTokenRevoker, sample_access_token: str
    ) -> None:
        """Test that Basic authentication is used correctly."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response

        github_revoker.httpx.AsyncClient = MagicMock(return_value=mock_client)

        await github_revoker.revoke_access_token(sample_access_token)

        # Verify Basic auth
        call_args = mock_client.request.call_args
        auth = call_args[1]["auth"]
        assert auth == (github_revoker.client_id, github_revoker.client_secret)
