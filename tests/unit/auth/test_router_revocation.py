"""Comprehensive tests for token revocation endpoints in auth router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auth.models import BulkTokenRevocationRequest, TokenRevocationRequest
from src.database.models import User


@pytest.fixture
def mock_current_user():
    """Mock current user for testing - DRY fixture."""
    user = MagicMock(spec=User)
    user.id = "user123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def mock_security_manager():
    """Mock SecurityManager - DRY fixture."""
    manager = AsyncMock()
    manager.verify_token = AsyncMock()
    return manager


@pytest.fixture
def mock_revocation_service():
    """Mock TokenRevocationService - DRY fixture."""
    service = AsyncMock()
    service.revoke_token = AsyncMock(return_value=True)
    service.revoke_all_user_tokens = AsyncMock(return_value=3)
    service.get_revocation_stats = AsyncMock()
    return service


@pytest.fixture
def sample_token():
    """Sample JWT token for testing - DRY fixture."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0dXNlciIsInVzZXJfaWQiOiJ1c2VyMTIzIiwianRpIjoidGVzdC1qdGktMTIzNDUiLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE2MDAwMDM2MDB9"


class TestRevokeTokenEndpoint:
    """Test /auth/revoke-token endpoint - SOLID Single Responsibility testing."""

    @pytest.mark.asyncio
    async def test_revoke_token_success(
        self, mock_current_user, mock_security_manager, mock_revocation_service, sample_token
    ):
        """Test successful token revocation - SOLID Single Responsibility."""
        # Arrange
        from src.auth.models import TokenData

        token_data = TokenData(
            username="testuser", user_id="user123", jti="test-jti-12345", token_type="access"
        )

        request_data = TokenRevocationRequest(token=sample_token, reason="user_requested")

        with (
            patch("src.auth.router.security_manager", mock_security_manager),
            patch("src.auth.router.get_current_active_user", return_value=mock_current_user),
            patch("src.auth.router.token_revocation_service", mock_revocation_service),
            patch("src.auth.router.get_remote_address", return_value="192.168.1.1"),
            patch("jwt.decode") as mock_jwt_decode,
        ):
            mock_security_manager.verify_token.return_value = token_data
            mock_jwt_decode.return_value = {
                "iat": 1600000000,
                "exp": 1600003600,
                "jti": "test-jti-12345",
            }

            # Import the endpoint function
            from src.auth.router import revoke_token

            # Create mock request
            mock_request = MagicMock()
            mock_request.headers.get.return_value = "Mozilla/5.0 Test Browser"

            # Act
            response = await revoke_token(mock_request, request_data, mock_current_user)

            # Assert
            assert response.success is True
            assert response.message == "Token revoked successfully"
            assert response.jti == "test-jti-12345"

            # Verify revocation service was called correctly
            mock_revocation_service.revoke_token.assert_called_once()
            call_args = mock_revocation_service.revoke_token.call_args[1]
            assert call_args["jti"] == "test-jti-12345"
            assert call_args["user_id"] == "user123"
            assert call_args["reason"] == "user_requested"
            assert call_args["client_ip"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_revoke_token_unauthorized_user(
        self, mock_current_user, mock_security_manager, sample_token
    ):
        """Test token revocation by unauthorized user - Security requirement."""
        # Arrange
        from src.auth.models import TokenData

        # Token belongs to different user
        token_data = TokenData(
            username="otheruser", user_id="other123", jti="test-jti-12345", token_type="access"
        )

        request_data = TokenRevocationRequest(token=sample_token)

        with patch("src.auth.router.security_manager", mock_security_manager):
            mock_security_manager.verify_token.return_value = token_data

            from src.auth.router import revoke_token

            mock_request = MagicMock()

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await revoke_token(mock_request, request_data, mock_current_user)

            # Should raise forbidden error
            assert "Cannot revoke token for another user" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_token_invalid_token(self, mock_current_user, mock_security_manager):
        """Test token revocation with invalid token format."""
        # Arrange
        request_data = TokenRevocationRequest(token="invalid.token.format")

        with (
            patch("src.auth.router.security_manager", mock_security_manager),
            patch("jwt.decode", side_effect=Exception("Invalid token")),
        ):
            mock_security_manager.verify_token.return_value = None

            from src.auth.router import revoke_token

            mock_request = MagicMock()

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await revoke_token(mock_request, request_data, mock_current_user)

            assert "Invalid token format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_token_service_failure(
        self, mock_current_user, mock_security_manager, mock_revocation_service, sample_token
    ):
        """Test token revocation when service fails."""
        # Arrange
        from src.auth.models import TokenData

        token_data = TokenData(
            username="testuser", user_id="user123", jti="test-jti-12345", token_type="access"
        )

        request_data = TokenRevocationRequest(token=sample_token)

        with (
            patch("src.auth.router.security_manager", mock_security_manager),
            patch("src.auth.router.token_revocation_service", mock_revocation_service),
            patch("jwt.decode") as mock_jwt_decode,
        ):
            mock_security_manager.verify_token.return_value = token_data
            mock_jwt_decode.return_value = {"iat": 1600000000, "exp": 1600003600}
            mock_revocation_service.revoke_token.return_value = False  # Service fails

            from src.auth.router import revoke_token

            mock_request = MagicMock()

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await revoke_token(mock_request, request_data, mock_current_user)

            assert "Failed to revoke token" in str(exc_info.value)


