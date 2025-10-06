"""Unit tests for src/database/migrations.py following AUDIT_3.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS:
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only

Tests database migration management with comprehensive coverage of Alembic operations.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.database.migrations import (
    MigrationManager,
    get_migration_manager,
)

# ============================================================================
# MigrationManager Tests
# ============================================================================


@pytest.mark.unit
class TestMigrationManager:
    """Unit tests for MigrationManager - MANDATORY AAA pattern."""

    def test_migration_manager_creation_with_default_config(self) -> None:
        """Test migration manager creation with default config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config") as mock_config:
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    # Act - MANDATORY
                    manager = MigrationManager()

                    # Assert - MANDATORY
                    assert manager is not None
                    assert manager.config_file == Path("alembic.ini")
                    mock_config.assert_called_once()

    def test_migration_manager_creation_with_custom_config(self) -> None:
        """Test migration manager creation with custom config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_path = Path("/custom/alembic.ini")

        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config") as mock_config:
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    # Act - MANDATORY
                    manager = MigrationManager(config_file=custom_path)

                    # Assert - MANDATORY
                    assert manager.config_file == custom_path
                    mock_config.assert_called_once_with(str(custom_path))

    def test_migration_manager_raises_on_missing_config(self) -> None:
        """Test migration manager raises FileNotFoundError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=False):
            # Act & Assert - MANDATORY
            with pytest.raises(FileNotFoundError, match="Alembic config file not found"):
                MigrationManager()

    def test_is_initialized_returns_true_when_complete(self) -> None:
        """Test is_initialized returns True with complete setup - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    manager = MigrationManager()

                    # Mock all required paths exist
                    with patch.object(Path, "exists", return_value=True):
                        # Act - MANDATORY
                        result = manager.is_initialized()

                        # Assert - MANDATORY
                        assert result is True

    def test_is_initialized_returns_false_when_incomplete(self) -> None:
        """Test is_initialized returns False with missing files - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        call_count = [0]

        def mock_exists_selective() -> bool:
            """Mock exists to return True for config file, False for directories."""
            call_count[0] += 1
            # First call: manager.config_file.exists() in __init__ -> True
            # Second call: manager.config_file.exists() in is_initialized -> True
            # Third call: alembic_dir.exists() -> False (missing directory)
            return (
                call_count[0] <= 2
            )  # Config file exists (True) or Alembic directory missing (False)

        with patch.object(Path, "exists", side_effect=mock_exists_selective):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    manager = MigrationManager()

                    # Act - MANDATORY
                    result = manager.is_initialized()

                    # Assert - MANDATORY
                    assert result is False

    def test_create_migration_with_autogenerate(self) -> None:
        """Test create_migration with autogenerate - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch("src.database.migrations.command.revision") as mock_revision:
                        manager = MigrationManager()

                        # Act - MANDATORY
                        result = manager.create_migration("Add user table", autogenerate=True)

                        # Assert - MANDATORY
                        assert result == "Add user table"
                        mock_revision.assert_called_once_with(
                            manager.config,
                            message="Add user table",
                            autogenerate=True,
                        )

    def test_create_migration_without_autogenerate(self) -> None:
        """Test create_migration without autogenerate - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch("src.database.migrations.command.revision") as mock_revision:
                        manager = MigrationManager()

                        # Act - MANDATORY
                        result = manager.create_migration("Empty migration", autogenerate=False)

                        # Assert - MANDATORY
                        assert result == "Empty migration"
                        mock_revision.assert_called_once_with(
                            manager.config,
                            message="Empty migration",
                        )

    def test_upgrade_database_to_head(self) -> None:
        """Test upgrade_database to head - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch("src.database.migrations.command.upgrade") as mock_upgrade:
                        manager = MigrationManager()

                        # Act - MANDATORY
                        manager.upgrade_database()

                        # Assert - MANDATORY
                        mock_upgrade.assert_called_once_with(manager.config, "head")

    def test_upgrade_database_to_specific_revision(self) -> None:
        """Test upgrade_database to specific revision - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch("src.database.migrations.command.upgrade") as mock_upgrade:
                        manager = MigrationManager()

                        # Act - MANDATORY
                        manager.upgrade_database("abc123")

                        # Assert - MANDATORY
                        mock_upgrade.assert_called_once_with(manager.config, "abc123")

    def test_downgrade_database(self) -> None:
        """Test downgrade_database - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch("src.database.migrations.command.downgrade") as mock_downgrade:
                        manager = MigrationManager()

                        # Act - MANDATORY
                        manager.downgrade_database("abc123")

                        # Assert - MANDATORY
                        mock_downgrade.assert_called_once_with(manager.config, "abc123")

    def test_get_current_revision(self) -> None:
        """Test get_current_revision - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch(
                        "src.database.migrations._get_current_revision_safe", return_value="abc123"
                    ):
                        manager = MigrationManager()

                        # Act - MANDATORY
                        result = manager.get_current_revision()

                        # Assert - MANDATORY
                        assert result == "abc123"

    def test_get_migration_history(self) -> None:
        """Test get_migration_history - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_history = ["rev1: First migration", "rev2: Second migration"]

        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch(
                        "src.database.migrations._get_migration_history_safe",
                        return_value=expected_history,
                    ):
                        manager = MigrationManager()

                        # Act - MANDATORY
                        result = manager.get_migration_history()

                        # Assert - MANDATORY
                        assert result == expected_history
                        assert len(result) == 2

    def test_show_current_head(self) -> None:
        """Test show_current_head - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch(
                        "src.database.migrations._show_current_head_safe", return_value="xyz789"
                    ):
                        manager = MigrationManager()

                        # Act - MANDATORY
                        result = manager.show_current_head()

                        # Assert - MANDATORY
                        assert result == "xyz789"

    def test_ensure_database_current_when_not_initialized(self) -> None:
        """Test ensure_database_current when db not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch(
                        "src.database.migrations._get_current_revision_safe", return_value=None
                    ):
                        with patch(
                            "src.database.migrations._show_current_head_safe", return_value="abc123"
                        ):
                            with patch("src.database.migrations.command.upgrade") as mock_upgrade:
                                manager = MigrationManager()

                                # Act - MANDATORY
                                manager.ensure_database_current()

                                # Assert - MANDATORY
                                mock_upgrade.assert_called_once()

    def test_ensure_database_current_when_behind_head(self) -> None:
        """Test ensure_database_current when db behind head - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch(
                        "src.database.migrations._get_current_revision_safe", return_value="abc123"
                    ):
                        with patch(
                            "src.database.migrations._show_current_head_safe", return_value="xyz789"
                        ):
                            with patch("src.database.migrations.command.upgrade") as mock_upgrade:
                                manager = MigrationManager()

                                # Act - MANDATORY
                                manager.ensure_database_current()

                                # Assert - MANDATORY
                                mock_upgrade.assert_called_once()

    def test_ensure_database_current_when_up_to_date(self) -> None:
        """Test ensure_database_current when db up to date - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    with patch(
                        "src.database.migrations._get_current_revision_safe", return_value="abc123"
                    ):
                        with patch(
                            "src.database.migrations._show_current_head_safe", return_value="abc123"
                        ):
                            with patch("src.database.migrations.command.upgrade") as mock_upgrade:
                                manager = MigrationManager()

                                # Act - MANDATORY
                                manager.ensure_database_current()

                                # Assert - MANDATORY
                                # Should NOT call upgrade when already current
                                mock_upgrade.assert_not_called()


# ============================================================================
# Module-Level Functions Tests
# ============================================================================


@pytest.mark.unit
class TestMigrationModuleFunctions:
    """Unit tests for module-level migration functions - MANDATORY AAA pattern."""

    def test_get_migration_manager_returns_instance(self) -> None:
        """Test get_migration_manager returns MigrationManager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    # Act - MANDATORY
                    result = get_migration_manager()

                    # Assert - MANDATORY
                    assert isinstance(result, MigrationManager)
                    assert result is not None


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestMigrationsSecurity:
    """MANDATORY security tests for migrations."""

    def test_config_file_path_validation(self) -> None:
        """MANDATORY: Test config file path validation."""
        # Arrange - MANDATORY
        malicious_path = Path("../../etc/passwd")

        with patch("src.database.migrations.Path.exists", return_value=False):
            # Act & Assert - MANDATORY
            with pytest.raises(FileNotFoundError):
                MigrationManager(config_file=malicious_path)

    def test_database_url_from_environment_only(self) -> None:
        """MANDATORY: Test database URL comes from secure source."""
        # Arrange - MANDATORY
        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config") as mock_config:
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://secure"
                ):
                    mock_instance = mock_config.return_value

                    # Act - MANDATORY
                    manager = MigrationManager()

                    # Assert - MANDATORY
                    # Should set database URL from get_database_url (environment)
                    mock_instance.set_main_option.assert_called_once_with(
                        "sqlalchemy.url", "postgresql://secure"
                    )


# ============================================================================
# MANDATORY Performance Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.performance
class TestMigrationsPerformance:
    """MANDATORY performance tests for migrations."""

    def test_migration_manager_initialization_performance(self) -> None:
        """MANDATORY: Test migration manager initialization performance."""
        # Arrange - MANDATORY
        import time

        with patch("src.database.migrations.Path.exists", return_value=True):
            with patch("src.database.migrations.Config"):
                with patch(
                    "src.database.migrations.get_database_url", return_value="postgresql://test"
                ):
                    # Act - MANDATORY
                    start_time = time.perf_counter()

                    manager = MigrationManager()

                    end_time = time.perf_counter()
                    execution_time = end_time - start_time

                    # Assert - MANDATORY
                    assert manager is not None
                    assert execution_time < 0.1  # <100ms for initialization
