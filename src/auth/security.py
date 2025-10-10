"""Security utilities for authentication following FastAPI official patterns."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from passlib.context import CryptContext

from src.config.settings import ConfigManager
from src.core.decorators import auth_error_handler

from .models import TokenData

if TYPE_CHECKING:
    from src.config.auth import AuthConfig


def _get_auth_config() -> "AuthConfig":
    """Get authentication configuration from settings."""
    try:
        settings = ConfigManager.get_config()
        return settings.auth
    except RuntimeError:
        # Fallback for testing or early initialization
        from src.config.auth import AuthConfig

        return AuthConfig()


auth_config = _get_auth_config()


class SecurityManager:
    """Centralized security operations manager."""

    def __init__(self) -> None:
        self.pwd_context = CryptContext(
            schemes=auth_config.PWD_CONTEXT_SCHEMES, deprecated=auth_config.PWD_CONTEXT_DEPRECATED
        )

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return self.pwd_context.hash(password)

    def create_access_token(
        self,
        data: dict[str, str | bool | datetime | list[str]],
        expires_delta: timedelta | None = None,
        jti: str | None = None,
    ) -> tuple[str, str]:
        """Create JWT access token with revocation support - SOLID Single Responsibility.

        Args:
            data: Token payload data
            expires_delta: Custom expiration delta
            jti: Optional JWT ID (generated if not provided)

        Returns:
            Tuple of (token, jti) for revocation tracking
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + auth_config.access_token_expire_delta

        # Generate JTI for revocation tracking - DRY principle
        token_jti = jti or str(uuid.uuid4())

        to_encode.update(
            {
                "exp": expire,
                "iat": datetime.now(UTC),  # Issued at
                "jti": token_jti,  # JWT ID for revocation
                "type": "access",  # Token type for validation
            }
        )

        encoded_jwt = jwt.encode(to_encode, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)
        return encoded_jwt, token_jti

    def create_refresh_token(
        self,
        data: dict[str, str | bool | datetime],
        expires_delta: timedelta | None = None,
        jti: str | None = None,
    ) -> tuple[str, str]:
        """Create JWT refresh token with revocation support - SOLID Single Responsibility.

        Args:
            data: Token payload data
            expires_delta: Custom expiration delta
            jti: Optional JWT ID (generated if not provided)

        Returns:
            Tuple of (token, jti) for revocation tracking
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + auth_config.refresh_token_expire_delta

        # Generate JTI for revocation tracking - DRY principle
        token_jti = jti or str(uuid.uuid4())

        to_encode.update(
            {
                "exp": expire,
                "iat": datetime.now(UTC),  # Issued at
                "jti": token_jti,  # JWT ID for revocation
                "type": "refresh",  # Token type for validation
            }
        )

        encoded_jwt = jwt.encode(to_encode, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)
        return encoded_jwt, token_jti

    @auth_error_handler("verify JWT token")
    async def verify_token(self, token: str) -> TokenData | None:
        """Verify and decode JWT token with revocation checking - SOLID Single Responsibility."""
        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])

        # Extract token claims
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        scopes: list[str] = payload.get("scopes", [])
        jti: str = payload.get("jti")
        token_type: str = payload.get("type")

        if username is None or jti is None:
            return None

        # Check if token is revoked - Security Requirement (fail securely)
        try:
            if await self.is_token_revoked(jti):
                return None
        except Exception:
            # Fail securely: if revocation check fails, reject the token
            return None

        token_data = TokenData(
            username=username, user_id=user_id, scopes=scopes, jti=jti, token_type=token_type
        )
        return token_data

    async def is_token_revoked(self, jti: str) -> bool:
        """Check if token JTI is in the revocation blacklist - SOLID Single Responsibility."""
        from .revocation_service import token_revocation_service

        return await token_revocation_service.is_token_revoked(jti)

    @auth_error_handler("decode access token")
    def decode_access_token(self, token: str) -> dict[str, str | int | bool]:
        """Decode JWT token without revocation checking - for OAuth state tokens."""
        from typing import Any

        payload: dict[str, Any] = jwt.decode(
            token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
        )
        return payload

    @auth_error_handler("check token expiration")
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        payload = jwt.decode(
            token,
            auth_config.SECRET_KEY,
            algorithms=[auth_config.ALGORITHM],
            options={"verify_exp": False},  # Don't verify expiration here
        )
        exp = payload.get("exp")
        if exp is None:
            return True

        return datetime.fromtimestamp(exp, tz=UTC) < datetime.now(UTC)


# Global security manager instance
security_manager = SecurityManager()
