"""Unit and integration tests for security module following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- PostgreSQL database for integration tests (ZERO TOLERANCE for SQLite)
- Factory Pattern for test data
- 85%+ coverage target for security functions - CRITICAL SECURITY REQUIREMENT
- Focus on security functions business logic

Tests SecurityManager for password hashing, JWT token creation/verification, and revocation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest

from src.auth.models import TokenData
from src.auth.security import SecurityManager, auth_config

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def security_manager():
    """Factory for SecurityManager instance - MANDATORY DI."""
    return SecurityManager()


@pytest.fixture
def sample_user_data():
    """Factory for sample user data - DRY principle."""
    return {"sub": "testuser", "user_id": str(uuid4()), "scopes": ["read", "write"]}


@pytest.fixture
def sample_token_payload():
    """Factory for sample token payload."""
    return {
        "sub": "testuser",
        "user_id": str(uuid4()),
        "scopes": ["read"],
        "jti": str(uuid4()),
        "type": "access",
    }


# ============================================================================
# Test Suite 1: Security Manager Initialization (1 test)
# ============================================================================


class TestSecurityManagerInitialization:
    """Test SecurityManager initialization - SOLID Dependency Injection."""

    @pytest.mark.unit
    def test_security_manager_initialization(self, security_manager):
        """Test SecurityManager initializes with password context.

        AAA Pattern:
        - Arrange: Create SecurityManager via fixture
        - Act: Access pwd_context
        - Assert: Password context properly configured
        """
        # Act
        pwd_context = security_manager.pwd_context

        # Assert
        assert pwd_context is not None
        assert "bcrypt" in pwd_context.schemes()


# ============================================================================
# Test Suite 2: Password Hashing (4 tests)
# ============================================================================


class TestPasswordHashing:
    """Test password hashing and verification - CRITICAL SECURITY."""

    @pytest.mark.unit
    def test_get_password_hash_generates_hash(self, security_manager):
        """Test password hashing generates valid bcrypt hash.

        AAA Pattern:
        - Arrange: Plain password
        - Act: Hash password
        - Assert: Hash is valid bcrypt format
        """
        # Arrange
        plain_password = "SecurePassword123!"

        # Act
        password_hash = security_manager.get_password_hash(plain_password)

        # Assert
        assert password_hash is not None
        assert password_hash != plain_password
        assert password_hash.startswith("$2b$")  # bcrypt prefix

    @pytest.mark.unit
    def test_verify_password_correct_password(self, security_manager):
        """Test verify_password succeeds with correct password."""
        # Arrange
        plain_password = "SecurePassword123!"
        password_hash = security_manager.get_password_hash(plain_password)

        # Act
        is_valid = security_manager.verify_password(plain_password, password_hash)

        # Assert
        assert is_valid is True

    @pytest.mark.unit
    def test_verify_password_incorrect_password(self, security_manager):
        """Test verify_password fails with incorrect password."""
        # Arrange
        correct_password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        password_hash = security_manager.get_password_hash(correct_password)

        # Act
        is_valid = security_manager.verify_password(wrong_password, password_hash)

        # Assert
        assert is_valid is False

    @pytest.mark.unit
    def test_password_hash_uniqueness(self, security_manager):
        """Test same password generates different hashes (bcrypt salt)."""
        # Arrange
        plain_password = "SecurePassword123!"

        # Act
        hash1 = security_manager.get_password_hash(plain_password)
        hash2 = security_manager.get_password_hash(plain_password)

        # Assert - Different hashes due to random salt
        assert hash1 != hash2
        # But both should verify
        assert security_manager.verify_password(plain_password, hash1)
        assert security_manager.verify_password(plain_password, hash2)


# ============================================================================
# Test Suite 3: Access Token Creation (6 tests)
# ============================================================================


class TestAccessTokenCreation:
    """Test JWT access token creation - CRITICAL SECURITY."""

    @pytest.mark.unit
    def test_create_access_token_basic(self, security_manager, sample_user_data):
        """Test access token creation with default expiration.

        AAA Pattern:
        - Arrange: User data payload
        - Act: Create access token
        - Assert: Token and JTI returned, token decodable
        """
        # Act
        token, jti = security_manager.create_access_token(sample_user_data)

        # Assert
        assert token is not None
        assert jti is not None
        assert isinstance(token, str)
        assert isinstance(jti, str)

        # Verify token can be decoded
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert decoded["sub"] == sample_user_data["sub"]
        assert decoded["jti"] == jti
        assert decoded["type"] == "access"

    @pytest.mark.unit
    def test_create_access_token_custom_expiration(self, security_manager, sample_user_data):
        """Test access token with custom expiration delta."""
        # Arrange
        custom_delta = timedelta(minutes=15)

        # Act
        token, jti = security_manager.create_access_token(
            sample_user_data, expires_delta=custom_delta
        )

        # Assert
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)

        # Verify expiration is approximately 15 minutes from now
        expected_exp = datetime.now(UTC) + custom_delta
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 2  # Within 2 seconds tolerance

    @pytest.mark.unit
    def test_create_access_token_custom_jti(self, security_manager, sample_user_data):
        """Test access token with custom JTI provided."""
        # Arrange
        custom_jti = str(uuid4())

        # Act
        token, returned_jti = security_manager.create_access_token(sample_user_data, jti=custom_jti)

        # Assert
        assert returned_jti == custom_jti
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert decoded["jti"] == custom_jti

    @pytest.mark.unit
    def test_access_token_contains_required_claims(self, security_manager, sample_user_data):
        """Test access token contains all required JWT claims."""
        # Act
        token, jti = security_manager.create_access_token(sample_user_data)

        # Assert
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert "sub" in decoded
        assert "user_id" in decoded
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded
        assert "type" in decoded
        assert decoded["type"] == "access"

    @pytest.mark.unit
    def test_access_token_preserves_scopes(self, security_manager, sample_user_data):
        """Test access token preserves user scopes."""
        # Act
        token, jti = security_manager.create_access_token(sample_user_data)

        # Assert
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert decoded["scopes"] == sample_user_data["scopes"]

    @pytest.mark.unit
    def test_access_token_issued_at_timestamp(self, security_manager, sample_user_data):
        """Test access token iat (issued at) claim is recent."""
        # Act
        token, jti = security_manager.create_access_token(sample_user_data)

        # Assert
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        iat_timestamp = decoded["iat"]
        iat_datetime = datetime.fromtimestamp(iat_timestamp, tz=UTC)

        # Verify iat is within last 5 seconds (generous tolerance for test execution)
        time_diff = abs((datetime.now(UTC) - iat_datetime).total_seconds())
        assert time_diff < 5


# ============================================================================
# Test Suite 4: Refresh Token Creation (5 tests)
# ============================================================================


class TestRefreshTokenCreation:
    """Test JWT refresh token creation - CRITICAL SECURITY."""

    @pytest.mark.unit
    def test_create_refresh_token_basic(self, security_manager, sample_user_data):
        """Test refresh token creation with default expiration."""
        # Act
        token, jti = security_manager.create_refresh_token(sample_user_data)

        # Assert
        assert token is not None
        assert jti is not None

        # Verify token type is refresh
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert decoded["type"] == "refresh"
        assert decoded["jti"] == jti

    @pytest.mark.unit
    def test_create_refresh_token_longer_expiration(self, security_manager, sample_user_data):
        """Test refresh token has longer expiration than access token."""
        # Act
        refresh_token, refresh_jti = security_manager.create_refresh_token(sample_user_data)

        # Assert
        decoded = jwt.decode(
            refresh_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
        )
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)

        # Verify expiration is approximately 7 days from now (default)
        expected_exp = datetime.now(UTC) + auth_config.refresh_token_expire_delta
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 2  # Within 2 seconds

    @pytest.mark.unit
    def test_create_refresh_token_custom_expiration(self, security_manager, sample_user_data):
        """Test refresh token with custom expiration."""
        # Arrange
        custom_delta = timedelta(days=30)

        # Act
        token, jti = security_manager.create_refresh_token(
            sample_user_data, expires_delta=custom_delta
        )

        # Assert
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)

        expected_exp = datetime.now(UTC) + custom_delta
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 2

    @pytest.mark.unit
    def test_create_refresh_token_custom_jti(self, security_manager, sample_user_data):
        """Test refresh token with custom JTI."""
        # Arrange
        custom_jti = str(uuid4())

        # Act
        token, returned_jti = security_manager.create_refresh_token(
            sample_user_data, jti=custom_jti
        )

        # Assert
        assert returned_jti == custom_jti
        decoded = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        assert decoded["jti"] == custom_jti

    @pytest.mark.unit
    def test_refresh_token_unique_jti(self, security_manager, sample_user_data):
        """Test multiple refresh tokens have unique JTIs."""
        # Act
        token1, jti1 = security_manager.create_refresh_token(sample_user_data)
        token2, jti2 = security_manager.create_refresh_token(sample_user_data)

        # Assert
        assert jti1 != jti2


# ============================================================================
# Test Suite 5: Token Verification (8 tests) - ASYNC INTEGRATION
# ============================================================================


class TestTokenVerification:
    """Test JWT token verification with revocation checking - CRITICAL SECURITY."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_valid_not_revoked(self, security_manager, sample_user_data):
        """Test verify_token succeeds for valid, non-revoked token.

        AAA Pattern:
        - Arrange: Create valid token, mock revocation check
        - Act: Verify token
        - Assert: Returns TokenData with correct claims
        """
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        # Mock revocation check to return False (not revoked)
        with patch.object(security_manager, "is_token_revoked", new=AsyncMock(return_value=False)):
            # Act
            token_data = await security_manager.verify_token(token)

            # Assert
            assert token_data is not None
            assert isinstance(token_data, TokenData)
            assert token_data.username == sample_user_data["sub"]
            assert token_data.jti == jti
            assert token_data.token_type == "access"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_revoked_token(self, security_manager, sample_user_data):
        """Test verify_token fails for revoked token - SECURITY REQUIREMENT."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        # Mock revocation check to return True (revoked)
        with patch.object(security_manager, "is_token_revoked", new=AsyncMock(return_value=True)):
            # Act
            token_data = await security_manager.verify_token(token)

            # Assert - Should return None for revoked token
            assert token_data is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_missing_jti(self, security_manager):
        """Test verify_token fails when token missing JTI claim."""
        # Arrange - Create token without JTI
        payload = {"sub": "testuser", "exp": datetime.now(UTC) + timedelta(minutes=30)}
        token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        # Act
        token_data = await security_manager.verify_token(token)

        # Assert
        assert token_data is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_missing_username(self, security_manager):
        """Test verify_token fails when token missing sub (username) claim."""
        # Arrange - Create token without sub
        payload = {
            "user_id": str(uuid4()),
            "jti": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        # Act
        token_data = await security_manager.verify_token(token)

        # Assert
        assert token_data is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_revocation_check_exception(
        self, security_manager, sample_user_data
    ):
        """Test verify_token fails securely when revocation check raises exception."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        # Mock revocation check to raise exception
        with patch.object(
            security_manager, "is_token_revoked", new=AsyncMock(side_effect=Exception("DB error"))
        ):
            # Act
            token_data = await security_manager.verify_token(token)

            # Assert - Should fail securely
            assert token_data is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_expired_token(self, security_manager, sample_user_data):
        """Test verify_token raises RuntimeError for expired token - error handler behavior."""
        # Arrange - Create token with negative expiration
        token, jti = security_manager.create_access_token(
            sample_user_data,
            expires_delta=timedelta(seconds=-10),  # Already expired
        )

        # Act & Assert - Error handler catches ExpiredSignatureError and raises RuntimeError
        with pytest.raises(RuntimeError, match="Authentication operation failed"):
            await security_manager.verify_token(token)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_invalid_signature(self, security_manager, sample_user_data):
        """Test verify_token raises RuntimeError for tampered token - error handler behavior."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        # Tamper with token
        tampered_token = token[:-10] + "tampered10"

        # Act & Assert - Error handler catches InvalidSignatureError and raises RuntimeError
        with pytest.raises(RuntimeError, match="Authentication operation failed"):
            await security_manager.verify_token(tampered_token)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_verify_token_preserves_scopes(self, security_manager, sample_user_data):
        """Test verify_token preserves user scopes."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        with patch.object(security_manager, "is_token_revoked", new=AsyncMock(return_value=False)):
            # Act
            token_data = await security_manager.verify_token(token)

            # Assert
            assert token_data.scopes == sample_user_data["scopes"]


