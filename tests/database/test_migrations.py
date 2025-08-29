"""Tests for database migration management."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from src.database.migrations import MigrationManager


class TestMigrationManager:
    """Test MigrationManager functionality."""

    def test_migration_manager_initialization(self):
        """Test MigrationManager initialization."""
        manager = MigrationManager()

        assert manager.config_file == Path("alembic.ini")
        assert manager.config is not None

        # Test that PostgreSQL database URL is configured (production standard)
        db_url = manager.config.get_main_option("sqlalchemy.url")
        assert db_url is not None
        assert len(db_url) > 0
        # Verify it's PostgreSQL URL format
        assert db_url.startswith("postgresql")

    def test_migration_manager_custom_config(self):
        """Test MigrationManager with custom config file."""
        with TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_alembic.ini"

            # Create minimal alembic.ini
            config_content = """[alembic]
script_location = alembic
sqlalchemy.url = postgresql+psycopg://test_user:test_password@localhost:5432/test_db
"""
            config_file.write_text(config_content)

            manager = MigrationManager(config_file=config_file)
            assert manager.config_file == config_file

    def test_migration_manager_missing_config(self):
        """Test MigrationManager with missing config file."""
        nonexistent_file = Path("/nonexistent/alembic.ini")

        with pytest.raises(FileNotFoundError):
            MigrationManager(config_file=nonexistent_file)

    def test_is_initialized(self):
        """Test is_initialized method."""
        manager = MigrationManager()

        # Should return True if alembic directory exists
        result = manager.is_initialized()

        # Check that the method works (actual result depends on test environment)
        assert isinstance(result, bool)

    @patch("src.database.migrations.command")
    def test_create_migration_autogenerate(self, mock_command):
        """Test creating migration with autogenerate."""
        mock_command.revision.return_value = None

        manager = MigrationManager()
        result = manager.create_migration("Test migration", autogenerate=True)

        mock_command.revision.assert_called_once_with(
            manager.config,
            message="Test migration",
            autogenerate=True,
        )
        assert result == "Test migration"

    @patch("src.database.migrations.command")
    def test_create_migration_empty(self, mock_command):
        """Test creating empty migration."""
        mock_command.revision.return_value = None

        manager = MigrationManager()
        result = manager.create_migration("Test migration", autogenerate=False)

        mock_command.revision.assert_called_once_with(
            manager.config,
            message="Test migration",
        )
        assert result == "Test migration"

    @patch("src.database.migrations.command")
    def test_create_migration_error(self, mock_command):
        """Test migration creation error handling."""
        mock_command.revision.side_effect = Exception("Migration failed")

        manager = MigrationManager()

        with pytest.raises(Exception) as exc_info:
            manager.create_migration("Test migration")

        assert str(exc_info.value) == "Migration failed"

    @patch("src.database.migrations.command")
    def test_upgrade_database(self, mock_command):
        """Test database upgrade."""
        mock_command.upgrade.return_value = None

        manager = MigrationManager()
        manager.upgrade_database()

        mock_command.upgrade.assert_called_once_with(manager.config, "head")

    @patch("src.database.migrations.command")
    def test_upgrade_database_specific_revision(self, mock_command):
        """Test database upgrade to specific revision."""
        mock_command.upgrade.return_value = None

        manager = MigrationManager()
        manager.upgrade_database("abc123")

        mock_command.upgrade.assert_called_once_with(manager.config, "abc123")

    @patch("src.database.migrations.command")
    def test_upgrade_database_error(self, mock_command):
        """Test database upgrade error handling."""
        mock_command.upgrade.side_effect = Exception("Upgrade failed")

        manager = MigrationManager()

        with pytest.raises(Exception) as exc_info:
            manager.upgrade_database()

        assert str(exc_info.value) == "Upgrade failed"

    @patch("src.database.migrations.command")
    def test_downgrade_database(self, mock_command):
        """Test database downgrade."""
        mock_command.downgrade.return_value = None

        manager = MigrationManager()
        manager.downgrade_database("abc123")

        mock_command.downgrade.assert_called_once_with(manager.config, "abc123")

    @patch("src.database.migrations.command")
    def test_downgrade_database_error(self, mock_command):
        """Test database downgrade error handling."""
        mock_command.downgrade.side_effect = Exception("Downgrade failed")

        manager = MigrationManager()

        with pytest.raises(Exception) as exc_info:
            manager.downgrade_database("abc123")

        assert str(exc_info.value) == "Downgrade failed"

    @patch("src.database.migrations.create_engine")
    @patch("src.database.migrations.MigrationContext")
    def test_get_current_revision(self, mock_context, mock_engine):
        """Test getting current database revision."""
        mock_connection = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_connection

        mock_migration_ctx = MagicMock()
        mock_migration_ctx.get_current_revision.return_value = "abc123"
        mock_context.configure.return_value = mock_migration_ctx

        manager = MigrationManager()
        result = manager.get_current_revision()

        assert result == "abc123"
        mock_engine.assert_called_once()

    @patch("src.database.migrations.create_engine")
    def test_get_current_revision_error(self, mock_engine):
        """Test get current revision error handling."""
        mock_engine.side_effect = Exception("Database connection failed")

        manager = MigrationManager()
        result = manager.get_current_revision()

        assert result is None

    @patch("src.database.migrations.ScriptDirectory")
    def test_get_migration_history(self, mock_script_dir):
        """Test getting migration history."""
        mock_revision1 = MagicMock()
        mock_revision1.revision = "abc123"
        mock_revision1.doc = "Initial migration"

        mock_revision2 = MagicMock()
        mock_revision2.revision = "def456"
        mock_revision2.doc = "Add new table"

        mock_script_dir.from_config.return_value.walk_revisions.return_value = [
            mock_revision1,
            mock_revision2,
        ]

        manager = MigrationManager()
        result = manager.get_migration_history()

        expected = ["abc123: Initial migration", "def456: Add new table"]
        assert result == expected

    @patch("src.database.migrations.ScriptDirectory")
    def test_get_migration_history_error(self, mock_script_dir):
        """Test migration history error handling."""
        mock_script_dir.from_config.side_effect = Exception("Script directory error")

        manager = MigrationManager()
        result = manager.get_migration_history()

        assert result == []

    @patch("src.database.migrations.ScriptDirectory")
    def test_show_current_head(self, mock_script_dir):
        """Test showing current head revision."""
        mock_script_dir.from_config.return_value.get_current_head.return_value = "xyz789"

        manager = MigrationManager()
        result = manager.show_current_head()

        assert result == "xyz789"

    @patch("src.database.migrations.ScriptDirectory")
    def test_show_current_head_error(self, mock_script_dir):
        """Test current head error handling."""
        mock_script_dir.from_config.side_effect = Exception("Head retrieval failed")

        manager = MigrationManager()
        result = manager.show_current_head()

        assert result is None

    def test_ensure_database_current_new_database(self):
        """Test ensuring database is current for new database."""
        manager = MigrationManager()

        with patch.object(manager, "get_current_revision") as mock_current:
            with patch.object(manager, "upgrade_database") as mock_upgrade:
                mock_current.return_value = None

                manager.ensure_database_current()

                mock_upgrade.assert_called_once()

    def test_ensure_database_current_needs_upgrade(self):
        """Test ensuring database is current when upgrade needed."""
        manager = MigrationManager()

        with patch.object(manager, "get_current_revision") as mock_current:
            with patch.object(manager, "show_current_head") as mock_head:
                with patch.object(manager, "upgrade_database") as mock_upgrade:
                    mock_current.return_value = "abc123"
                    mock_head.return_value = "xyz789"

                    manager.ensure_database_current()

                    mock_upgrade.assert_called_once()

    def test_ensure_database_current_up_to_date(self):
        """Test ensuring database is current when already up to date."""
        manager = MigrationManager()

        with patch.object(manager, "get_current_revision") as mock_current:
            with patch.object(manager, "show_current_head") as mock_head:
                with patch.object(manager, "upgrade_database") as mock_upgrade:
                    mock_current.return_value = "xyz789"
                    mock_head.return_value = "xyz789"

                    manager.ensure_database_current()

                    mock_upgrade.assert_not_called()

    def test_ensure_database_current_error(self):
        """Test ensure database current error handling."""
        manager = MigrationManager()

        with patch.object(manager, "get_current_revision") as mock_current:
            mock_current.side_effect = Exception("Database error")

            with pytest.raises(Exception) as exc_info:
                manager.ensure_database_current()

            assert str(exc_info.value) == "Database error"


class TestMigrationManagerIntegration:
    """Integration tests for MigrationManager."""

    def test_manager_with_real_config(self):
        """Test manager with real Alembic config."""
        # This test assumes alembic.ini exists in project root
        try:
            manager = MigrationManager()
            assert manager.config is not None

            # Test that we can get basic config values
            script_location = manager.config.get_main_option("script_location")
            assert script_location is not None

            # Test is_initialized method
            initialized = manager.is_initialized()
            assert isinstance(initialized, bool)

        except FileNotFoundError:
            pytest.skip("Alembic not initialized in test environment")

    def test_database_url_override(self):
        """Test that database URL is correctly configured."""
        try:
            manager = MigrationManager()

            # Get the configured URL
            configured_url = manager.config.get_main_option("sqlalchemy.url")

            # Should be PostgreSQL URL (production standard)
            assert configured_url.startswith("postgresql")
            # Verify it contains expected database components
            assert "scraper" in configured_url

        except FileNotFoundError:
            pytest.skip("Alembic not initialized in test environment")
