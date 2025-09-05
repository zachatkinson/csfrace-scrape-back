"""Unit tests for WebAuthn service - following CLAUDE.md IDT and SOLID principles."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session
from webauthn.authentication.verify_authentication_response import VerifiedAuthentication
from webauthn.helpers.structs import (
    AuthenticationCredential,
    RegistrationCredential,
)
from webauthn.registration.verify_registration_response import VerifiedRegistration

from src.auth.models import User
from src.auth.webauthn_service import (
    PasskeyManager,
    WebAuthnAuthenticationOptions,
    WebAuthnCredential,
    WebAuthnRegistrationOptions,
    WebAuthnService,
)
from src.constants import WEBAUTHN_CONSTANTS


class TestWebAuthnCredential:
    """Test WebAuthn credential model - Single Responsibility Principle."""

    def test_webauthn_credential_creation(self):
        """Test WebAuthn credential model instantiation."""
        from src.auth.webauthn_service import CredentialMetadata

        now = datetime.now(UTC)
        metadata = CredentialMetadata(
            created_at=now,
            device_name="Test Device",
            is_active=True,
        )
        credential = WebAuthnCredential(
            credential_id="test_credential_id",
            public_key="test_public_key",
            sign_count=0,
            user_id="test_user_id",
            metadata=metadata,
        )

        assert credential.credential_id == "test_credential_id"
        assert credential.public_key == "test_public_key"
        assert credential.sign_count == 0
        assert credential.user_id == "test_user_id"
        assert credential.metadata.created_at == now
        assert credential.metadata.device_name == "Test Device"
        assert credential.metadata.is_active is True
        assert credential.metadata.last_used_at is None

    def test_webauthn_credential_defaults(self):
        """Test WebAuthn credential default values."""
        from src.auth.webauthn_service import CredentialMetadata

        now = datetime.now(UTC)
        metadata = CredentialMetadata(
            created_at=now,
        )
        credential = WebAuthnCredential(
            credential_id="test_credential_id",
            public_key="test_public_key",
            sign_count=0,
            user_id="test_user_id",
            metadata=metadata,
        )

        assert credential.metadata.last_used_at is None
        assert credential.metadata.device_name is None
        assert credential.metadata.is_active is True


class TestWebAuthnRegistrationOptions:
    """Test WebAuthn registration options model - Interface Segregation."""

    def test_registration_options_creation(self):
        """Test WebAuthn registration options model instantiation."""
        from src.auth.webauthn_service import (
            RegistrationCredentialOptions,
            RelyingPartyInfo,
            WebAuthnRegistrationOptions,
        )

        rp_info = RelyingPartyInfo(rp={"id": "example.com", "name": "Example"}, rp_id="example.com")

        cred_options = RegistrationCredentialOptions(
            pub_key_cred_params=[{"type": "public-key", "alg": -7}],
            exclude_credentials=[],
            authenticator_selection={"userVerification": "preferred"},
            attestation="none",
        )

        options = WebAuthnRegistrationOptions(
            challenge="test_challenge",
            relying_party=rp_info,
            user={"id": "user123", "name": "testuser", "displayName": "Test User"},
            credential_options=cred_options,
            timeout=60000,
        )

        assert options.challenge == "test_challenge"
        assert options.relying_party.rp == {"id": "example.com", "name": "Example"}
        assert options.user["name"] == "testuser"
        assert len(options.credential_options.pub_key_cred_params) == 1
        assert options.timeout == 60000


class TestWebAuthnAuthenticationOptions:
    """Test WebAuthn authentication options model - Interface Segregation."""

    def test_authentication_options_creation(self):
        """Test WebAuthn authentication options model instantiation."""
        options = WebAuthnAuthenticationOptions(
            challenge="test_challenge",
            timeout=60000,
            rp_id="example.com",
            allow_credentials=[{"id": "cred123", "type": "public-key"}],
            user_verification="preferred",
        )

        assert options.challenge == "test_challenge"
        assert options.timeout == 60000
        assert options.rp_id == "example.com"
        assert len(options.allow_credentials) == 1
        assert options.user_verification == "preferred"


class TestWebAuthnService:
    """Test WebAuthn service - SOLID Dependency Inversion testing."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_auth_service(self):
        """Mock auth service for testing."""
        return Mock()

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        return User(
            id="test_user_id",
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
        )

    @pytest.fixture
    def webauthn_service(self, mock_db_session, mock_auth_service):
        """Create WebAuthn service instance for testing."""
        from src.auth.webauthn_service import WebAuthnConfig

        config = WebAuthnConfig(
            rp_id="example.com",
            rp_name="Example App",
            origin="https://example.com",
        )
        return WebAuthnService(
            db_session=mock_db_session,
            config=config,
            auth_service=mock_auth_service,
        )

    @pytest.fixture
    def sample_webauthn_credential(self):
        """Sample WebAuthn credential for testing."""
        from src.auth.webauthn_service import CredentialMetadata, WebAuthnCredential

        return WebAuthnCredential(
            credential_id="test_credential_id",
            public_key="test_public_key",
            sign_count=0,
            user_id="test_user_id",
            metadata=CredentialMetadata(
                created_at=datetime.now(UTC),
                device_name="Test Device",
                is_active=True,
            ),
        )

    def test_webauthn_service_initialization(self, mock_db_session):
        """Test WebAuthn service initialization with dependency injection."""
        from src.auth.webauthn_service import WebAuthnConfig

        config = WebAuthnConfig(
            rp_id="test.com",
            rp_name="Test App",
            origin="https://test.com",
        )
        service = WebAuthnService(
            db_session=mock_db_session,
            config=config,
        )

        assert service.db_session == mock_db_session
        assert service.config.rp_id == "test.com"
        assert service.config.rp_name == "Test App"
        assert service.config.origin == "https://test.com"
        assert service.auth_service is not None
        assert isinstance(service._pending_challenges, dict)

    def test_webauthn_service_default_values(self, mock_db_session):
        """Test WebAuthn service uses default constants."""
        service = WebAuthnService(db_session=mock_db_session)

        assert service.config.rp_id == WEBAUTHN_CONSTANTS.WEBAUTHN_RP_ID
        assert service.config.rp_name == WEBAUTHN_CONSTANTS.WEBAUTHN_RP_NAME
        assert service.config.origin == WEBAUTHN_CONSTANTS.WEBAUTHN_ORIGIN

    @patch("src.auth.webauthn_service.generate_registration_options")
    def test_generate_registration_options_success(
        self, mock_generate_options, webauthn_service, sample_user
    ):
        """Test successful WebAuthn registration options generation."""
        # Mock the webauthn library function
        mock_reg_options = Mock()
        mock_reg_options.challenge = b"test_challenge"
        mock_reg_options.rp.id = "example.com"
        mock_reg_options.rp.name = "Example App"
        mock_reg_options.user.id = b"test_user_id"
        mock_reg_options.user.name = "testuser"
        mock_reg_options.user.display_name = "Test User"
        mock_reg_options.pub_key_cred_params = [Mock(type="public-key", alg=-7)]
        mock_reg_options.timeout = 60000
        mock_reg_options.attestation = "none"
        mock_reg_options.authenticator_selection = Mock(user_verification="preferred")
        mock_generate_options.return_value = mock_reg_options

        # Mock getting user credentials (empty list for new user)
        webauthn_service._get_user_credentials = Mock(return_value=[])

        options, challenge_key = webauthn_service.generate_registration_options(sample_user)

        # Verify options structure
        assert isinstance(options, WebAuthnRegistrationOptions)
        assert options.relying_party.rp["id"] == "example.com"
        assert options.relying_party.rp["name"] == "Example App"
        assert options.user["name"] == "testuser"
        assert len(options.credential_options.pub_key_cred_params) == 1
        assert options.timeout == 60000

        # Verify challenge is stored
        assert challenge_key in webauthn_service._pending_challenges
        challenge_data = webauthn_service._pending_challenges[challenge_key]
        assert challenge_data["user_id"] == sample_user.id
        assert challenge_data["type"] == "registration"

    @patch("src.auth.webauthn_service.generate_registration_options")
    def test_generate_registration_options_with_existing_credentials(
        self, mock_generate_options, webauthn_service, sample_user, sample_webauthn_credential
    ):
        """Test registration options generation excludes existing credentials."""
        # Mock the webauthn library function
        mock_reg_options = Mock()
        mock_reg_options.challenge = b"test_challenge"
        mock_reg_options.rp.id = "example.com"
        mock_reg_options.rp.name = "Example App"
        mock_reg_options.user.id = b"test_user_id"
        mock_reg_options.user.name = "testuser"
        mock_reg_options.user.display_name = "Test User"
        mock_reg_options.pub_key_cred_params = [Mock(type="public-key", alg=-7)]
        mock_reg_options.timeout = 60000
        mock_reg_options.attestation = "none"
        mock_reg_options.authenticator_selection = Mock(user_verification="preferred")
        mock_generate_options.return_value = mock_reg_options

        # Mock getting existing user credentials
        webauthn_service._get_user_credentials = Mock(return_value=[sample_webauthn_credential])

        options, challenge_key = webauthn_service.generate_registration_options(sample_user)

        # Verify exclude credentials includes existing credential
        assert len(options.credential_options.exclude_credentials) == 1
        assert (
            options.credential_options.exclude_credentials[0]["id"]
            == sample_webauthn_credential.credential_id
        )
        assert options.credential_options.exclude_credentials[0]["type"] == "public-key"

    @patch("src.auth.webauthn_service.verify_registration_response")
    def test_verify_registration_response_success(self, mock_verify, webauthn_service):
        """Test successful WebAuthn registration response verification."""
        # Set up challenge
        challenge_key = "reg_test_user_test_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": "test_user_id",
            "type": "registration",
            "created_at": datetime.now(UTC),
        }

        # Mock verification response
        mock_verification = Mock(spec=VerifiedRegistration)
        mock_verification.credential_id = b"test_credential_id"
        mock_verification.credential_public_key = b"test_public_key"
        mock_verification.sign_count = 0
        mock_verify.return_value = mock_verification

        # Mock credential storage
        webauthn_service._store_credential = Mock()

        # Create mock registration credential
        mock_credential = Mock(spec=RegistrationCredential)

        result = webauthn_service.verify_registration_response(
            mock_credential, challenge_key, "Test Device"
        )

        # Verify result
        assert isinstance(result, WebAuthnCredential)
        assert result.user_id == "test_user_id"
        assert result.metadata.device_name == "Test Device"
        assert result.metadata.is_active is True

        # Verify challenge was cleaned up
        assert challenge_key not in webauthn_service._pending_challenges

        # Verify credential was stored
        webauthn_service._store_credential.assert_called_once()

    def test_verify_registration_response_invalid_challenge(self, webauthn_service):
        """Test registration response verification with invalid challenge."""
        mock_credential = Mock(spec=RegistrationCredential)

        with pytest.raises(ValueError, match="Invalid or expired challenge"):
            webauthn_service.verify_registration_response(mock_credential, "invalid_key")

    def test_verify_registration_response_wrong_challenge_type(self, webauthn_service):
        """Test registration response verification with wrong challenge type."""
        # Set up authentication challenge (wrong type)
        challenge_key = "auth_test_user_test_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": "test_user_id",
            "type": "authentication",  # Wrong type
            "created_at": datetime.now(UTC),
        }

        mock_credential = Mock(spec=RegistrationCredential)

        with pytest.raises(ValueError, match="Challenge type mismatch"):
            webauthn_service.verify_registration_response(mock_credential, challenge_key)

    @patch("src.auth.webauthn_service.generate_authentication_options")
    def test_generate_authentication_options_with_user(
        self, mock_generate_options, webauthn_service, sample_user, sample_webauthn_credential
    ):
        """Test authentication options generation for specific user."""
        # Mock the webauthn library function
        mock_auth_options = Mock()
        mock_auth_options.challenge = b"test_challenge"
        mock_auth_options.timeout = 60000
        mock_auth_options.rp_id = "example.com"
        mock_auth_options.user_verification = "preferred"
        mock_generate_options.return_value = mock_auth_options

        # Mock getting user credentials
        webauthn_service._get_user_credentials = Mock(return_value=[sample_webauthn_credential])

        options, challenge_key = webauthn_service.generate_authentication_options(sample_user)

        # Verify options structure
        assert isinstance(options, WebAuthnAuthenticationOptions)
        assert options.rp_id == "example.com"
        assert options.timeout == 60000
        assert len(options.allow_credentials) == 1
        assert options.allow_credentials[0]["id"] == sample_webauthn_credential.credential_id

        # Verify challenge is stored
        assert challenge_key in webauthn_service._pending_challenges
        challenge_data = webauthn_service._pending_challenges[challenge_key]
        assert challenge_data["user_id"] == sample_user.id
        assert challenge_data["type"] == "authentication"

    @patch("src.auth.webauthn_service.generate_authentication_options")
    def test_generate_authentication_options_usernameless(
        self, mock_generate_options, webauthn_service
    ):
        """Test authentication options generation for usernameless login."""
        # Mock the webauthn library function
        mock_auth_options = Mock()
        mock_auth_options.challenge = b"test_challenge"
        mock_auth_options.timeout = 60000
        mock_auth_options.rp_id = "example.com"
        mock_auth_options.user_verification = "preferred"
        mock_generate_options.return_value = mock_auth_options

        options, challenge_key = webauthn_service.generate_authentication_options(user=None)

        # Verify options for usernameless authentication
        assert isinstance(options, WebAuthnAuthenticationOptions)
        assert options.allow_credentials == []  # Empty for discoverable authentication

        # Verify challenge is stored
        assert challenge_key in webauthn_service._pending_challenges
        challenge_data = webauthn_service._pending_challenges[challenge_key]
        assert challenge_data["user_id"] is None
        assert challenge_data["type"] == "authentication"

    @patch("src.auth.webauthn_service.verify_authentication_response")
    def test_verify_authentication_response_success(
        self, mock_verify, webauthn_service, sample_user, sample_webauthn_credential
    ):
        """Test successful WebAuthn authentication response verification."""
        # Set up challenge
        challenge_key = "auth_test_user_test_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": sample_user.id,
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        # Mock verification response
        mock_verification = Mock(spec=VerifiedAuthentication)
        mock_verification.new_sign_count = 1
        mock_verify.return_value = mock_verification

        # Mock credential retrieval and update
        webauthn_service._get_credential_by_id = Mock(return_value=sample_webauthn_credential)
        webauthn_service._update_credential = Mock()
        webauthn_service.auth_service.get_user_by_id = Mock(return_value=sample_user)

        # Create mock authentication credential
        mock_credential = Mock(spec=AuthenticationCredential)
        mock_credential.raw_id = b"test_credential_id"

        user, credential = webauthn_service.verify_authentication_response(
            mock_credential, challenge_key
        )

        # Verify results
        assert user == sample_user
        assert credential == sample_webauthn_credential
        assert credential.sign_count == 1  # Updated sign count

        # Verify challenge was cleaned up
        assert challenge_key not in webauthn_service._pending_challenges

        # Verify credential was updated
        webauthn_service._update_credential.assert_called_once_with(sample_webauthn_credential)

    def test_verify_authentication_response_invalid_challenge(self, webauthn_service):
        """Test authentication response verification with invalid challenge."""
        mock_credential = Mock(spec=AuthenticationCredential)

        with pytest.raises(ValueError, match="Invalid or expired challenge"):
            webauthn_service.verify_authentication_response(mock_credential, "invalid_key")

    def test_verify_authentication_response_credential_not_found(self, webauthn_service):
        """Test authentication response verification with credential not found."""
        # Set up challenge
        challenge_key = "auth_test_user_test_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": "test_user_id",
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        # Mock credential not found
        webauthn_service._get_credential_by_id = Mock(return_value=None)

        mock_credential = Mock(spec=AuthenticationCredential)
        mock_credential.raw_id = b"nonexistent_credential"

        with pytest.raises(ValueError, match="Credential not found or inactive"):
            webauthn_service.verify_authentication_response(mock_credential, challenge_key)

    def test_verify_authentication_response_inactive_credential(
        self, webauthn_service, sample_webauthn_credential
    ):
        """Test authentication response verification with inactive credential."""
        # Set up challenge
        challenge_key = "auth_test_user_test_challenge"
        webauthn_service._pending_challenges[challenge_key] = {
            "challenge": "test_challenge",
            "user_id": "test_user_id",
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        # Make credential inactive
        sample_webauthn_credential.metadata.is_active = False
        webauthn_service._get_credential_by_id = Mock(return_value=sample_webauthn_credential)

        mock_credential = Mock(spec=AuthenticationCredential)
        mock_credential.raw_id = b"test_credential_id"
        mock_credential.id = "test_credential_id"  # Add missing id attribute

        with pytest.raises(ValueError, match="Credential not found or inactive"):
            webauthn_service.verify_authentication_response(mock_credential, challenge_key)

    def test_get_user_credentials(self, webauthn_service, sample_user, sample_webauthn_credential):
        """Test getting user credentials - read-only operation."""
        webauthn_service._get_user_credentials = Mock(return_value=[sample_webauthn_credential])

        credentials = webauthn_service.get_user_credentials(sample_user)

        assert len(credentials) == 1
        assert credentials[0] == sample_webauthn_credential
        webauthn_service._get_user_credentials.assert_called_once_with(sample_user.id)

    def test_revoke_credential_success(
        self, webauthn_service, sample_user, sample_webauthn_credential
    ):
        """Test successful credential revocation."""
        webauthn_service._get_credential_by_id = Mock(return_value=sample_webauthn_credential)
        webauthn_service._update_credential = Mock()

        result = webauthn_service.revoke_credential(sample_user, "test_credential_id")

        assert result is True
        assert sample_webauthn_credential.metadata.is_active is False
        webauthn_service._update_credential.assert_called_once_with(sample_webauthn_credential)

    def test_revoke_credential_not_found(self, webauthn_service, sample_user):
        """Test credential revocation when credential not found."""
        webauthn_service._get_credential_by_id = Mock(return_value=None)

        result = webauthn_service.revoke_credential(sample_user, "nonexistent_credential")

        assert result is False

    def test_revoke_credential_wrong_user(
        self, webauthn_service, sample_user, sample_webauthn_credential
    ):
        """Test credential revocation for wrong user."""
        # Set credential to different user
        sample_webauthn_credential.user_id = "different_user_id"
        webauthn_service._get_credential_by_id = Mock(return_value=sample_webauthn_credential)

        result = webauthn_service.revoke_credential(sample_user, "test_credential_id")

        assert result is False

    def test_cleanup_expired_challenges(self, webauthn_service):
        """Test cleanup of expired challenges."""
        now = datetime.now(UTC)
        old_time = now - timedelta(minutes=15)  # Older than max age

        # Add challenges with different ages
        webauthn_service._pending_challenges["fresh_challenge"] = {
            "created_at": now,
            "user_id": "user1",
        }
        webauthn_service._pending_challenges["expired_challenge"] = {
            "created_at": old_time,
            "user_id": "user2",
        }

        cleaned_count = webauthn_service.cleanup_expired_challenges(max_age_minutes=10)

        assert cleaned_count == 1
        assert "fresh_challenge" in webauthn_service._pending_challenges
        assert "expired_challenge" not in webauthn_service._pending_challenges


class TestWebAuthnServiceDatabaseIntegration:
    """Test WebAuthn service database integration - private methods testing."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        return Mock(spec=Session)

    @pytest.fixture
    def webauthn_service(self, mock_db_session):
        """Create WebAuthn service instance for testing."""
        return WebAuthnService(db_session=mock_db_session)

    def test_get_user_credentials_database_query(self, webauthn_service, mock_db_session):
        """Test database query for getting user credentials."""

        # Mock database model
        mock_db_cred = Mock()
        mock_db_cred.credential_id = "test_cred_id"
        mock_db_cred.public_key = "test_public_key"
        mock_db_cred.sign_count = 5
        mock_db_cred.user_id = "test_user_id"
        mock_db_cred.created_at = datetime.now(UTC)
        mock_db_cred.last_used_at = datetime.now(UTC)
        mock_db_cred.device_name = "Test Device"
        mock_db_cred.is_active = True

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_db_cred]
        mock_db_session.query.return_value = mock_query

        credentials = webauthn_service._get_user_credentials("test_user_id")

        # Verify query was constructed correctly
        mock_db_session.query.assert_called_once()
        assert mock_query.filter.call_count == 2  # user_id and is_active filters
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()

        # Verify returned credentials are real WebAuthnCredential objects
        assert len(credentials) == 1
        assert credentials[0].credential_id == "test_cred_id"
        assert credentials[0].user_id == "test_user_id"
        assert credentials[0].metadata.device_name == "Test Device"
        assert credentials[0].metadata.is_active is True

    def test_get_credential_by_id_database_query(self, webauthn_service, mock_db_session):
        """Test database query for getting credential by ID."""
        # Mock database model
        mock_db_cred = Mock()
        mock_db_cred.credential_id = "test_cred_id"
        mock_db_cred.public_key = "test_public_key"
        mock_db_cred.sign_count = 5
        mock_db_cred.user_id = "test_user_id"
        mock_db_cred.created_at = datetime.now(UTC)
        mock_db_cred.last_used_at = None
        mock_db_cred.device_name = "Test Device"
        mock_db_cred.is_active = True

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_db_cred
        mock_db_session.query.return_value = mock_query

        credential = webauthn_service._get_credential_by_id("test_cred_id")

        # Verify query was constructed correctly
        mock_db_session.query.assert_called_once()
        assert mock_query.filter.call_count == 2  # credential_id and is_active filters
        mock_query.first.assert_called_once()

        # Verify returned credential is real WebAuthnCredential object
        assert credential is not None
        assert credential.credential_id == "test_cred_id"
        assert credential.user_id == "test_user_id"
        assert credential.metadata.device_name == "Test Device"
        assert credential.metadata.is_active is True
        assert credential.metadata.last_used_at is None

    @patch("src.auth.webauthn_service.WebAuthnCredential")
    def test_get_credential_by_id_not_found(
        self, mock_webauthn_credential_model, webauthn_service, mock_db_session
    ):
        """Test getting credential by ID when not found."""
        # Mock query chain returning None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db_session.query.return_value = mock_query

        credential = webauthn_service._get_credential_by_id("nonexistent_id")

        assert credential is None

    @patch("src.auth.webauthn_service.WebAuthnCredential")
    def test_store_credential_database_operation(
        self, mock_webauthn_credential_model, webauthn_service, mock_db_session
    ):
        """Test storing credential in database."""
        now = datetime.now(UTC)
        from src.auth.webauthn_service import CredentialMetadata

        metadata = CredentialMetadata(
            created_at=now,
            device_name="Test Device",
            is_active=True,
        )
        credential = WebAuthnCredential(
            credential_id="test_cred_id",
            public_key="test_public_key",
            sign_count=0,
            user_id="test_user_id",
            metadata=metadata,
        )

        webauthn_service._store_credential(credential)

        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @patch("src.auth.webauthn_service.WebAuthnCredential")
    def test_update_credential_database_operation(
        self, mock_webauthn_credential_model, webauthn_service, mock_db_session
    ):
        """Test updating credential in database."""
        # Mock existing database credential
        mock_db_cred = Mock()
        mock_db_cred.usage_count = 5

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_db_cred
        mock_db_session.query.return_value = mock_query

        now = datetime.now(UTC)
        from src.auth.webauthn_service import CredentialMetadata

        metadata = CredentialMetadata(
            created_at=now,
            last_used_at=now,
            device_name="Test Device",
            is_active=False,
        )
        credential = WebAuthnCredential(
            credential_id="test_cred_id",
            public_key="test_public_key",
            sign_count=10,
            user_id="test_user_id",
            metadata=metadata,
        )

        webauthn_service._update_credential(credential)

        # Verify database updates
        assert mock_db_cred.sign_count == 10
        assert mock_db_cred.last_used_at == now
        assert mock_db_cred.is_active is False
        assert mock_db_cred.usage_count == 6  # Incremented
        mock_db_session.commit.assert_called_once()


class TestPasskeyManager:
    """Test PasskeyManager - Facade pattern testing."""

    @pytest.fixture
    def mock_webauthn_service(self):
        """Mock WebAuthn service for testing."""
        return Mock(spec=WebAuthnService)

    @pytest.fixture
    def passkey_manager(self, mock_webauthn_service):
        """Create PasskeyManager instance for testing."""
        return PasskeyManager(mock_webauthn_service)

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        return User(
            id="test_user_id",
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
        )

    def test_passkey_manager_initialization(self, mock_webauthn_service):
        """Test PasskeyManager initialization with dependency injection."""
        manager = PasskeyManager(mock_webauthn_service)

        assert manager.webauthn_service == mock_webauthn_service

    def test_start_passkey_registration(self, passkey_manager, sample_user):
        """Test starting passkey registration flow."""
        # Mock WebAuthn service response
        from src.auth.webauthn_service import RegistrationCredentialOptions, RelyingPartyInfo

        rp_info = RelyingPartyInfo(rp={"id": "example.com", "name": "Example"}, rp_id="example.com")

        cred_options = RegistrationCredentialOptions(
            pub_key_cred_params=[{"type": "public-key", "alg": -7}],
            exclude_credentials=[],
            authenticator_selection={"userVerification": "preferred"},
            attestation="none",
        )

        mock_options = WebAuthnRegistrationOptions(
            challenge="test_challenge",
            relying_party=rp_info,
            user={"id": "user123", "name": "testuser", "displayName": "Test User"},
            credential_options=cred_options,
            timeout=60000,
        )
        mock_challenge_key = "reg_test_user_challenge"

        passkey_manager.webauthn_service.generate_registration_options.return_value = (
            mock_options,
            mock_challenge_key,
        )

        result = passkey_manager.start_passkey_registration(sample_user, "My Device")

        # Verify result structure
        assert "publicKey" in result
        assert "challengeKey" in result
        assert "deviceName" in result

        public_key = result["publicKey"]
        assert public_key["challenge"] == "test_challenge"
        assert public_key["rp"]["id"] == "example.com"
        assert public_key["user"]["name"] == "testuser"
        assert result["challengeKey"] == mock_challenge_key
        assert result["deviceName"] == "My Device"

    def test_start_passkey_registration_default_device(self, passkey_manager, sample_user):
        """Test starting passkey registration with default device name."""
        # Mock WebAuthn service response
        from src.auth.webauthn_service import RegistrationCredentialOptions, RelyingPartyInfo

        rp_info = RelyingPartyInfo(rp={"id": "example.com", "name": "Example"}, rp_id="example.com")

        cred_options = RegistrationCredentialOptions(
            pub_key_cred_params=[{"type": "public-key", "alg": -7}],
            exclude_credentials=[],
            authenticator_selection={"userVerification": "preferred"},
            attestation="none",
        )

        mock_options = WebAuthnRegistrationOptions(
            challenge="test_challenge",
            relying_party=rp_info,
            user={"id": "user123", "name": "testuser", "displayName": "Test User"},
            credential_options=cred_options,
            timeout=60000,
        )
        mock_challenge_key = "reg_test_user_challenge"

        passkey_manager.webauthn_service.generate_registration_options.return_value = (
            mock_options,
            mock_challenge_key,
        )

        result = passkey_manager.start_passkey_registration(sample_user)

        assert result["deviceName"] == "Default Device"

    def test_start_passkey_authentication_with_user(self, passkey_manager, sample_user):
        """Test starting passkey authentication for specific user."""
        # Mock WebAuthn service response
        mock_options = WebAuthnAuthenticationOptions(
            challenge="test_challenge",
            timeout=60000,
            rp_id="example.com",
            allow_credentials=[{"id": "cred123", "type": "public-key"}],
            user_verification="preferred",
        )
        mock_challenge_key = "auth_test_user_challenge"

        passkey_manager.webauthn_service.generate_authentication_options.return_value = (
            mock_options,
            mock_challenge_key,
        )

        result = passkey_manager.start_passkey_authentication(sample_user)

        # Verify result structure
        assert "publicKey" in result
        assert "challengeKey" in result

        public_key = result["publicKey"]
        assert public_key["challenge"] == "test_challenge"
        assert public_key["rpId"] == "example.com"
        assert len(public_key["allowCredentials"]) == 1
        assert result["challengeKey"] == mock_challenge_key

    def test_start_passkey_authentication_usernameless(self, passkey_manager):
        """Test starting passkey authentication for usernameless login."""
        # Mock WebAuthn service response
        mock_options = WebAuthnAuthenticationOptions(
            challenge="test_challenge",
            timeout=60000,
            rp_id="example.com",
            allow_credentials=[],  # Empty for discoverable
            user_verification="preferred",
        )
        mock_challenge_key = "auth_any_challenge"

        passkey_manager.webauthn_service.generate_authentication_options.return_value = (
            mock_options,
            mock_challenge_key,
        )

        result = passkey_manager.start_passkey_authentication(user=None)

        # Verify usernameless authentication
        public_key = result["publicKey"]
        assert public_key["allowCredentials"] == []

    def test_get_passkey_summary(self, passkey_manager, sample_user):
        """Test getting user's passkey summary."""
        # Mock credentials
        now = datetime.now(UTC)
        from src.auth.webauthn_service import CredentialMetadata

        mock_credentials = [
            WebAuthnCredential(
                credential_id="cred1",
                public_key="key1",
                sign_count=5,
                user_id="test_user_id",
                metadata=CredentialMetadata(
                    created_at=now,
                    last_used_at=now,
                    device_name="Device 1",
                    is_active=True,
                ),
            ),
            WebAuthnCredential(
                credential_id="cred2",
                public_key="key2",
                sign_count=0,
                user_id="test_user_id",
                metadata=CredentialMetadata(
                    created_at=now,
                    device_name="Device 2",
                    is_active=False,
                ),
            ),
        ]

        passkey_manager.webauthn_service.get_user_credentials.return_value = mock_credentials

        summary = passkey_manager.get_passkey_summary(sample_user)

        # Verify summary structure
        assert summary["total_passkeys"] == 2
        assert summary["active_passkeys"] == 1
        assert summary["last_used"] == now
        assert len(summary["devices"]) == 2

        # Verify device details
        device1 = summary["devices"][0]
        assert device1["id"] == "cred1"
        assert device1["name"] == "Device 1"
        assert device1["is_active"] is True

    def test_get_passkey_summary_no_credentials(self, passkey_manager, sample_user):
        """Test passkey summary with no credentials."""
        passkey_manager.webauthn_service.get_user_credentials.return_value = []

        summary = passkey_manager.get_passkey_summary(sample_user)

        assert summary["total_passkeys"] == 0
        assert summary["active_passkeys"] == 0
        assert summary["last_used"] is None
        assert summary["devices"] == []

    def test_get_passkey_summary_no_last_used(self, passkey_manager, sample_user):
        """Test passkey summary when no credentials have been used."""
        # Mock credentials without last_used_at
        now = datetime.now(UTC)
        from src.auth.webauthn_service import CredentialMetadata

        mock_credentials = [
            WebAuthnCredential(
                credential_id="cred1",
                public_key="key1",
                sign_count=0,
                user_id="test_user_id",
                metadata=CredentialMetadata(
                    created_at=now,
                    last_used_at=None,  # Never used
                    device_name="Device 1",
                    is_active=True,
                ),
            ),
        ]

        passkey_manager.webauthn_service.get_user_credentials.return_value = mock_credentials

        summary = passkey_manager.get_passkey_summary(sample_user)

        assert summary["last_used"] is None
