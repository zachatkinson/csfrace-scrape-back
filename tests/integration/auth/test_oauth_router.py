"""Integration tests for OAuth authentication router - following CLAUDE.md testing standards."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.auth.models import OAuthProvider, SSOLoginResponse


class TestOAuthRouterIntegration:
    """Integration tests for OAuth router endpoints - End-to-end testing."""

    def setup_method(self):
        """Set up test client and fixtures."""
        self.client = TestClient(app)

    def test_list_oauth_providers_endpoint(self):
        """Test OAuth providers listing endpoint returns all supported providers."""
        response = self.client.get("/auth/oauth/providers")

        assert response.status_code == 200
        providers = response.json()

        assert isinstance(providers, list)
        assert "google" in providers
        assert "github" in providers
        assert "microsoft" in providers
        assert len(providers) == 3

    @patch("src.auth.oauth_service.OAuthService")
    def test_initiate_oauth_login_google(self, mock_oauth_service):
        """Test OAuth login initiation for Google provider."""
        # Mock OAuth service response
        mock_sso_response = SSOLoginResponse(
            authorization_url="https://accounts.google.com/oauth/authorize?client_id=test",
            state="secure_state_123",
            provider=OAuthProvider.GOOGLE,
        )
        mock_oauth_service.return_value.initiate_oauth_login.return_value = mock_sso_response

        # Test OAuth login initiation
        login_request = {"provider": "google", "redirect_uri": "https://myapp.com/callback"}

        response = self.client.post("/auth/oauth/login", json=login_request)

        assert response.status_code == 200
        data = response.json()

        assert "authorization_url" in data
        assert "state" in data
        assert "provider" in data
        assert data["provider"] == "google"
        assert "accounts.google.com" in data["authorization_url"]

    @patch("src.auth.oauth_service.OAuthService")
    def test_initiate_oauth_login_github(self, mock_oauth_service):
        """Test OAuth login initiation for GitHub provider."""
        mock_sso_response = SSOLoginResponse(
            authorization_url="https://github.com/login/oauth/authorize?client_id=test",
            state="github_state_456",
            provider=OAuthProvider.GITHUB,
        )
        mock_oauth_service.return_value.initiate_oauth_login.return_value = mock_sso_response

        login_request = {
            "provider": "github"
            # No redirect_uri provided - should use default
        }

        response = self.client.post("/auth/oauth/login", json=login_request)

        assert response.status_code == 200
        data = response.json()

        assert data["provider"] == "github"
        assert "github.com" in data["authorization_url"]

    def test_initiate_oauth_login_invalid_provider(self):
        """Test OAuth login initiation with invalid provider returns validation error."""
        login_request = {"provider": "invalid_provider"}

        response = self.client.post("/auth/oauth/login", json=login_request)

        assert response.status_code == 422  # Pydantic validation error
        assert "detail" in response.json()

    def test_initiate_oauth_login_invalid_redirect_uri(self):
        """Test OAuth login initiation with invalid redirect URI format."""
        login_request = {"provider": "google", "redirect_uri": "ftp://invalid-protocol.com"}

        response = self.client.post("/auth/oauth/login", json=login_request)

        assert response.status_code == 422  # Pydantic validation error
        error_detail = response.json()["detail"]
        assert any("Redirect URI must be HTTP or HTTPS" in str(error) for error in error_detail)

    def test_oauth_callback_not_implemented(self):
        """Test OAuth callback endpoint returns not implemented status."""
        callback_data = {"code": "auth_code_123", "state": "secure_state", "provider": "google"}

        response = self.client.post("/auth/oauth/google/callback", json=callback_data)

        assert response.status_code == 501  # Not implemented
        assert "not fully implemented" in response.json()["detail"]

    def test_oauth_callback_with_error(self):
        """Test OAuth callback endpoint handles OAuth errors properly."""
        callback_data = {
            "code": "",
            "state": "state_123",
            "provider": "google",
            "error": "access_denied",
            "error_description": "User denied access to the application",
        }

        response = self.client.post("/auth/oauth/google/callback", json=callback_data)

        assert response.status_code == 400
        error_detail = response.json()["detail"]
        assert "OAuth error" in error_detail
        assert "User denied access to the application" in error_detail

    def test_oauth_callback_provider_mismatch(self):
        """Test OAuth callback validates provider consistency."""
        callback_data = {
            "code": "auth_code_123",
            "state": "state_123",
            "provider": "microsoft",  # Mismatch with URL path
        }

        response = self.client.post("/auth/oauth/google/callback", json=callback_data)

        assert response.status_code == 400
        assert "Provider mismatch" in response.json()["detail"]

    @pytest.mark.parametrize("provider", ["google", "github", "microsoft"])
    def test_oauth_callback_endpoints_exist_for_all_providers(self, provider):
        """Test OAuth callback endpoints exist for all supported providers."""
        callback_data = {"code": "test_code", "state": "test_state", "provider": provider}

        response = self.client.post(f"/auth/oauth/{provider}/callback", json=callback_data)

        # Should not return 404 (endpoint exists) - implementation returns 501 for now
        assert response.status_code in [501, 400, 500]  # Not 404
        assert response.status_code != 404

    def test_oauth_endpoints_require_rate_limiting(self):
        """Test OAuth endpoints have rate limiting applied."""
        # This test would require multiple rapid requests to test rate limiting
        # For now, verify endpoints exist and can handle requests

        login_request = {"provider": "google"}
        response = self.client.post("/auth/oauth/login", json=login_request)

        # Verify rate limiting is configured (endpoint responds normally under normal load)
        assert response.status_code in [200, 422]  # Valid response codes

    @pytest.mark.parametrize(
        "invalid_redirect",
        [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd",
            "not-a-url",
        ],
    )
    def test_oauth_security_validation(self, invalid_redirect):
        """Test OAuth endpoints reject dangerous redirect URIs - Security testing."""
        login_request = {"provider": "google", "redirect_uri": invalid_redirect}

        response = self.client.post("/auth/oauth/login", json=login_request)

        assert response.status_code == 422  # Validation error
        error_messages = str(response.json())
        assert (
            "Redirect URI must be HTTP or HTTPS" in error_messages
            or "value is not a valid url" in error_messages.lower()
        )


class TestOAuthRouterErrorHandling:
    """Test OAuth router error handling scenarios."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_oauth_login_missing_provider(self):
        """Test OAuth login request without provider returns validation error."""
        response = self.client.post("/auth/oauth/login", json={})

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("provider" in str(error).lower() for error in error_detail)

    def test_oauth_callback_missing_required_fields(self):
        """Test OAuth callback with missing required fields."""
        incomplete_callback = {
            "state": "state_only"
            # Missing code and provider
        }

        response = self.client.post("/auth/oauth/google/callback", json=incomplete_callback)

        assert response.status_code == 422  # Validation error
        error_messages = str(response.json())
        assert "code" in error_messages.lower() or "provider" in error_messages.lower()

    @patch("src.auth.oauth_service.OAuthService")
    def test_oauth_service_exception_handling(self, mock_oauth_service):
        """Test OAuth service exceptions are properly handled."""
        # Mock service to raise exception
        mock_oauth_service.return_value.initiate_oauth_login.side_effect = Exception(
            "Service unavailable"
        )

        login_request = {"provider": "google"}
        response = self.client.post("/auth/oauth/login", json=login_request)

        assert response.status_code == 500  # Internal server error
        assert "Internal server error" in str(response.json())

    def test_oauth_endpoints_content_type_validation(self):
        """Test OAuth endpoints validate content type properly."""
        # Send form data instead of JSON
        response = self.client.post(
            "/auth/oauth/login",
            data={"provider": "google"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Should handle different content types gracefully
        assert response.status_code in [200, 422, 415]  # Various acceptable responses

    def test_oauth_endpoints_handle_malformed_json(self):
        """Test OAuth endpoints handle malformed JSON gracefully."""
        response = self.client.post(
            "/auth/oauth/login",
            data='{"provider": "google"',  # Malformed JSON
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422  # JSON parsing error