class TestRevokeAllTokensEndpoint:
    """Test /auth/revoke-all-tokens endpoint - SOLID Single Responsibility testing."""

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_success(self, mock_current_user, mock_revocation_service):
        """Test successful bulk token revocation."""
        # Arrange
        request_data = BulkTokenRevocationRequest(
            reason="password_change", revoke_all_sessions=True
        )

        with patch("src.auth.router.token_revocation_service", mock_revocation_service):
            mock_revocation_service.revoke_all_user_tokens.return_value = 5

            from src.auth.router import revoke_all_user_tokens

            mock_request = MagicMock()

            # Act
            response = await revoke_all_user_tokens(mock_request, request_data, mock_current_user)

            # Assert
            assert response.success is True
            assert "All tokens revoked successfully (5 sessions)" in response.message
            assert response.revoked_count == 5

            # Verify service called correctly
            mock_revocation_service.revoke_all_user_tokens.assert_called_once_with(
                user_id="user123", reason="password_change", revoked_by="testuser"
            )

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_service_error(
        self, mock_current_user, mock_revocation_service
    ):
        """Test bulk revocation when service fails."""
        # Arrange
        request_data = BulkTokenRevocationRequest(reason="security_incident")

        with patch("src.auth.router.token_revocation_service", mock_revocation_service):
            mock_revocation_service.revoke_all_user_tokens.side_effect = Exception("Database error")

            from src.auth.router import revoke_all_user_tokens

            mock_request = MagicMock()

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await revoke_all_user_tokens(mock_request, request_data, mock_current_user)

            assert "Failed to revoke tokens" in str(exc_info.value)


class TestRevocationStatsEndpoint:
    """Test /auth/revocation-stats endpoint - SOLID Single Responsibility testing."""

    @pytest.mark.asyncio
    async def test_get_revocation_stats_success(self, mock_current_user, mock_revocation_service):
        """Test successful retrieval of user revocation stats."""
        # Arrange
        mock_stats = {
            "total_revocations": 10,
            "revocations_by_type": {"access": 7, "refresh": 3},
            "revocations_by_reason": {"user_requested": 5, "security_lockout": 3, "expired": 2},
            "recent_revocations_24h": 2,
            "recent_revocations_7d": 8,
        }

        with patch("src.auth.router.token_revocation_service", mock_revocation_service):
            mock_revocation_service.get_revocation_stats.return_value = mock_stats

            from src.auth.router import get_revocation_stats

            # Act
            response = await get_revocation_stats(mock_current_user)

            # Assert
            assert response.total_revocations == 10
            assert response.revocations_by_type == {"access": 7, "refresh": 3}
            assert response.revocations_by_reason == {
                "user_requested": 5,
                "security_lockout": 3,
                "expired": 2,
            }
            assert response.recent_revocations_24h == 2
            assert response.recent_revocations_7d == 8
            assert response.user_id == "user123"

            # Verify service called with correct user ID
            mock_revocation_service.get_revocation_stats.assert_called_once_with(user_id="user123")

    @pytest.mark.asyncio
    async def test_get_revocation_stats_service_error(
        self, mock_current_user, mock_revocation_service
    ):
        """Test revocation stats when service fails."""
        # Arrange
        with patch("src.auth.router.token_revocation_service", mock_revocation_service):
            mock_revocation_service.get_revocation_stats.side_effect = Exception("Database error")

            from src.auth.router import get_revocation_stats

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await get_revocation_stats(mock_current_user)

            assert "Failed to get revocation statistics" in str(exc_info.value)


