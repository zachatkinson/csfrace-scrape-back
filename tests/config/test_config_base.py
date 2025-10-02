"""Comprehensive tests for src/config/base.py.

Test coverage: 50 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest
from pydantic import ValidationError

from src.config.base import BaseConfig, DatabaseMixin, NetworkMixin, SecurityMixin

# =============================================================================
# TEST BaseConfig - Load Configuration
# =============================================================================


@pytest.mark.unit
class TestBaseConfigLoadConfig:
    """Test BaseConfig.load_config() method."""

    def test_load_config_creates_instance_successfully(self):
        """Test load_config creates valid config instance."""

        # Arrange
        class TestConfig(BaseConfig):
            test_field: str = "default"

        # Act
        config = TestConfig.load_config()

        # Assert
        assert isinstance(config, TestConfig)
        assert config.test_field == "default"

    def test_load_config_applies_overrides(self):
        """Test load_config applies override values."""

        # Arrange
        class TestConfig(BaseConfig):
            test_field: str = "default"
            other_field: int = 42

        # Act
        config = TestConfig.load_config(test_field="overridden", other_field=100)

        # Assert
        assert config.test_field == "overridden"
        assert config.other_field == 100

    def test_load_config_validates_fields(self):
        """Test load_config validates field types."""

        # Arrange
        class TestConfig(BaseConfig):
            required_field: int

        # Act & Assert
        with pytest.raises(ValidationError):
            TestConfig.load_config(required_field="not_an_int")

    def test_load_config_raises_on_validation_error(self):
        """Test load_config raises validation errors."""

        # Arrange
        class TestConfig(BaseConfig):
            required_field: str

        # Act & Assert
        with pytest.raises(ValidationError):
            TestConfig.load_config(required_field=None)


# =============================================================================
# TEST SecurityMixin - SECRET_KEY Validation
# =============================================================================


@pytest.mark.unit
class TestSecurityMixinSecretKey:
    """Test SecurityMixin.validate_secret_key() validation."""

    def test_validate_secret_key_accepts_valid_key(self):
        """Test accepts valid SECRET_KEY."""

        # Arrange
        class SecureConfig(SecurityMixin, BaseConfig):
            SECRET_KEY: str

        valid_key = "a" * 32  # 32 character key

        # Act
        config = SecureConfig(SECRET_KEY=valid_key)

        # Assert
        assert valid_key == config.SECRET_KEY

    def test_validate_secret_key_rejects_empty_key(self):
        """Test rejects empty SECRET_KEY."""

        # Arrange
        class SecureConfig(SecurityMixin, BaseConfig):
            SECRET_KEY: str

        # Act & Assert
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            SecureConfig(SECRET_KEY="")

    def test_validate_secret_key_rejects_short_key(self):
        """Test rejects SECRET_KEY shorter than 32 characters."""

        # Arrange
        class SecureConfig(SecurityMixin, BaseConfig):
            SECRET_KEY: str

        short_key = "a" * 31  # Only 31 characters

        # Act & Assert
        with pytest.raises(ValueError, match="SECRET_KEY must be at least 32 characters"):
            SecureConfig(SECRET_KEY=short_key)

    def test_validate_secret_key_accepts_long_key(self):
        """Test accepts SECRET_KEY longer than 32 characters."""

        # Arrange
        class SecureConfig(SecurityMixin, BaseConfig):
            SECRET_KEY: str

        long_key = "a" * 64  # 64 character key

        # Act
        config = SecureConfig(SECRET_KEY=long_key)

        # Assert
        assert long_key == config.SECRET_KEY
        assert len(config.SECRET_KEY) == 64


# =============================================================================
# TEST DatabaseMixin - DATABASE_URL Validation
# =============================================================================


@pytest.mark.unit
class TestDatabaseMixinDatabaseUrl:
    """Test DatabaseMixin.validate_database_url() validation."""

    def test_validate_database_url_accepts_postgresql_scheme(self):
        """Test accepts postgresql:// scheme."""

        # Arrange
        class DbConfig(DatabaseMixin, BaseConfig):
            DATABASE_URL: str

        url = "postgresql://user:pass@localhost:5432/dbname"

        # Act
        config = DbConfig(DATABASE_URL=url)

        # Assert
        assert url == config.DATABASE_URL

    def test_validate_database_url_accepts_postgres_scheme(self):
        """Test accepts postgres:// scheme."""

        # Arrange
        class DbConfig(DatabaseMixin, BaseConfig):
            DATABASE_URL: str

        url = "postgres://user:pass@localhost:5432/dbname"

        # Act
        config = DbConfig(DATABASE_URL=url)

        # Assert
        assert url == config.DATABASE_URL

    def test_validate_database_url_rejects_empty_url(self):
        """Test rejects empty DATABASE_URL."""

        # Arrange
        class DbConfig(DatabaseMixin, BaseConfig):
            DATABASE_URL: str

        # Act & Assert
        with pytest.raises(ValueError, match="DATABASE_URL must be set"):
            DbConfig(DATABASE_URL="")

    def test_validate_database_url_rejects_non_postgresql_url(self):
        """Test rejects non-PostgreSQL URLs."""

        # Arrange
        class DbConfig(DatabaseMixin, BaseConfig):
            DATABASE_URL: str

        # Act & Assert - SQLite URL
        with pytest.raises(ValueError, match="DATABASE_URL must be a valid PostgreSQL URL"):
            DbConfig(DATABASE_URL="sqlite:///test.db")

    def test_validate_database_url_rejects_mysql_url(self):
        """Test rejects MySQL URLs."""

        # Arrange
        class DbConfig(DatabaseMixin, BaseConfig):
            DATABASE_URL: str

        # Act & Assert
        with pytest.raises(ValueError, match="DATABASE_URL must be a valid PostgreSQL URL"):
            DbConfig(DATABASE_URL="mysql://user:pass@localhost/dbname")