# ============================================================================
# Test Suite 6: Token Revocation Check (2 tests) - ASYNC INTEGRATION
# ============================================================================


class TestTokenRevocationCheck:
    """Test is_token_revoked integration with revocation service."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_is_token_revoked_delegates_to_service(self, security_manager):
        """Test is_token_revoked delegates to token_revocation_service.

        AAA Pattern:
        - Arrange: Mock revocation service
        - Act: Check if token is revoked
        - Assert: Service method was called
        """
        # Arrange
        test_jti = str(uuid4())

        with patch("src.auth.revocation_service.token_revocation_service") as mock_service:
            mock_service.is_token_revoked = AsyncMock(return_value=True)

            # Act
            result = await security_manager.is_token_revoked(test_jti)

            # Assert
            assert result is True
            mock_service.is_token_revoked.assert_called_once_with(test_jti)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_is_token_revoked_returns_false_for_valid_token(self, security_manager):
        """Test is_token_revoked returns False for non-revoked token."""
        # Arrange
        test_jti = str(uuid4())

        with patch("src.auth.revocation_service.token_revocation_service") as mock_service:
            mock_service.is_token_revoked = AsyncMock(return_value=False)

            # Act
            result = await security_manager.is_token_revoked(test_jti)

            # Assert
            assert result is False


# ============================================================================
# Test Suite 7: Token Decoding Without Verification (3 tests)
# ============================================================================


class TestTokenDecoding:
    """Test decode_access_token for OAuth state tokens - NO revocation check."""

    @pytest.mark.unit
    def test_decode_access_token_success(self, security_manager, sample_user_data):
        """Test decode_access_token returns payload dictionary."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        # Act
        decoded = security_manager.decode_access_token(token)

        # Assert
        assert decoded is not None
        assert decoded["sub"] == sample_user_data["sub"]
        assert decoded["jti"] == jti

    @pytest.mark.unit
    def test_decode_access_token_invalid_signature(self, security_manager, sample_user_data):
        """Test decode_access_token raises RuntimeError with tampered token - error handler."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)
        tampered_token = token[:-10] + "tampered10"

        # Act & Assert - Error handler catches jwt.InvalidSignatureError and raises RuntimeError
        with pytest.raises(RuntimeError, match="Authentication operation failed"):
            security_manager.decode_access_token(tampered_token)

    @pytest.mark.unit
    def test_decode_access_token_expired_fails(self, security_manager, sample_user_data):
        """Test decode_access_token raises RuntimeError for expired token - error handler."""
        # Arrange - Create expired token
        token, jti = security_manager.create_access_token(
            sample_user_data, expires_delta=timedelta(seconds=-10)
        )

        # Act & Assert - Error handler catches jwt.ExpiredSignatureError and raises RuntimeError
        with pytest.raises(RuntimeError, match="Authentication operation failed"):
            security_manager.decode_access_token(token)


# ============================================================================
# Test Suite 8: Token Expiration Check (4 tests)
# ============================================================================


class TestTokenExpirationCheck:
    """Test is_token_expired method - expiration validation."""

    @pytest.mark.unit
    def test_is_token_expired_valid_token(self, security_manager, sample_user_data):
        """Test is_token_expired returns False for valid token."""
        # Arrange
        token, jti = security_manager.create_access_token(sample_user_data)

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert
        assert is_expired is False

    @pytest.mark.unit
    def test_is_token_expired_expired_token(self, security_manager, sample_user_data):
        """Test is_token_expired returns True for expired token."""
        # Arrange - Create token that's already expired
        token, jti = security_manager.create_access_token(
            sample_user_data, expires_delta=timedelta(seconds=-10)
        )

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert
        assert is_expired is True

    @pytest.mark.unit
    def test_is_token_expired_missing_exp_claim(self, security_manager):
        """Test is_token_expired returns True when exp claim missing."""
        # Arrange - Create token without exp claim
        payload = {"sub": "testuser", "jti": str(uuid4())}
        token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert - Should return True for missing exp (fail securely)
        assert is_expired is True

    @pytest.mark.unit
    def test_is_token_expired_just_expired(self, security_manager, sample_user_data):
        """Test is_token_expired returns True for token that just expired."""
        # Arrange - Create token expiring in 1 second
        token, jti = security_manager.create_access_token(
            sample_user_data, expires_delta=timedelta(seconds=1)
        )

        # Wait for token to expire
        import time

        time.sleep(2)

        # Act
        is_expired = security_manager.is_token_expired(token)

        # Assert
        assert is_expired is True