class TestAdminRevocationStatsEndpoint:
    """Test /auth/admin/revocation-stats endpoint - SOLID Single Responsibility testing."""

    @pytest.mark.asyncio
    async def test_get_system_revocation_stats_success(self, mock_revocation_service):
        """Test successful retrieval of system-wide revocation stats."""
        # Arrange
        mock_admin_user = MagicMock(spec=User)
        mock_admin_user.id = "admin123"
        mock_admin_user.username = "admin"
        mock_admin_user.is_superuser = True

        mock_stats = {
            "total_revocations": 500,
            "revocations_by_type": {"access": 300, "refresh": 150, "bulk_revocation": 50},
            "revocations_by_reason": {
                "user_requested": 200,
                "security_lockout": 150,
                "expired": 100,
                "suspicious_activity": 50,
            },
            "recent_revocations_24h": 25,
            "recent_revocations_7d": 100,
        }

        with patch("src.auth.router.token_revocation_service", mock_revocation_service):
            mock_revocation_service.get_revocation_stats.return_value = mock_stats

            from src.auth.router import get_system_revocation_stats

            # Act
            response = await get_system_revocation_stats(mock_admin_user)

            # Assert
            assert response.total_revocations == 500
            assert response.revocations_by_type == {
                "access": 300,
                "refresh": 150,
                "bulk_revocation": 50,
            }
            assert response.recent_revocations_24h == 25
            assert response.recent_revocations_7d == 100
            assert response.user_id is None  # System-wide stats don't include user_id

            # Verify service called without user ID filter
            mock_revocation_service.get_revocation_stats.assert_called_once_with()


class TestRevocationEndpointsEdgeCases:
    """Test edge cases and security scenarios - Comprehensive coverage."""

    @pytest.mark.asyncio
    async def test_revoke_expired_token_allowed(
        self, mock_current_user, mock_security_manager, mock_revocation_service, sample_token
    ):
        """Test that expired tokens can still be revoked - Security requirement."""
        # Arrange
        from src.auth.models import TokenData

        # Token data for expired token (verify_token would normally return None for expired)
        token_data = TokenData(
            username="testuser", user_id="user123", jti="expired-jti-12345", token_type="access"
        )

        request_data = TokenRevocationRequest(token=sample_token)

        with (
            patch("src.auth.router.security_manager", mock_security_manager),
            patch("src.auth.router.token_revocation_service", mock_revocation_service),
            patch("jwt.decode") as mock_jwt_decode,
        ):
            # Verify token succeeds (we want to allow revoking expired tokens)
            mock_security_manager.verify_token.return_value = token_data

            # JWT decode with verify_exp=False should work for expired tokens
            mock_jwt_decode.return_value = {
                "iat": 1600000000,
                "exp": 1600000001,  # Expired 1 second after issue
                "jti": "expired-jti-12345",
            }

            from src.auth.router import revoke_token

            mock_request = MagicMock()

            # Act
            response = await revoke_token(mock_request, request_data, mock_current_user)

            # Assert - Should succeed for expired tokens
            assert response.success is True
            assert response.jti == "expired-jti-12345"

            # Verify JWT was decoded with verify_exp=False
            mock_jwt_decode.assert_called_with(
                sample_token,
                mock_security_manager.create_access_token().__class__.auth_config.SECRET_KEY,
                algorithms=[
                    mock_security_manager.create_access_token().__class__.auth_config.ALGORITHM
                ],
                options={"verify_exp": False},
            )

    @pytest.mark.asyncio
    async def test_revocation_with_minimal_request_data(
        self, mock_current_user, mock_security_manager, mock_revocation_service, sample_token
    ):
        """Test revocation with minimal request data (no reason) - DRY principle validation."""
        # Arrange
        from src.auth.models import TokenData

        token_data = TokenData(
            username="testuser", user_id="user123", jti="test-jti-12345", token_type="access"
        )

        # Request without reason
        request_data = TokenRevocationRequest(token=sample_token)

        with (
            patch("src.auth.router.security_manager", mock_security_manager),
            patch("src.auth.router.token_revocation_service", mock_revocation_service),
            patch("jwt.decode") as mock_jwt_decode,
        ):
            mock_security_manager.verify_token.return_value = token_data
            mock_jwt_decode.return_value = {"iat": 1600000000, "exp": 1600003600}

            from src.auth.router import revoke_token

            mock_request = MagicMock()

            # Act
            response = await revoke_token(mock_request, request_data, mock_current_user)

            # Assert
            assert response.success is True

            # Verify default reason was used
            call_args = mock_revocation_service.revoke_token.call_args[1]
            assert call_args["reason"] == "user_requested"  # Default reason

    @pytest.mark.asyncio
    async def test_stats_with_empty_results(self, mock_current_user, mock_revocation_service):
        """Test stats endpoint with no revocations - DRY principle validation."""
        # Arrange
        mock_stats = {
            "total_revocations": 0,
            "revocations_by_type": {},
            "revocations_by_reason": {},
            "recent_revocations_24h": 0,
            "recent_revocations_7d": 0,
        }

        with patch("src.auth.router.token_revocation_service", mock_revocation_service):
            mock_revocation_service.get_revocation_stats.return_value = mock_stats

            from src.auth.router import get_revocation_stats

            # Act
            response = await get_revocation_stats(mock_current_user)

            # Assert
            assert response.total_revocations == 0
            assert response.revocations_by_type == {}
            assert response.revocations_by_reason == {}
            assert response.recent_revocations_24h == 0
            assert response.recent_revocations_7d == 0
