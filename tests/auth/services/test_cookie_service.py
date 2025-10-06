"""Unit tests for CookieService following audit_3.md standards.

Tests for secure HTTP-only cookie management service with comprehensive coverage
following AAA pattern and OWASP security best practices.
"""

import json
import os
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import Response

from src.auth.models import Token
from src.auth.services.cookie_service import CookieService


class TestCookieService:
    """Test suite for CookieService following AAA pattern."""

    @pytest.fixture
    def mock_response(self) -> Mock:
        """Create mock FastAPI response object."""
        response = Mock(spec=Response)
        response.set_cookie = Mock()
        return response

    @pytest.fixture
    def sample_token(self) -> Token:
        """Create sample token for testing."""
        return Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="bearer",
            expires_in=3600,  # 1 hour
            is_new_user=False,
        )

    @pytest.fixture
    def sample_token_new_user(self) -> Token:
        """Create sample token for new user testing."""
        return Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="bearer",
            expires_in=3600,
            is_new_user=True,
        )

    @pytest.fixture
    def sample_token_no_refresh(self) -> Token:
        """Create sample token without refresh token."""
        return Token(
            access_token="test_access_token",
            refresh_token=None,
            token_type="bearer",
            expires_in=3600,
            is_new_user=False,
        )

    @pytest.mark.unit
    def test_init_development_environment(self) -> None:
        """Test initialization in development environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            # Act
            service = CookieService()

            # Assert
            assert service.environment == "development"
            assert service.is_production is False

    @pytest.mark.unit
    def test_init_production_environment(self) -> None:
        """Test initialization in production environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            # Act
            service = CookieService()

            # Assert
            assert service.environment == "production"
            assert service.is_production is True

    @pytest.mark.unit
    def test_init_default_environment(self) -> None:
        """Test initialization with default environment when not set."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            # Act
            service = CookieService()

            # Assert
            assert service.environment == "development"  # Default value
            assert service.is_production is False

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "env_value", ["PRODUCTION", "Production", "DEVELOPMENT", "Development"]
    )
    def test_init_case_insensitive_environment(self, env_value: str) -> None:
        """Test environment detection is case insensitive."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": env_value}):
            # Act
            service = CookieService()

            # Assert
            assert service.environment == env_value.lower()

    @pytest.mark.unit
    def test_set_auth_cookies_development(self, mock_response: Mock, sample_token: Token) -> None:
        """Test setting auth cookies in development environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            assert mock_response.set_cookie.call_count == 3  # auth_token, refresh_token, auth_user

            # Verify auth_token cookie
            auth_token_call = mock_response.set_cookie.call_args_list[0]
            assert auth_token_call[1]["key"] == "auth_token"
            assert auth_token_call[1]["value"] == "test_access_token"
            assert auth_token_call[1]["max_age"] == 3600
            assert auth_token_call[1]["httponly"] is True
            assert auth_token_call[1]["secure"] is False  # Development
            assert auth_token_call[1]["samesite"] == "lax"  # Development
            assert auth_token_call[1]["path"] == "/"
            assert auth_token_call[1]["domain"] == "localhost"

            # Verify refresh_token cookie
            refresh_token_call = mock_response.set_cookie.call_args_list[1]
            assert refresh_token_call[1]["key"] == "refresh_token"
            assert refresh_token_call[1]["value"] == "test_refresh_token"
            assert refresh_token_call[1]["max_age"] == 60 * 60 * 24 * 30  # 30 days
            assert refresh_token_call[1]["httponly"] is True
            assert refresh_token_call[1]["secure"] is False
            assert refresh_token_call[1]["samesite"] == "lax"

            # Verify auth_user cookie
            auth_user_call = mock_response.set_cookie.call_args_list[2]
            assert auth_user_call[1]["key"] == "auth_user"
            expected_user_data = '{"isAuthenticated":true,"isNewUser":false}'
            assert auth_user_call[1]["value"] == expected_user_data
            assert auth_user_call[1]["httponly"] is False  # Frontend readable
            assert auth_user_call[1]["secure"] is False

    @pytest.mark.unit
    def test_set_auth_cookies_production(self, mock_response: Mock, sample_token: Token) -> None:
        """Test setting auth cookies in production environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            assert mock_response.set_cookie.call_count == 3

            # Verify production security settings
            auth_token_call = mock_response.set_cookie.call_args_list[0]
            assert auth_token_call[1]["secure"] is True  # Production requires HTTPS
            assert auth_token_call[1]["samesite"] == "strict"  # Stricter in production
            assert auth_token_call[1]["domain"] is None  # No explicit domain in production

    @pytest.mark.unit
    def test_set_auth_cookies_new_user(
        self, mock_response: Mock, sample_token_new_user: Token
    ) -> None:
        """Test setting cookies for new user."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token_new_user)

            # Assert
            auth_user_call = mock_response.set_cookie.call_args_list[2]
            expected_user_data = '{"isAuthenticated":true,"isNewUser":true}'
            assert auth_user_call[1]["value"] == expected_user_data

    @pytest.mark.unit
    def test_set_auth_cookies_no_refresh_token(
        self, mock_response: Mock, sample_token_no_refresh: Token
    ) -> None:
        """Test setting cookies when refresh token is None."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token_no_refresh)

            # Assert
            assert mock_response.set_cookie.call_count == 2  # Only auth_token and auth_user

            # Verify only auth_token and auth_user cookies were set
            call_keys = [call[1]["key"] for call in mock_response.set_cookie.call_args_list]
            assert "auth_token" in call_keys
            assert "auth_user" in call_keys
            assert "refresh_token" not in call_keys

    @pytest.mark.unit
    def test_clear_auth_cookies_development(self, mock_response: Mock) -> None:
        """Test clearing auth cookies in development environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.clear_auth_cookies(mock_response)

            # Assert
            assert mock_response.set_cookie.call_count == 3  # Clear all three cookies

            # Verify all cookies are cleared with past expiration
            for call in mock_response.set_cookie.call_args_list:
                assert call[1]["value"] == ""  # Empty value
                assert isinstance(call[1]["expires"], datetime)
                assert call[1]["expires"] < datetime.now(UTC)  # Past date
                assert call[1]["secure"] is False  # Development
                assert call[1]["samesite"] == "lax"  # Development
                assert call[1]["domain"] == "localhost"

            # Verify cookie names
            cookie_names = [call[1]["key"] for call in mock_response.set_cookie.call_args_list]
            assert "auth_token" in cookie_names
            assert "refresh_token" in cookie_names
            assert "auth_user" in cookie_names

    @pytest.mark.unit
    def test_clear_auth_cookies_production(self, mock_response: Mock) -> None:
        """Test clearing auth cookies in production environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            service = CookieService()

            # Act
            service.clear_auth_cookies(mock_response)

            # Assert
            # Verify production security settings in cleared cookies
            for call in mock_response.set_cookie.call_args_list:
                assert call[1]["secure"] is True  # Production
                assert call[1]["samesite"] == "strict"  # Production
                assert call[1]["domain"] is None  # Production

    @pytest.mark.unit
    def test_get_cookie_domain_development(self) -> None:
        """Test cookie domain in development environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            domain = service._get_cookie_domain()

            # Assert
            assert domain == "localhost"

    @pytest.mark.unit
    def test_get_cookie_domain_production(self) -> None:
        """Test cookie domain in production environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            service = CookieService()

            # Act
            domain = service._get_cookie_domain()

            # Assert
            assert domain is None

    @pytest.mark.unit
    def test_get_samesite_policy_development(self) -> None:
        """Test SameSite policy in development environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            policy = service._get_samesite_policy()

            # Assert
            assert policy == "lax"

    @pytest.mark.unit
    def test_get_samesite_policy_production(self) -> None:
        """Test SameSite policy in production environment."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            service = CookieService()

            # Act
            policy = service._get_samesite_policy()

            # Assert
            assert policy == "strict"

    @pytest.mark.unit
    def test_cookie_expiration_consistency(self, mock_response: Mock, sample_token: Token) -> None:
        """Test that cookie expiration is consistent with token expiration."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            auth_token_call = mock_response.set_cookie.call_args_list[0]
            auth_user_call = mock_response.set_cookie.call_args_list[2]

            # Both auth_token and auth_user should have same expiration as token
            assert auth_token_call[1]["max_age"] == sample_token.expires_in
            assert auth_user_call[1]["max_age"] == sample_token.expires_in

            # Refresh token should have fixed 30-day expiration
            refresh_token_call = mock_response.set_cookie.call_args_list[1]
            assert refresh_token_call[1]["max_age"] == 60 * 60 * 24 * 30

    @pytest.mark.unit
    def test_auth_user_cookie_json_format(self, mock_response: Mock, sample_token: Token) -> None:
        """Test that auth_user cookie contains valid JSON."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            auth_user_call = mock_response.set_cookie.call_args_list[2]
            user_data_json = auth_user_call[1]["value"]

            # Verify it's valid JSON
            user_data = json.loads(user_data_json)
            assert user_data["isAuthenticated"] is True
            assert user_data["isNewUser"] is False

    @pytest.mark.unit
    def test_security_headers_consistency(self, mock_response: Mock, sample_token: Token) -> None:
        """Test that security headers are consistent across all cookies."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            # All cookies should have consistent security settings
            for call in mock_response.set_cookie.call_args_list:
                assert call[1]["secure"] is True
                assert call[1]["samesite"] == "strict"
                assert call[1]["path"] == "/"
                assert call[1]["domain"] is None

    @pytest.mark.unit
    def test_httponly_flag_behavior(self, mock_response: Mock, sample_token: Token) -> None:
        """Test HTTPOnly flag is set correctly for different cookie types."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            auth_token_call = mock_response.set_cookie.call_args_list[0]
            refresh_token_call = mock_response.set_cookie.call_args_list[1]
            auth_user_call = mock_response.set_cookie.call_args_list[2]

            # Security-sensitive cookies should be HTTPOnly
            assert auth_token_call[1]["httponly"] is True
            assert refresh_token_call[1]["httponly"] is True

            # User info cookie should be readable by frontend
            assert auth_user_call[1]["httponly"] is False

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "environment,expected_secure,expected_samesite,expected_domain",
        [
            ("development", False, "lax", "localhost"),
            ("production", True, "strict", None),
            ("staging", False, "lax", "localhost"),  # Non-production environment
            ("test", False, "lax", "localhost"),  # Non-production environment
        ],
    )
    def test_environment_specific_settings(
        self,
        mock_response: Mock,
        sample_token: Token,
        environment: str,
        expected_secure: bool,
        expected_samesite: str,
        expected_domain: str | None,
    ) -> None:
        """Test environment-specific cookie settings using parameterized tests."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": environment}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, sample_token)

            # Assert
            for call in mock_response.set_cookie.call_args_list:
                assert call[1]["secure"] == expected_secure
                assert call[1]["samesite"] == expected_samesite
                assert call[1]["domain"] == expected_domain


class TestCookieServiceEdgeCases:
    """Edge cases and error scenarios for CookieService."""

    @pytest.fixture
    def mock_response(self) -> Mock:
        """Create mock FastAPI response object."""
        response = Mock(spec=Response)
        response.set_cookie = Mock()
        return response

    @pytest.fixture
    def sample_token(self) -> Token:
        """Create sample token for testing."""
        return Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="bearer",
            expires_in=3600,  # 1 hour
            is_new_user=False,
        )

    @pytest.mark.unit
    def test_token_with_zero_expiration(self, mock_response: Mock) -> None:
        """Test handling token with zero expiration time."""
        # Arrange
        token = Token(
            access_token="test_token",
            refresh_token="test_refresh",
            token_type="bearer",
            expires_in=0,  # Zero expiration
            is_new_user=False,
        )
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, token)

            # Assert
            auth_token_call = mock_response.set_cookie.call_args_list[0]
            assert auth_token_call[1]["max_age"] == 0

    @pytest.mark.unit
    def test_token_with_large_expiration(self, mock_response: Mock) -> None:
        """Test handling token with very large expiration time."""
        # Arrange
        token = Token(
            access_token="test_token",
            refresh_token="test_refresh",
            token_type="bearer",
            expires_in=999999999,  # Very large expiration
            is_new_user=False,
        )
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            # Act
            service.set_auth_cookies(mock_response, token)

            # Assert
            auth_token_call = mock_response.set_cookie.call_args_list[0]
            assert auth_token_call[1]["max_age"] == 999999999

    @pytest.mark.unit
    def test_clear_cookies_maintains_security_settings(self, mock_response: Mock) -> None:
        """Test that clearing cookies maintains the same security settings."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            service = CookieService()

            # Act
            service.clear_auth_cookies(mock_response)

            # Assert
            # Verify cleared cookies have same security settings as when they were set
            for call in mock_response.set_cookie.call_args_list:
                assert call[1]["secure"] is True  # Production security
                assert call[1]["samesite"] == "strict"
                assert call[1]["path"] == "/"
                assert call[1]["domain"] is None

    @pytest.mark.unit
    def test_logging_integration(self, mock_response: Mock, sample_token: Token) -> None:
        """Test that appropriate logging occurs during cookie operations."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            service = CookieService()

            with patch("src.auth.services.cookie_service.logger") as mock_logger:
                # Act
                service.set_auth_cookies(mock_response, sample_token)

                # Assert
                mock_logger.info.assert_called_once()
                log_call = mock_logger.info.call_args
                assert "Secure authentication cookies set" in log_call[0][0]

                # Verify log contains relevant information
                log_kwargs = log_call[1]
                assert "access_token_expires" in log_kwargs
                assert "has_refresh_token" in log_kwargs
                assert "environment" in log_kwargs
