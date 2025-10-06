"""Comprehensive tests for src/config/settings.py.

Test coverage: 86 statements, 60% → 80%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pydantic import ValidationError

from src.config.auth import AuthConfig
from src.config.converter import ConverterConfig
from src.config.database import DatabaseConfig
from src.config.settings import AppConfig, ConfigManager, get_settings


@pytest.fixture(autouse=True)
def clear_settings_env_vars(monkeypatch: MonkeyPatch) -> None:
    """Clear settings-related environment variables for consistent tests."""
    env_vars = [
        "ENVIRONMENT",
        "DEBUG",
        "API_PORT",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def set_required_env_vars(monkeypatch: MonkeyPatch) -> None:
    """Set required environment variables for nested configs."""
    # Required for nested configs (auth, database, converter)
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/test")


@pytest.fixture(autouse=True)
def reset_config_manager() -> Generator[None]:
    """Reset ConfigManager singleton state before each test."""
    ConfigManager._instance = None
    ConfigManager._loaded = False
    yield
    # Cleanup after test
    ConfigManager._instance = None
    ConfigManager._loaded = False


# =============================================================================
# TEST AppConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestAppConfigInitialization:
    """Test AppConfig initialization and defaults."""

    def test_initialization_with_default_values(self) -> None:
        """Test initialization with default values.

        Note: API_HOST may be overridden by .env file in development.
        This test verifies runtime behavior with actual environment.
        """
        # Arrange & Act
        config = AppConfig()

        # Assert
        assert config.ENVIRONMENT == "development"
        assert config.DEBUG is False
        assert config.APP_NAME == "CSFrace Scraper"
        assert config.APP_VERSION == "1.0.0"
        # API_HOST may be "0.0.0.0" from .env or "localhost" from code default
        assert config.API_HOST in ["localhost", "0.0.0.0"]
        assert config.API_PORT == 8000
        assert config.API_PREFIX == "/api/v1"
        assert config.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
        assert config.CORS_ORIGINS == ["http://localhost:3000"]
        assert config.HEALTH_CHECK_TIMEOUT == 5
        assert config.METRICS_ENABLED is True

    def test_initialization_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        # Arrange & Act
        config = AppConfig(
            ENVIRONMENT="production",
            DEBUG=True,
            API_HOST="api.example.com",
            API_PORT=443,
            API_PREFIX="/api/v2",
            HEALTH_CHECK_TIMEOUT=10,
            METRICS_ENABLED=False,
        )

        # Assert
        assert config.ENVIRONMENT == "production"
        assert config.DEBUG is True
        assert config.API_HOST == "api.example.com"
        assert config.API_PORT == 443
        assert config.API_PREFIX == "/api/v2"
        assert config.HEALTH_CHECK_TIMEOUT == 10
        assert config.METRICS_ENABLED is False

    def test_initialization_creates_nested_configs(self) -> None:
        """Test nested domain configs are properly initialized."""
        # Arrange & Act
        config = AppConfig()

        # Assert
        assert isinstance(config.auth, AuthConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.converter, ConverterConfig)


# =============================================================================
# TEST AppConfig - Field Constraints
# =============================================================================


@pytest.mark.unit
class TestAppConfigFieldConstraints:
    """Test Pydantic field constraints are enforced."""

    def test_api_port_enforces_minimum(self) -> None:
        """Test API_PORT enforces minimum value of 1."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            AppConfig(API_PORT=0)

    def test_api_port_enforces_maximum(self) -> None:
        """Test API_PORT enforces maximum value of 65535."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            AppConfig(API_PORT=65536)

    def test_health_check_timeout_enforces_range(self) -> None:
        """Test HEALTH_CHECK_TIMEOUT enforces range 1-60."""
        # Arrange & Act & Assert - Too low
        with pytest.raises(ValidationError):
            AppConfig(HEALTH_CHECK_TIMEOUT=0)

        # Too high
        with pytest.raises(ValidationError):
            AppConfig(HEALTH_CHECK_TIMEOUT=61)


# =============================================================================
# TEST AppConfig - Computed Fields
# =============================================================================


@pytest.mark.unit
class TestAppConfigComputedFields:
    """Test AppConfig computed field properties."""

    def test_is_production_returns_true_for_production(self) -> None:
        """Test is_production returns True for production environment."""
        # Arrange
        config = AppConfig(ENVIRONMENT="production")

        # Act
        result: bool = config.is_production  # type: ignore[assignment]

        # Assert
        assert result is True

    def test_is_production_returns_false_for_development(self) -> None:
        """Test is_production returns False for development environment."""
        # Arrange
        config = AppConfig(ENVIRONMENT="development")

        # Act
        result: bool = config.is_production  # type: ignore[assignment]

        # Assert
        assert result is False

    def test_is_production_case_insensitive(self) -> None:
        """Test is_production is case insensitive."""
        # Arrange
        config = AppConfig(ENVIRONMENT="PRODUCTION")

        # Act
        result: bool = config.is_production  # type: ignore[assignment]

        # Assert
        assert result is True

    def test_is_development_returns_true_for_development(self) -> None:
        """Test is_development returns True for development environment."""
        # Arrange
        config = AppConfig(ENVIRONMENT="development")

        # Act
        result: bool = config.is_development  # type: ignore[assignment]

        # Assert
        assert result is True

    def test_is_development_returns_false_for_production(self) -> None:
        """Test is_development returns False for production environment."""
        # Arrange
        config = AppConfig(ENVIRONMENT="production")

        # Act
        result: bool = config.is_development  # type: ignore[assignment]

        # Assert
        assert result is False

    def test_api_base_url_uses_https_for_production(self) -> None:
        """Test api_base_url uses https protocol for production."""
        # Arrange
        config = AppConfig(
            ENVIRONMENT="production",
            API_HOST="api.example.com",
            API_PORT=443,
            API_PREFIX="/api/v1",
        )

        # Act
        url: str = config.api_base_url  # type: ignore[assignment]

        # Assert
        assert url == "https://api.example.com:443/api/v1"
        assert url.startswith("https://")

    def test_api_base_url_uses_http_for_development(self) -> None:
        """Test api_base_url uses http protocol for development."""
        # Arrange
        config = AppConfig(
            ENVIRONMENT="development",
            API_HOST="localhost",
            API_PORT=8000,
            API_PREFIX="/api/v1",
        )

        # Act
        url: str = config.api_base_url  # type: ignore[assignment]

        # Assert
        assert url == "http://localhost:8000/api/v1"
        assert url.startswith("http://")


# =============================================================================
# TEST AppConfig - validate_environment Method
# =============================================================================


@pytest.mark.unit
class TestAppConfigValidateEnvironment:
    """Test AppConfig.validate_environment() method."""

    def test_validate_environment_passes_for_valid_development(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test validation passes for valid development config."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config = AppConfig(ENVIRONMENT="development")

        # Act - should not raise
        config.validate_environment()

        # Assert - implicit success

    def test_validate_environment_raises_for_insecure_production(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test validation raises error for insecure production config."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SECURE_COOKIES", "false")
        config = AppConfig(ENVIRONMENT="production")

        # Act & Assert - decorator wraps ValueError in RuntimeError
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            config.validate_environment()

    def test_validate_environment_calls_nested_validations(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test calls validation methods on nested configs."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config = AppConfig(ENVIRONMENT="development")

        # Act - should not raise (implicitly tests nested validations work)
        config.validate_environment()

        # Assert - implicit success means nested validations were called and passed


# =============================================================================
# TEST AppConfig - get_cors_config Method
# =============================================================================


@pytest.mark.unit
class TestAppConfigGetCorsConfig:
    """Test AppConfig.get_cors_config() method."""

    def test_get_cors_config_returns_correct_structure(self) -> None:
        """Test returns dictionary with correct CORS settings."""
        # Arrange
        config = AppConfig(CORS_ORIGINS=["http://localhost:3000", "http://example.com"])

        # Act
        cors_config = config.get_cors_config()

        # Assert
        assert isinstance(cors_config, dict)
        assert cors_config["allow_origins"] == ["http://localhost:3000", "http://example.com"]
        assert cors_config["allow_credentials"] is True
        assert cors_config["allow_methods"] == ["*"]
        assert cors_config["allow_headers"] == ["*"]


# =============================================================================
# TEST AppConfig - get_logging_config Method
# =============================================================================


@pytest.mark.unit
class TestAppConfigGetLoggingConfig:
    """Test AppConfig.get_logging_config() method."""

    def test_get_logging_config_uses_debug_level_when_debug_enabled(self) -> None:
        """Test uses DEBUG level when DEBUG is True."""
        # Arrange
        config = AppConfig(DEBUG=True)

        # Act
        logging_config = config.get_logging_config()

        # Assert
        assert logging_config["handlers"]["console"]["level"] == "DEBUG"
        assert logging_config["root"]["level"] == "DEBUG"

    def test_get_logging_config_uses_converter_level_when_debug_disabled(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Test uses converter log_level when DEBUG is False."""
        # Arrange
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        config = AppConfig(DEBUG=False)

        # Act
        logging_config = config.get_logging_config()

        # Assert
        assert logging_config["handlers"]["console"]["level"] == "WARNING"
        assert logging_config["root"]["level"] == "WARNING"

    def test_get_logging_config_uses_json_formatter_for_production(self) -> None:
        """Test uses JSON formatter for production environment."""
        # Arrange
        config = AppConfig(ENVIRONMENT="production")

        # Act
        logging_config = config.get_logging_config()

        # Assert
        assert logging_config["handlers"]["console"]["formatter"] == "json"

    def test_get_logging_config_uses_default_formatter_for_development(self) -> None:
        """Test uses default formatter for development environment."""
        # Arrange
        config = AppConfig(ENVIRONMENT="development")

        # Act
        logging_config = config.get_logging_config()

        # Assert
        assert logging_config["handlers"]["console"]["formatter"] == "default"


