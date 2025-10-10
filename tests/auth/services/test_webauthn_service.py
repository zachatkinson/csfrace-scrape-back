"""Unit tests for WebAuthn service following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Mock external webauthn library calls (NO real FIDO2 operations)
- PostgreSQL database for integration tests
- Factory Pattern for test data
- 85%+ coverage target
- Focus on business logic, NOT third-party library functionality

Tests WebAuthn/Passkeys authentication flows - 80% unit tests (MANDATORY).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from src.auth.webauthn_service import (
    CredentialMetadata,
    PasskeyManager,
    WebAuthnConfig,
    WebAuthnCredential,
    WebAuthnService,
)

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def mock_db_session() -> Mock:
    """Mock database session for unit tests - MANDATORY isolation."""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def mock_auth_service() -> Mock:
    """Mock AuthService - Dependency Inversion."""
    auth_service = Mock()
    mock_user = Mock(
        id=str(uuid4()),
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
    )
    auth_service.get_user_by_id.return_value = mock_user
    return auth_service


@pytest.fixture
def webauthn_config() -> Any:
    """WebAuthn configuration - DRY principle."""
    return WebAuthnConfig(rp_id="localhost", rp_name="Test RP", origin="http://localhost:3000")


@pytest.fixture
def webauthn_service(mock_db_session: Mock, webauthn_config: Any, mock_auth_service: Mock) -> Any:
    """Create WebAuthnService instance - MANDATORY DI."""
    return WebAuthnService(
        db_session=mock_db_session, config=webauthn_config, auth_service=mock_auth_service
    )


@pytest.fixture
def sample_user() -> Mock:
    """Factory for User model - DRY principle."""
    return Mock(
        id=str(uuid4()),
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
    )


@pytest.fixture
def sample_credential() -> Any:
    """Factory for WebAuthn credential - DRY principle."""
    return WebAuthnCredential(
        credential_id="test_credential_id_123",
        public_key="test_public_key_base64",
        sign_count=0,
        user_id=str(uuid4()),
        metadata=CredentialMetadata(
            created_at=datetime.now(UTC), device_name="Test Device", is_active=True
        ),
    )


# ============================================================================
# Test Suite 1: Registration Flow (3 tests) - MANDATORY AAA Pattern
# ============================================================================


class TestWebAuthnRegistration:
    """Test WebAuthn registration flow - MANDATORY business logic focus."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_registration_options_creates_challenge(
        self, webauthn_service: Any, sample_user: Mock
    ) -> None:
        """Test registration options generation creates challenge.

        AAA Pattern:
        - Arrange: Mock user credentials lookup
        - Act: Generate registration options
        - Assert: Challenge created and stored
        """
        # Arrange
        webauthn_service._get_user_credentials = Mock(return_value=[])

        # Mock webauthn library call (MANDATORY - don't test third-party)
        with patch("src.auth.webauthn_service.generate_registration_options") as mock_gen:
            mock_options = Mock()
            mock_options.challenge = b"test_challenge"
            mock_options.rp.id = "localhost"
            mock_options.rp.name = "Test RP"
            mock_options.user.id = sample_user.id.encode("utf-8")
            mock_options.user.name = sample_user.username
            mock_options.user.display_name = sample_user.full_name
            mock_options.pub_key_cred_params = []
            mock_options.timeout = 60000
            mock_options.authenticator_selection = None
            mock_options.attestation = "none"
            mock_gen.return_value = mock_options

            # Act
            options, challenge_key = await webauthn_service.generate_registration_options(sample_user)

        # Assert - Test OUR business logic using challenge storage API
        challenge_data = await webauthn_service._challenge_storage.get_challenge(challenge_key)
        assert challenge_data is not None
        assert challenge_data["user_id"] == sample_user.id
        assert challenge_data["type"] == "registration"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_verify_registration_stores_credential(
        self, webauthn_service: Any, sample_user: Mock
    ) -> None:
        """Test registration verification stores credential in database.

        Focus: Business logic of storing credential, NOT webauthn verification.
        """
        # Arrange
        challenge_key = f"reg_{sample_user.id}_challenge"
        # Store challenge using the challenge storage API
        await webauthn_service._challenge_storage.store_challenge(
            challenge_key,
            {
                "challenge": "test_challenge",
                "user_id": sample_user.id,
                "type": "registration",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

        mock_credential = Mock()
        mock_credential.id = b"credential_id"
        mock_credential.raw_id = b"credential_id"

        # Mock webauthn verification (MANDATORY - don't test third-party)
        mock_verification = Mock()
        mock_verification.credential_id = b"test_credential_id"
        mock_verification.credential_public_key = b"test_public_key"
        mock_verification.sign_count = 0

        webauthn_service._store_credential = Mock()

        # Act
        with patch("src.auth.webauthn_service.verify_registration_response") as mock_verify:
            mock_verify.return_value = mock_verification

            result = await webauthn_service.verify_registration_response(
                mock_credential, challenge_key, device_name="Test Device"
            )

        # Assert - Test OUR business logic
        assert result.user_id == sample_user.id
        assert result.metadata.device_name == "Test Device"
        # Verify challenge was deleted
        challenge_data = await webauthn_service._challenge_storage.get_challenge(challenge_key)
        assert challenge_data is None
        webauthn_service._store_credential.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_registration_rejects_invalid_challenge(self, webauthn_service: Any) -> None:
        """Test registration rejects invalid challenge - Security validation."""
        # Arrange
        invalid_challenge = "invalid_key"
        mock_credential = Mock()

        # Act & Assert - Test OUR validation logic
        with pytest.raises(ValueError, match="Invalid or expired challenge"):
            await webauthn_service.verify_registration_response(mock_credential, invalid_challenge)


# ============================================================================
# Test Suite 2: Authentication Flow (3 tests) - MANDATORY coverage
# ============================================================================


class TestWebAuthnAuthentication:
    """Test WebAuthn authentication flow - Business logic focus."""

    @pytest.mark.unit
    def test_generate_authentication_options_creates_challenge(
        self, webauthn_service: Any, sample_user: Mock, sample_credential: Any
    ) -> None:
        """Test authentication options generation creates challenge."""
        # Arrange
        webauthn_service._get_user_credentials = Mock(return_value=[sample_credential])

        # Mock webauthn library (MANDATORY)
        with patch("src.auth.webauthn_service.generate_authentication_options") as mock_gen:
            mock_options = Mock()
            mock_options.challenge = b"test_challenge"
            mock_options.rp_id = "localhost"
            mock_options.timeout = 60000
            mock_options.user_verification = "preferred"
            mock_gen.return_value = mock_options

            # Act
            options, challenge_key = webauthn_service.generate_authentication_options(sample_user)

        # Assert - Test OUR business logic
        assert challenge_key in webauthn_service._pending_challenges
        assert webauthn_service._pending_challenges[challenge_key]["user_id"] == sample_user.id
        assert webauthn_service._pending_challenges[challenge_key]["type"] == "authentication"

    @pytest.mark.unit
    def test_verify_authentication_updates_credential(
        self,
        webauthn_service: Any,
        sample_user: Mock,
        sample_credential: Any,
        mock_auth_service: Mock,
    ) -> None:
        """Test authentication updates credential sign count and usage."""
        # Arrange
        challenge_key = f"auth_{sample_user.id}_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": sample_user.id,
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        mock_credential = Mock()
        mock_credential.raw_id = b"credential_id"

        # Make sure credential belongs to the correct user
        sample_credential.user_id = sample_user.id
        webauthn_service._get_credential_by_id = Mock(return_value=sample_credential)
        webauthn_service._update_credential = Mock()

        # Make mock_auth_service return the sample_user
        mock_auth_service.get_user_by_id.return_value = sample_user

        # Mock webauthn verification (MANDATORY)
        mock_verification = Mock()
        mock_verification.new_sign_count = 1

        # Act
        with patch("src.auth.webauthn_service.verify_authentication_response") as mock_verify:
            mock_verify.return_value = mock_verification

            user, credential = webauthn_service.verify_authentication_response(
                mock_credential, challenge_key
            )

        # Assert - Test OUR business logic
        assert user.id == sample_user.id
        assert credential.sign_count == 1
        assert challenge_key not in webauthn_service._pending_challenges
        webauthn_service._update_credential.assert_called_once()

    @pytest.mark.unit
    def test_authentication_rejects_invalid_challenge(self, webauthn_service: Any) -> None:
        """Test authentication rejects invalid challenge - Security validation."""
        # Arrange
        invalid_challenge = "invalid_key"
        mock_credential = Mock()

        # Act & Assert - Test OUR validation logic
        with pytest.raises(ValueError, match="Invalid or expired challenge"):
            webauthn_service.verify_authentication_response(mock_credential, invalid_challenge)


# ============================================================================
# Test Suite 3: Credential Management (3 tests) - Business logic
# ============================================================================


class TestCredentialManagement:
    """Test credential management operations - MANDATORY business logic."""

    @pytest.mark.unit
    def test_get_user_credentials(self, webauthn_service: Any, sample_user: Mock) -> None:
        """Test retrieving user credentials."""
        # Arrange
        mock_credentials = [Mock(), Mock()]
        webauthn_service._get_user_credentials = Mock(return_value=mock_credentials)

        # Act
        credentials = webauthn_service.get_user_credentials(sample_user)

        # Assert
        assert len(credentials) == 2
        webauthn_service._get_user_credentials.assert_called_once_with(sample_user.id)

    @pytest.mark.unit
    def test_revoke_credential_success(
        self, webauthn_service: Any, sample_user: Mock, sample_credential: Any
    ) -> None:
        """Test credential revocation marks credential inactive."""
        # Arrange
        sample_credential.user_id = sample_user.id
        webauthn_service._get_credential_by_id = Mock(return_value=sample_credential)
        webauthn_service._update_credential = Mock()

        # Act
        result = webauthn_service.revoke_credential(sample_user, sample_credential.credential_id)

        # Assert - Test OUR business logic
        assert result is True
        assert sample_credential.metadata.is_active is False
        webauthn_service._update_credential.assert_called_once()

    @pytest.mark.unit
    def test_cleanup_expired_challenges(self, webauthn_service: Any, sample_user: Mock) -> None:
        """Test cleanup of expired challenges - Maintenance logic."""
        # Arrange
        current_time = datetime.now(UTC)

        # Expired challenge (15 minutes old)
        expired_key = f"reg_{sample_user.id}_expired"
        webauthn_service._pending_challenges[expired_key] = {
            "challenge": "expired",
            "user_id": sample_user.id,
            "type": "registration",
            "created_at": current_time - timedelta(minutes=15),
        }

        # Valid challenge (5 minutes old)
        valid_key = f"reg_{sample_user.id}_valid"
        webauthn_service._pending_challenges[valid_key] = {
            "challenge": "valid",
            "user_id": sample_user.id,
            "type": "registration",
            "created_at": current_time - timedelta(minutes=5),
        }

        # Act
        cleaned = webauthn_service.cleanup_expired_challenges(max_age_minutes=10)

        # Assert - Test OUR cleanup logic
        assert cleaned == 1
        assert expired_key not in webauthn_service._pending_challenges
        assert valid_key in webauthn_service._pending_challenges


# ============================================================================
# Test Suite 4: Edge Cases (2 tests) - Security validation
# ============================================================================


class TestWebAuthnEdgeCases:
    """Edge cases and security scenarios - MANDATORY security testing."""

    @pytest.mark.unit
    def test_authentication_rejects_inactive_credential(
        self, webauthn_service: Any, sample_user: Mock, sample_credential: Any
    ) -> None:
        """Test authentication rejects inactive credentials - Security."""
        # Arrange
        challenge_key = f"auth_{sample_user.id}_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": sample_user.id,
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        sample_credential.metadata.is_active = False
        webauthn_service._get_credential_by_id = Mock(return_value=sample_credential)

        mock_credential = Mock()
        mock_credential.raw_id = b"credential_id"

        # Act & Assert - Test OUR security logic
        with pytest.raises(ValueError, match="Credential not found or inactive"):
            webauthn_service.verify_authentication_response(mock_credential, challenge_key)

    @pytest.mark.unit
    def test_revoke_credential_wrong_user_fails(
        self, webauthn_service: Any, sample_user: Mock, sample_credential: Any
    ) -> None:
        """Test credential revocation fails for wrong user - Security."""
        # Arrange
        sample_credential.user_id = "different_user_id"
        webauthn_service._get_credential_by_id = Mock(return_value=sample_credential)

        # Act
        result = webauthn_service.revoke_credential(sample_user, sample_credential.credential_id)

        # Assert - Test OUR security logic
        assert result is False


# ============================================================================
# Test Suite 5: PasskeyManager Facade (2 tests) - High-level API
# ============================================================================


class TestPasskeyManager:
    """Test PasskeyManager facade - High-level API testing."""

    @pytest.fixture
    def passkey_manager(self, webauthn_service: Any) -> Any:
        """Create PasskeyManager instance."""
        return PasskeyManager(webauthn_service)

    @pytest.mark.unit
    def test_start_passkey_registration(
        self, passkey_manager: Any, webauthn_service: Any, sample_user: Mock
    ) -> None:
        """Test passkey registration returns proper API format."""
        # Arrange
        mock_options = Mock()
        mock_options.challenge = "test_challenge"
        mock_options.timeout = 60000
        mock_options.relying_party = Mock()
        mock_options.relying_party.rp = {"id": "localhost", "name": "Test RP"}
        mock_options.user = {"id": "user_id", "name": "testuser", "displayName": "Test User"}
        mock_options.credential_options = Mock()
        mock_options.credential_options.pub_key_cred_params = []
        mock_options.credential_options.exclude_credentials = []
        mock_options.credential_options.authenticator_selection = {}
        mock_options.credential_options.attestation = "none"

        webauthn_service.generate_registration_options = Mock(
            return_value=(mock_options, "challenge_key")
        )

        # Act
        result = passkey_manager.start_passkey_registration(sample_user, device_name="Test Device")

        # Assert - Test API format
        assert "publicKey" in result
        assert "challengeKey" in result
        assert "deviceName" in result
        assert result["deviceName"] == "Test Device"

    @pytest.mark.unit
    def test_get_passkey_summary(
        self, passkey_manager: Any, webauthn_service: Any, sample_user: Mock
    ) -> None:
        """Test passkey summary returns dashboard data."""
        # Arrange
        mock_credentials = [
            Mock(
                credential_id="cred1",
                metadata=Mock(
                    device_name="Device 1",
                    created_at=datetime.now(UTC),
                    last_used_at=datetime.now(UTC),
                    is_active=True,
                ),
            ),
            Mock(
                credential_id="cred2",
                metadata=Mock(
                    device_name="Device 2",
                    created_at=datetime.now(UTC),
                    last_used_at=None,
                    is_active=False,
                ),
            ),
        ]
        webauthn_service.get_user_credentials = Mock(return_value=mock_credentials)

        # Act
        result = passkey_manager.get_passkey_summary(sample_user)

        # Assert - Test summary format
        assert result["total_passkeys"] == 2
        assert result["active_passkeys"] == 1
        assert len(result["devices"]) == 2


# ============================================================================
# Test Suite 6: Enhanced Edge Cases (7 tests) - Missing coverage
# ============================================================================


class TestWebAuthnEnhancedEdgeCases:
    """Test additional edge cases to achieve 95%+ coverage."""

    @pytest.mark.unit
    def test_registration_rejects_wrong_challenge_type(
        self, webauthn_service: Any, sample_user: Mock
    ) -> None:
        """Test registration rejects authentication challenge - Line 217."""
        # Arrange - Create authentication challenge instead of registration
        challenge_key = f"reg_{sample_user.id}_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": sample_user.id,
            "type": "authentication",  # Wrong type!
            "created_at": datetime.now(UTC),
        }

        mock_credential = Mock()

        # Act & Assert
        with pytest.raises(ValueError, match="Challenge type mismatch"):
            webauthn_service.verify_registration_response(mock_credential, challenge_key)

    @pytest.mark.unit
    def test_authentication_rejects_wrong_challenge_type(
        self, webauthn_service: Any, sample_user: Mock
    ) -> None:
        """Test authentication rejects registration challenge - Line 317."""
        # Arrange - Create registration challenge instead of authentication
        challenge_key = f"auth_{sample_user.id}_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": sample_user.id,
            "type": "registration",  # Wrong type!
            "created_at": datetime.now(UTC),
        }

        mock_credential = Mock()
        mock_credential.raw_id = b"credential_id"

        # Act & Assert
        with pytest.raises(ValueError, match="Challenge type mismatch"):
            webauthn_service.verify_authentication_response(mock_credential, challenge_key)

    @pytest.mark.unit
    def test_usernameless_authentication_no_user_provided(self, webauthn_service: Any) -> None:
        """Test usernameless/discoverable authentication - Lines 265-266."""
        # Arrange - No user provided (usernameless login)
        with patch("src.auth.webauthn_service.generate_authentication_options") as mock_gen:
            mock_options = Mock()
            mock_options.challenge = b"test_challenge"
            mock_options.rp_id = "localhost"
            mock_options.timeout = 60000
            mock_options.user_verification = "preferred"
            mock_gen.return_value = mock_options

            # Act - Pass None for user (usernameless)
            options, challenge_key = webauthn_service.generate_authentication_options(user=None)

        # Assert
        assert "auth_any_" in challenge_key
        assert webauthn_service._pending_challenges[challenge_key]["user_id"] is None
        assert webauthn_service._pending_challenges[challenge_key]["type"] == "authentication"
        # Should pass empty allow_credentials for discoverable credentials
        assert options.allow_credentials == []

    @pytest.mark.unit
    def test_authentication_rejects_inactive_user(
        self,
        webauthn_service: Any,
        sample_user: Mock,
        sample_credential: Any,
        mock_auth_service: Mock,
    ) -> None:
        """Test authentication rejects inactive user - Line 346."""
        # Arrange
        challenge_key = f"auth_{sample_user.id}_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": sample_user.id,
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        mock_credential = Mock()
        mock_credential.raw_id = b"credential_id"

        sample_credential.user_id = sample_user.id
        webauthn_service._get_credential_by_id = Mock(return_value=sample_credential)
        webauthn_service._update_credential = Mock()

        # Make user inactive
        inactive_user = Mock(
            id=sample_user.id,
            username="testuser",
            is_active=False,  # Inactive!
        )
        mock_auth_service.get_user_by_id.return_value = inactive_user

        # Mock webauthn verification
        mock_verification = Mock()
        mock_verification.new_sign_count = 1

        # Act & Assert
        with patch("src.auth.webauthn_service.verify_authentication_response") as mock_verify:
            mock_verify.return_value = mock_verification

            with pytest.raises(ValueError, match="User not found or inactive"):
                webauthn_service.verify_authentication_response(mock_credential, challenge_key)

    @pytest.mark.unit
    def test_passkey_authentication_usernameless(
        self, mock_db_session: Mock, webauthn_config: Any, mock_auth_service: Mock
    ) -> None:
        """Test PasskeyManager start_passkey_authentication without user - Lines 506-508."""
        # Arrange
        webauthn_service = WebAuthnService(
            db_session=mock_db_session, config=webauthn_config, auth_service=mock_auth_service
        )
        passkey_manager = PasskeyManager(webauthn_service)

        mock_options = Mock()
        mock_options.challenge = "test_challenge"
        mock_options.timeout = 60000
        mock_options.rp_id = "localhost"
        mock_options.allow_credentials = []
        mock_options.user_verification = "preferred"

        with patch.object(
            webauthn_service,
            "generate_authentication_options",
            return_value=(mock_options, "challenge_key_any"),
        ) as mock_generate:
            # Act - No user provided (usernameless)
            result = passkey_manager.start_passkey_authentication(user=None)

            # Assert
            assert "publicKey" in result
            assert "challengeKey" in result
            assert result["challengeKey"] == "challenge_key_any"
            mock_generate.assert_called_once_with(None)


