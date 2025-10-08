"""Comprehensive tests for FacebookTokenRevoker.

Tests cover:
- Successful token revocation scenarios
- Error handling (network errors, invalid tokens, timeouts)
- HTTP status code handling
- Response parsing edge cases
- Mock httpx for isolated unit testing
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.auth.models.oauth_models import OAuthProvider
from src.auth.oauth_revocation_service import (
    FacebookTokenRevoker,
    OAuthRevocationRegistry,
)


class TestFacebookTokenRevokerInitialization:
    """Test FacebookTokenRevoker initialization and configuration."""

    def test_default_initialization(self):
        """Test revoker initializes with default values."""
        revoker = FacebookTokenRevoker()

        assert revoker.api_base == "https://graph.facebook.com/v18.0"
        assert revoker.timeout == 10.0

    def test_custom_api_base(self):
        """Test revoker accepts custom API base URL."""
        custom_base = "https://graph.facebook.com/v19.0"
        revoker = FacebookTokenRevoker(api_base=custom_base)

        assert revoker.api_base == custom_base

    def test_custom_timeout(self):
        """Test revoker accepts custom timeout."""
        revoker = FacebookTokenRevoker(timeout=30.0)

        assert revoker.timeout == 30.0


class TestFacebookTokenRevokerRevokeAccessToken:
    """Test revoke_access_token method."""

    @pytest.mark.asyncio
    async def test_successful_revocation(self):
        """Test successful access token revocation."""
        revoker = FacebookTokenRevoker()
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        assert result is True
        mock_client.delete.assert_called_once_with(
            "https://graph.facebook.com/v18.0/me/permissions",
            params={"access_token": access_token},
        )

    @pytest.mark.asyncio
    async def test_revocation_failure_non_200_status(self):
        """Test handling of non-200 HTTP status codes."""
        revoker = FacebookTokenRevoker()
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response with error status
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Invalid token"}}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revocation_invalid_json_response(self):
        """Test handling of invalid JSON response."""
        revoker = FacebookTokenRevoker()
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid JSON response"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        # Should return False but not raise exception (graceful degradation)
        assert result is False

    @pytest.mark.asyncio
    async def test_revocation_success_false_in_response(self):
        """Test handling of success: false in response."""
        revoker = FacebookTokenRevoker()
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response with success: false
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False}
        mock_response.text = '{"success": false}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revocation_timeout_error(self):
        """Test handling of timeout errors."""
        revoker = FacebookTokenRevoker(timeout=5.0)
        access_token = "EAABwzLixnjYBO123456"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revocation_request_error(self):
        """Test handling of general request errors."""
        revoker = FacebookTokenRevoker()
        access_token = "EAABwzLixnjYBO123456"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=httpx.RequestError("Network error"))
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revocation_unexpected_exception(self):
        """Test handling of unexpected exceptions."""
        revoker = FacebookTokenRevoker()
        access_token = "EAABwzLixnjYBO123456"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token(access_token)

        # Should handle gracefully without raising
        assert result is False


class TestFacebookTokenRevokerRevokeAllTokens:
    """Test revoke_all_tokens method."""

    @pytest.mark.asyncio
    async def test_successful_revoke_all_tokens(self):
        """Test successful revocation of all tokens for a user."""
        revoker = FacebookTokenRevoker()
        user_id = "123456789"
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is True
        mock_client.delete.assert_called_once_with(
            f"https://graph.facebook.com/v18.0/{user_id}/permissions",
            params={"access_token": access_token},
        )

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_with_numeric_user_id(self):
        """Test revoke_all_tokens with numeric user ID."""
        revoker = FacebookTokenRevoker()
        user_id = "987654321"
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_failure_non_200_status(self):
        """Test revoke_all_tokens with non-200 HTTP status."""
        revoker = FacebookTokenRevoker()
        user_id = "123456789"
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response with error status
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": {"message": "Invalid OAuth token"}}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_invalid_json_response(self):
        """Test revoke_all_tokens with invalid JSON response."""
        revoker = FacebookTokenRevoker()
        user_id = "123456789"
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid JSON"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_timeout_error(self):
        """Test revoke_all_tokens timeout handling."""
        revoker = FacebookTokenRevoker(timeout=5.0)
        user_id = "123456789"
        access_token = "EAABwzLixnjYBO123456"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_request_error(self):
        """Test revoke_all_tokens request error handling."""
        revoker = FacebookTokenRevoker()
        user_id = "123456789"
        access_token = "EAABwzLixnjYBO123456"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=httpx.RequestError("Network error"))
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_unexpected_exception(self):
        """Test revoke_all_tokens unexpected exception handling."""
        revoker = FacebookTokenRevoker()
        user_id = "123456789"
        access_token = "EAABwzLixnjYBO123456"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens(user_id, access_token)

        assert result is False


class TestFacebookTokenRevokerRegistry:
    """Test FacebookTokenRevoker registration with OAuthRevocationRegistry."""

    def test_facebook_revoker_registered(self):
        """Test that FacebookTokenRevoker is registered at module import."""
        # Check if Facebook provider is registered
        assert OAuthRevocationRegistry.is_registered(OAuthProvider.FACEBOOK)

        # Get the revoker
        revoker = OAuthRevocationRegistry.get_revoker(OAuthProvider.FACEBOOK)

        # Verify it's the correct type
        assert isinstance(revoker, FacebookTokenRevoker)

    def test_facebook_revoker_can_be_retrieved(self):
        """Test that registered Facebook revoker can be retrieved."""
        revoker = OAuthRevocationRegistry.get_revoker(OAuthProvider.FACEBOOK)

        assert revoker is not None
        assert isinstance(revoker, FacebookTokenRevoker)
        assert revoker.api_base == "https://graph.facebook.com/v18.0"


class TestFacebookTokenRevokerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_revoke_with_empty_access_token(self):
        """Test revocation with empty access token."""
        revoker = FacebookTokenRevoker()

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Invalid token"}}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_access_token("")

        # Should handle gracefully
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_with_empty_user_id(self):
        """Test revoke_all_tokens with empty user ID."""
        revoker = FacebookTokenRevoker()

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Invalid user ID"}}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await revoker.revoke_all_tokens("", "token123")

        assert result is False

    @pytest.mark.asyncio
    async def test_custom_api_base_is_used(self):
        """Test that custom API base URL is properly used."""
        custom_base = "https://graph.facebook.com/v20.0"
        revoker = FacebookTokenRevoker(api_base=custom_base)
        access_token = "EAABwzLixnjYBO123456"

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await revoker.revoke_access_token(access_token)

        # Verify custom API base was used
        mock_client.delete.assert_called_once_with(
            f"{custom_base}/me/permissions",
            params={"access_token": access_token},
        )

    @pytest.mark.asyncio
    async def test_custom_timeout_is_used(self):
        """Test that custom timeout is properly configured."""
        custom_timeout = 30.0
        revoker = FacebookTokenRevoker(timeout=custom_timeout)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            await revoker.revoke_access_token("token123")

        # Verify timeout was passed to AsyncClient
        mock_client_class.assert_called_once_with(timeout=custom_timeout)
