"""Main application configuration settings.

This module provides the unified configuration system that combines all
domain-specific configurations into a single, coherent interface.
"""

from typing import Any

from pydantic import Field, computed_field

from src.core.decorators import content_processing_error_handler
from src.core.logging_hierarchy import get_core_logger

from .auth import AuthConfig
from .base import BaseConfig
from .converter import ConverterConfig
from .database import DatabaseConfig

logger = get_core_logger()


class AppConfig(BaseConfig):
    """Main application configuration combining all domain configs."""

    # Environment settings
    ENVIRONMENT: str = Field("development", description="Application environment")
    DEBUG: bool = Field(False, description="Debug mode")

    # Application metadata
    APP_NAME: str = Field("CSFrace Scraper", description="Application name")
    APP_VERSION: str = Field("1.0.0", description="Application version")

    # API settings
    API_HOST: str = Field("localhost", description="API host")
    API_PORT: int = Field(8000, ge=1, le=65535, description="API port")
    API_PREFIX: str = Field("/api/v1", description="API prefix")

    # CORS settings
    ALLOWED_HOSTS: list[str] = Field(["localhost", "127.0.0.1"], description="Allowed hosts")
    CORS_ORIGINS: list[str] = Field(["http://localhost:3000"], description="CORS allowed origins")

    # Domain configurations - loaded from environment variables
    auth: AuthConfig = Field(
        default_factory=AuthConfig,
        description="Authentication configuration",
    )
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration",
    )
    converter: ConverterConfig = Field(
        default_factory=ConverterConfig,
        description="Converter configuration",
    )

    # Monitoring and health
    HEALTH_CHECK_TIMEOUT: int = Field(5, ge=1, le=60, description="Health check timeout")
    METRICS_ENABLED: bool = Field(True, description="Enable metrics collection")

    @computed_field
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @computed_field
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"

    @computed_field
    def api_base_url(self) -> str:
        """Get the full API base URL."""
        protocol = "https" if bool(self.is_production) else "http"
        return f"{protocol}://{self.API_HOST}:{self.API_PORT}{self.API_PREFIX}"

    @content_processing_error_handler("validate environment configuration")
    def validate_environment(self) -> None:
        """Validate environment-specific settings."""
        if bool(self.is_production):
            # Production validations
            if self.DEBUG:
                logger.warning("DEBUG mode is enabled in production environment")

            if not self.auth.SECURE_COOKIES:
                raise ValueError("SECURE_COOKIES must be True in production")

            if "localhost" in self.CORS_ORIGINS:
                logger.warning("Localhost in CORS_ORIGINS for production environment")

        # Validate all sub-configurations
        self.database.validate_connection_url()
        self.converter.validate_output_directory()
        logger.info("All configuration validations passed")

    def get_cors_config(self) -> dict[str, Any]:
        """Get CORS configuration for FastAPI."""
        return {
            "allow_origins": self.CORS_ORIGINS,
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }

    def get_logging_config(self) -> dict[str, Any]:
        """Get logging configuration."""
        level = "DEBUG" if self.DEBUG else self.converter.log_level
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
                },
                "json": {
                    "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": "json" if bool(self.is_production) else "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
        }


class ConfigManager:
    """Configuration manager for loading and validating settings."""

    _instance: AppConfig | None = None
    _loaded: bool = False

    @classmethod
    @content_processing_error_handler("load application configuration")
    def load_config(cls, **overrides: Any) -> AppConfig:
        """Load and validate application configuration.

        Args:
            **overrides: Configuration overrides

        Returns:
            Validated AppConfig instance
        """
        if cls._instance is None or overrides:
            cls._instance = AppConfig(**overrides)
            cls._instance.validate_environment()
            cls._loaded = True
            logger.info(
                "Configuration loaded successfully",
                environment=cls._instance.ENVIRONMENT,
                debug=cls._instance.DEBUG,
            )

        return cls._instance

    @classmethod
    def get_config(cls) -> AppConfig:
        """Get current configuration instance.

        Returns:
            Current AppConfig instance

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        if cls._instance is None or not cls._loaded:
            raise RuntimeError("Configuration not loaded. Call ConfigManager.load_config() first.")
        return cls._instance

    @classmethod
    def reload_config(cls, **overrides: Any) -> AppConfig:
        """Reload configuration with new overrides.

        Args:
            **overrides: Configuration overrides

        Returns:
            Reloaded AppConfig instance
        """
        cls._instance = None
        cls._loaded = False
        return cls.load_config(**overrides)


# Convenience function for getting configuration
def get_settings(**overrides: Any) -> AppConfig:
    """Get application settings.

    Args:
        **overrides: Configuration overrides for testing

    Returns:
        AppConfig instance
    """
    if overrides:
        # For testing - create temporary instance
        return AppConfig(**overrides)

    # For normal use - use singleton
    return ConfigManager.get_config()


# Initialize default configuration on import (can be overridden)
@content_processing_error_handler("initialize default configuration")
def _initialize_default_config() -> AppConfig | None:
    """Initialize default configuration with error handling."""
    return ConfigManager.load_config()


try:
    default_settings = _initialize_default_config()
except Exception:
    logger.warning("Could not load default configuration, will initialize on first use")
    default_settings = None

# Export the default settings
settings = default_settings
