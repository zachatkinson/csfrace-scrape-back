"""OAuth token encryption service for secure token storage.

This service provides AES-128 encryption for OAuth tokens with support for:
- Symmetric encryption using Fernet (AES-128 in CBC mode)
- Secure key management via environment variables
- Token encryption/decryption with comprehensive error handling
- Key rotation capability for security best practices
- Structured logging for all operations

Follows SOLID principles:
- Single Responsibility: Only handles token encryption/decryption
- Open/Closed: Extensible for additional encryption algorithms
- Dependency Inversion: Accepts encryption key via dependency injection
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.core.logging_hierarchy import get_auth_logger

logger = get_auth_logger(__name__)


class TokenEncryptionError(Exception):
    """Base exception for token encryption errors."""

    pass


class InvalidEncryptionKeyError(TokenEncryptionError):
    """Raised when encryption key is invalid or missing."""

    pass


class TokenDecryptionError(TokenEncryptionError):
    """Raised when token decryption fails."""

    pass


class TokenEncryptionService:
    """Service for encrypting and decrypting OAuth tokens.

    Uses Fernet (AES-128 in CBC mode with HMAC for authentication) for
    symmetric encryption of sensitive OAuth tokens before database storage.

    Attributes:
        _fernet: Fernet cipher instance for encryption/decryption
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        """Initialize token encryption service.

        Args:
            encryption_key: Base64-encoded Fernet encryption key.
                          If None, loads from OAUTH_TOKEN_ENCRYPTION_KEY environment variable.

        Raises:
            InvalidEncryptionKeyError: If encryption key is missing or invalid
        """
        # Load from environment if not provided
        if encryption_key is None:
            from src.constants.auth import OAUTH_TOKEN_ENCRYPTION_KEY

            encryption_key = OAUTH_TOKEN_ENCRYPTION_KEY

        # Validate encryption key
        if not encryption_key:
            logger.error("Encryption key not provided and OAUTH_TOKEN_ENCRYPTION_KEY not set")
            raise InvalidEncryptionKeyError(
                "Encryption key is required. Set OAUTH_TOKEN_ENCRYPTION_KEY environment variable "
                "or provide key during initialization."
            )

        # Validate key format and create Fernet instance
        try:
            # Ensure key is properly formatted
            if not encryption_key.endswith("="):
                # Fernet keys should be 44 bytes base64-encoded (32 bytes raw + padding)
                logger.warning("Encryption key may not be properly formatted")

            self._fernet = Fernet(encryption_key.encode())
            logger.info("Token encryption service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Fernet cipher: {e}")
            raise InvalidEncryptionKeyError(
                f"Invalid encryption key format: {e}. "
                'Generate a valid key with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from e

    def encrypt_token(self, plain_token: str) -> str:
        """Encrypt a plain text token.

        Args:
            plain_token: Plain text OAuth token to encrypt

        Returns:
            Base64-encoded encrypted token

        Raises:
            TokenEncryptionError: If encryption fails
        """
        if not plain_token:
            logger.warning("Attempted to encrypt empty token")
            raise TokenEncryptionError("Cannot encrypt empty token")

        try:
            # Encrypt token and return base64-encoded string
            encrypted_bytes = self._fernet.encrypt(plain_token.encode())
            encrypted_token = encrypted_bytes.decode()

            logger.debug(
                "Token encrypted successfully",
                token_length=len(plain_token),
                encrypted_length=len(encrypted_token),
            )

            return encrypted_token

        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise TokenEncryptionError(f"Failed to encrypt token: {e}") from e

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt an encrypted token.

        Args:
            encrypted_token: Base64-encoded encrypted token

        Returns:
            Decrypted plain text token

        Raises:
            TokenDecryptionError: If decryption fails or token is corrupted
        """
        if not encrypted_token:
            logger.warning("Attempted to decrypt empty token")
            raise TokenDecryptionError("Cannot decrypt empty token")

        try:
            # Decrypt token and return plain text
            decrypted_bytes = self._fernet.decrypt(encrypted_token.encode())
            plain_token = decrypted_bytes.decode()

            logger.debug(
                "Token decrypted successfully",
                encrypted_length=len(encrypted_token),
                decrypted_length=len(plain_token),
            )

            return plain_token

        except InvalidToken as e:
            logger.error("Token decryption failed: Invalid or corrupted token")
            raise TokenDecryptionError(
                "Failed to decrypt token. Token may be corrupted or encrypted with a different key."
            ) from e

        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise TokenDecryptionError(f"Failed to decrypt token: {e}") from e

    def rotate_encryption_key(self, old_key: str, new_key: str, encrypted_token: str) -> str:
        """Rotate encryption key by re-encrypting token with new key.

        This enables secure key rotation without service downtime.
        Decrypt with old key, re-encrypt with new key.

        Args:
            old_key: Previous encryption key (base64-encoded)
            new_key: New encryption key (base64-encoded)
            encrypted_token: Token encrypted with old key

        Returns:
            Token re-encrypted with new key

        Raises:
            InvalidEncryptionKeyError: If old or new key is invalid
            TokenDecryptionError: If decryption with old key fails
            TokenEncryptionError: If encryption with new key fails
        """
        logger.info("Starting encryption key rotation")

        try:
            # Create temporary services with old and new keys
            old_service = TokenEncryptionService(encryption_key=old_key)
            new_service = TokenEncryptionService(encryption_key=new_key)

            # Decrypt with old key
            plain_token = old_service.decrypt_token(encrypted_token)

            # Re-encrypt with new key
            new_encrypted_token = new_service.encrypt_token(plain_token)

            logger.info("Encryption key rotation completed successfully")

            return new_encrypted_token

        except InvalidEncryptionKeyError:
            logger.error("Key rotation failed: Invalid encryption key")
            raise

        except TokenDecryptionError:
            logger.error("Key rotation failed: Could not decrypt with old key")
            raise

        except TokenEncryptionError:
            logger.error("Key rotation failed: Could not encrypt with new key")
            raise

        except Exception as e:
            logger.error(f"Key rotation failed with unexpected error: {e}")
            raise TokenEncryptionError(f"Key rotation failed: {e}") from e

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key suitable for use as OAUTH_TOKEN_ENCRYPTION_KEY

        Example:
            >>> service = TokenEncryptionService()
            >>> new_key = service.generate_key()
            >>> print(f"OAUTH_TOKEN_ENCRYPTION_KEY={new_key}")
        """
        new_key = Fernet.generate_key().decode()
        logger.info("Generated new encryption key")
        return new_key

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes | None = None) -> tuple[str, bytes]:
        """Derive a Fernet key from a password using PBKDF2.

        Useful for generating encryption keys from user-provided passwords
        or passphrases. NOT RECOMMENDED for production - use generate_key() instead.

        Args:
            password: Password to derive key from
            salt: Optional salt (generates random if not provided)

        Returns:
            Tuple of (base64-encoded key, salt used for derivation)

        Note:
            This is provided for compatibility but using randomly generated
            keys via generate_key() is more secure for production use.
        """
        if salt is None:
            import os

            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # OWASP recommendation as of 2023
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        logger.warning("Key derived from password - consider using generate_key() for production")

        return key.decode(), salt
