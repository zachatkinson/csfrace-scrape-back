"""Unit tests for TokenService following audit_3.md standards.

Tests for JWT token creation and management service with comprehensive coverage
following AAA pattern and SOLID testing principles.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.auth.models import Token, User
from src.auth.services.token_service import TokenService
from src.constants.auth import BEARER_TOKEN_TYPE


class TestTokenService:
    """Test suite for TokenService following AAA pattern."""

    @pytest.fixture
    def sample_user(self):
        """Create sample user for testing."""
        return User(
            id=str(uuid4()),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            is_superuser=False,
            created_at=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_security_manager(self):
        """Mock security_manager for testing."""
        with patch("src.auth.services.token_service.security_manager") as mock:
            # Configure mock return values
            mock.create_access_token.return_value = ("mock_access_token", "mock_access_jti")
            mock.create_refresh_token.return_value = ("mock_refresh_token", "mock_refresh_jti")
            yield mock

    @pytest.fixture
    def mock_auth_config(self):
        """Mock auth_config for testing."""
        with patch("src.auth.services.token_service.auth_config") as mock:
            mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes
            yield mock

    @pytest.mark.unit
    def test_create_tokens_for_user_success(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test successful token creation for user.

        AAA Pattern:
        - Arrange: Set up user and mocks
        - Act: Create tokens
        - Assert: Verify token creation and properties
        """
        # Arrange
        scopes = ["read", "write"]
        is_new_user = True

        # Act
        result = TokenService.create_tokens_for_user(
            user=sample_user, is_new_user=is_new_user, scopes=scopes
        )

        # Assert
        assert isinstance(result, Token)
        assert result.access_token == "mock_access_token"
        assert result.refresh_token == "mock_refresh_token"
        assert result.token_type == BEARER_TOKEN_TYPE
        assert result.expires_in == 30 * 60  # 30 minutes in seconds
        assert result.is_new_user is True

        # Verify security manager was called correctly
        mock_security_manager.create_access_token.assert_called_once_with(
            data={"sub": sample_user.username, "user_id": sample_user.id, "scopes": scopes},
            expires_delta=timedelta(minutes=30),
        )
        mock_security_manager.create_refresh_token.assert_called_once_with(
            data={"sub": sample_user.username, "user_id": sample_user.id}
        )

    @pytest.mark.unit
    def test_create_tokens_for_user_default_parameters(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test token creation with default parameters.

        Ensures DRY principle compliance by testing default values.
        """
        # Arrange - no explicit scopes or is_new_user

        # Act
        result = TokenService.create_tokens_for_user(user=sample_user)

        # Assert
        assert isinstance(result, Token)
        assert result.access_token == "mock_access_token"
        assert result.refresh_token == "mock_refresh_token"
        assert result.is_new_user is False  # Default value

        # Verify empty scopes were passed
        mock_security_manager.create_access_token.assert_called_once_with(
            data={"sub": sample_user.username, "user_id": sample_user.id, "scopes": []},
            expires_delta=timedelta(minutes=30),
        )

    @pytest.mark.unit
    def test_create_tokens_for_user_empty_scopes(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test token creation with explicitly empty scopes."""
        # Arrange
        scopes = []

        # Act
        result = TokenService.create_tokens_for_user(user=sample_user, scopes=scopes)

        # Assert
        assert isinstance(result, Token)

        # Verify empty scopes were passed correctly
        mock_security_manager.create_access_token.assert_called_once_with(
            data={"sub": sample_user.username, "user_id": sample_user.id, "scopes": []},
            expires_delta=timedelta(minutes=30),
        )

    @pytest.mark.unit
    def test_create_tokens_for_user_with_custom_scopes(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test token creation with custom scopes array."""
        # Arrange
        custom_scopes = ["admin", "read", "write", "delete"]

        # Act
        result = TokenService.create_tokens_for_user(user=sample_user, scopes=custom_scopes)

        # Assert
        assert isinstance(result, Token)

        # Verify custom scopes were passed correctly
        mock_security_manager.create_access_token.assert_called_once_with(
            data={"sub": sample_user.username, "user_id": sample_user.id, "scopes": custom_scopes},
            expires_delta=timedelta(minutes=30),
        )

    @pytest.mark.unit
    def test_create_access_token_only_success(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test successful creation of access token only.

        Used for refresh token operations.
        """
        # Arrange - Act
        result = TokenService.create_access_token_only(user=sample_user)

        # Assert
        assert isinstance(result, Token)
        assert result.access_token == "mock_access_token"
        assert result.refresh_token is None  # No refresh token
        assert result.token_type == BEARER_TOKEN_TYPE
        assert result.expires_in == 30 * 60  # 30 minutes in seconds
        assert result.is_new_user is False  # Always False for refresh operations

        # Verify only access token was created
        mock_security_manager.create_access_token.assert_called_once_with(
            data={"sub": sample_user.username, "user_id": sample_user.id},
            expires_delta=timedelta(minutes=30),
        )
        mock_security_manager.create_refresh_token.assert_not_called()

    @pytest.mark.unit
    def test_create_access_token_only_user_data(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test that correct user data is included in access token."""
        # Arrange - Act
        result = TokenService.create_access_token_only(user=sample_user)

        # Assert
        # Verify the exact data passed to security manager
        expected_data = {"sub": sample_user.username, "user_id": sample_user.id}
        mock_security_manager.create_access_token.assert_called_once_with(
            data=expected_data,
            expires_delta=timedelta(minutes=30),
        )

    @pytest.mark.unit
    def test_token_expiration_calculation(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test that token expiration is calculated correctly in seconds."""
        # Arrange
        mock_auth_config.ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour

        # Act
        result = TokenService.create_tokens_for_user(user=sample_user)

        # Assert
        assert result.expires_in == 60 * 60  # 1 hour in seconds

    @pytest.mark.unit
    def test_token_type_consistency(self, sample_user, mock_security_manager, mock_auth_config):
        """Test that token type is consistent across all token creation methods."""
        # Arrange - Act
        full_token = TokenService.create_tokens_for_user(user=sample_user)
        access_only_token = TokenService.create_access_token_only(user=sample_user)

        # Assert
        assert full_token.token_type == BEARER_TOKEN_TYPE
        assert access_only_token.token_type == BEARER_TOKEN_TYPE
        assert full_token.token_type == access_only_token.token_type

    @pytest.mark.unit
    def test_is_new_user_flag_behavior(self, sample_user, mock_security_manager, mock_auth_config):
        """Test is_new_user flag behavior in different scenarios."""
        # Arrange - Act
        new_user_token = TokenService.create_tokens_for_user(user=sample_user, is_new_user=True)
        existing_user_token = TokenService.create_tokens_for_user(
            user=sample_user, is_new_user=False
        )
        refresh_token = TokenService.create_access_token_only(user=sample_user)

        # Assert
        assert new_user_token.is_new_user is True
        assert existing_user_token.is_new_user is False
        assert refresh_token.is_new_user is False  # Always False for refresh

    @pytest.mark.unit
    def test_user_data_inclusion(self, sample_user, mock_security_manager, mock_auth_config):
        """Test that all required user data is included in tokens."""
        # Arrange
        scopes = ["test_scope"]

        # Act
        TokenService.create_tokens_for_user(user=sample_user, scopes=scopes)

        # Assert
        # Check access token data
        access_call_args = mock_security_manager.create_access_token.call_args[1]["data"]
        assert access_call_args["sub"] == sample_user.username
        assert access_call_args["user_id"] == sample_user.id
        assert access_call_args["scopes"] == scopes

        # Check refresh token data
        refresh_call_args = mock_security_manager.create_refresh_token.call_args[1]["data"]
        assert refresh_call_args["sub"] == sample_user.username
        assert refresh_call_args["user_id"] == sample_user.id
        assert "scopes" not in refresh_call_args  # Refresh tokens don't include scopes

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "expire_minutes,expected_seconds",
        [
            (15, 900),  # 15 minutes
            (30, 1800),  # 30 minutes
            (60, 3600),  # 1 hour
            (120, 7200),  # 2 hours
        ],
    )
    def test_expiration_time_calculation_parametrized(
        self, sample_user, mock_security_manager, expire_minutes, expected_seconds
    ):
        """Test expiration time calculation with various durations.

        Parametrized test for comprehensive coverage of edge cases.
        """
        # Arrange
        with patch("src.auth.services.token_service.auth_config") as mock_config:
            mock_config.ACCESS_TOKEN_EXPIRE_MINUTES = expire_minutes

            # Act
            result = TokenService.create_tokens_for_user(user=sample_user)

            # Assert
            assert result.expires_in == expected_seconds

    @pytest.mark.unit
    def test_security_manager_integration(
        self, sample_user, mock_security_manager, mock_auth_config
    ):
        """Test integration with security_manager follows contract."""
        # Arrange
        scopes = ["admin"]

        # Act
        TokenService.create_tokens_for_user(user=sample_user, scopes=scopes)

        # Assert
        # Verify security manager was called with correct parameters
        assert mock_security_manager.create_access_token.call_count == 1
        assert mock_security_manager.create_refresh_token.call_count == 1

        # Verify timedelta objects are passed correctly
        access_call = mock_security_manager.create_access_token.call_args
        assert isinstance(access_call[1]["expires_delta"], timedelta)
        assert access_call[1]["expires_delta"] == timedelta(minutes=30)

    @pytest.mark.unit
    def test_method_isolation(self, sample_user, mock_security_manager, mock_auth_config):
        """Test that methods don't interfere with each other.

        Ensures SOLID Single Responsibility principle compliance.
        """
        # Arrange - Act
        full_token = TokenService.create_tokens_for_user(user=sample_user)

        # Reset mock to test isolation
        mock_security_manager.reset_mock()

        access_only = TokenService.create_access_token_only(user=sample_user)

        # Assert
        # Verify that second call didn't affect first result
        assert full_token.access_token == "mock_access_token"
        assert full_token.refresh_token == "mock_refresh_token"

        # Verify second call only created access token
        mock_security_manager.create_access_token.assert_called_once()
        mock_security_manager.create_refresh_token.assert_not_called()


class TestTokenServiceEdgeCases:
    """Edge cases and error scenarios for TokenService."""

    @pytest.fixture
    def user_with_special_chars(self):
        """User with special characters in username."""
        return User(
            id=str(uuid4()),
            username="test.user+special@domain",
            email="test@example.com",
            full_name="Test User with Special Chars",
            is_active=True,
            is_superuser=False,
            created_at=datetime.now(UTC),
        )

    @pytest.mark.unit
    def test_user_with_special_characters(
        self, user_with_special_chars, mock_security_manager, mock_auth_config
    ):
        """Test token creation with special characters in username."""
        with (
            patch("src.auth.services.token_service.security_manager", mock_security_manager),
            patch("src.auth.services.token_service.auth_config", mock_auth_config),
        ):
            # Act
            result = TokenService.create_tokens_for_user(user=user_with_special_chars)

            # Assert
            assert isinstance(result, Token)

            # Verify special characters are handled correctly
            access_call_data = mock_security_manager.create_access_token.call_args[1]["data"]
            assert access_call_data["sub"] == user_with_special_chars.username

    @pytest.mark.unit
    def test_large_scopes_array(self, sample_user, mock_security_manager, mock_auth_config):
        """Test token creation with large scopes array."""
        with (
            patch("src.auth.services.token_service.security_manager", mock_security_manager),
            patch("src.auth.services.token_service.auth_config", mock_auth_config),
        ):
            # Arrange
            large_scopes = [f"scope_{i}" for i in range(100)]

            # Act
            result = TokenService.create_tokens_for_user(user=sample_user, scopes=large_scopes)

            # Assert
            assert isinstance(result, Token)

            # Verify large scopes array is handled
            access_call_data = mock_security_manager.create_access_token.call_args[1]["data"]
            assert access_call_data["scopes"] == large_scopes
            assert len(access_call_data["scopes"]) == 100

    @pytest.fixture
    def sample_user(self):
        """Create sample user for testing."""
        return User(
            id=str(uuid4()),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            is_superuser=False,
            created_at=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_security_manager(self):
        """Mock security_manager for edge case testing."""
        with patch("src.auth.services.token_service.security_manager") as mock:
            mock.create_access_token.return_value = ("mock_access_token", "mock_access_jti")
            mock.create_refresh_token.return_value = ("mock_refresh_token", "mock_refresh_jti")
            yield mock

    @pytest.fixture
    def mock_auth_config(self):
        """Mock auth_config for edge case testing."""
        with patch("src.auth.services.token_service.auth_config") as mock:
            mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30
            yield mock
