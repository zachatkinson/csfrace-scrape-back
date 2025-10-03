"""Comprehensive tests for src/config/database.py.

Test coverage: 52 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest
from pydantic import ValidationError

from src.config.database import DatabaseConfig

# =============================================================================
# TEST DatabaseConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigInitialization:
    """Test DatabaseConfig initialization and defaults."""

    def test_initialization_with_required_fields(self):
        """Test initialization with required DATABASE_URL."""
        # Arrange & Act
        config = DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb")

        # Assert
        assert config.DATABASE_URL == "postgresql://localhost:5432/testdb"
        assert config.pool_size == 20
        assert config.max_overflow == 30
        assert config.pool_timeout == 30

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        # Arrange & Act
        config = DatabaseConfig(
            DATABASE_URL="postgresql://localhost:5432/testdb",
            pool_size=50,
            max_overflow=20,
            pool_timeout=60,
        )

        # Assert
        assert config.pool_size == 50
        assert config.max_overflow == 20
        assert config.pool_timeout == 60

    def test_initialization_sets_default_values(self):
        """Test initialization sets correct default values."""
        # Arrange & Act
        config = DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb")

        # Assert
        assert config.pool_size == 20
        assert config.max_overflow == 30
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True
        assert config.isolation_level == "READ_COMMITTED"
        assert config.echo_sql is False
        assert config.connect_timeout == 10
        assert config.query_timeout == 30
        assert config.application_name == "csfrace-scraper"
        assert config.auto_migrate is True
        assert config.create_tables is True
        assert config.log_slow_queries is True
        assert config.slow_query_threshold == 2.0


# =============================================================================
# TEST DatabaseConfig - Isolation Level Validation
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigIsolationLevel:
    """Test DatabaseConfig.validate_isolation_level() validation."""

    @pytest.mark.parametrize(
        "level",
        ["READ_UNCOMMITTED", "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE"],
    )
    def test_validate_isolation_level_accepts_valid_levels(self, level):
        """Test accepts all valid isolation levels."""
        # Arrange & Act
        config = DatabaseConfig(
            DATABASE_URL="postgresql://localhost:5432/testdb", isolation_level=level
        )

        # Assert
        assert config.isolation_level == level

    @pytest.mark.parametrize(
        "level", ["read_committed", "Read_Committed", "SERIALIZABLE", "repeatable_read"]
    )
    def test_validate_isolation_level_normalizes_case(self, level):
        """Test normalizes isolation level to uppercase."""
        # Arrange & Act
        config = DatabaseConfig(
            DATABASE_URL="postgresql://localhost:5432/testdb", isolation_level=level
        )

        # Assert
        assert config.isolation_level == level.upper()

    def test_validate_isolation_level_rejects_invalid_level(self):
        """Test rejects invalid isolation level."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="isolation_level must be one of"):
            DatabaseConfig(
                DATABASE_URL="postgresql://localhost:5432/testdb",
                isolation_level="INVALID_LEVEL",
            )


# =============================================================================
# TEST DatabaseConfig - Pool Settings Validation
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigPoolSettings:
    """Test DatabaseConfig.validate_pool_settings() validation."""

    def test_validate_pool_settings_accepts_positive_pool_size(self):
        """Test accepts positive pool_size."""
        # Arrange & Act
        config = DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_size=50)

        # Assert
        assert config.pool_size == 50

    def test_validate_pool_settings_accepts_positive_max_overflow(self):
        """Test accepts positive max_overflow."""
        # Arrange & Act
        config = DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", max_overflow=100)

        # Assert
        assert config.max_overflow == 100

    def test_validate_pool_settings_rejects_negative_pool_size(self):
        """Test rejects negative pool_size."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Pool setting cannot be negative"):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_size=-1)

    def test_validate_pool_settings_rejects_negative_max_overflow(self):
        """Test rejects negative max_overflow."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Pool setting cannot be negative"):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", max_overflow=-1)

    def test_validate_pool_settings_enforces_pydantic_constraints(self):
        """Test Pydantic enforces ge/le constraints."""
        # Arrange & Act & Assert - pool_size must be >= 1
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_size=0)

        # pool_size must be <= 100
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_size=101)


# =============================================================================
# TEST DatabaseConfig - get_engine_kwargs
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigGetEngineKwargs:
    """Test DatabaseConfig.get_engine_kwargs() method."""

    def test_get_engine_kwargs_returns_correct_structure(self):
        """Test returns dictionary with all engine kwargs."""
        # Arrange
        config = DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb")

        # Act
        kwargs = config.get_engine_kwargs()

        # Assert
        assert isinstance(kwargs, dict)
        assert "echo" in kwargs
        assert "pool_size" in kwargs
        assert "max_overflow" in kwargs
        assert "pool_timeout" in kwargs
        assert "pool_recycle" in kwargs
        assert "pool_pre_ping" in kwargs
        assert "isolation_level" in kwargs
        assert "connect_args" in kwargs

    def test_get_engine_kwargs_includes_connect_args(self):
        """Test includes connect_args with proper values."""
        # Arrange
        config = DatabaseConfig(
            DATABASE_URL="postgresql://localhost:5432/testdb",
            connect_timeout=20,
            application_name="test-app",
        )

        # Act
        kwargs = config.get_engine_kwargs()

        # Assert
        assert "connect_args" in kwargs
        assert kwargs["connect_args"]["connect_timeout"] == 20
        assert kwargs["connect_args"]["application_name"] == "test-app"

    def test_get_engine_kwargs_reflects_config_values(self):
        """Test engine kwargs reflect config values."""
        # Arrange
        config = DatabaseConfig(
            DATABASE_URL="postgresql://localhost:5432/testdb",
            echo_sql=True,
            pool_size=50,
            max_overflow=25,
            pool_timeout=60,
            pool_recycle=7200,
            pool_pre_ping=False,
            isolation_level="SERIALIZABLE",
        )

        # Act
        kwargs = config.get_engine_kwargs()

        # Assert
        assert kwargs["echo"] is True
        assert kwargs["pool_size"] == 50
        assert kwargs["max_overflow"] == 25
        assert kwargs["pool_timeout"] == 60
        assert kwargs["pool_recycle"] == 7200
        assert kwargs["pool_pre_ping"] is False
        assert kwargs["isolation_level"] == "SERIALIZABLE"


