"""Comprehensive tests for TokenEncryptionService.

Tests cover:
- Encryption/decryption roundtrip
- Invalid key handling
- Corrupted token handling
- Key rotation
- Edge cases and error conditions
- Target: 80%+ code coverage
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from src.auth.token_encryption_service import (
    InvalidEncryptionKeyError,
    TokenDecryptionError,
    TokenEncryptionError,
    TokenEncryptionService,
)


class TestTokenEncryptionService:
    """Test suite for TokenEncryptionService."""

    @pytest.fixture
    def valid_key(self) -> str:
        """Generate a valid Fernet encryption key."""
        return Fernet.generate_key().decode()

    @pytest.fixture
    def service(self, valid_key: str) -> TokenEncryptionService:
        """Create a TokenEncryptionService instance with valid key."""
        return TokenEncryptionService(encryption_key=valid_key)

    @pytest.fixture
    def sample_token(self) -> str:
        """Sample OAuth token for testing."""
        return "ya29.a0AfH6SMBx3xK4..."  # Sample Google OAuth token format

    # Basic Functionality Tests

    def test_initialization_with_valid_key(self, valid_key: str) -> None:
        """Test service initialization with valid encryption key."""
        service = TokenEncryptionService(encryption_key=valid_key)
        assert service is not None
        assert service._fernet is not None

    def test_initialization_with_invalid_key(self) -> None:
        """Test service initialization with invalid encryption key."""
        with pytest.raises(InvalidEncryptionKeyError) as exc_info:
            TokenEncryptionService(encryption_key="invalid_key")

        assert "Invalid encryption key format" in str(exc_info.value)

    def test_initialization_with_empty_key(self) -> None:
        """Test service initialization with empty encryption key."""
        with pytest.raises(InvalidEncryptionKeyError) as exc_info:
            TokenEncryptionService(encryption_key="")

        assert "Encryption key is required" in str(exc_info.value)

    def test_initialization_without_key_and_no_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test initialization without key when environment variable is not set.

        NOTE: This test is skipped because OAUTH_TOKEN_ENCRYPTION_KEY is now a required
        constant that's loaded at module import time. If it's not set, the application
        won't start. This is intentional security design - the key must be configured.
        """
        pytest.skip(
            "Test not applicable - OAUTH_TOKEN_ENCRYPTION_KEY is required at module import time"
        )

    # Encryption Tests

    def test_encrypt_token_success(
        self, service: TokenEncryptionService, sample_token: str
    ) -> None:
        """Test successful token encryption."""
        encrypted = service.encrypt_token(sample_token)

        assert encrypted is not None
        assert isinstance(encrypted, str)
        assert encrypted != sample_token
        assert len(encrypted) > len(sample_token)

    def test_encrypt_empty_token(self, service: TokenEncryptionService) -> None:
        """Test encryption of empty token raises error."""
        with pytest.raises(TokenEncryptionError) as exc_info:
            service.encrypt_token("")

        assert "Cannot encrypt empty token" in str(exc_info.value)

    def test_encrypt_different_tokens_produce_different_results(
        self, service: TokenEncryptionService
    ) -> None:
        """Test that encrypting different tokens produces different ciphertexts."""
        token1 = "token_1234567890"
        token2 = "token_0987654321"

        encrypted1 = service.encrypt_token(token1)
        encrypted2 = service.encrypt_token(token2)

        assert encrypted1 != encrypted2

    def test_encrypt_same_token_twice_produces_different_results(
        self, service: TokenEncryptionService, sample_token: str
    ) -> None:
        """Test that Fernet produces different ciphertexts for same plaintext (with timestamp)."""
        encrypted1 = service.encrypt_token(sample_token)
        encrypted2 = service.encrypt_token(sample_token)

        # Fernet includes timestamp, so same plaintext -> different ciphertext
        assert encrypted1 != encrypted2

    # Decryption Tests

    def test_decrypt_token_success(
        self, service: TokenEncryptionService, sample_token: str
    ) -> None:
        """Test successful token decryption."""
        encrypted = service.encrypt_token(sample_token)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == sample_token

    def test_decrypt_empty_token(self, service: TokenEncryptionService) -> None:
        """Test decryption of empty token raises error."""
        with pytest.raises(TokenDecryptionError) as exc_info:
            service.decrypt_token("")

        assert "Cannot decrypt empty token" in str(exc_info.value)

    def test_decrypt_invalid_token(self, service: TokenEncryptionService) -> None:
        """Test decryption of invalid/corrupted token."""
        with pytest.raises(TokenDecryptionError) as exc_info:
            service.decrypt_token("invalid_encrypted_token_12345")

        assert "Failed to decrypt token" in str(exc_info.value)

    def test_decrypt_with_wrong_key(self, sample_token: str) -> None:
        """Test decryption fails when using different key than encryption."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        service1 = TokenEncryptionService(encryption_key=key1)
        service2 = TokenEncryptionService(encryption_key=key2)

        encrypted = service1.encrypt_token(sample_token)

        with pytest.raises(TokenDecryptionError) as exc_info:
            service2.decrypt_token(encrypted)

        assert "Failed to decrypt token" in str(exc_info.value)

    def test_decrypt_corrupted_token(
        self, service: TokenEncryptionService, sample_token: str
    ) -> None:
        """Test decryption of corrupted token data."""
        encrypted = service.encrypt_token(sample_token)

        # Corrupt the encrypted token by modifying it
        corrupted = encrypted[:-5] + "XXXXX"

        with pytest.raises(TokenDecryptionError):
            service.decrypt_token(corrupted)

    # Roundtrip Tests

    def test_encryption_decryption_roundtrip(
        self, service: TokenEncryptionService, sample_token: str
    ) -> None:
        """Test encryption followed by decryption returns original token."""
        encrypted = service.encrypt_token(sample_token)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == sample_token

    def test_roundtrip_with_special_characters(self, service: TokenEncryptionService) -> None:
        """Test roundtrip with tokens containing special characters."""
        special_tokens = [
            "token_with_underscore",
            "token-with-dash",
            "token.with.dots",
            "token/with/slashes",
            "token=with=equals",
            "token+with+plus",
            "token with spaces",
            "token_with_émoji_🔐",
        ]

        for token in special_tokens:
            encrypted = service.encrypt_token(token)
            decrypted = service.decrypt_token(encrypted)
            assert decrypted == token, f"Roundtrip failed for token: {token}"

    def test_roundtrip_with_long_token(self, service: TokenEncryptionService) -> None:
        """Test roundtrip with very long token."""
        long_token = "x" * 10000

        encrypted = service.encrypt_token(long_token)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == long_token
        assert len(decrypted) == 10000

    # Key Rotation Tests

    def test_rotate_encryption_key_success(self, sample_token: str) -> None:
        """Test successful key rotation."""
        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        # Encrypt with old key
        old_service = TokenEncryptionService(encryption_key=old_key)
        encrypted_with_old_key = old_service.encrypt_token(sample_token)

        # Rotate to new key
        re_encrypted = old_service.rotate_encryption_key(
            old_key=old_key, new_key=new_key, encrypted_token=encrypted_with_old_key
        )

        # Verify decryption with new key
        new_service = TokenEncryptionService(encryption_key=new_key)
        decrypted = new_service.decrypt_token(re_encrypted)

        assert decrypted == sample_token

    def test_rotate_encryption_key_with_invalid_old_key(self, sample_token: str) -> None:
        """Test key rotation fails with invalid old key."""
        valid_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()
        wrong_old_key = "invalid_key"

        service = TokenEncryptionService(encryption_key=valid_key)
        encrypted = service.encrypt_token(sample_token)

        with pytest.raises(InvalidEncryptionKeyError):
            service.rotate_encryption_key(
                old_key=wrong_old_key, new_key=new_key, encrypted_token=encrypted
            )

    def test_rotate_encryption_key_with_invalid_new_key(self, sample_token: str) -> None:
        """Test key rotation fails with invalid new key."""
        old_key = Fernet.generate_key().decode()
        invalid_new_key = "invalid_key"

        service = TokenEncryptionService(encryption_key=old_key)
        encrypted = service.encrypt_token(sample_token)

        with pytest.raises(InvalidEncryptionKeyError):
            service.rotate_encryption_key(
                old_key=old_key, new_key=invalid_new_key, encrypted_token=encrypted
            )

    def test_rotate_encryption_key_with_wrong_old_key(self, sample_token: str) -> None:
        """Test key rotation fails when old key doesn't match encryption key."""
        actual_old_key = Fernet.generate_key().decode()
        wrong_old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        service = TokenEncryptionService(encryption_key=actual_old_key)
        encrypted = service.encrypt_token(sample_token)

        with pytest.raises(TokenDecryptionError):
            service.rotate_encryption_key(
                old_key=wrong_old_key, new_key=new_key, encrypted_token=encrypted
            )

    # Key Generation Tests

    def test_generate_key_returns_valid_key(self) -> None:
        """Test that generate_key returns a valid Fernet key."""
        new_key = TokenEncryptionService.generate_key()

        assert new_key is not None
        assert isinstance(new_key, str)
        assert len(new_key) == 44  # Fernet keys are 44 characters base64-encoded

        # Verify key works with Fernet
        Fernet(new_key.encode())  # Should not raise

    def test_generate_key_produces_different_keys(self) -> None:
        """Test that generate_key produces unique keys each time."""
        key1 = TokenEncryptionService.generate_key()
        key2 = TokenEncryptionService.generate_key()

        assert key1 != key2

    def test_generated_key_can_encrypt_decrypt(self, sample_token: str) -> None:
        """Test that generated key can be used for encryption/decryption."""
        new_key = TokenEncryptionService.generate_key()
        service = TokenEncryptionService(encryption_key=new_key)

        encrypted = service.encrypt_token(sample_token)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == sample_token

    # Password-based Key Derivation Tests

    def test_derive_key_from_password(self) -> None:
        """Test password-based key derivation."""
        password = "my_secure_password_12345"

        key, salt = TokenEncryptionService.derive_key_from_password(password)

        assert key is not None
        assert isinstance(key, str)
        assert len(key) == 44  # Fernet key length
        assert salt is not None
        assert isinstance(salt, bytes)
        assert len(salt) == 16

    def test_derive_key_from_password_with_same_salt_produces_same_key(self) -> None:
        """Test that same password and salt produce same key."""
        password = "my_secure_password_12345"

        key1, salt = TokenEncryptionService.derive_key_from_password(password)
        key2, _ = TokenEncryptionService.derive_key_from_password(password, salt=salt)

        assert key1 == key2

    def test_derive_key_from_password_with_different_salt_produces_different_key(self) -> None:
        """Test that same password with different salts produce different keys."""
        password = "my_secure_password_12345"

        key1, salt1 = TokenEncryptionService.derive_key_from_password(password)
        key2, salt2 = TokenEncryptionService.derive_key_from_password(password)

        assert key1 != key2
        assert salt1 != salt2

    def test_derived_key_can_encrypt_decrypt(self, sample_token: str) -> None:
        """Test that derived key can be used for encryption/decryption."""
        password = "my_secure_password_12345"
        key, _ = TokenEncryptionService.derive_key_from_password(password)

        service = TokenEncryptionService(encryption_key=key)

        encrypted = service.encrypt_token(sample_token)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == sample_token

    # Edge Cases

    def test_encrypt_token_with_unicode_characters(self, service: TokenEncryptionService) -> None:
        """Test encryption of token with unicode characters."""
        unicode_token = "token_with_unicode_日本語_中文_한국어"

        encrypted = service.encrypt_token(unicode_token)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == unicode_token

    def test_encrypt_token_with_newlines(self, service: TokenEncryptionService) -> None:
        """Test encryption of token with newline characters."""
        token_with_newlines = "token_line1\ntoken_line2\ntoken_line3"

        encrypted = service.encrypt_token(token_with_newlines)
        decrypted = service.decrypt_token(encrypted)

        assert decrypted == token_with_newlines

    def test_multiple_services_with_same_key_can_decrypt(self, sample_token: str) -> None:
        """Test that multiple service instances with same key can decrypt each other's tokens."""
        shared_key = Fernet.generate_key().decode()

        service1 = TokenEncryptionService(encryption_key=shared_key)
        service2 = TokenEncryptionService(encryption_key=shared_key)

        encrypted_by_service1 = service1.encrypt_token(sample_token)
        decrypted_by_service2 = service2.decrypt_token(encrypted_by_service1)

        assert decrypted_by_service2 == sample_token
