"""Unified configuration system.

This package provides a modern, type-safe configuration system that combines
all domain-specific configurations into a coherent interface.

Features:
- Environment variable support with validation
- Type safety with Pydantic
- Domain separation (auth, database, converter)
- Production-ready defaults
- Comprehensive validation

Usage:
    from src.config import get_settings

    settings = get_settings()

    # Access domain configs
    db_config = settings.database
    auth_config = settings.auth
    converter_config = settings.converter

    # Access unified settings
    api_url = settings.api_base_url
    is_prod = settings.is_production
"""

from .auth import AuthConfig
from .base import BaseConfig, DatabaseMixin, NetworkMixin, SecurityMixin
from .converter import ConverterConfig, HttpConfig, OutputConfig, RobotsConfig, ShopifyConfig
from .database import DatabaseConfig
from .settings import AppConfig, ConfigManager, get_settings

# Default settings instance
try:
    config_settings = ConfigManager.get_config()
except RuntimeError:
    # Configuration not loaded yet - this is expected during testing
    config_settings = None  # type: ignore

__all__ = [
    # Main configuration classes
    "AppConfig",
    "AuthConfig",
    "DatabaseConfig",
    "ConverterConfig",
    # Sub-configuration classes
    "HttpConfig",
    "OutputConfig",
    "RobotsConfig",
    "ShopifyConfig",
    # Base classes and mixins
    "BaseConfig",
    "SecurityMixin",
    "DatabaseMixin",
    "NetworkMixin",
    # Configuration management
    "ConfigManager",
    "get_settings",
    "config_settings",
]
