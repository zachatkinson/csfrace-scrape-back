"""Database migration management using Alembic."""

import logging
from pathlib import Path

from alembic.config import Config  # pylint: disable=no-name-in-module
from alembic.runtime.migration import MigrationContext  # pylint: disable=no-name-in-module
from alembic.script import ScriptDirectory  # pylint: disable=no-name-in-module
from sqlalchemy import create_engine

from alembic import command  # pylint: disable=no-name-in-module
from src.core.decorators import database_error_handler

from .utils import get_database_url

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations using Alembic."""

    def __init__(self, config_file: Path | None = None):
        """Initialize migration manager.

        Args:
            config_file: Path to alembic.ini. If None, uses default location.
        """
        self.config_file = config_file or Path("alembic.ini")
        if not self.config_file.exists():
            raise FileNotFoundError(f"Alembic config file not found: {self.config_file}")

        # Create Alembic configuration
        self.config = Config(str(self.config_file))

        # Override database URL if needed
        database_url = get_database_url()
        self.config.set_main_option("sqlalchemy.url", database_url)

    def is_initialized(self) -> bool:
        """Check if Alembic is properly initialized."""
        alembic_dir = Path("alembic")
        return (
            self.config_file.exists()
            and alembic_dir.exists()
            and (alembic_dir / "versions").exists()
            and (alembic_dir / "env.py").exists()
        )

    @database_error_handler("create database migration")
    def create_migration(self, description: str, autogenerate: bool = True) -> str:
        """Create a new migration.

        Args:
            description: Migration description
            autogenerate: Whether to auto-generate migration from model changes

        Returns:
            Migration revision ID
        """
        logger.info("Creating migration: %s", description)

        if autogenerate:
            # Create auto-generated migration
            command.revision(
                self.config,
                message=description,
                autogenerate=True,
            )
        else:
            # Create empty migration
            command.revision(
                self.config,
                message=description,
            )

        logger.info("Created migration: %s", description)
        return description

    @database_error_handler("upgrade database")
    def upgrade_database(self, revision: str = "head") -> None:  # pylint: disable=redefined-outer-name
        """Upgrade database to specified revision.

        Args:
            revision: Target revision (default: head)
        """
        logger.info("Upgrading database to %s", revision)
        command.upgrade(self.config, revision)
        logger.info("Database upgrade completed successfully")

    @database_error_handler("downgrade database")
    def downgrade_database(self, revision: str) -> None:  # pylint: disable=redefined-outer-name
        """Downgrade database to specified revision.

        Args:
            revision: Target revision
        """
        logger.info("Downgrading database to %s", revision)
        command.downgrade(self.config, revision)
        logger.info("Database downgrade completed successfully")

    def get_current_revision(self) -> str | None:
        """Get current database revision."""
        return _get_current_revision_safe(self)

    def get_migration_history(self) -> list[str]:  # pylint: disable=redefined-outer-name
        """Get migration history."""
        return _get_migration_history_safe(self)

    def show_current_head(self) -> str | None:
        """Show current head revision."""
        return _show_current_head_safe(self)

    @database_error_handler("ensure database current")
    def ensure_database_current(self) -> None:
        """Ensure database is at current migration head."""
        current_rev = self.get_current_revision()
        head_rev = self.show_current_head()

        if current_rev is None:
            logger.info("Database not initialized, running initial migration")
            self.upgrade_database()
        elif current_rev != head_rev:
            logger.info("Database at %s, upgrading to %s", current_rev, head_rev)
            self.upgrade_database()
        else:
            logger.info("Database is current")


# CLI interface for migration management
def get_migration_manager() -> MigrationManager:
    """Get configured migration manager instance."""
    return MigrationManager()


@database_error_handler("execute CLI command")
def _execute_cli_command_safe(manager: MigrationManager, cmd: str) -> None:
    """Safely execute CLI command."""
    if cmd == "init":
        logger.error("Alembic initialization must be done manually with 'alembic init alembic'")
        sys.exit(1)
    elif cmd == "create":
        if len(sys.argv) < 3:
            logger.error("Migration message required")
            sys.exit(1)
        migration_description = " ".join(sys.argv[2:])  # pylint: disable=invalid-name
        manager.create_migration(migration_description)
    elif cmd == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        manager.upgrade_database(revision)
    elif cmd == "downgrade":
        if len(sys.argv) < 3:
            logger.error("Target revision required")
            sys.exit(1)
        revision = sys.argv[2]
        manager.downgrade_database(revision)
    elif cmd == "current":
        current = manager.get_current_revision()
        logger.info("Current revision: %s", current)
    elif cmd == "history":
        history = manager.get_migration_history()
        for item in history:
            logger.info("%s", item)
    elif cmd == "head":
        head = manager.show_current_head()
        logger.info("Head revision: %s", head)
    else:
        logger.error("Unknown command: %s", cmd)
        sys.exit(1)


if __name__ == "__main__":
    # Command-line interface for migrations
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: python -m src.database.migrations <command> [args]")
        logger.info("Commands:")
        logger.info("  init                    - Initialize migrations")
        logger.info("  create <message>        - Create new migration")
        logger.info("  upgrade [revision]      - Upgrade to revision (default: head)")
        logger.info("  downgrade <revision>    - Downgrade to revision")
        logger.info("  current                 - Show current revision")
        logger.info("  history                 - Show migration history")
        logger.info("  head                    - Show head revision")
        sys.exit(1)

    manager = get_migration_manager()
    cmd = sys.argv[1]

    _execute_cli_command_safe(manager, cmd)


@database_error_handler("get current revision")
def _get_current_revision_safe(manager: MigrationManager) -> str | None:
    """Safely get current database revision."""
    database_url = manager.config.get_main_option("sqlalchemy.url")
    if database_url is None:
        logger.error("Database URL not configured")
        return None
    engine = create_engine(database_url)
    with engine.connect() as connection:
        migration_ctx = MigrationContext.configure(connection)
        current_rev = migration_ctx.get_current_revision()
        return current_rev


@database_error_handler("get migration history")
def _get_migration_history_safe(manager: MigrationManager) -> list[str]:
    """Safely get migration history."""
    script_dir = ScriptDirectory.from_config(manager.config)
    revisions = []

    for rev in script_dir.walk_revisions():
        revisions.append(f"{rev.revision}: {rev.doc}")

    return revisions


@database_error_handler("show current head")
def _show_current_head_safe(manager: MigrationManager) -> str | None:
    """Safely show current head revision."""
    script_dir = ScriptDirectory.from_config(manager.config)
    return script_dir.get_current_head()
