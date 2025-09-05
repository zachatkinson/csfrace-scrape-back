"""Unit tests for WebAuthn router - following CLAUDE.md IDT and SOLID principles."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.models import User
from src.auth.router import router
from src.auth.webauthn_service import PasskeyManager, WebAuthnCredential
from src.database.service import DatabaseService


class TestWebAuthnRouterEndpoints:
    """Test WebAuthn router endpoints - FastAPI testing with dependency overrides."""

    @pytest.fixture
    def mock_database_service(self):
        """Mock database service for testing."""
        from unittest.mock import MagicMock
        
        mock_service = Mock(spec=DatabaseService)
        mock_session = MagicMock()
        
        # Setup context manager for get_session
        context_manager = MagicMock()
        context_manager.__enter__.return_value = mock_session
        context_manager.__exit__.return_value = None
        mock_service.get_session.return_value = context_manager
        
        return mock_service

    @pytest.fixture
    def mock_passkey_manager(self):
        """Mock passkey manager for testing."""
        return Mock(spec=PasskeyManager)

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
    def client(self, mock_database_service, mock_passkey_manager, sample_user):
        """Create test client with mocked dependencies."""
        # Create FastAPI app with router
        from fastapi import FastAPI

        from src.auth.dependencies import get_passkey_manager, get_database_service, get_current_active_user
        app = FastAPI()
        app.include_router(router)

        # Override dependencies
        app.dependency_overrides[get_database_service] = lambda: mock_database_service
        app.dependency_overrides[get_passkey_manager] = lambda: mock_passkey_manager
        app.dependency_overrides[get_current_active_user] = lambda: sample_user

        return TestClient(app)

    @patch("src.auth.router.PasskeyManager")
    @patch("src.auth.router.WebAuthnService")
    def test_start_webauthn_registration_success(
        self, mock_webauthn_service_class, mock_passkey_manager_class, client, sample_user, mock_passkey_manager
    ):
        """Test successful WebAuthn registration start."""
        # Authentication is handled by dependency override
        
        # Setup mocks for service classes created inside the route
        mock_webauthn_service_instance = Mock()
        mock_webauthn_service_class.return_value = mock_webauthn_service_instance
        mock_passkey_manager_class.return_value = mock_passkey_manager

        # Mock passkey manager response
        mock_registration_data = {
            "publicKey": {
                "challenge": "test_challenge",
                "rp": {"id": "example.com", "name": "Example"},
                "user": {"id": "user123", "name": "testuser", "displayName": "Test User"},
                "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
                "timeout": 60000,
                "attestation": "none",
                "excludeCredentials": [],
                "authenticatorSelection": {"userVerification": "preferred"},
            },
            "challengeKey": "reg_test_user_challenge",
            "deviceName": "Test Device",
        }
        mock_passkey_manager.start_passkey_registration.return_value = mock_registration_data

        # Make request
        response = client.post(
            "/auth/passkeys/register/begin",
            json={"device_name": "Test Device"},
        )

        # Verify response
        assert response.status_code == 200
        response_data = response.json()

        assert "public_key" in response_data
        assert "challenge_key" in response_data
        assert response_data["challenge_key"] == "reg_test_user_challenge"
        assert response_data["public_key"]["challenge"] == "test_challenge"

        # Verify service was called correctly
        mock_passkey_manager.start_passkey_registration.assert_called_once_with(
            user=sample_user, device_name="Test Device"
        )

    @patch("src.auth.dependencies.get_current_active_user")
    def test_start_webauthn_registration_default_device(
        self, mock_get_current_active_user, client, sample_user, mock_passkey_manager
    ):
        """Test WebAuthn registration start with default device name."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock passkey manager response
        mock_registration_data = {
            "publicKey": {
                "challenge": "test_challenge",
                "rp": {"id": "example.com", "name": "Example"},
                "user": {"id": "user123", "name": "testuser", "displayName": "Test User"},
                "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
                "timeout": 60000,
                "attestation": "none",
                "excludeCredentials": [],
                "authenticatorSelection": {"userVerification": "preferred"},
            },
            "challengeKey": "reg_test_user_challenge",
            "deviceName": "Default Device",
        }
        mock_passkey_manager.start_passkey_registration.return_value = mock_registration_data

        # Make request without device_name
        response = client.post("/auth/passkeys/register/begin", json={})

        # Verify response
        assert response.status_code == 200

        # Verify service was called with default device name
        mock_passkey_manager.start_passkey_registration.assert_called_once_with(
            user=sample_user, device_name="Default Device"
        )

    @patch("src.auth.dependencies.get_current_active_user")
    def test_start_webauthn_registration_service_error(
        self, mock_get_current_active_user, client, sample_user, mock_passkey_manager
    ):
        """Test WebAuthn registration start with service error."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock service error
        mock_passkey_manager.start_passkey_registration.side_effect = Exception("Service error")

        # Make request
        response = client.post(
            "/auth/passkeys/register/begin",
            json={"device_name": "Test Device"},
        )

        # Verify error response
        assert response.status_code == 500
        response_data = response.json()
        assert "detail" in response_data
        assert "Failed to initiate passkey registration" in response_data["detail"]

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_complete_webauthn_registration_success(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test successful WebAuthn registration completion."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock successful verification
        from src.auth.webauthn_service import WebAuthnCredential, CredentialMetadata
        now = datetime.now(UTC)
        mock_credential = WebAuthnCredential(
            credential_id="test_credential_id",
            public_key="test_public_key",
            sign_count=0,
            user_id=sample_user.id,
            metadata=CredentialMetadata(
                created_at=now,
                device_name="Test Device",
                is_active=True,
            ),
        )
        mock_webauthn_service.verify_registration_response.return_value = mock_credential

        # Make request with mock credential data (proper base64 encoding)
        import base64
        raw_id_bytes = b"test_credential_raw_id_12345"
        raw_id_b64 = base64.urlsafe_b64encode(raw_id_bytes).decode('ascii').rstrip('=')
        
        credential_data = {
            "challenge_key": "reg_test_user_challenge",
            "credential_response": {
                "id": "test_credential_id_12345",
                "rawId": raw_id_b64,
                "response": {
                    "attestationObject": base64.urlsafe_b64encode(b"mock_attestation_object").decode('ascii').rstrip('='),
                    "clientDataJSON": base64.urlsafe_b64encode(b"mock_client_data_json").decode('ascii').rstrip('='),
                },
                "type": "public-key",
            },
            "device_name": "Test Device",
        }

        response = client.post("/auth/passkeys/register/complete", json=credential_data)

        # Verify response
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["message"] == "Passkey registered successfully"
        assert response_data["credential_id"] == "test_credential_id"
        assert response_data["device_name"] == "Test Device"

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_complete_webauthn_registration_verification_error(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test WebAuthn registration completion with verification error."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock verification error
        mock_webauthn_service.verify_registration_response.side_effect = ValueError(
            "Invalid challenge"
        )

        # Make request with proper base64 encoding
        import base64
        raw_id_bytes = b"test_credential_raw_id_12345"
        raw_id_b64 = base64.urlsafe_b64encode(raw_id_bytes).decode('ascii').rstrip('=')
        
        credential_data = {
            "challenge_key": "invalid_challenge",
            "credential_response": {
                "id": "test_credential_id_12345",
                "rawId": raw_id_b64,
                "response": {
                    "attestationObject": base64.urlsafe_b64encode(b"mock_attestation_object").decode('ascii').rstrip('='),
                    "clientDataJSON": base64.urlsafe_b64encode(b"mock_client_data_json").decode('ascii').rstrip('='),
                },
                "type": "public-key",
            },
            "device_name": "Test Device",
        }

        response = client.post("/auth/passkeys/register/complete", json=credential_data)

        # Verify error response
        assert response.status_code == 422
        response_data = response.json()
        assert "detail" in response_data
        assert "Invalid challenge" in response_data["detail"]

    @patch("src.auth.router.get_webauthn_service")
    def test_start_webauthn_authentication_success(
        self, mock_get_webauthn_service, client
    ):
        """Test successful WebAuthn authentication start."""
        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock dependencies
        with patch("src.auth.router.get_auth_service") as mock_get_auth_service, \
             patch("src.auth.router.get_passkey_manager") as mock_get_passkey_manager:
            
            mock_auth_service = Mock()
            mock_get_auth_service.return_value = mock_auth_service
            
            mock_passkey_manager = Mock()
            mock_get_passkey_manager.return_value = mock_passkey_manager
            
            # Mock authentication data for usernameless auth
            mock_authentication_data = {
                "publicKey": {
                    "challenge": "test_challenge",
                    "timeout": 60000,
                    "rpId": "example.com",
                    "allowCredentials": [],  # Usernameless
                    "userVerification": "preferred",
                },
                "challengeKey": "auth_any_challenge",
            }
            mock_passkey_manager.start_passkey_authentication.return_value = mock_authentication_data

            # Make request for usernameless authentication (no username = usernameless)
            response = client.post("/auth/passkeys/authenticate/begin", json={})

            # Verify response
            assert response.status_code == 200
            response_data = response.json()

            assert "public_key" in response_data
            assert "challenge_key" in response_data
            assert response_data["challenge_key"] == "auth_any_challenge"
            assert response_data["public_key"]["challenge"] == "test_challenge"

            # Verify service was called for usernameless auth
            mock_passkey_manager.start_passkey_authentication.assert_called_once_with(None)

    @patch("src.auth.router.get_webauthn_service")
    def test_start_webauthn_authentication_service_error(
        self, mock_get_webauthn_service, client
    ):
        """Test WebAuthn authentication start with service error."""
        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock passkey manager error
        mock_passkey_manager = Mock()
        mock_webauthn_service.passkey_manager = mock_passkey_manager
        mock_passkey_manager.start_passkey_authentication.side_effect = Exception("Service error")

        # Make request
        response = client.post("/auth/passkeys/authenticate/begin")

        # Verify error response
        assert response.status_code == 500
        response_data = response.json()
        assert "error" in response_data
        assert "Failed to start WebAuthn authentication" in response_data["error"]

    @patch("src.auth.router.get_webauthn_service")
    @patch("src.auth.router.create_access_token")
    def test_complete_webauthn_authentication_success(
        self, mock_create_token, mock_get_webauthn_service, client, sample_user
    ):
        """Test successful WebAuthn authentication completion."""
        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock successful verification
        now = datetime.now(UTC)
        mock_credential = WebAuthnCredential(
            credential_id="test_credential_id",
            public_key="test_public_key",
            sign_count=1,
            user_id=sample_user.id,
            created_at=now,
            last_used_at=now,
            device_name="Test Device",
            is_active=True,
        )
        mock_webauthn_service.verify_authentication_response.return_value = (
            sample_user,
            mock_credential,
        )

        # Mock token creation
        mock_create_token.return_value = "test_access_token"

        # Make request with mock credential data
        credential_data = {
            "challengeKey": "auth_test_user_challenge",
            "credential": {
                "id": "credential_id",
                "rawId": "credential_raw_id",
                "response": {
                    "authenticatorData": "authenticator_data",
                    "clientDataJSON": "client_data_json",
                    "signature": "signature",
                },
                "type": "public-key",
            },
        }

        response = client.post("/auth/passkeys/authenticate/complete", json=credential_data)

        # Verify response
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["access_token"] == "test_access_token"
        assert response_data["token_type"] == "bearer"
        assert response_data["user"]["id"] == sample_user.id
        assert response_data["user"]["username"] == sample_user.username

        # Verify token was created with correct user
        mock_create_token.assert_called_once_with(data={"sub": sample_user.id})

    @patch("src.auth.router.get_webauthn_service")
    def test_complete_webauthn_authentication_verification_error(
        self, mock_get_webauthn_service, client
    ):
        """Test WebAuthn authentication completion with verification error."""
        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock verification error
        mock_webauthn_service.verify_authentication_response.side_effect = ValueError(
            "Invalid challenge"
        )

        # Make request
        credential_data = {
            "challengeKey": "invalid_challenge",
            "credential": {
                "id": "credential_id",
                "rawId": "credential_raw_id",
                "response": {
                    "authenticatorData": "authenticator_data",
                    "clientDataJSON": "client_data_json",
                    "signature": "signature",
                },
                "type": "public-key",
            },
        }

        response = client.post("/auth/passkeys/authenticate/complete", json=credential_data)

        # Verify error response
        assert response.status_code == 400
        response_data = response.json()
        assert "Invalid challenge" in response_data["detail"]

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_get_user_passkeys_success(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test successful retrieval of user passkeys."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock passkey manager
        mock_passkey_manager = Mock()
        mock_webauthn_service.passkey_manager = mock_passkey_manager

        # Mock passkey summary
        now = datetime.now(UTC)
        mock_summary = {
            "total_passkeys": 2,
            "active_passkeys": 1,
            "last_used": now,
            "devices": [
                {
                    "id": "cred1",
                    "name": "Device 1",
                    "created_at": now,
                    "last_used_at": now,
                    "is_active": True,
                },
                {
                    "id": "cred2",
                    "name": "Device 2",
                    "created_at": now,
                    "last_used_at": None,
                    "is_active": False,
                },
            ],
        }
        mock_passkey_manager.get_passkey_summary.return_value = mock_summary

        # Make request
        response = client.get("/auth/passkeys/summary")

        # Verify response
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["total_passkeys"] == 2
        assert response_data["active_passkeys"] == 1
        assert len(response_data["devices"]) == 2
        assert response_data["devices"][0]["name"] == "Device 1"

        # Verify service was called correctly
        mock_passkey_manager.get_passkey_summary.assert_called_once_with(sample_user)

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_get_user_passkeys_service_error(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test passkey retrieval with service error."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock passkey manager error
        mock_passkey_manager = Mock()
        mock_webauthn_service.passkey_manager = mock_passkey_manager
        mock_passkey_manager.get_passkey_summary.side_effect = Exception("Service error")

        # Make request
        response = client.get("/auth/passkeys/summary")

        # Verify error response
        assert response.status_code == 500
        response_data = response.json()
        assert "error" in response_data
        assert "Failed to retrieve passkeys" in response_data["error"]

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_revoke_passkey_success(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test successful passkey revocation."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock successful revocation
        mock_webauthn_service.revoke_credential.return_value = True

        # Make request
        response = client.delete("/auth/passkeys/test_credential_id")

        # Verify response
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["success"] is True
        assert response_data["message"] == "Passkey revoked successfully"

        # Verify service was called correctly
        mock_webauthn_service.revoke_credential.assert_called_once_with(
            sample_user, "test_credential_id"
        )

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_revoke_passkey_not_found(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test passkey revocation when credential not found."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock failed revocation (credential not found)
        mock_webauthn_service.revoke_credential.return_value = False

        # Make request
        response = client.delete("/auth/passkeys/nonexistent_credential")

        # Verify error response
        assert response.status_code == 404
        response_data = response.json()
        assert "Passkey not found" in response_data["detail"]

    @patch("src.auth.dependencies.get_current_active_user")
    @patch("src.auth.router.get_webauthn_service")
    def test_revoke_passkey_service_error(
        self, mock_get_webauthn_service, mock_get_current_active_user, client, sample_user
    ):
        """Test passkey revocation with service error."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Mock WebAuthn service
        mock_webauthn_service = Mock()
        mock_get_webauthn_service.return_value = mock_webauthn_service

        # Mock service error
        mock_webauthn_service.revoke_credential.side_effect = Exception("Service error")

        # Make request
        response = client.delete("/auth/passkeys/test_credential_id")

        # Verify error response
        assert response.status_code == 500
        response_data = response.json()
        assert "error" in response_data
        assert "Failed to revoke passkey" in response_data["error"]