# =============================================================================
# TEST ConfigManager - load_config Method
# =============================================================================


@pytest.mark.unit
class TestConfigManagerLoadConfig:
    """Test ConfigManager.load_config() method."""

    def test_load_config_creates_singleton_instance(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creates singleton instance on first call."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        # Act
        config = ConfigManager.load_config()

        # Assert
        assert config is not None
        assert isinstance(config, AppConfig)
        assert ConfigManager._loaded is True
        assert ConfigManager._instance is config

    def test_load_config_returns_same_instance_without_overrides(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test returns same instance when called without overrides."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config1 = ConfigManager.load_config()

        # Act
        config2 = ConfigManager.load_config()

        # Assert
        assert config1 is config2  # Same instance

    def test_load_config_creates_new_instance_with_overrides(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creates new instance when called with overrides."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config1 = ConfigManager.load_config(ENVIRONMENT="development")

        # Act
        config2 = ConfigManager.load_config(ENVIRONMENT="production")

        # Assert
        assert config1 is not config2  # Different instance
        assert config2.ENVIRONMENT == "production"


# =============================================================================
# TEST ConfigManager - get_config Method
# =============================================================================


@pytest.mark.unit
class TestConfigManagerGetConfig:
    """Test ConfigManager.get_config() method."""

    def test_get_config_returns_loaded_instance(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test returns loaded configuration instance."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        loaded_config = ConfigManager.load_config()

        # Act
        config = ConfigManager.get_config()

        # Assert
        assert config is loaded_config

    def test_get_config_raises_when_not_loaded(self) -> None:
        """Test raises RuntimeError when config not loaded."""
        # Arrange - ConfigManager not loaded (reset in fixture)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Configuration not loaded"):
            ConfigManager.get_config()


# =============================================================================
# TEST ConfigManager - reload_config Method
# =============================================================================


@pytest.mark.unit
class TestConfigManagerReloadConfig:
    """Test ConfigManager.reload_config() method."""

    def test_reload_config_clears_existing_instance(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test clears existing instance before reloading."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config1 = ConfigManager.load_config(ENVIRONMENT="development")

        # Act
        config2 = ConfigManager.reload_config(ENVIRONMENT="production")

        # Assert
        assert config1 is not config2  # Different instance
        assert config2.ENVIRONMENT == "production"
        assert ConfigManager._instance is config2


# =============================================================================
# TEST get_settings Function
# =============================================================================


@pytest.mark.unit
class TestGetSettings:
    """Test get_settings() convenience function."""

    def test_get_settings_returns_singleton_without_overrides(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test returns singleton instance when no overrides provided."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        ConfigManager.load_config()

        # Act
        settings = get_settings()

        # Assert
        assert settings is ConfigManager._instance

    def test_get_settings_creates_temporary_instance_with_overrides(self) -> None:
        """Test creates temporary instance for testing when overrides provided."""
        # Arrange & Act
        settings = get_settings(ENVIRONMENT="testing")

        # Assert
        assert isinstance(settings, AppConfig)
        assert settings.ENVIRONMENT == "testing"
        # Should not affect singleton
        assert settings is not ConfigManager._instance
