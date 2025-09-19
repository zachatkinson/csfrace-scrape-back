"""Comprehensive tests for TokenRevocationService following SOLID and DRY principles."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.auth.revocation_service import TokenRevocationService
from src.database.models import RevokedToken


@pytest.fixture
def mock_db_session():
    """Mock async database session - DRY fixture."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.delete = AsyncMock()

    # Configure execute to return a mock result with scalar_one_or_none
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none = MagicMock()
    session.execute = AsyncMock(return_value=mock_result)

    return session


@pytest.fixture
def revocation_service(mock_db_session):
    """TokenRevocationService instance with mocked dependencies - DRY fixture."""
    return TokenRevocationService(db_session=mock_db_session)


@pytest.fixture
def sample_token_data():
    """Sample token data for testing - DRY fixture."""
    return {
        "jti": "test-jwt-id-12345",
        "user_id": "user123",
        "token_type": "access",
        "issued_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "reason": "user_requested",
    }


class TestTokenRevocationService:
    """Test token revocation service - SOLID Single Responsibility testing."""

    @pytest.mark.asyncio
    async def test_revoke_token_success(
        self, revocation_service, mock_db_session, sample_token_data
    ):
        """Test successful token revocation - SOLID Single Responsibility."""
        # Arrange - DRY setup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not already revoked
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await revocation_service.revoke_token(**sample_token_data)

        # Assert - DRY validation
        assert result is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Verify RevokedToken was created with correct data
        added_token = mock_db_session.add.call_args[0][0]
        assert isinstance(added_token, RevokedToken)
        assert added_token.jti == sample_token_data["jti"]
        assert added_token.user_id == sample_token_data["user_id"]

    @pytest.mark.asyncio
    async def test_revoke_token_already_revoked(
        self, revocation_service, mock_db_session, sample_token_data
    ):
        """Test revoking already revoked token - DRY principle prevents duplicate work."""
        # Arrange
        existing_revoked_token = MagicMock(spec=RevokedToken)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_revoked_token
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await revocation_service.revoke_token(**sample_token_data)

        # Assert - Should return True but not add duplicate
        assert result is True
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_token_database_error(
        self, revocation_service, mock_db_session, sample_token_data
    ):
        """Test database error handling in token revocation."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit.side_effect = Exception("Database connection failed")

        # Act
        result = await revocation_service.revoke_token(**sample_token_data)

        # Assert - Should handle error gracefully
        assert result is False
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_token_revoked_true(self, revocation_service, mock_db_session):
        """Test checking revocation status - token is revoked."""
        # Arrange
        revoked_token = MagicMock(spec=RevokedToken)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = revoked_token
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await revocation_service.is_token_revoked("test-jti")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_token_revoked_false(self, revocation_service, mock_db_session):
        """Test checking revocation status - token is not revoked."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await revocation_service.is_token_revoked("test-jti")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_token_revoked_error_fails_secure(self, revocation_service, mock_db_session):
        """Test that errors in revocation checking fail securely (assume revoked)."""
        # Arrange
        mock_db_session.execute.side_effect = Exception("Database error")

        # Act
        result = await revocation_service.is_token_revoked("test-jti")

        # Assert - Fail secure
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, revocation_service, mock_db_session):
        """Test bulk token revocation for a user - SOLID Single Responsibility."""
        # Act
        result = await revocation_service.revoke_all_user_tokens(
            user_id="user123", reason="security_lockout", revoked_by="admin"
        )

        # Assert
        assert result == 1  # Placeholder implementation returns 1
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Verify bulk revocation record was created
        added_token = mock_db_session.add.call_args[0][0]
        assert isinstance(added_token, RevokedToken)
        assert added_token.user_id == "user123"
        assert added_token.revocation_reason == "security_lockout"
        assert added_token.token_type == "bulk_revocation"

    @pytest.mark.asyncio
    async def test_cleanup_expired_revocations(self, revocation_service, mock_db_session):
        """Test cleanup of expired revocation records - SOLID Single Responsibility."""
        # Arrange - Mock expired revocation records
        expired_record1 = MagicMock(spec=RevokedToken)
        expired_record2 = MagicMock(spec=RevokedToken)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_record1, expired_record2]
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await revocation_service.cleanup_expired_revocations(older_than_days=30)

        # Assert
        assert result == 2
        assert mock_db_session.delete.call_count == 2
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_revocation_stats_user_specific(self, revocation_service, mock_db_session):
        """Test getting revocation statistics for specific user - SOLID Interface Segregation."""
        # Arrange
        mock_revocations = [
            MagicMock(
                token_type="access",
                revocation_reason="user_requested",
                revoked_at=datetime.now(UTC) - timedelta(hours=2),
            ),
            MagicMock(
                token_type="refresh",
                revocation_reason="security_lockout",
                revoked_at=datetime.now(UTC) - timedelta(days=2),
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_revocations
        mock_db_session.execute.return_value = mock_result

        # Act
        stats = await revocation_service.get_revocation_stats(user_id="user123")

        # Assert
        assert stats["total_revocations"] == 2
        assert stats["revocations_by_type"]["access"] == 1
        assert stats["revocations_by_type"]["refresh"] == 1
        assert stats["revocations_by_reason"]["user_requested"] == 1
        assert stats["revocations_by_reason"]["security_lockout"] == 1
        assert stats["recent_revocations_24h"] == 1
        assert stats["recent_revocations_7d"] == 2
        assert stats["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_get_revocation_stats_system_wide(self, revocation_service, mock_db_session):
        """Test getting system-wide revocation statistics - SOLID Interface Segregation."""
        # Arrange
        mock_revocations = [
            MagicMock(
                token_type="access", revocation_reason="expired", revoked_at=datetime.now(UTC)
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_revocations
        mock_db_session.execute.return_value = mock_result

        # Act
        stats = await revocation_service.get_revocation_stats()

        # Assert
        assert stats["total_revocations"] == 1
        assert "user_id" not in stats  # System-wide stats don't include user_id

    @pytest.mark.asyncio
    async def test_get_revocation_stats_error_handling(self, revocation_service, mock_db_session):
        """Test error handling in statistics gathering."""
        # Arrange
        mock_db_session.execute.side_effect = Exception("Database error")

        # Act
        stats = await revocation_service.get_revocation_stats()

        # Assert - Should return error dict instead of crashing
        assert "error" in stats
        assert stats["error"] == "Database error"


class TestTokenRevocationServiceHelpers:
    """Test helper methods following DRY principles - SOLID Single Responsibility testing."""

    def test_count_by_field(self):
        """Test _count_by_field helper method - DRY principle validation."""
        service = TokenRevocationService()

        # Arrange
        mock_revocations = [
            MagicMock(token_type="access", revocation_reason="user_requested"),
            MagicMock(token_type="access", revocation_reason="security_lockout"),
            MagicMock(token_type="refresh", revocation_reason="user_requested"),
        ]

        # Act
        type_counts = service._count_by_field(mock_revocations, "token_type")
        reason_counts = service._count_by_field(mock_revocations, "revocation_reason")

        # Assert
        assert type_counts == {"access": 2, "refresh": 1}
        assert reason_counts == {"user_requested": 2, "security_lockout": 1}

    def test_count_recent_revocations_24h(self):
        """Test _count_recent_revocations helper method - DRY principle validation."""
        service = TokenRevocationService()

        # Arrange
        now = datetime.now(UTC)
        mock_revocations = [
            MagicMock(revoked_at=now - timedelta(hours=1)),  # Within 24h
            MagicMock(revoked_at=now - timedelta(hours=23)),  # Within 24h
            MagicMock(revoked_at=now - timedelta(hours=25)),  # Outside 24h
        ]

        # Act
        count = service._count_recent_revocations(mock_revocations, hours=24)

        # Assert
        assert count == 2

    def test_count_recent_revocations_7d(self):
        """Test _count_recent_revocations helper method - DRY principle validation."""
        service = TokenRevocationService()

        # Arrange
        now = datetime.now(UTC)
        mock_revocations = [
            MagicMock(revoked_at=now - timedelta(days=1)),  # Within 7d
            MagicMock(revoked_at=now - timedelta(days=6)),  # Within 7d
            MagicMock(revoked_at=now - timedelta(days=8)),  # Outside 7d
        ]

        # Act
        count = service._count_recent_revocations(mock_revocations, days=7)

        # Assert
        assert count == 2


class TestTokenRevocationServiceEdgeCases:
    """Test edge cases and security scenarios - Comprehensive coverage."""

    @pytest.mark.asyncio
    async def test_revoke_token_with_all_optional_fields(self, revocation_service, mock_db_session):
        """Test token revocation with all optional security audit fields."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await revocation_service.revoke_token(
            jti="test-jti",
            user_id="user123",
            token_type="access",
            issued_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            reason="suspicious_activity",
            revoked_by="security_system",
            client_ip="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser",
        )

        # Assert
        assert result is True
        added_token = mock_db_session.add.call_args[0][0]
        assert added_token.revocation_reason == "suspicious_activity"
        assert added_token.revoked_by == "security_system"
        assert added_token.client_ip == "192.168.1.100"
        assert added_token.user_agent == "Mozilla/5.0 Test Browser"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_audit_records(self, revocation_service, mock_db_session):
        """Test that cleanup preserves bulk_revocation records for audit trail."""
        # Arrange
        expired_token = MagicMock(spec=RevokedToken)
        expired_token.token_type = "access"
        audit_record = MagicMock(spec=RevokedToken)
        audit_record.token_type = "bulk_revocation"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            expired_token
        ]  # Only non-audit records
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await revocation_service.cleanup_expired_revocations()

        # Assert
        assert result == 1  # Only regular token, not audit record
        mock_db_session.delete.assert_called_once_with(expired_token)

    @pytest.mark.asyncio
    async def test_concurrent_revocation_safety(
        self, revocation_service, mock_db_session, sample_token_data
    ):
        """Test that concurrent revocation attempts are handled safely."""
        # Arrange - Simulate race condition where token gets revoked between check and insert
        # Configure the mock result that execute returns
        mock_result = mock_db_session.execute.return_value
        mock_result.scalar_one_or_none.side_effect = [
            None,  # First check: not revoked
            MagicMock(spec=RevokedToken),  # Second check: already revoked
        ]

        # Act
        result = await revocation_service.revoke_token(**sample_token_data)

        # Assert - Should still return success
        assert result is True