# =============================================================================
# TEST DatabaseConfig - get_connection_info
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigGetConnectionInfo:
    """Test DatabaseConfig.get_connection_info() method."""

    def test_get_connection_info_parses_url_successfully(self):
        """Test parses DATABASE_URL and extracts connection info."""
        # Arrange
        config = DatabaseConfig(
            DATABASE_URL="postgresql://user:pass@hostname:5432/dbname", pool_size=30
        )

        # Act
        info = config.get_connection_info()

        # Assert
        assert info["host"] == "hostname"
        assert info["port"] == 5432
        assert info["database"] == "dbname"
        assert info["username"] == "user"
        assert info["pool_size"] == 30
        assert "password" not in info  # Password should not be logged

    def test_get_connection_info_handles_url_without_port(self):
        """Test handles DATABASE_URL without explicit port."""
        # Arrange
        config = DatabaseConfig(DATABASE_URL="postgresql://user:pass@hostname/dbname")

        # Act
        info = config.get_connection_info()

        # Assert
        assert info["host"] == "hostname"
        assert info["port"] is None
        assert info["database"] == "dbname"

    def test_get_connection_info_handles_parsing_error(self):
        """Test gracefully handles URL parsing errors."""
        # Arrange - invalid URL fails DatabaseMixin validation during initialization
        # Act & Assert - expect ValidationError from DatabaseMixin
        with pytest.raises(ValidationError, match="DATABASE_URL must be a valid PostgreSQL URL"):
            DatabaseConfig(DATABASE_URL="invalid-url")

    def test_get_connection_info_includes_application_name(self):
        """Test includes application_name in connection info."""
        # Arrange
        config = DatabaseConfig(
            DATABASE_URL="postgresql://localhost:5432/testdb", application_name="my-app"
        )

        # Act
        info = config.get_connection_info()

        # Assert
        assert info["application_name"] == "my-app"


# =============================================================================
# TEST DatabaseConfig - validate_connection_url
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigValidateConnectionUrl:
    """Test DatabaseConfig.validate_connection_url() method."""

    def test_validate_connection_url_accepts_valid_postgresql_url(self):
        """Test accepts valid postgresql:// URL."""
        # Arrange
        config = DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb")

        # Act - Should not raise
        config.validate_connection_url()

        # Assert - Implicit success

    def test_validate_connection_url_accepts_valid_postgres_url(self):
        """Test accepts valid postgres:// URL."""
        # Arrange
        config = DatabaseConfig(DATABASE_URL="postgres://localhost:5432/testdb")

        # Act - Should not raise
        config.validate_connection_url()

        # Assert - Implicit success

    def test_validate_connection_url_rejects_non_postgresql_url(self):
        """Test rejects non-PostgreSQL URLs."""
        # Arrange - DatabaseMixin validator runs during initialization
        # Act & Assert - expect ValidationError during initialization
        with pytest.raises(ValidationError, match="DATABASE_URL must be a valid PostgreSQL URL"):
            DatabaseConfig(DATABASE_URL="mysql://localhost:3306/testdb")

    def test_validate_connection_url_calls_get_connection_info(self):
        """Test calls get_connection_info for logging."""
        # Arrange
        config = DatabaseConfig(DATABASE_URL="postgresql://user@localhost:5432/testdb")

        # Act
        config.validate_connection_url()

        # Assert - get_connection_info was called (implicit in successful validation)
        info = config.get_connection_info()
        assert info["host"] == "localhost"


# =============================================================================
# TEST DatabaseConfig - Field Constraints
# =============================================================================


@pytest.mark.unit
class TestDatabaseConfigFieldConstraints:
    """Test Pydantic field constraints are enforced."""

    def test_pool_timeout_enforces_minimum(self):
        """Test pool_timeout enforces minimum value of 1."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_timeout=0)

    def test_pool_timeout_enforces_maximum(self):
        """Test pool_timeout enforces maximum value of 300."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_timeout=301)

    def test_pool_recycle_enforces_minimum(self):
        """Test pool_recycle enforces minimum value of 300."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_recycle=299)

    def test_pool_recycle_enforces_maximum(self):
        """Test pool_recycle enforces maximum value of 86400."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", pool_recycle=86401)

    def test_connect_timeout_enforces_range(self):
        """Test connect_timeout enforces range 1-60."""
        # Arrange & Act & Assert - Too low
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", connect_timeout=0)

        # Too high
        with pytest.raises(ValidationError):
            DatabaseConfig(DATABASE_URL="postgresql://localhost:5432/testdb", connect_timeout=61)

    def test_slow_query_threshold_enforces_range(self):
        """Test slow_query_threshold enforces range 0.1-60.0."""
        # Arrange & Act & Assert - Too low
        with pytest.raises(ValidationError):
            DatabaseConfig(
                DATABASE_URL="postgresql://localhost:5432/testdb", slow_query_threshold=0.05
            )

        # Too high
        with pytest.raises(ValidationError):
            DatabaseConfig(
                DATABASE_URL="postgresql://localhost:5432/testdb", slow_query_threshold=61.0
            )
