"""Tests for user account deletion functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set test-friendly rate limits BEFORE importing any modules that use rate limits
os.environ["TESTING"] = "true"

from src.auth.models import User
from src.auth.service import AuthService


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = MagicMock()
    return session


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    user = MagicMock(spec=User)
    user.id = "user123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def auth_service(mock_db_session):
    """AuthService instance for testing."""
    return AuthService(mock_db_session)


class TestDeleteUserAccount:
    """Test cases for delete_user_account method."""

    def test_delete_user_account_success(self, auth_service, mock_db_session, mock_user):
        """Test successful user account deletion."""
        # Arrange
        user_id = "user123"

        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        # Act
        result = auth_service.delete_user_account(user_id)

        # Assert
        assert result is True
        mock_db_session.execute.assert_called_once()
        mock_db_session.delete.assert_called_once_with(mock_user)
        mock_db_session.commit.assert_called_once()

    def test_delete_user_account_user_not_found(self, auth_service, mock_db_session):
        """Test deletion when user does not exist."""
        # Arrange
        user_id = "nonexistent"

        # Mock database query result - user not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act
        result = auth_service.delete_user_account(user_id)

        # Assert
        assert result is False
        mock_db_session.execute.assert_called_once()
        mock_db_session.delete.assert_not_called()
        mock_db_session.commit.assert_not_called()

    def test_delete_user_account_database_error(self, auth_service, mock_db_session, mock_user):
        """Test deletion when database error occurs."""
        # Arrange
        user_id = "user123"

        # Mock database query to succeed, but delete to fail
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        mock_db_session.delete.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            auth_service.delete_user_account(user_id)

        # Verify rollback was called (handled by decorator)
        mock_db_session.rollback.assert_called_once()


@pytest.mark.asyncio
class TestDeleteAccountEndpoint:
    """Test cases for the /auth/delete-account endpoint."""

    @patch("src.auth.router.get_current_active_user")
    @patch("src.auth.router.get_auth_service")
    async def test_delete_account_endpoint_success(
        self, mock_get_auth_service, mock_get_current_user
    ):
        """Test successful account deletion via endpoint."""
        # Arrange

        from fastapi import Request

        from src.auth.router import delete_user_account

        mock_user = MagicMock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"

        mock_auth_service = MagicMock()
        mock_auth_service.delete_user_account.return_value = True

        mock_get_current_user.return_value = mock_user
        mock_get_auth_service.return_value = mock_auth_service

        # Create a mock request for rate limiting
        mock_request = MagicMock(spec=Request)

        # Act
        result = await delete_user_account(
            request=mock_request, current_user=mock_user, auth_service=mock_auth_service
        )

        # Assert
        assert result.status_code == 200
        import json
        response_body = json.loads(result.body.decode())
        assert response_body == {"status": "success", "message": "Account deleted successfully"}
        mock_auth_service.delete_user_account.assert_called_once_with(mock_user.id)

    @patch("src.auth.router.get_current_active_user")
    @patch("src.auth.router.get_auth_service")
    async def test_delete_account_endpoint_failure(
        self, mock_get_auth_service, mock_get_current_user
    ):
        """Test account deletion failure via endpoint."""
        # Arrange
        from fastapi import Request

        from src.auth.router import delete_user_account

        mock_user = MagicMock(spec=User)
        mock_user.id = "user123"

        mock_auth_service = MagicMock()
        mock_auth_service.delete_user_account.return_value = False

        mock_get_current_user.return_value = mock_user
        mock_get_auth_service.return_value = mock_auth_service

        # Create a mock request for rate limiting
        mock_request = MagicMock(spec=Request)

        # Act & Assert
        with pytest.raises(Exception):  # APIErrorFactory will raise an HTTPException
            await delete_user_account(
                request=mock_request, current_user=mock_user, auth_service=mock_auth_service
            )
