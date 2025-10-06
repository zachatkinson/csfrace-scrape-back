"""Base configuration classes and utilities.

This module provides base classes and utilities for configuration management
following modern Python best practices with Pydantic settings.
"""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.logging_hierarchy import get_core_logger

logger = get_core_logger()


class BaseConfig(BaseSettings):
    """Base configuration class with common settings and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    @classmethod
    def load_config(cls, **kwargs: Any) -> "BaseConfig":
        """Load configuration with validation and logging.

        Args:
            **kwargs: Override configuration values

        Returns:
            Validated configuration instance
        """
        try:
            config = cls(**kwargs)
            logger.info(f"Loaded {cls.__name__} configuration successfully")
            return config
        except Exception as e:
            logger.error(f"Failed to load {cls.__name__} configuration", error=str(e))
            raise


class SecurityMixin:
    """Mixin for security-related validation."""

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate SECRET_KEY meets security requirements."""
        if not v:
            raise ValueError("SECRET_KEY must be set. Generate one with: openssl rand -hex 32")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v


class DatabaseMixin:
    """Mixin for database-related validation."""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate DATABASE_URL is properly formatted."""
        if not v:
            raise ValueError("DATABASE_URL must be set")
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL")
        return v


class NetworkMixin:
    """Mixin for network-related validation."""

    @field_validator("timeout", mode="before", check_fields=False)
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout values."""
        if v <= 0:
            raise ValueError("timeout must be greater than 0")
        if v > 300:  # 5 minutes max
            raise ValueError("timeout must be <= 300 seconds")
        return v

    @field_validator("max_concurrent", mode="before", check_fields=False)
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Validate concurrency limits."""
        if v <= 0:
            raise ValueError("max_concurrent must be greater than 0")
        if v > 100:  # Reasonable upper limit
            raise ValueError("max_concurrent must be <= 100")
        return v