class TestWebAuthnRouterAuthentication:
    """Test WebAuthn router authentication and authorization."""

    @pytest.fixture
    def client(self):
        """Create test client without dependency overrides for auth testing."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_webauthn_register_start_requires_authentication(self, client):
        """Test that WebAuthn registration start requires authentication."""
        response = client.post("/auth/passkeys/register/begin", json={})

        # Should return 401 without authentication
        assert response.status_code == 401

    def test_webauthn_register_complete_requires_authentication(self, client):
        """Test that WebAuthn registration completion requires authentication."""
        credential_data = {
            "challengeKey": "test_challenge",
            "credential": {
                "id": "test_id",
                "rawId": "test_raw_id",
                "response": {
                    "attestationObject": "test_attestation",
                    "clientDataJSON": "test_client_data",
                },
                "type": "public-key",
            },
            "deviceName": "Test Device",
        }

        response = client.post("/auth/passkeys/register/complete", json=credential_data)

        # Should return 401 without authentication
        assert response.status_code == 401

    def test_webauthn_passkeys_requires_authentication(self, client):
        """Test that passkey listing requires authentication."""
        response = client.get("/auth/passkeys/summary")

        # Should return 401 without authentication
        assert response.status_code == 401

    def test_webauthn_revoke_requires_authentication(self, client):
        """Test that passkey revocation requires authentication."""
        response = client.delete("/auth/passkeys/test_credential_id")

        # Should return 401 without authentication
        assert response.status_code == 401


class TestWebAuthnRouterValidation:
    """Test WebAuthn router input validation."""

    @pytest.fixture
    def mock_database_service(self):
        """Mock database service for testing."""
        return Mock(spec=DatabaseService)

    @pytest.fixture
    def mock_passkey_manager(self):
        """Mock passkey manager for testing."""
        return Mock(spec=PasskeyManager)

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
    def client(self, mock_database_service, mock_passkey_manager):
        """Create test client with mocked dependencies."""
        # Create FastAPI app with router
        from fastapi import FastAPI

        from src.auth.dependencies import get_passkey_manager, get_database_service
        app = FastAPI()
        app.include_router(router)

        # Override dependencies
        app.dependency_overrides[get_database_service] = lambda: mock_database_service
        app.dependency_overrides[get_passkey_manager] = lambda: mock_passkey_manager

        return TestClient(app)

    @patch("src.auth.dependencies.get_current_active_user")
    def test_webauthn_register_start_invalid_device_name(
        self, mock_get_current_active_user, client, sample_user
    ):
        """Test WebAuthn registration start with invalid device name."""
        # Mock authenticated user
        mock_get_current_active_user.return_value = sample_user

        # Make request with too long device name
        response = client.post(
            "/auth/passkeys/register/begin",
            json={"device_name": "x" * 256},  # Too long
        )

        # Should validate device name length
        assert response.status_code == 422

    def test_webauthn_register_complete_missing_fields(self, client):
        """Test WebAuthn registration completion with missing required fields."""
        # Make request with missing fields
        response = client.post(
            "/auth/passkeys/register/complete",
            json={"challengeKey": "test_challenge"},  # Missing credential
        )

        # Should validate required fields
        assert response.status_code == 422

    def test_webauthn_authenticate_complete_invalid_credential(self, client):
        """Test WebAuthn authentication completion with invalid credential format."""
        # Make request with invalid credential structure
        credential_data = {
            "challengeKey": "test_challenge",
            "credential": {
                "id": "test_id",
                # Missing required fields like rawId, response, type
            },
        }

        response = client.post("/auth/passkeys/authenticate/complete", json=credential_data)

        # Should validate credential structure
        assert response.status_code == 422
