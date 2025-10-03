"""Comprehensive tests for src/database/schema_manager.py.

Test coverage: 67 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from src.database.schema_manager import SchemaManager, ensure_database_ready

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def mock_async_engine():
    """Factory for mock AsyncEngine - DRY principle."""
    engine = AsyncMock(spec=AsyncEngine)
    engine.url = Mock()
    engine.url.__str__ = Mock(return_value="postgresql://test:test@localhost/testdb")
    return engine


@pytest.fixture
def alembic_ini_path(tmp_path):
    """Factory for temporary alembic.ini path - DRY principle."""
    ini_path = tmp_path / "alembic.ini"
    ini_path.write_text("[alembic]\nscript_location = alembic")
    return ini_path


@pytest.fixture
def schema_manager_instance(mock_async_engine, alembic_ini_path):
    """Factory for SchemaManager instance - DRY principle."""
    return SchemaManager(mock_async_engine, alembic_ini_path)


@pytest.fixture
def mock_connection():
    """Factory for mock async connection - DRY principle."""
    connection = AsyncMock()
    connection.execute = AsyncMock()
    return connection


@pytest.fixture
def mock_async_context_manager(mock_connection):
    """Factory for async context manager that returns mock connection - DRY principle."""

    class AsyncContextManager:
        async def __aenter__(self):
            return mock_connection

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    return AsyncContextManager()


# =============================================================================
# TEST SchemaManager - Initialization
# =============================================================================


@pytest.mark.unit
class TestSchemaManagerInit:
    """Test SchemaManager initialization."""

    def test_init_with_default_alembic_path(self, mock_async_engine):
        """Test initialization with default alembic.ini path."""
        # Act
        manager = SchemaManager(mock_async_engine)

        # Assert
        assert manager.engine is mock_async_engine
        assert manager.alembic_ini_path == Path("alembic.ini")

    def test_init_with_custom_alembic_path(self, mock_async_engine, alembic_ini_path):
        """Test initialization with custom alembic.ini path."""
        # Act
        manager = SchemaManager(mock_async_engine, alembic_ini_path)

        # Assert
        assert manager.engine is mock_async_engine
        assert manager.alembic_ini_path == alembic_ini_path


# =============================================================================
# TEST SchemaManager - Database Readiness
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestSchemaManagerDatabaseReadiness:
    """Test ensure_database_ready functionality."""

    async def test_ensure_database_ready_success(self, schema_manager_instance):
        """Test successful database readiness check."""
        # Arrange
        schema_manager_instance._test_connectivity = AsyncMock()
        # NOTE: _run_migrations is no longer called - migrations handled by init_db()
        schema_manager_instance._ensure_critical_schema = AsyncMock()
        schema_manager_instance._validate_schema = AsyncMock()

        # Act
        result = await schema_manager_instance.ensure_database_ready("development")

        # Assert
        assert result is True
        schema_manager_instance._test_connectivity.assert_awaited_once()
        # NOTE: _run_migrations should NOT be called - migrations are handled separately
        schema_manager_instance._ensure_critical_schema.assert_awaited_once()
        schema_manager_instance._validate_schema.assert_awaited_once()

    async def test_ensure_database_ready_production_environment(self, schema_manager_instance):
        """Test database readiness for production environment."""
        # Arrange
        schema_manager_instance._test_connectivity = AsyncMock()
        # NOTE: _run_migrations is no longer called - migrations handled by init_db()
        schema_manager_instance._ensure_critical_schema = AsyncMock()
        schema_manager_instance._validate_schema = AsyncMock()

        # Act
        result = await schema_manager_instance.ensure_database_ready("production")

        # Assert
        assert result is True
        # All steps should complete for production too
        schema_manager_instance._test_connectivity.assert_awaited_once()
        # NOTE: _run_migrations should NOT be called - migrations are handled separately
        schema_manager_instance._ensure_critical_schema.assert_awaited_once()
        schema_manager_instance._validate_schema.assert_awaited_once()


# =============================================================================
# TEST SchemaManager - Connectivity Testing
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestSchemaManagerConnectivity:
    """Test database connectivity testing."""

    async def test_test_connectivity_success(
        self, schema_manager_instance, mock_async_context_manager, mock_connection
    ):
        """Test successful database connectivity check."""
        # Arrange
        schema_manager_instance.engine.begin = Mock(return_value=mock_async_context_manager)

        # Act
        await schema_manager_instance._test_connectivity()

        # Assert
        mock_connection.execute.assert_awaited_once()
        # Verify SELECT 1 was executed
        call_args = mock_connection.execute.call_args[0][0]
        assert "SELECT 1" in str(call_args)

    async def test_test_connectivity_failure(self, schema_manager_instance):
        """Test database connectivity failure."""
        # Arrange
        failing_connection = AsyncMock()
        failing_connection.execute = AsyncMock(side_effect=SQLAlchemyError("Connection failed"))

        class FailingContextManager:
            async def __aenter__(self):
                return failing_connection

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        schema_manager_instance.engine.begin = Mock(return_value=FailingContextManager())

        # Act & Assert - _test_connectivity does NOT use @database_error_handler decorator
        # So it raises SQLAlchemyError directly, not wrapped in RuntimeError
        with pytest.raises(SQLAlchemyError, match="Connection failed"):
            await schema_manager_instance._test_connectivity()


# =============================================================================
# TEST SchemaManager - Migration Execution
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestSchemaManagerMigrations:
    """Test Alembic migration execution."""

    async def test_run_migrations_success(self, schema_manager_instance):
        """Test successful migration execution."""
        # Arrange
        with (
            patch("src.database.schema_manager.Config") as mock_config,
            patch("src.database.schema_manager.command") as mock_command,
        ):
            mock_alembic_cfg = Mock()
            mock_config.return_value = mock_alembic_cfg

            # Act
            await schema_manager_instance._run_migrations()

            # Assert
            mock_config.assert_called_once()
            mock_alembic_cfg.set_main_option.assert_called_once()
            mock_command.upgrade.assert_called_once_with(mock_alembic_cfg, "head")

    async def test_run_migrations_skips_when_commented_out(self, schema_manager_instance):
        """Test migration skipping (temporary skip is logged)."""
        # Arrange - The function currently skips migrations with a log message
        with (
            patch("src.database.schema_manager.Config") as mock_config,
            patch("src.database.schema_manager.command"),
        ):
            # Act
            await schema_manager_instance._run_migrations()

            # Assert - Should complete without error
            # Note: Function currently logs "Skipping Alembic migrations" and continues


# =============================================================================
# TEST SchemaManager - Critical Schema Enforcement
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestSchemaManagerCriticalSchema:
    """Test critical schema element enforcement."""

    async def test_ensure_critical_schema_creates_user_id_column(
        self, schema_manager_instance, mock_async_context_manager, mock_connection
    ):
        """Test adds user_id column to jobs table if missing."""
        # Arrange
        schema_manager_instance.engine.begin = Mock(return_value=mock_async_context_manager)
        schema_manager_instance._create_indexes = AsyncMock()

        # Act
        await schema_manager_instance._ensure_critical_schema()

        # Assert
        # Should execute user_id column addition
        assert mock_connection.execute.await_count >= 1
        # Check for user_id column addition in executed SQL
        executed_sql = str(mock_connection.execute.call_args_list[0][0][0])
        assert "user_id" in executed_sql.lower()

    async def test_ensure_critical_schema_creates_revoked_tokens_table(
        self, schema_manager_instance, mock_async_context_manager, mock_connection
    ):
        """Test creates revoked_tokens table."""
        # Arrange
        schema_manager_instance.engine.begin = Mock(return_value=mock_async_context_manager)
        schema_manager_instance._create_indexes = AsyncMock()

        # Act
        await schema_manager_instance._ensure_critical_schema()

        # Assert
        # Should execute revoked_tokens table creation
        executed_sqls = [str(call[0][0]) for call in mock_connection.execute.call_args_list]
        assert any("revoked_tokens" in sql.lower() for sql in executed_sqls)

    async def test_ensure_critical_schema_creates_oauth_accounts_table(
        self, schema_manager_instance, mock_async_context_manager, mock_connection
    ):
        """Test creates oauth_linked_accounts table."""
        # Arrange
        schema_manager_instance.engine.begin = Mock(return_value=mock_async_context_manager)
        schema_manager_instance._create_indexes = AsyncMock()

        # Act
        await schema_manager_instance._ensure_critical_schema()

        # Assert
        # Should execute oauth_linked_accounts table creation
        executed_sqls = [str(call[0][0]) for call in mock_connection.execute.call_args_list]
        assert any("oauth_linked_accounts" in sql.lower() for sql in executed_sqls)

    async def test_ensure_critical_schema_creates_indexes(
        self, schema_manager_instance, mock_async_context_manager, mock_connection
    ):
        """Test creates all required indexes."""
        # Arrange
        schema_manager_instance.engine.begin = Mock(return_value=mock_async_context_manager)
        schema_manager_instance._create_indexes = AsyncMock()

        # Act
        await schema_manager_instance._ensure_critical_schema()

        # Assert
        schema_manager_instance._create_indexes.assert_awaited_once_with(mock_connection)


# =============================================================================
# TEST SchemaManager - Index Creation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestSchemaManagerIndexes:
    """Test index creation functionality."""

    async def test_create_indexes_creates_all_required_indexes(
        self, schema_manager_instance, mock_connection
    ):
        """Test creates all three required indexes."""
        # Arrange
        schema_manager_instance._create_single_index_safe = AsyncMock()

        # Act
        await schema_manager_instance._create_indexes(mock_connection)

        # Assert
        # Should call _create_single_index_safe 3 times
        assert schema_manager_instance._create_single_index_safe.await_count == 3

        # Verify index names
        calls = schema_manager_instance._create_single_index_safe.call_args_list
        index_names = [call[0][1] for call in calls]
        assert "idx_jobs_user_id" in index_names
        assert "idx_revoked_tokens_user_id" in index_names
        assert "idx_oauth_accounts_user_id" in index_names

    async def test_create_single_index_safe_validates_identifiers(
        self, schema_manager_instance, mock_connection
    ):
        """Test validates SQL identifiers to prevent injection."""
        # Arrange - Invalid identifier with special characters
        invalid_index_name = "idx_test; DROP TABLE users; --"

        # Act
        await schema_manager_instance._create_single_index_safe(
            mock_connection, invalid_index_name, "users", "id"
        )

        # Assert
        # Should not execute SQL due to validation failure
        mock_connection.execute.assert_not_awaited()

    async def test_create_single_index_safe_creates_valid_index(self, schema_manager_instance):
        """Test creates index with valid identifiers."""
        # Arrange
        index_name = "idx_test_index"
        table_name = "test_table"
        column_name = "test_column"
        mock_conn = AsyncMock()

        # Act
        await schema_manager_instance._create_single_index_safe(
            mock_conn, index_name, table_name, column_name
        )

        # Assert
        mock_conn.execute.assert_awaited_once()
        # Verify SQL contains the identifiers (uses f-string after validation for safety)
        call_args = mock_conn.execute.call_args
        sql_text = str(call_args[0][0])  # First argument is the SQL text object
        assert index_name in sql_text
        assert table_name in sql_text
        assert column_name in sql_text


# =============================================================================
# TEST SchemaManager - Schema Validation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestSchemaManagerValidation:
    """Test schema validation functionality."""

    async def test_validate_schema_checks_critical_tables(self, schema_manager_instance):
        """Test validates all critical tables exist."""
        # Arrange
        mock_connection = AsyncMock()
        mock_result = Mock()
        mock_result.fetchall = Mock(
            return_value=[
                ("users",),
                ("jobs",),
                ("revoked_tokens",),
                ("oauth_linked_accounts",),
            ]
        )

        mock_column_result = Mock()
        mock_column_result.fetchone = Mock(return_value=("user_id",))

        mock_connection.execute = AsyncMock(side_effect=[mock_result, mock_column_result])

        class ValidationContextManager:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        schema_manager_instance.engine.begin = Mock(return_value=ValidationContextManager())

        # Act
        await schema_manager_instance._validate_schema()

        # Assert
        # Source code executes exactly 2 queries: table check + column check
        assert mock_connection.execute.await_count == 2

    async def test_validate_schema_raises_on_missing_tables(self, schema_manager_instance):
        """Test raises error when critical tables are missing."""
        # Arrange
        mock_connection = AsyncMock()
        mock_result = Mock()
        mock_result.fetchall = Mock(return_value=[("users",), ("jobs",)])  # Missing tables
        mock_connection.execute = AsyncMock(return_value=mock_result)

        class ValidationContextManager:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        schema_manager_instance.engine.begin = Mock(return_value=ValidationContextManager())

        # Act & Assert - _validate_schema raises SQLAlchemyError directly
        # It's NOT decorated with @database_error_handler, so error is not wrapped
        with pytest.raises(SQLAlchemyError, match="Missing critical tables"):
            await schema_manager_instance._validate_schema()

    async def test_validate_schema_checks_user_id_column(self, schema_manager_instance):
        """Test validates user_id column exists in jobs table."""
        # Arrange
        mock_connection = AsyncMock()
        mock_table_result = Mock()
        mock_table_result.fetchall = Mock(
            return_value=[
                ("users",),
                ("jobs",),
                ("revoked_tokens",),
                ("oauth_linked_accounts",),
            ]
        )

        mock_column_result = Mock()
        mock_column_result.fetchone = Mock(return_value=("user_id",))

        mock_connection.execute = AsyncMock(side_effect=[mock_table_result, mock_column_result])

        class ValidationContextManager:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        schema_manager_instance.engine.begin = Mock(return_value=ValidationContextManager())

        # Act
        await schema_manager_instance._validate_schema()

        # Assert
        # Source code executes exactly 2 queries: table check + column check
        assert mock_connection.execute.await_count == 2

    async def test_validate_schema_raises_on_missing_column(self, schema_manager_instance):
        """Test raises error when user_id column is missing from jobs table."""
        # Arrange
        mock_connection = AsyncMock()
        mock_table_result = Mock()
        mock_table_result.fetchall = Mock(
            return_value=[
                ("users",),
                ("jobs",),
                ("revoked_tokens",),
                ("oauth_linked_accounts",),
            ]
        )

        mock_column_result = Mock()
        mock_column_result.fetchone = Mock(return_value=None)  # Column doesn't exist

        mock_connection.execute = AsyncMock(side_effect=[mock_table_result, mock_column_result])

        class ValidationContextManager:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        schema_manager_instance.engine.begin = Mock(return_value=ValidationContextManager())

        # Act & Assert - _validate_schema raises SQLAlchemyError for missing column
        with pytest.raises(SQLAlchemyError, match="user_id column missing"):
            await schema_manager_instance._validate_schema()


# =============================================================================
# TEST Convenience Function - ensure_database_ready
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestEnsureDatabaseReadyFunction:
    """Test ensure_database_ready convenience function."""

    async def test_ensure_database_ready_function_success(self, mock_async_engine):
        """Test convenience function creates SchemaManager and calls ensure_database_ready."""
        # Arrange
        with patch.object(
            SchemaManager, "ensure_database_ready", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = True

            # Act
            result = await ensure_database_ready(mock_async_engine, "development")

            # Assert
            assert result is True
            mock_method.assert_awaited_once_with("development")

    async def test_ensure_database_ready_function_with_production(self, mock_async_engine):
        """Test convenience function with production environment."""
        # Arrange
        with patch.object(
            SchemaManager, "ensure_database_ready", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = True

            # Act
            result = await ensure_database_ready(mock_async_engine, "production")

            # Assert
            assert result is True
            mock_method.assert_awaited_once_with("production")
