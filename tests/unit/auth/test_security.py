"""Comprehensive tests for SecurityManager with token revocation functionality."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest

from src.auth.models import TokenData
from src.auth.security import SecurityManager


@pytest.fixture
def security_manager():
    """SecurityManager instance for testing - DRY fixture."""
    return SecurityManager()


@pytest.fixture
def mock_token_revocation_service():
    """Mock TokenRevocationService - DRY fixture."""
    service = AsyncMock()
    service.is_token_revoked = AsyncMock(return_value=False)
    return service


@pytest.fixture
def sample_token_data():
    """Sample token data for testing - DRY fixture."""
    return {
        "sub": "testuser",
        "user_id": "user123",
        "scopes": ["read", "write"],
    }


class TestSecurityManagerPasswordOperations:
    """Test password operations - SOLID Single Responsibility testing."""

    def test_verify_password_correct(self, security_manager):
        """Test password verification with correct password."""
        # Arrange
        password = "test_password123"
        hashed = security_manager.get_password_hash(password)

        # Act
        result = security_manager.verify_password(password, hashed)

        # Assert
        assert result is True

    def test_verify_password_incorrect(self, security_manager):
        """Test password verification with incorrect password."""
        # Arrange
        correct_password = "test_password123"
        wrong_password = "wrong_password"
        hashed = security_manager.get_password_hash(correct_password)

        # Act
        result = security_manager.verify_password(wrong_password, hashed)

        # Assert
        assert result is False

    def test_get_password_hash_generates_hash(self, security_manager):
        """Test password hash generation - DRY principle validation."""
        # Arrange
        password = "test_password123"

        # Act
        hashed = security_manager.get_password_hash(password)

        # Assert
        assert hashed != password  # Should be hashed, not plaintext
        assert len(hashed) > 20  # Hashes should be reasonably long
        assert hashed.startswith("$")  # bcrypt hashes start with $

    def test_password_hash_consistency(self, security_manager):
        """Test that password hashing is consistent but unique - Security requirement."""
        # Arrange
        password = "test_password123"

        # Act
        hash1 = security_manager.get_password_hash(password)
        hash2 = security_manager.get_password_hash(password)

        # Assert
        assert hash1 != hash2  # Salt should make each hash unique
        assert security_manager.verify_password(password, hash1)
        assert security_manager.verify_password(password, hash2)


class TestSecurityManagerTokenCreation:
    """Test JWT token creation with JTI support - SOLID Single Responsibility testing."""

    def test_create_access_token_with_jti(self, security_manager, sample_token_data):
        """Test access token creation returns token and JTI - SOLID Single Responsibility."""
        # Act
        token, jti = security_manager.create_access_token(sample_token_data)

        # Assert
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert len(jti) > 10  # JTI should be reasonable length

        # Verify token can be decoded
        from src.auth.config import auth_config

        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert payload["jti"] == jti
        assert payload["type"] == "access"
        assert payload["sub"] == sample_token_data["sub"]

    def test_create_refresh_token_with_jti(self, security_manager, sample_token_data):
        """Test refresh token creation returns token and JTI - SOLID Single Responsibility."""
        # Act
        token, jti = security_manager.create_refresh_token(sample_token_data)

        # Assert
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert len(jti) > 10

        # Verify token can be decoded
        from src.auth.config import auth_config

        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert payload["jti"] == jti
        assert payload["type"] == "refresh"
        assert payload["sub"] == sample_token_data["sub"]

    def test_create_access_token_with_custom_jti(self, security_manager, sample_token_data):
        """Test access token creation with custom JTI - DRY principle validation."""
        # Arrange
        custom_jti = "custom-jwt-id-12345"

        # Act
        token, returned_jti = security_manager.create_access_token(
            sample_token_data, jti=custom_jti
        )

        # Assert
        assert returned_jti == custom_jti

        # Verify custom JTI is in token
        from src.auth.config import auth_config

        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert payload["jti"] == custom_jti

    def test_create_access_token_with_custom_expiry(self, security_manager, sample_token_data):
        """Test access token creation with custom expiry - SOLID Single Responsibility."""
        # Arrange
        custom_expiry = timedelta(minutes=30)

        # Act
        token, jti = security_manager.create_access_token(
            sample_token_data, expires_delta=custom_expiry
        )

        # Assert
        from src.auth.config import auth_config

        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])

        issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
        actual_duration = expires_at - issued_at

        # Should be close to 30 minutes (allowing for small timing differences)
        assert 29 * 60 <= actual_duration.total_seconds() <= 31 * 60

    def test_token_jti_uniqueness(self, security_manager, sample_token_data):
        """Test that each token gets a unique JTI - Security requirement."""
        # Act
        token1, jti1 = security_manager.create_access_token(sample_token_data)
        token2, jti2 = security_manager.create_access_token(sample_token_data)

        # Assert
        assert jti1 != jti2  # JTIs should be unique
        assert token1 != token2  # Tokens should be different


class TestSecurityManagerTokenVerification:
    """Test JWT token verification with revocation checking - SOLID Single Responsibility testing."""

    @pytest.mark.asyncio
    async def test_verify_token_valid_not_revoked(self, security_manager, sample_token_data):
        """Test token verification for valid, non-revoked token."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_token_data)

        with patch("src.auth.revocation_service.token_revocation_service") as mock_service:
            mock_service.is_token_revoked = AsyncMock(return_value=False)

            # Act
            token_data = await security_manager.verify_token(token)

            # Assert
            assert token_data is not None
            assert isinstance(token_data, TokenData)
            assert token_data.username == sample_token_data["sub"]
            assert token_data.user_id == sample_token_data["user_id"]
            assert token_data.scopes == sample_token_data["scopes"]
            assert token_data.jti == jti
            assert token_data.token_type == "access"
            mock_service.is_token_revoked.assert_called_once_with(jti)

    @pytest.mark.asyncio
    async def test_verify_token_revoked(self, security_manager, sample_token_data):
        """Test token verification for revoked token - Security requirement."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_token_data)

        with patch("src.auth.revocation_service.token_revocation_service") as mock_service:
            mock_service.is_token_revoked = AsyncMock(return_value=True)

            # Act
            token_data = await security_manager.verify_token(token)

            # Assert
            assert token_data is None  # Revoked tokens should be rejected
            mock_service.is_token_revoked.assert_called_once_with(jti)

    @pytest.mark.asyncio
    async def test_verify_token_invalid_signature(self, security_manager):
        """Test token verification with invalid signature."""
        # Arrange
        invalid_token = "invalid.jwt.token"

        # Act
        token_data = await security_manager.verify_token(invalid_token)

        # Assert
        assert token_data is None

    @pytest.mark.asyncio
    async def test_verify_token_missing_required_claims(self, security_manager):
        """Test token verification with missing required claims."""
        # Arrange - Create token without username (sub claim)
        from src.auth.config import auth_config

        payload = {"user_id": "user123", "jti": "test-jti"}
        token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        # Act
        token_data = await security_manager.verify_token(token)

        # Assert
        assert token_data is None

    @pytest.mark.asyncio
    async def test_verify_token_missing_jti(self, security_manager):
        """Test token verification with missing JTI claim - Security requirement."""
        # Arrange - Create token without JTI
        from src.auth.config import auth_config

        payload = {"sub": "testuser", "user_id": "user123"}
        token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        # Act
        token_data = await security_manager.verify_token(token)

        # Assert
        assert token_data is None  # Tokens without JTI should be rejected

    @pytest.mark.asyncio
    async def test_verify_token_expired(self, security_manager, sample_token_data):
        """Test token verification with expired token."""
        # Arrange - Create token that expires immediately
        expired_delta = timedelta(seconds=-1)
        token, jti = security_manager.create_access_token(
            sample_token_data, expires_delta=expired_delta
        )

        # Act
        token_data = await security_manager.verify_token(token)

        # Assert
        assert token_data is None


class TestSecurityManagerTokenExpiration:
    """Test token expiration checking - SOLID Single Responsibility testing."""

    def test_is_token_expired_not_expired(self, security_manager, sample_token_data):
        """Test checking expiration for valid token."""
        # Arrange
        token, _ = security_manager.create_access_token(sample_token_data)

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert
        assert is_expired is False

    def test_is_token_expired_expired_token(self, security_manager, sample_token_data):
        """Test checking expiration for expired token."""
        # Arrange - Create token that expires immediately
        expired_delta = timedelta(seconds=-10)
        token, _ = security_manager.create_access_token(
            sample_token_data, expires_delta=expired_delta
        )

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert
        assert is_expired is True

    def test_is_token_expired_invalid_token(self, security_manager):
        """Test checking expiration for invalid token."""
        # Act
        is_expired = security_manager.is_token_expired("invalid.token")

        # Assert
        assert is_expired is True  # Invalid tokens should be considered expired

    def test_is_token_expired_missing_exp_claim(self, security_manager):
        """Test checking expiration for token without exp claim."""
        # Arrange - Create token without expiration claim
        from src.auth.config import auth_config

        payload = {"sub": "testuser", "jti": "test-jti"}
        token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert
        assert is_expired is True  # Tokens without exp claim should be considered expired


class TestSecurityManagerEdgeCases:
    """Test edge cases and security scenarios - Comprehensive coverage."""

    @pytest.mark.asyncio
    async def test_verify_token_revocation_check_error(self, security_manager, sample_token_data):
        """Test token verification when revocation check fails."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_token_data)

        with patch("src.auth.revocation_service.token_revocation_service") as mock_service:
            mock_service.is_token_revoked = AsyncMock(side_effect=Exception("Database error"))

            # Act
            token_data = await security_manager.verify_token(token)

            # Assert - Should fail securely when revocation check fails
            assert token_data is None

    def test_create_token_with_all_scopes(self, security_manager):
        """Test token creation with comprehensive scope list - SOLID Interface Segregation."""
        # Arrange
        token_data = {
            "sub": "testuser",
            "user_id": "user123",
            "scopes": ["read", "write", "admin", "delete", "manage_users"],
        }

        # Act
        token, jti = security_manager.create_access_token(token_data)

        # Assert
        from src.auth.config import auth_config

        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert payload["scopes"] == token_data["scopes"]

    def test_token_structure_completeness(self, security_manager, sample_token_data):
        """Test that created tokens have all required fields - Security requirement."""
        # Act
        access_token, access_jti = security_manager.create_access_token(sample_token_data)
        refresh_token, refresh_jti = security_manager.create_refresh_token(sample_token_data)

        # Assert access token structure
        from src.auth.config import auth_config

        access_payload = jwt.decode(
            access_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
        )
        required_access_fields = ["sub", "user_id", "exp", "iat", "jti", "type", "scopes"]
        for field in required_access_fields:
            assert field in access_payload, f"Access token missing required field: {field}"
        assert access_payload["type"] == "access"

        # Assert refresh token structure
        refresh_payload = jwt.decode(
            refresh_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
        )
        required_refresh_fields = ["sub", "user_id", "exp", "iat", "jti", "type"]
        for field in required_refresh_fields:
            assert field in refresh_payload, f"Refresh token missing required field: {field}"
        assert refresh_payload["type"] == "refresh"

    @pytest.mark.asyncio
    async def test_concurrent_token_verification(self, security_manager, sample_token_data):
        """Test concurrent token verification doesn't interfere - Thread safety."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_token_data)

        with patch("src.auth.revocation_service.token_revocation_service") as mock_service:
            mock_service.is_token_revoked = AsyncMock(return_value=False)

            # Act - Simulate concurrent verification
            import asyncio

            results = await asyncio.gather(
                security_manager.verify_token(token),
                security_manager.verify_token(token),
                security_manager.verify_token(token),
            )

            # Assert - All should succeed
            assert all(result is not None for result in results)
            assert all(result.jti == jti for result in results)
            assert mock_service.is_token_revoked.call_count == 3