# ============================================================================
# Test Suite 7: Private Method Coverage (3 tests) - Database operations
# ============================================================================


class TestWebAuthnPrivateMethods:
    """Test private database operation methods - Lines 387-475."""

    @pytest.mark.unit
    def test_get_user_credentials_empty_list(
        self, mock_db_session: Mock, webauthn_config: Any, mock_auth_service: Mock
    ) -> None:
        """Test _get_user_credentials when user has no credentials - Lines 387-396."""
        # Arrange
        webauthn_service = WebAuthnService(
            db_session=mock_db_session, config=webauthn_config, auth_service=mock_auth_service
        )

        # Mock database query returning empty list
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []  # No credentials
        mock_db_session.query.return_value = mock_query

        # Act
        credentials = webauthn_service._get_user_credentials("user_id_123")

        # Assert
        assert credentials == []
        mock_db_session.query.assert_called_once()

    @pytest.mark.unit
    def test_get_credential_by_id_not_found(
        self, mock_db_session: Mock, webauthn_config: Any, mock_auth_service: Mock
    ) -> None:
        """Test _get_credential_by_id when credential not found - Lines 414-425."""
        # Arrange
        webauthn_service = WebAuthnService(
            db_session=mock_db_session, config=webauthn_config, auth_service=mock_auth_service
        )

        # Mock database query returning None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Not found
        mock_db_session.query.return_value = mock_query

        # Act
        credential = webauthn_service._get_credential_by_id("nonexistent_id")

        # Assert
        assert credential is None
        mock_db_session.query.assert_called_once()

    @pytest.mark.unit
    def test_update_credential_database_operation(
        self,
        mock_db_session: Mock,
        webauthn_config: Any,
        mock_auth_service: Mock,
        sample_credential: Any,
    ) -> None:
        """Test _update_credential database operation - Lines 461-475."""
        # Arrange
        webauthn_service = WebAuthnService(
            db_session=mock_db_session, config=webauthn_config, auth_service=mock_auth_service
        )

        # Mock existing database credential
        mock_db_credential = Mock()
        mock_db_credential.credential_id = sample_credential.credential_id
        mock_db_credential.sign_count = 0
        mock_db_credential.usage_count = 5
        mock_db_credential.is_active = True
        mock_db_credential.last_used_at = None

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_db_credential
        mock_db_session.query.return_value = mock_query

        # Update sample_credential
        sample_credential.sign_count = 1
        sample_credential.metadata.last_used_at = datetime.now(UTC)
        sample_credential.metadata.is_active = False

        # Act
        webauthn_service._update_credential(sample_credential)

        # Assert
        assert mock_db_credential.sign_count == 1
        assert mock_db_credential.last_used_at == sample_credential.metadata.last_used_at
        assert mock_db_credential.is_active is False
        assert mock_db_credential.usage_count == 6  # Incremented
        mock_db_session.commit.assert_called_once()
