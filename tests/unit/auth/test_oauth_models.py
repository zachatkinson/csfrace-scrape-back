"""Unit tests for OAuth authentication models - following CLAUDE.md IDT standards."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from src.auth.models import (
    LinkedAccount,
    OAuthCallback,
    OAuthProvider,
    OAuthUserInfo,
    PasswordValidatorMixin,
    SSOLoginRequest,
    SSOLoginResponse,
)


class TestOAuthProvider:
    """Test OAuth provider enumeration - Single Responsibility testing."""

    def test_oauth_provider_valid_values(self):
        """Test all valid OAuth provider values."""
        assert OAuthProvider.GOOGLE == "google"
        assert OAuthProvider.GITHUB == "github"
        assert OAuthProvider.MICROSOFT == "microsoft"

    def test_oauth_provider_string_conversion(self):
        """Test OAuth provider string conversion."""
        assert str(OAuthProvider.GOOGLE) == "google"
        assert str(OAuthProvider.GITHUB) == "github"
        assert str(OAuthProvider.MICROSOFT) == "microsoft"


class TestOAuthUserInfo:
    """Test OAuth user information model - Single Responsibility testing."""

    def test_oauth_user_info_valid_data(self):
        """Test OAuth user info with valid data."""
        user_info = OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id="123456789",
            email="user@example.com",
            name="John Doe",
            avatar_url="https://example.com/avatar.jpg",
        )

        assert user_info.provider == OAuthProvider.GOOGLE
        assert user_info.provider_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name == "John Doe"
        assert user_info.avatar_url == "https://example.com/avatar.jpg"

    def test_oauth_user_info_without_avatar(self):
        """Test OAuth user info without optional avatar URL."""
        user_info = OAuthUserInfo(
            provider=OAuthProvider.GITHUB,
            provider_id="987654321",
            email="developer@example.com",
            name="Jane Developer",
        )

        assert user_info.avatar_url is None
        assert user_info.provider == OAuthProvider.GITHUB

    def test_oauth_user_info_invalid_email(self):
        """Test OAuth user info with invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            OAuthUserInfo(
                provider=OAuthProvider.GOOGLE,
                provider_id="123",
                email="invalid-email",
                name="Test User",
            )

        assert "value is not a valid email address" in str(exc_info.value)


class TestOAuthCallback:
    """Test OAuth callback model - Interface Segregation testing."""

    def test_oauth_callback_success(self):
        """Test successful OAuth callback."""
        callback = OAuthCallback(
            code="auth_code_123", state="secure_state_456", provider=OAuthProvider.MICROSOFT
        )

        assert callback.code == "auth_code_123"
        assert callback.state == "secure_state_456"
        assert callback.provider == OAuthProvider.MICROSOFT
        assert callback.error is None
        assert callback.error_description is None

    def test_oauth_callback_with_error(self):
        """Test OAuth callback with error."""
        callback = OAuthCallback(
            code="",
            state="state_123",
            provider=OAuthProvider.GOOGLE,
            error="access_denied",
            error_description="User denied access",
        )

        assert callback.error == "access_denied"
        assert callback.error_description == "User denied access"


class TestSSOLoginRequest:
    """Test SSO login request model - DRY validation testing."""

    def test_sso_login_request_valid(self):
        """Test valid SSO login request."""
        request = SSOLoginRequest(
            provider=OAuthProvider.GOOGLE, redirect_uri="https://myapp.com/callback"
        )

        assert request.provider == OAuthProvider.GOOGLE
        assert request.redirect_uri == "https://myapp.com/callback"

    def test_sso_login_request_no_redirect_uri(self):
        """Test SSO login request without redirect URI."""
        request = SSOLoginRequest(provider=OAuthProvider.GITHUB)
        assert request.redirect_uri is None

    def test_sso_login_request_invalid_redirect_uri(self):
        """Test SSO login request with invalid redirect URI - DRY validation."""
        with pytest.raises(ValidationError) as exc_info:
            SSOLoginRequest(
                provider=OAuthProvider.GOOGLE, redirect_uri="ftp://invalid-protocol.com"
            )

        assert "Redirect URI must be HTTP or HTTPS" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_uri",
        [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd",
            "not-a-url-at-all",
        ],
    )
    def test_sso_login_request_security_validation(self, invalid_uri):
        """Test SSO login request rejects dangerous URIs - Security validation."""
        with pytest.raises(ValidationError):
            SSOLoginRequest(provider=OAuthProvider.GOOGLE, redirect_uri=invalid_uri)


class TestSSOLoginResponse:
    """Test SSO login response model - Consistent interface testing."""

    def test_sso_login_response_valid(self):
        """Test valid SSO login response."""
        response = SSOLoginResponse(
            authorization_url="https://accounts.google.com/oauth/authorize?client_id=123",
            state="secure_random_state",
            provider=OAuthProvider.GOOGLE,
        )

        assert "accounts.google.com" in response.authorization_url
        assert response.state == "secure_random_state"
        assert response.provider == OAuthProvider.GOOGLE


class TestLinkedAccount:
    """Test linked account model - Multiple provider support."""

    def test_linked_account_valid(self):
        """Test valid linked account."""
        from datetime import datetime

        linked_at = datetime.now(UTC)
        account = LinkedAccount(
            user_id="user_123",
            provider=OAuthProvider.MICROSOFT,
            provider_id="ms_user_456",
            provider_email="user@company.com",
            linked_at=linked_at,
            is_primary=True,
        )

        assert account.user_id == "user_123"
        assert account.provider == OAuthProvider.MICROSOFT
        assert account.provider_id == "ms_user_456"
        assert account.is_primary is True
        assert account.linked_at == linked_at

    def test_linked_account_default_not_primary(self):
        """Test linked account defaults to not primary."""
        from datetime import datetime

        account = LinkedAccount(
            user_id="user_123",
            provider=OAuthProvider.GITHUB,
            provider_id="gh_user_789",
            provider_email="dev@example.com",
            linked_at=datetime.now(UTC),
        )

        assert account.is_primary is False


class TestPasswordValidatorMixin:
    """Test password validation mixin - DRY principle testing."""

    def test_password_validator_mixin_valid_password(self):
        """Test password validator with valid password."""
        password = "SecurePass123"
        result = PasswordValidatorMixin.validate_password_strength(password)
        assert result == password

    @pytest.mark.parametrize(
        "invalid_password,expected_error",
        [
            ("short", "Password must be at least 8 characters"),
            ("alllowercase123", "Password must contain uppercase letter"),
            ("ALLUPPERCASE123", "Password must contain lowercase letter"),
            ("NoNumbersHere", "Password must contain number"),
        ],
    )
    def test_password_validator_mixin_invalid_passwords(self, invalid_password, expected_error):
        """Test password validator with various invalid passwords - Comprehensive validation."""
        with pytest.raises(ValueError) as exc_info:
            PasswordValidatorMixin.validate_password_strength(invalid_password)

        assert expected_error in str(exc_info.value)

    def test_password_validator_mixin_edge_case_exactly_8_chars(self):
        """Test password validator with exactly 8 character password."""
        password = "Pass123A"
        result = PasswordValidatorMixin.validate_password_strength(password)
        assert result == password
        assert len(result) == 8
