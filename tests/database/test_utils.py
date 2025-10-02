"""Comprehensive tests for src/database/utils.py.

Test coverage: 54 statements, 52% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from enum import Enum
from unittest.mock import MagicMock, Mock, patch

import pytest
import sqlalchemy.exc
from sqlalchemy import Connection

from src.database.utils import (
    create_postgresql_enums,
    get_database_url,
    get_standard_enum_definitions,
    test_database_connection as util_test_database_connection,
)

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def mock_connection():
    """Factory for mock SQLAlchemy connection - DRY principle."""
    connection = Mock(spec=Connection)
    connection.execute = Mock()
    return connection


@pytest.fixture
def sample_enum_class():
    """Factory for sample Enum class - DRY principle."""

    class SampleStatus(str, Enum):
        PENDING = "pending"
        COMPLETED = "completed"
        FAILED = "failed"

    return SampleStatus


@pytest.fixture
def sample_enum_definitions(sample_enum_class):
    """Factory for sample enum definitions - DRY principle."""
    return [("sample_status", sample_enum_class)]


@pytest.fixture
def mock_env_vars():
    """Factory for mock environment variables - DRY principle."""
    return {
        "DATABASE_URL": None,
        "DATABASE_HOST": "testhost",
        "DATABASE_PORT": "5433",
        "DATABASE_NAME": "testdb",
        "DATABASE_USER": "testuser",
        "DATABASE_PASSWORD": "testpass",
    }


# =============================================================================
# TEST create_postgresql_enums - Success Cases
# =============================================================================


@pytest.mark.unit
class TestCreatePostgreSQLEnumsSuccess:
    """Test create_postgresql_enums success cases."""

    def test_create_enum_when_not_exists(self, mock_connection, sample_enum_definitions):
        """Test creates enum when it doesn't exist."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=False)  # Enum doesn't exist
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            mock_enum_instance = Mock()
            mock_pg_enum.return_value = mock_enum_instance

            # Act
            create_postgresql_enums(mock_connection, sample_enum_definitions)

        # Assert
        mock_connection.execute.assert_called_once()
        mock_pg_enum.assert_called_once()
        mock_enum_instance.create.assert_called_once_with(mock_connection, checkfirst=True)

    def test_skips_existing_enum(self, mock_connection, sample_enum_definitions):
        """Test skips creating enum when it already exists."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=True)  # Enum exists
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            # Act
            create_postgresql_enums(mock_connection, sample_enum_definitions)

        # Assert
        mock_connection.execute.assert_called_once()
        mock_pg_enum.assert_not_called()  # Should not attempt creation

    def test_handles_multiple_enums(self, mock_connection, sample_enum_class):
        """Test handles multiple enum definitions."""

        # Arrange
        class SecondEnum(str, Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        enum_defs = [("first_enum", sample_enum_class), ("second_enum", SecondEnum)]
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=False)
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            mock_enum_instance = Mock()
            mock_pg_enum.return_value = mock_enum_instance

            # Act
            create_postgresql_enums(mock_connection, enum_defs)

        # Assert
        assert mock_connection.execute.call_count == 2
        assert mock_pg_enum.call_count == 2


# =============================================================================
# TEST create_postgresql_enums - Error Handling
# =============================================================================


@pytest.mark.unit
class TestCreatePostgreSQLEnumsErrors:
    """Test create_postgresql_enums error handling."""

    def test_handles_concurrent_creation_already_exists(
        self, mock_connection, sample_enum_definitions
    ):
        """Test handles concurrent enum creation gracefully."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=False)
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            mock_enum_instance = Mock()
            mock_enum_instance.create.side_effect = sqlalchemy.exc.ProgrammingError(
                "statement", "params", "orig", connection_invalidated=False
            )
            # Mock the error message check
            mock_pg_enum.return_value = mock_enum_instance

            with patch.object(
                sqlalchemy.exc.ProgrammingError, "__str__", return_value="already exists"
            ):
                # Act - should not raise
                create_postgresql_enums(mock_connection, sample_enum_definitions)

    def test_handles_duplicate_key_error(self, mock_connection, sample_enum_definitions):
        """Test handles duplicate key errors gracefully."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=False)
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            mock_enum_instance = Mock()
            error = sqlalchemy.exc.IntegrityError("statement", "params", "orig")
            mock_enum_instance.create.side_effect = error
            mock_pg_enum.return_value = mock_enum_instance

            with patch.object(
                sqlalchemy.exc.IntegrityError, "__str__", return_value="duplicate key"
            ):
                # Act - should not raise
                create_postgresql_enums(mock_connection, sample_enum_definitions)

    def test_handles_unique_constraint_violation(self, mock_connection, sample_enum_definitions):
        """Test handles unique constraint violations gracefully."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=False)
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            mock_enum_instance = Mock()
            error = sqlalchemy.exc.IntegrityError("statement", "params", "orig")
            mock_enum_instance.create.side_effect = error
            mock_pg_enum.return_value = mock_enum_instance

            with patch.object(
                sqlalchemy.exc.IntegrityError, "__str__", return_value="violates unique constraint"
            ):
                # Act - should not raise
                create_postgresql_enums(mock_connection, sample_enum_definitions)

    def test_raises_non_concurrent_errors(self, mock_connection, sample_enum_definitions):
        """Test raises non-concurrent errors."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar = Mock(return_value=False)
        mock_connection.execute = Mock(return_value=mock_result)

        with patch("src.database.utils.PostgreSQLEnum") as mock_pg_enum:
            mock_enum_instance = Mock()
            error = sqlalchemy.exc.ProgrammingError(
                "statement", "params", "orig", connection_invalidated=False
            )
            mock_enum_instance.create.side_effect = error
            mock_pg_enum.return_value = mock_enum_instance

            with patch.object(
                sqlalchemy.exc.ProgrammingError, "__str__", return_value="syntax error"
            ):
                # Act & Assert
                with pytest.raises(sqlalchemy.exc.ProgrammingError):
                    create_postgresql_enums(mock_connection, sample_enum_definitions)


# =============================================================================
# TEST get_standard_enum_definitions
# =============================================================================


@pytest.mark.unit
class TestGetStandardEnumDefinitions:
    """Test get_standard_enum_definitions function."""

    def test_returns_list_of_tuples(self):
        """Test returns list of tuples."""
        # Act
        result = get_standard_enum_definitions()

        # Assert
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)
        assert all(len(item) == 2 for item in result)

    def test_includes_jobstatus_enum(self):
        """Test includes JobStatus enum."""
        # Act
        result = get_standard_enum_definitions()

        # Assert
        enum_names = [name for name, _ in result]
        assert "jobstatus" in enum_names

    def test_includes_jobpriority_when_available(self):
        """Test includes JobPriority enum when available."""
        # Act
        result = get_standard_enum_definitions()

        # Assert
        enum_names = [name for name, _ in result]
        # JobPriority should be included if imported successfully
        assert "jobpriority" in enum_names


# =============================================================================
# TEST get_database_url
# =============================================================================


@pytest.mark.unit
class TestGetDatabaseURL:
    """Test get_database_url function."""

    def test_uses_database_url_env_var_when_set(self, mock_env_vars):
        """Test uses DATABASE_URL environment variable when set."""
        # Arrange
        mock_env_vars["DATABASE_URL"] = "postgresql://user:pass@host:5432/db"

        with patch.dict("os.environ", mock_env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert result == "postgresql+psycopg://user:pass@host:5432/db"

    def test_converts_postgresql_to_psycopg_driver(self):
        """Test converts postgresql:// to postgresql+psycopg://."""
        # Arrange
        env_vars = {"DATABASE_URL": "postgresql://user:pass@host:5432/db"}

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert "postgresql+psycopg://" in result

    def test_builds_url_from_individual_vars(self):
        """Test builds URL from individual environment variables."""
        # Arrange
        env_vars = {
            "DATABASE_HOST": "testhost",
            "DATABASE_PORT": "5433",
            "DATABASE_NAME": "testdb",
            "DATABASE_USER": "testuser",
            "DATABASE_PASSWORD": "testpass",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert result == "postgresql+psycopg://testuser:testpass@testhost:5433/testdb"

    def test_uses_default_host(self):
        """Test uses default host when not set."""
        # Arrange
        env_vars = {
            "DATABASE_NAME": "testdb",
            "DATABASE_USER": "testuser",
            "DATABASE_PASSWORD": "testpass",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert "localhost" in result

    def test_uses_default_port(self):
        """Test uses default port when not set."""
        # Arrange
        env_vars = {
            "DATABASE_HOST": "testhost",
            "DATABASE_NAME": "testdb",
            "DATABASE_USER": "testuser",
            "DATABASE_PASSWORD": "testpass",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert ":5432/" in result

    def test_uses_default_database_name(self):
        """Test uses default database name when not set."""
        # Arrange
        env_vars = {"DATABASE_USER": "testuser", "DATABASE_PASSWORD": "testpass"}

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert "scraper_db" in result

    def test_uses_default_username(self):
        """Test uses default username when not set."""
        # Arrange
        env_vars = {"DATABASE_NAME": "testdb", "DATABASE_PASSWORD": "testpass"}

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert "postgres:" in result

    def test_uses_default_password(self):
        """Test uses default password when not set."""
        # Arrange
        env_vars = {"DATABASE_NAME": "testdb", "DATABASE_USER": "testuser"}

        with patch.dict("os.environ", env_vars, clear=True):
            # Act
            result = get_database_url()

        # Assert
        assert ":postgres@" in result


# =============================================================================
# TEST test_database_connection
# =============================================================================


@pytest.mark.unit
class TestDatabaseConnection:
    """Test test_database_connection function."""

    def test_successful_connection_returns_true(self):
        """Test successful database connection returns True."""
        # Arrange
        mock_engine = Mock()
        mock_connection = MagicMock()
        mock_engine.connect = MagicMock(
            return_value=MagicMock(__enter__=Mock(return_value=mock_connection))
        )

        with (
            patch("src.database.utils.get_database_url", return_value="test://db"),
            patch("sqlalchemy.create_engine", return_value=mock_engine),
        ):
            # Act
            result = util_test_database_connection()

        # Assert
        assert result is True
        mock_connection.execute.assert_called_once()

    def test_failed_connection_raises_exception(self):
        """Test failed database connection raises exception."""
        # Arrange
        with (
            patch("src.database.utils.get_database_url", return_value="test://db"),
            patch("sqlalchemy.create_engine", side_effect=Exception("Connection failed")),
        ):
            # Act & Assert
            with pytest.raises(Exception, match="Connection failed"):
                util_test_database_connection()

    def test_masks_credentials_in_log(self):
        """Test masks credentials in log messages."""
        # Arrange
        mock_engine = Mock()
        mock_connection = MagicMock()
        mock_engine.connect = MagicMock(
            return_value=MagicMock(__enter__=Mock(return_value=mock_connection))
        )

        with (
            patch(
                "src.database.utils.get_database_url",
                return_value="postgresql://user:secret@host/db",
            ),
            patch("sqlalchemy.create_engine", return_value=mock_engine),
            patch("src.database.utils.logger") as mock_logger,
        ):
            # Act
            util_test_database_connection()

        # Assert
        # Verify logger was called and credentials were masked
        assert any("@***" in str(call) for call in mock_logger.info.call_args_list), (
            "Credentials should be masked in logs"
        )
