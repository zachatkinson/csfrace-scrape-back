"""Database configuration settings.

This module provides database connection and performance configuration
following modern best practices.
"""

from typing import Any

from pydantic import Field, field_validator

from src.core.logging_hierarchy import get_core_logger

from .base import BaseConfig, DatabaseMixin

logger = get_core_logger()


class DatabaseConfig(BaseConfig, DatabaseMixin):
    """Database configuration with connection pooling and performance settings."""

    # Connection settings
    DATABASE_URL: str = Field(..., description="PostgreSQL database connection URL")

    # Connection pool settings - optimized for concurrent scraping
    pool_size: int = Field(20, ge=1, le=100, description="Base connection pool size")
    max_overflow: int = Field(30, ge=0, le=100, description="Max overflow connections")
    pool_timeout: int = Field(30, ge=1, le=300, description="Pool timeout in seconds")
    pool_recycle: int = Field(3600, ge=300, le=86400, description="Pool recycle time in seconds")
    pool_pre_ping: bool = Field(True, description="Validate connections before use")

    # Query settings
    isolation_level: str = Field("READ_COMMITTED", description="Transaction isolation level")
    echo_sql: bool = Field(False, description="Echo SQL statements for debugging")

    # Connection timeouts
    connect_timeout: int = Field(10, ge=1, le=60, description="Connection timeout in seconds")
    query_timeout: int = Field(30, ge=1, le=300, description="Query timeout in seconds")

    # Application settings
    application_name: str = Field("csfrace-scraper", description="Application name for monitoring")

    # Migration settings
    auto_migrate: bool = Field(True, description="Automatically run migrations on startup")
    create_tables: bool = Field(True, description="Create tables if they don't exist")

    # Monitoring and logging
    log_slow_queries: bool = Field(True, description="Log slow queries")
    slow_query_threshold: float = Field(
        2.0, ge=0.1, le=60.0, description="Slow query threshold in seconds"
    )

    @field_validator("isolation_level", mode="before")
    @classmethod
    def validate_isolation_level(cls, v: str) -> str:
        """Validate transaction isolation level."""
        valid_levels = {"READ_UNCOMMITTED", "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"isolation_level must be one of {valid_levels}")
        return v_upper

    @field_validator("pool_size", "max_overflow", mode="before")
    @classmethod
    def validate_pool_settings(cls, v: int) -> int:
        """Validate pool size settings."""
        if v < 0:
            raise ValueError("Pool setting cannot be negative")
        return v

    def get_engine_kwargs(self) -> dict[str, Any]:
        """Get SQLAlchemy engine configuration kwargs."""
        return {
            "echo": self.echo_sql,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "isolation_level": self.isolation_level,
            "connect_args": {
                "connect_timeout": self.connect_timeout,
                "application_name": self.application_name,
            },
        }

    def get_connection_info(self) -> dict[str, Any]:
        """Get sanitized connection info for logging (no passwords)."""
        # Parse DATABASE_URL safely for logging
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self.DATABASE_URL)
            return {
                "host": parsed.hostname,
                "port": parsed.port,
                "database": parsed.path.lstrip("/") if parsed.path else None,
                "username": parsed.username,
                "application_name": self.application_name,
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
            }
        except Exception as e:
            logger.warning(f"Could not parse DATABASE_URL for logging: {e}")
            return {"application_name": self.application_name}

    def validate_connection_url(self) -> None:
        """Validate database connection URL format and connectivity."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")

        # Basic URL format validation
        if not self.DATABASE_URL.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL")

        # Log connection info (without password)
        conn_info = self.get_connection_info()
        logger.info("Database configuration loaded", **conn_info)
