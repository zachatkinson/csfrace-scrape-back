"""Unit tests for auth database models following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- PostgreSQL database for integration tests (ZERO TOLERANCE for SQLite)
- Factory Pattern for test data
- 85%+ coverage target
- Focus on model properties and business logic

Tests User, WebAuthnCredential, WebAuthnChallenge, AccountLockout, and LinkedAccount models.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.database.models.auth import (
    AccountLockout,
    LinkedAccount,
    User,
    WebAuthnChallenge,
    WebAuthnCredential,
)

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def sample_user() -> User:
    """Factory for User test data - DRY principle."""
    return User(
        id=str(uuid4()),
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
    )


@pytest.fixture
def sample_webauthn_credential() -> WebAuthnCredential:
    """Factory for WebAuthnCredential test data."""
    return WebAuthnCredential(
        id=1,
        user_id=str(uuid4()),
        credential_id="test_credential_123",
        public_key="test_public_key",
        sign_count=0,
        device_name="Test Device",
        is_active=True,
    )


@pytest.fixture
def sample_webauthn_challenge() -> WebAuthnChallenge:
    """Factory for WebAuthnChallenge test data."""
    return WebAuthnChallenge(
        challenge_key="test_challenge_key",
        user_id=str(uuid4()),
        challenge_type="registration",
        challenge="test_challenge_base64_data",  # Base64url-encoded challenge
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


@pytest.fixture
def sample_account_lockout() -> AccountLockout:
    """Factory for AccountLockout test data."""
    return AccountLockout(
        user_id=str(uuid4()),
        username="testuser",
        failed_attempts=3,
        is_locked=False,
    )


# ============================================================================
# Test Suite 1: WebAuthnCredential Properties (3 tests) - Lines 317, 321-322
# ============================================================================


class TestWebAuthnCredentialProperties:
    """Test WebAuthnCredential property methods and revocation."""

    @pytest.mark.unit
    def test_is_revoked_property_false(
        self, sample_webauthn_credential: WebAuthnCredential
    ) -> None:
        """Test is_revoked returns False when revoked_at is None - Line 317."""
        # Arrange
        sample_webauthn_credential.revoked_at = None

        # Act
        result = sample_webauthn_credential.is_revoked

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_is_revoked_property_true(self, sample_webauthn_credential: WebAuthnCredential) -> None:
        """Test is_revoked returns True when revoked_at is set."""
        # Arrange
        sample_webauthn_credential.revoked_at = datetime.now(UTC)

        # Act
        result = sample_webauthn_credential.is_revoked

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_revoke_method(self, sample_webauthn_credential: WebAuthnCredential) -> None:
        """Test revoke() method marks credential inactive - Lines 321-322."""
        # Arrange
        sample_webauthn_credential.is_active = True
        sample_webauthn_credential.revoked_at = None

        # Act
        sample_webauthn_credential.revoke()

        # Assert
        assert sample_webauthn_credential.is_active is False
        assert sample_webauthn_credential.revoked_at is not None
        assert isinstance(sample_webauthn_credential.revoked_at, datetime)


# ============================================================================
# Test Suite 2: WebAuthnChallenge Properties (4 tests) - Lines 386, 391, 395
# ============================================================================


class TestWebAuthnChallengeProperties:
    """Test WebAuthnChallenge property methods and lifecycle."""

    @pytest.mark.unit
    def test_is_expired_property_false(self, sample_webauthn_challenge: WebAuthnChallenge) -> None:
        """Test is_expired returns False for valid challenge - Line 386."""
        # Arrange - Challenge expires in 5 minutes (set in fixture)

        # Act
        result = sample_webauthn_challenge.is_expired

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_is_expired_property_true(self, sample_webauthn_challenge: WebAuthnChallenge) -> None:
        """Test is_expired returns True for expired challenge."""
        # Arrange - Set expiration to past
        sample_webauthn_challenge.expires_at = datetime.now(UTC) - timedelta(minutes=1)

        # Act
        result = sample_webauthn_challenge.is_expired

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_is_used_property_false(self, sample_webauthn_challenge: WebAuthnChallenge) -> None:
        """Test is_used returns False when not used - Line 391."""
        # Arrange
        sample_webauthn_challenge.used_at = None

        # Act
        result = sample_webauthn_challenge.is_used

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_is_used_property_true(self, sample_webauthn_challenge: WebAuthnChallenge) -> None:
        """Test is_used returns True when used."""
        # Arrange
        sample_webauthn_challenge.used_at = datetime.now(UTC)

        # Act
        result = sample_webauthn_challenge.is_used

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_mark_used_method(self, sample_webauthn_challenge: WebAuthnChallenge) -> None:
        """Test mark_used() method sets used_at timestamp - Line 395."""
        # Arrange
        sample_webauthn_challenge.used_at = None

        # Act
        sample_webauthn_challenge.mark_used()

        # Assert
        assert sample_webauthn_challenge.used_at is not None
        assert isinstance(sample_webauthn_challenge.used_at, datetime)


# ============================================================================
# Test Suite 3: AccountLockout Factory Methods (4 tests) - Lines 513-518, 551-553
# ============================================================================


class TestAccountLockoutFactoryMethods:
    """Test AccountLockout factory methods for creating lockout records."""

    @pytest.mark.unit
    def test_create_lockout_record_with_duration(self) -> None:
        """Test create_lockout_record factory with duration - Lines 513-518."""
        # Arrange
        user_id = str(uuid4())
        username = "testuser"
        failed_attempts = 5
        reason = "Too many failed attempts"
        duration = 30  # 30 minutes

        # Act
        lockout = AccountLockout.create_lockout_record(
            user_id=user_id,
            username=username,
            failed_attempts=failed_attempts,
            lockout_reason=reason,
            lockout_duration_minutes=duration,
            client_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        # Assert
        assert lockout.user_id == user_id
        assert lockout.username == username
        assert lockout.failed_attempts == failed_attempts
        assert lockout.is_locked is True
        assert lockout.lockout_reason == reason
        assert lockout.locked_until is not None
        assert lockout.locked_at is not None
        # Check duration is approximately 30 minutes
        duration_seconds = (lockout.locked_until - lockout.locked_at).total_seconds()
        assert abs(duration_seconds - 1800) < 1  # Within 1 second of 30 minutes

    @pytest.mark.unit
    def test_create_lockout_record_permanent(self) -> None:
        """Test create_lockout_record factory with permanent lockout."""
        # Arrange
        user_id = str(uuid4())
        username = "testuser"

        # Act
        lockout = AccountLockout.create_lockout_record(
            user_id=user_id,
            username=username,
            failed_attempts=10,
            lockout_reason="Permanent ban",
            lockout_duration_minutes=None,  # Permanent
        )

        # Assert
        assert lockout.is_locked is True
        assert lockout.locked_until is None  # Permanent lockout

    @pytest.mark.unit
    def test_create_failed_attempt_record(self) -> None:
        """Test create_failed_attempt_record factory - Lines 551-553."""
        # Arrange
        user_id = str(uuid4())
        username = "testuser"
        client_ip = "192.168.1.100"
        user_agent = "Mozilla/5.0"

        # Act
        lockout = AccountLockout.create_failed_attempt_record(
            user_id=user_id,
            username=username,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # Assert
        assert lockout.user_id == user_id
        assert lockout.username == username
        assert lockout.failed_attempts == 0  # Factory creates new record, not incremented yet
        assert lockout.is_locked is False  # Not locked yet
        assert lockout.client_ip == client_ip
        assert lockout.user_agent == user_agent
        assert lockout.first_failed_attempt_at is not None

    @pytest.mark.unit
    def test_create_failed_attempt_record_minimal(self) -> None:
        """Test create_failed_attempt_record with minimal parameters."""
        # Arrange
        user_id = str(uuid4())
        username = "testuser"

        # Act
        lockout = AccountLockout.create_failed_attempt_record(
            user_id=user_id,
            username=username,
        )

        # Assert
        assert lockout.user_id == user_id
        assert lockout.username == username
        assert lockout.failed_attempts == 0  # Factory creates new record, not incremented yet
        assert lockout.is_locked is False
        assert lockout.client_ip is None
        assert lockout.user_agent is None


# ============================================================================
# Test Suite 4: Additional Property Methods (8 tests) - Cover remaining lines
# ============================================================================


class TestAccountLockoutProperties:
    """Test AccountLockout property methods and lifecycle."""

    @pytest.mark.unit
    def test_is_lockout_expired_property_true(self) -> None:
        """Test is_lockout_expired returns True for expired lockout - Lines 605-607."""
        # Arrange
        lockout = AccountLockout(
            user_id=str(uuid4()),
            username="testuser",
            is_locked=True,
            locked_until=datetime.now(UTC) - timedelta(hours=1),  # Expired
        )

        # Act
        result = lockout.is_lockout_expired

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_is_lockout_expired_property_false(self) -> None:
        """Test is_lockout_expired returns False when not expired."""
        # Arrange
        lockout = AccountLockout(
            user_id=str(uuid4()),
            username="testuser",
            is_locked=True,
            locked_until=datetime.now(UTC) + timedelta(hours=1),
        )

        # Act
        result = lockout.is_lockout_expired

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_lockout_remaining_minutes_property(self) -> None:
        """Test lockout_remaining_minutes property - Lines 612-619."""
        # Arrange
        lockout = AccountLockout(
            user_id=str(uuid4()),
            username="testuser",
            is_locked=True,
            locked_until=datetime.now(UTC) + timedelta(minutes=30),
        )

        # Act
        result = lockout.lockout_remaining_minutes

        # Assert
        assert result is not None
        assert 29 <= result <= 31  # Allow 1 minute tolerance for execution time

    @pytest.mark.unit
    def test_unlock_account_method(self) -> None:
        """Test unlock_account() method clears lockout - Lines 571-574."""
        # Arrange
        lockout = AccountLockout(
            user_id=str(uuid4()),
            username="testuser",
            is_locked=True,
            failed_attempts=5,
        )

        # Act
        lockout.unlock_account(unlocked_by="admin_user")

        # Assert
        assert lockout.is_locked is False
        assert lockout.unlocked_at is not None
        assert lockout.unlocked_by == "admin_user"

    @pytest.mark.unit
    def test_increment_failed_attempts(self) -> None:
        """Test increment_failed_attempts() method - Lines 585-593."""
        # Arrange
        lockout = AccountLockout(
            user_id=str(uuid4()),
            username="testuser",
            failed_attempts=2,
        )

        # Act
        lockout.increment_failed_attempts(client_ip="192.168.1.1", user_agent="TestAgent")

        # Assert
        assert lockout.failed_attempts == 3
        assert lockout.last_failed_attempt_at is not None
        assert lockout.client_ip == "192.168.1.1"
        assert lockout.user_agent == "TestAgent"

    @pytest.mark.unit
    def test_reset_failed_attempts(self) -> None:
        """Test reset_failed_attempts() method - Lines 597-600."""
        # Arrange
        lockout = AccountLockout(
            user_id=str(uuid4()),
            username="testuser",
            failed_attempts=5,
            first_failed_attempt_at=datetime.now(UTC),
            last_failed_attempt_at=datetime.now(UTC),
        )

        # Act
        lockout.reset_failed_attempts()

        # Assert
        assert lockout.failed_attempts == 0
        assert lockout.first_failed_attempt_at is None
        assert lockout.last_failed_attempt_at is None


# ============================================================================
# Test Suite 5: Model Representations (5 tests) - String methods
# ============================================================================


class TestModelRepresentations:
    """Test __repr__ methods for all auth models."""

    @pytest.mark.unit
    def test_user_repr(self, sample_user: User) -> None:
        """Test User string representation."""
        # Act
        repr_str = repr(sample_user)

        # Assert
        assert "User" in repr_str
        assert sample_user.username in repr_str
        assert sample_user.email in repr_str

    @pytest.mark.unit
    def test_webauthn_credential_repr(self, sample_webauthn_credential: WebAuthnCredential) -> None:
        """Test WebAuthnCredential string representation."""
        # Act
        repr_str = repr(sample_webauthn_credential)

        # Assert
        assert repr_str is not None
        assert "WebAuthnCredential" in repr_str
        assert str(sample_webauthn_credential.id) in repr_str
        assert sample_webauthn_credential.device_name is not None
        assert sample_webauthn_credential.device_name in repr_str

    @pytest.mark.unit
    def test_webauthn_challenge_repr(self, sample_webauthn_challenge: WebAuthnChallenge) -> None:
        """Test WebAuthnChallenge string representation."""
        # Act
        repr_str = repr(sample_webauthn_challenge)

        # Assert
        assert repr_str is not None
        assert "WebAuthnChallenge" in repr_str
        assert "registration" in repr_str  # challenge_type
        # user_id is a string, repr_str is also a string
        user_id = sample_webauthn_challenge.user_id
        assert user_id is not None
        assert user_id in repr_str

    @pytest.mark.unit
    def test_linked_account_repr(self) -> None:
        """Test LinkedAccount string representation."""
        # Arrange
        user_id = str(uuid4())
        linked_account = LinkedAccount(
            user_id=user_id,
            provider="google",
            provider_account_id="google_123",  # Correct field name
        )

        # Act
        repr_str = repr(linked_account)

        # Assert
        assert "LinkedAccount" in repr_str
        assert "google" in repr_str
        assert user_id in repr_str
