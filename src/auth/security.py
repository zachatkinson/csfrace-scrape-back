"""Security utilities for authentication following FastAPI official patterns."""

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from .config import auth_config
from .models import TokenData


class SecurityManager:
    """Centralized security operations manager."""

    def __init__(self):
        self.pwd_context = CryptContext(
            schemes=auth_config.PWD_CONTEXT_SCHEMES, deprecated=auth_config.PWD_CONTEXT_DEPRECATED
        )

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return self.pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        """Create JWT access token following FastAPI official pattern."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + auth_config.access_token_expire_delta

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + auth_config.refresh_token_expire_delta

        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> TokenData | None:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            scopes: list[str] = payload.get("scopes", [])

            if username is None:
                return None

            token_data = TokenData(username=username, user_id=user_id, scopes=scopes)
            return token_data
        except jwt.PyJWTError:
            return None

    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        try:
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
        except jwt.PyJWTError:
            return True


# Global security manager instance
security_manager = SecurityManager()
