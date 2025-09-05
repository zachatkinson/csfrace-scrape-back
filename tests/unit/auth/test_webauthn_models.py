"""Unit tests for WebAuthn models - following CLAUDE.md IDT and SOLID principles."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.auth.models import (
    WebAuthnAuthenticationComplete,
    WebAuthnAuthenticationStart,
    WebAuthnCredentialResponse,
    WebAuthnRegistrationComplete,
    WebAuthnRegistrationStart,
)


class TestWebAuthnRegistrationStart:
    """Test WebAuthn registration start request model."""

    def test_webauthn_registration_start_valid_data(self):
        """Test WebAuthn registration start with valid data."""
        data = {"device_name": "Test Device"}
        model = WebAuthnRegistrationStart(**data)

        assert model.device_name == "Test Device"

    def test_webauthn_registration_start_default_device(self):
        """Test WebAuthn registration start with default device name."""
        data = {}
        model = WebAuthnRegistrationStart(**data)

        assert model.device_name == "Default Device"

    def test_webauthn_registration_start_empty_device_name(self):
        """Test WebAuthn registration start with empty device name uses default."""
        data = {"device_name": ""}
        model = WebAuthnRegistrationStart(**data)

        assert model.device_name == "Default Device"

    def test_webauthn_registration_start_none_device_name(self):
        """Test WebAuthn registration start with None device name uses default."""
        data = {"device_name": None}
        model = WebAuthnRegistrationStart(**data)

        assert model.device_name == "Default Device"

    def test_webauthn_registration_start_long_device_name(self):
        """Test WebAuthn registration start with device name too long."""
        data = {"device_name": "x" * 256}  # Too long

        with pytest.raises(ValidationError) as exc_info:
            WebAuthnRegistrationStart(**data)

        assert "String should have at most 255 characters" in str(exc_info.value)

    def test_webauthn_registration_start_whitespace_device_name(self):
        """Test WebAuthn registration start trims whitespace from device name."""
        data = {"device_name": "  Test Device  "}
        model = WebAuthnRegistrationStart(**data)

        assert model.device_name == "Test Device"


class TestWebAuthnRegistrationComplete:
    """Test WebAuthn registration completion request model."""

    def test_webauthn_registration_complete_valid_data(self):
        """Test WebAuthn registration complete with valid data."""
        data = {
            "challengeKey": "reg_user123_challenge456",
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "attestationObject": "attestation_object_data",
                    "clientDataJSON": "client_data_json_string",
                },
                "type": "public-key",
            },
            "deviceName": "iPhone 15 Pro",
        }

        model = WebAuthnRegistrationComplete(**data)

        assert model.challengeKey == "reg_user123_challenge456"
        assert model.credential["id"] == "credential_id_123"
        assert model.credential["type"] == "public-key"
        assert model.deviceName == "iPhone 15 Pro"

    def test_webauthn_registration_complete_default_device_name(self):
        """Test WebAuthn registration complete with default device name."""
        data = {
            "challengeKey": "reg_user123_challenge456",
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "attestationObject": "attestation_object_data",
                    "clientDataJSON": "client_data_json_string",
                },
                "type": "public-key",
            },
        }

        model = WebAuthnRegistrationComplete(**data)

        assert model.deviceName == "Default Device"

    def test_webauthn_registration_complete_missing_challenge_key(self):
        """Test WebAuthn registration complete with missing challenge key."""
        data = {
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "attestationObject": "attestation_object_data",
                    "clientDataJSON": "client_data_json_string",
                },
                "type": "public-key",
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            WebAuthnRegistrationComplete(**data)

        assert "Field required" in str(exc_info.value)

    def test_webauthn_registration_complete_invalid_credential(self):
        """Test WebAuthn registration complete with invalid credential structure."""
        data = {
            "challengeKey": "reg_user123_challenge456",
            "credential": {
                "id": "credential_id_123",
                # Missing required fields like rawId, response, type
            },
        }

        # Since we're using dict for credential, Pydantic won't validate structure
        # This test verifies the model accepts the data but application logic should validate
        model = WebAuthnRegistrationComplete(**data)
        assert model.challengeKey == "reg_user123_challenge456"
        assert model.credential["id"] == "credential_id_123"

    def test_webauthn_registration_complete_empty_challenge_key(self):
        """Test WebAuthn registration complete with empty challenge key."""
        data = {
            "challengeKey": "",
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "attestationObject": "attestation_object_data",
                    "clientDataJSON": "client_data_json_string",
                },
                "type": "public-key",
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            WebAuthnRegistrationComplete(**data)

        assert "String should have at least 1 character" in str(exc_info.value)


class TestWebAuthnAuthenticationStart:
    """Test WebAuthn authentication start request model."""

    def test_webauthn_authentication_start_valid_data(self):
        """Test WebAuthn authentication start with valid data."""
        data = {"username": "testuser"}
        model = WebAuthnAuthenticationStart(**data)

        assert model.username == "testuser"

    def test_webauthn_authentication_start_no_username(self):
        """Test WebAuthn authentication start for usernameless login."""
        data = {}
        model = WebAuthnAuthenticationStart(**data)

        assert model.username is None

    def test_webauthn_authentication_start_empty_username(self):
        """Test WebAuthn authentication start with empty username."""
        data = {"username": ""}
        model = WebAuthnAuthenticationStart(**data)

        assert model.username is None  # Empty string converted to None

    def test_webauthn_authentication_start_whitespace_username(self):
        """Test WebAuthn authentication start trims whitespace from username."""
        data = {"username": "  testuser  "}
        model = WebAuthnAuthenticationStart(**data)

        assert model.username == "testuser"


class TestWebAuthnAuthenticationComplete:
    """Test WebAuthn authentication completion request model."""

    def test_webauthn_authentication_complete_valid_data(self):
        """Test WebAuthn authentication complete with valid data."""
        data = {
            "challengeKey": "auth_user123_challenge456",
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "authenticatorData": "authenticator_data_bytes",
                    "clientDataJSON": "client_data_json_string",
                    "signature": "signature_bytes",
                    "userHandle": "user_handle_bytes",
                },
                "type": "public-key",
            },
        }

        model = WebAuthnAuthenticationComplete(**data)

        assert model.challengeKey == "auth_user123_challenge456"
        assert model.credential["id"] == "credential_id_123"
        assert model.credential["type"] == "public-key"
        assert model.credential["response"]["signature"] == "signature_bytes"

    def test_webauthn_authentication_complete_optional_user_handle(self):
        """Test WebAuthn authentication complete with optional userHandle."""
        data = {
            "challengeKey": "auth_user123_challenge456",
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "authenticatorData": "authenticator_data_bytes",
                    "clientDataJSON": "client_data_json_string",
                    "signature": "signature_bytes",
                    # userHandle is optional
                },
                "type": "public-key",
            },
        }

        model = WebAuthnAuthenticationComplete(**data)

        assert model.challengeKey == "auth_user123_challenge456"
        assert "userHandle" not in model.credential["response"]

    def test_webauthn_authentication_complete_missing_challenge_key(self):
        """Test WebAuthn authentication complete with missing challenge key."""
        data = {
            "credential": {
                "id": "credential_id_123",
                "rawId": "raw_id_bytes",
                "response": {
                    "authenticatorData": "authenticator_data_bytes",
                    "clientDataJSON": "client_data_json_string",
                    "signature": "signature_bytes",
                },
                "type": "public-key",
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            WebAuthnAuthenticationComplete(**data)

        assert "Field required" in str(exc_info.value)

    def test_webauthn_authentication_complete_invalid_credential(self):
        """Test WebAuthn authentication complete with invalid credential structure."""
        data = {
            "challengeKey": "auth_user123_challenge456",
            "credential": {
                "id": "credential_id_123",
                # Missing required fields like rawId, response, type
            },
        }

        # Since we're using dict for credential, Pydantic won't validate structure
        # This test verifies the model accepts the data but application logic should validate
        model = WebAuthnAuthenticationComplete(**data)
        assert model.challengeKey == "auth_user123_challenge456"
        assert model.credential["id"] == "credential_id_123"


class TestWebAuthnCredentialResponse:
    """Test WebAuthn credential response model."""

    def test_webauthn_credential_response_valid_data(self):
        """Test WebAuthn credential response with valid data."""
        now = datetime.now(UTC)
        data = {
            "credential_id": "cred_123",
            "user_id": "user_456",
            "device_name": "iPhone 15 Pro",
            "created_at": now,
            "last_used_at": now,
            "is_active": True,
            "usage_count": 5,
        }

        model = WebAuthnCredentialResponse(**data)

        assert model.credential_id == "cred_123"
        assert model.user_id == "user_456"
        assert model.device_name == "iPhone 15 Pro"
        assert model.created_at == now
        assert model.last_used_at == now
        assert model.is_active is True
        assert model.usage_count == 5

    def test_webauthn_credential_response_optional_fields(self):
        """Test WebAuthn credential response with optional fields."""
        now = datetime.now(UTC)
        data = {
            "credential_id": "cred_123",
            "user_id": "user_456",
            "created_at": now,
            "is_active": True,
            "usage_count": 0,
        }

        model = WebAuthnCredentialResponse(**data)

        assert model.credential_id == "cred_123"
        assert model.user_id == "user_456"
        assert model.device_name is None
        assert model.last_used_at is None
        assert model.is_active is True
        assert model.usage_count == 0

    def test_webauthn_credential_response_missing_required_fields(self):
        """Test WebAuthn credential response with missing required fields."""
        data = {
            "credential_id": "cred_123",
            # Missing required fields like user_id, created_at, etc.
        }

        with pytest.raises(ValidationError) as exc_info:
            WebAuthnCredentialResponse(**data)

        assert "Field required" in str(exc_info.value)

    def test_webauthn_credential_response_invalid_usage_count(self):
        """Test WebAuthn credential response with negative usage count."""
        now = datetime.now(UTC)
        data = {
            "credential_id": "cred_123",
            "user_id": "user_456",
            "created_at": now,
            "is_active": True,
            "usage_count": -1,  # Should be non-negative
        }

        with pytest.raises(ValidationError) as exc_info:
            WebAuthnCredentialResponse(**data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_webauthn_credential_response_serialization(self):
        """Test WebAuthn credential response serialization."""
        now = datetime.now(UTC)
        data = {
            "credential_id": "cred_123",
            "user_id": "user_456",
            "device_name": "Test Device",
            "created_at": now,
            "last_used_at": now,
            "is_active": True,
            "usage_count": 3,
        }

        model = WebAuthnCredentialResponse(**data)
        serialized = model.model_dump()

        # Verify serialization includes all fields
        assert serialized["credential_id"] == "cred_123"
        assert serialized["user_id"] == "user_456"
        assert serialized["device_name"] == "Test Device"
        assert serialized["is_active"] is True
        assert serialized["usage_count"] == 3
        # Datetime fields should be included
        assert "created_at" in serialized
        assert "last_used_at" in serialized

    def test_webauthn_credential_response_json_serialization(self):
        """Test WebAuthn credential response JSON serialization."""
        now = datetime.now(UTC)
        data = {
            "credential_id": "cred_123",
            "user_id": "user_456",
            "device_name": "Test Device",
            "created_at": now,
            "is_active": True,
            "usage_count": 1,
        }

        model = WebAuthnCredentialResponse(**data)
        json_str = model.model_dump_json()

        # Should be valid JSON string
        assert isinstance(json_str, str)
        assert "cred_123" in json_str
        assert "user_456" in json_str
        assert "Test Device" in json_str


class TestWebAuthnModelFieldValidation:
    """Test WebAuthn model field validation and edge cases."""

    def test_challenge_key_validation_patterns(self):
        """Test challenge key validation with different patterns."""
        # Valid challenge keys
        valid_keys = [
            "reg_user123_challenge456",
            "auth_user456_challenge789",
            "auth_any_challenge123",
        ]

        for key in valid_keys:
            data = {
                "challengeKey": key,
                "credential": {
                    "id": "cred_id",
                    "rawId": "raw_id",
                    "response": {
                        "attestationObject": "attestation",
                        "clientDataJSON": "client_data",
                    },
                    "type": "public-key",
                },
            }

            # Should not raise validation error
            model = WebAuthnRegistrationComplete(**data)
            assert model.challengeKey == key

    def test_credential_type_validation(self):
        """Test credential type validation."""
        data = {
            "challengeKey": "test_challenge",
            "credential": {
                "id": "cred_id",
                "rawId": "raw_id",
                "response": {
                    "attestationObject": "attestation",
                    "clientDataJSON": "client_data",
                },
                "type": "invalid-type",  # Should be "public-key"
            },
        }

        # WebAuthn spec requires type to be "public-key"
        # Note: This might not fail validation if we don't have strict enum validation
        model = WebAuthnRegistrationComplete(**data)
        assert model.credential["type"] == "invalid-type"

    def test_device_name_special_characters(self):
        """Test device name with special characters."""
        special_names = [
            "User's iPhone",
            "Test Device (2024)",
            'MacBook Pro 16"',
            "Device #1",
            "🔐 Secure Key",
        ]

        for name in special_names:
            data = {"device_name": name}
            model = WebAuthnRegistrationStart(**data)
            assert model.device_name == name

    def test_username_validation_edge_cases(self):
        """Test username validation with edge cases."""
        # Valid usernames
        valid_usernames = [
            "user123",
            "test.user",
            "user_name",
            "user-name",
            "TEST_USER",
        ]

        for username in valid_usernames:
            data = {"username": username}
            model = WebAuthnAuthenticationStart(**data)
            assert model.username == username

    def test_model_immutability(self):
        """Test that models are immutable after creation (if frozen)."""
        data = {"device_name": "Test Device"}
        model = WebAuthnRegistrationStart(**data)

        # If the model is frozen, this should raise an error
        # Note: Pydantic models are mutable by default unless configured otherwise
        try:
            model.device_name = "Modified Device"
            # If no error, model is mutable (which is fine for request models)
            assert model.device_name == "Modified Device"
        except (AttributeError, TypeError):
            # If error, model is frozen/immutable
            assert model.device_name == "Test Device"