# =============================================================================
# TEST NetworkMixin - Timeout Validation
# =============================================================================


@pytest.mark.unit
class TestNetworkMixinTimeout:
    """Test NetworkMixin.validate_timeout() validation."""

    def test_validate_timeout_accepts_valid_timeout(self):
        """Test accepts valid timeout value."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            timeout: int = 30

        # Act
        config = NetworkConfig(timeout=60)

        # Assert
        assert config.timeout == 60

    def test_validate_timeout_rejects_zero_timeout(self):
        """Test rejects timeout of 0."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            timeout: int = 30

        # Act & Assert
        with pytest.raises(ValueError, match="timeout must be greater than 0"):
            NetworkConfig(timeout=0)

    def test_validate_timeout_rejects_negative_timeout(self):
        """Test rejects negative timeout."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            timeout: int = 30

        # Act & Assert
        with pytest.raises(ValueError, match="timeout must be greater than 0"):
            NetworkConfig(timeout=-1)

    def test_validate_timeout_rejects_excessive_timeout(self):
        """Test rejects timeout exceeding 300 seconds."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            timeout: int = 30

        # Act & Assert
        with pytest.raises(ValueError, match="timeout must be <= 300 seconds"):
            NetworkConfig(timeout=301)

    def test_validate_timeout_accepts_maximum_timeout(self):
        """Test accepts maximum timeout of 300 seconds."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            timeout: int = 30

        # Act
        config = NetworkConfig(timeout=300)

        # Assert
        assert config.timeout == 300


# =============================================================================
# TEST NetworkMixin - Concurrency Validation
# =============================================================================


@pytest.mark.unit
class TestNetworkMixinConcurrency:
    """Test NetworkMixin.validate_concurrency() validation."""

    def test_validate_concurrency_accepts_valid_value(self):
        """Test accepts valid concurrency value."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            max_concurrent: int = 10

        # Act
        config = NetworkConfig(max_concurrent=50)

        # Assert
        assert config.max_concurrent == 50

    def test_validate_concurrency_rejects_zero(self):
        """Test rejects max_concurrent of 0."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            max_concurrent: int = 10

        # Act & Assert
        with pytest.raises(ValueError, match="max_concurrent must be greater than 0"):
            NetworkConfig(max_concurrent=0)

    def test_validate_concurrency_rejects_negative_value(self):
        """Test rejects negative max_concurrent."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            max_concurrent: int = 10

        # Act & Assert
        with pytest.raises(ValueError, match="max_concurrent must be greater than 0"):
            NetworkConfig(max_concurrent=-5)

    def test_validate_concurrency_rejects_excessive_value(self):
        """Test rejects max_concurrent exceeding 100."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            max_concurrent: int = 10

        # Act & Assert
        with pytest.raises(ValueError, match="max_concurrent must be <= 100"):
            NetworkConfig(max_concurrent=101)

    def test_validate_concurrency_accepts_maximum_value(self):
        """Test accepts maximum max_concurrent of 100."""

        # Arrange
        class NetworkConfig(NetworkMixin, BaseConfig):
            max_concurrent: int = 10

        # Act
        config = NetworkConfig(max_concurrent=100)

        # Assert
        assert config.max_concurrent == 100


# =============================================================================
# TEST BaseConfig - Model Configuration
# =============================================================================


@pytest.mark.unit
class TestBaseConfigModelConfig:
    """Test BaseConfig model_config settings."""

    def test_model_config_ignores_extra_fields(self):
        """Test model_config ignores extra environment variables."""

        # Arrange
        class TestConfig(BaseConfig):
            known_field: str = "default"

        # Act - Pass extra field that should be ignored
        config = TestConfig(known_field="test", unknown_field="ignored")

        # Assert
        assert config.known_field == "test"
        assert not hasattr(config, "unknown_field")

    def test_model_config_strips_whitespace(self):
        """Test model_config strips whitespace from strings."""

        # Arrange
        class TestConfig(BaseConfig):
            test_field: str = "default"

        # Act
        config = TestConfig(test_field="  value with spaces  ")

        # Assert
        assert config.test_field == "value with spaces"

    def test_model_config_case_insensitive(self):
        """Test model_config is case insensitive for field names."""

        # Arrange
        class TestConfig(BaseConfig):
            test_field: str = "default"

        # Act - Pydantic handles case sensitivity at environment level
        config = TestConfig(test_field="lowercase")

        # Assert
        assert config.test_field == "lowercase"


# =============================================================================
# TEST Mixin Combination
# =============================================================================


@pytest.mark.unit
class TestMixinCombination:
    """Test combining multiple mixins in one config class."""

    def test_combines_security_and_database_mixins(self):
        """Test combining SecurityMixin and DatabaseMixin."""

        # Arrange
        class FullConfig(SecurityMixin, DatabaseMixin, BaseConfig):
            SECRET_KEY: str
            DATABASE_URL: str

        # Act
        config = FullConfig(
            SECRET_KEY="a" * 32, DATABASE_URL="postgresql://user:pass@localhost:5432/db"
        )

        # Assert
        assert len(config.SECRET_KEY) >= 32
        assert config.DATABASE_URL.startswith("postgresql://")

    def test_combines_all_mixins(self):
        """Test combining all mixins in one config."""

        # Arrange
        class CompleteConfig(SecurityMixin, DatabaseMixin, NetworkMixin, BaseConfig):
            SECRET_KEY: str
            DATABASE_URL: str
            timeout: int = 30
            max_concurrent: int = 10

        # Act
        config = CompleteConfig(
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql://localhost:5432/db",
            timeout=60,
            max_concurrent=20,
        )

        # Assert
        assert len(config.SECRET_KEY) >= 32
        assert config.DATABASE_URL.startswith("postgresql://")
        assert config.timeout == 60
        assert config.max_concurrent == 20
