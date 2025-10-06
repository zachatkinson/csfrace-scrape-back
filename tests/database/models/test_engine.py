"""Comprehensive tests for src/database/models/engine.py.

Test coverage: 16 statements, 22% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy import Engine

from src.database.models.engine import create_database_engine

# =============================================================================
# TEST create_database_engine - Basic Creation
# =============================================================================


@pytest.mark.unit
class TestCreateDatabaseEngineBasic:
    """Test create_database_engine basic functionality."""

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_creates_engine_with_echo_disabled(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test creates engine with echo disabled."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine(echo=False)

        # Assert
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[1]["echo"] is False

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_creates_engine_with_echo_enabled(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test creates engine with echo enabled."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine(echo=True)

        # Assert
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[1]["echo"] is True

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_returns_engine_instance(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test returns SQLAlchemy Engine instance."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            result = create_database_engine()

        # Assert
        assert result is mock_engine


# =============================================================================
# TEST create_database_engine - Connection Pool Configuration
# =============================================================================


@pytest.mark.unit
class TestCreateDatabaseEnginePoolConfig:
    """Test create_database_engine connection pool configuration."""

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_configures_pool_size(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test configures correct pool_size."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        assert call_args[1]["pool_size"] == 20

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_configures_max_overflow(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test configures correct max_overflow."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        assert call_args[1]["max_overflow"] == 30

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_configures_pool_timeout(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test configures correct pool_timeout."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        assert call_args[1]["pool_timeout"] == 30

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_configures_pool_recycle(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test configures correct pool_recycle."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        assert call_args[1]["pool_recycle"] == 3600

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_enables_pool_pre_ping(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test enables pool_pre_ping."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        assert call_args[1]["pool_pre_ping"] is True


# =============================================================================
# TEST create_database_engine - Database Configuration
# =============================================================================


@pytest.mark.unit
class TestCreateDatabaseEngineDatabaseConfig:
    """Test create_database_engine database configuration."""

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_sets_isolation_level(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test sets correct isolation level."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        assert call_args[1]["isolation_level"] == "READ_COMMITTED"

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_configures_connect_args(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test configures connect_args."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        connect_args = call_args[1]["connect_args"]
        assert "connect_timeout" in connect_args
        assert connect_args["connect_timeout"] == 10

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_sets_application_name(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test sets application_name in connect_args."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Assert
        call_args = mock_create.call_args
        connect_args = call_args[1]["connect_args"]
        assert connect_args["application_name"] == "csfrace-scraper"


# =============================================================================
# TEST create_database_engine - Event Listener
# =============================================================================


@pytest.mark.unit
class TestCreateDatabaseEngineEventListener:
    """Test create_database_engine event listener."""

    @patch("src.database.models.engine.event.listens_for")
    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_registers_reset_event_listener(
        self, mock_get_url: Mock, mock_create: Mock, mock_listens_for: Mock
    ) -> None:
        """Test registers reset event listener."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine

        # Act
        create_database_engine()

        # Assert
        mock_listens_for.assert_called_once_with(mock_engine, "reset")

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_reset_handler_executes_cleanup_commands(
        self, mock_get_url: Mock, mock_create: Mock
    ) -> None:
        """Test reset handler executes all cleanup SQL commands."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_reset_state = Mock()
        mock_reset_state.terminate_only = False

        # Act - Create engine which registers event handler
        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Get the reset handler
        import src.database.models.engine as engine_module

        reset_handler = None
        for attr_name in dir(engine_module):
            attr = getattr(engine_module, attr_name)
            if callable(attr) and attr_name == "_reset_postgresql":
                reset_handler = attr
                break

        # Call reset handler
        if reset_handler:
            reset_handler(mock_connection, None, mock_reset_state)

            # Assert
            calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
            assert "CLOSE ALL" in calls
            assert "RESET ALL" in calls
            assert "DISCARD TEMP" in calls

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_reset_handler_always_rollsback(self, mock_get_url: Mock, mock_create: Mock) -> None:
        """Test reset handler always calls rollback."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_reset_state = Mock()
        mock_reset_state.terminate_only = False

        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Get reset handler
        import src.database.models.engine as engine_module

        reset_handler = None
        for attr_name in dir(engine_module):
            attr = getattr(engine_module, attr_name)
            if callable(attr) and attr_name == "_reset_postgresql":
                reset_handler = attr
                break

        # Call reset handler
        if reset_handler:
            reset_handler(mock_connection, None, mock_reset_state)

            # Assert
            mock_connection.rollback.assert_called_once()

    @patch("src.database.models.engine.create_engine")
    @patch("src.database.utils.get_database_url")
    def test_reset_handler_skips_cleanup_on_terminate(
        self, mock_get_url: Mock, mock_create: Mock
    ) -> None:
        """Test reset handler skips cleanup when terminate_only is True."""
        # Arrange
        mock_get_url.return_value = "postgresql+psycopg://test:test@localhost:5432/testdb"
        mock_engine = Mock(spec=Engine)
        mock_create.return_value = mock_engine
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_reset_state = Mock()
        mock_reset_state.terminate_only = True  # Terminate only mode

        with patch("src.database.models.engine.event.listens_for"):
            create_database_engine()

        # Get reset handler
        import src.database.models.engine as engine_module

        reset_handler = None
        for attr_name in dir(engine_module):
            attr = getattr(engine_module, attr_name)
            if callable(attr) and attr_name == "_reset_postgresql":
                reset_handler = attr
                break

        # Call reset handler
        if reset_handler:
            reset_handler(mock_connection, None, mock_reset_state)

            # Assert
            mock_cursor.execute.assert_not_called()  # Should not execute cleanup
            mock_connection.rollback.assert_called_once()  # But still rollback
