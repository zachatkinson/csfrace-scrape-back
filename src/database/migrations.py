"""Database migration management using Alembic."""

import logging
from pathlib import Path

from sqlalchemy import create_engine

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .models import get_database_url

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

    def create_migration(self, message: str, autogenerate: bool = True) -> str:
        """Create a new migration.

        Args:
            message: Migration description
            autogenerate: Whether to auto-generate migration from model changes

        Returns:
            Migration revision ID
        """
        try:
            logger.info(f"Creating migration: {message}")

            if autogenerate:
                # Create auto-generated migration
                command.revision(
                    self.config,
                    message=message,
                    autogenerate=True,
                )
            else:
                # Create empty migration
                command.revision(
                    self.config,
                    message=message,
                )

            logger.info(f"Created migration: {message}")
            return message

        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise

    def upgrade_database(self, revision: str = "head") -> None:
        """Upgrade database to specified revision.

        Args:
            revision: Target revision (default: head)
        """
        try:
            logger.info(f"Upgrading database to {revision}")
            command.upgrade(self.config, revision)
            logger.info("Database upgrade completed successfully")

        except Exception as e:
            logger.error(f"Failed to upgrade database: {e}")
            raise

    def downgrade_database(self, revision: str) -> None:
        """Downgrade database to specified revision.

        Args:
            revision: Target revision
        """
        try:
            logger.info(f"Downgrading database to {revision}")
            command.downgrade(self.config, revision)
            logger.info("Database downgrade completed successfully")

        except Exception as e:
            logger.error(f"Failed to downgrade database: {e}")
            raise

    def get_current_revision(self) -> str | None:
        """Get current database revision."""
        try:
            database_url = self.config.get_main_option("sqlalchemy.url")
            if database_url is None:
                logger.error("Database URL not configured")
                return None
            engine = create_engine(database_url)
            with engine.connect() as connection:
                migration_ctx = MigrationContext.configure(connection)
                current_rev = migration_ctx.get_current_revision()
                return current_rev

        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None

    def get_migration_history(self) -> list[str]:
        """Get migration history."""
        try:
            script_dir = ScriptDirectory.from_config(self.config)
            revisions = []

            for revision in script_dir.walk_revisions():
                revisions.append(f"{revision.revision}: {revision.doc}")

            return revisions

        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []

    def show_current_head(self) -> str | None:
        """Show current head revision."""
        try:
            script_dir = ScriptDirectory.from_config(self.config)
            return script_dir.get_current_head()

        except Exception as e:
            logger.error(f"Failed to get current head: {e}")
            return None

    def ensure_database_current(self) -> None:
        """Ensure database is at current migration head."""
        try:
            current_rev = self.get_current_revision()
            head_rev = self.show_current_head()

            if current_rev is None:
                logger.info("Database not initialized, running initial migration")
                self.upgrade_database()
            elif current_rev != head_rev:
                logger.info(f"Database at {current_rev}, upgrading to {head_rev}")
                self.upgrade_database()
            else:
                logger.info("Database is current")

        except Exception as e:
            logger.error(f"Failed to ensure database currency: {e}")
            raise


# CLI interface for migration management
def get_migration_manager() -> MigrationManager:
    """Get configured migration manager instance."""
    return MigrationManager()


if __name__ == "__main__":
    # Command-line interface for migrations
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.database.migrations <command> [args]")
        print("Commands:")
        print("  init                    - Initialize migrations")
        print("  create <message>        - Create new migration")
        print("  upgrade [revision]      - Upgrade to revision (default: head)")
        print("  downgrade <revision>    - Downgrade to revision")
        print("  current                 - Show current revision")
        print("  history                 - Show migration history")
        print("  head                    - Show head revision")
        sys.exit(1)

    manager = get_migration_manager()
    cmd = sys.argv[1]

    try:
        if cmd == "init":
            print("Error: Alembic initialization must be done manually with 'alembic init alembic'")
            sys.exit(1)
        elif cmd == "create":
            if len(sys.argv) < 3:
                print("Error: Migration message required")
                sys.exit(1)
            message = " ".join(sys.argv[2:])
            manager.create_migration(message)
        elif cmd == "upgrade":
            revision = sys.argv[2] if len(sys.argv) > 2 else "head"
            manager.upgrade_database(revision)
        elif cmd == "downgrade":
            if len(sys.argv) < 3:
                print("Error: Target revision required")
                sys.exit(1)
            revision = sys.argv[2]
            manager.downgrade_database(revision)
        elif cmd == "current":
            current = manager.get_current_revision()
            print(f"Current revision: {current}")
        elif cmd == "history":
            history = manager.get_migration_history()
            for item in history:
                print(item)
        elif cmd == "head":
            head = manager.show_current_head()
            print(f"Head revision: {head}")
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
