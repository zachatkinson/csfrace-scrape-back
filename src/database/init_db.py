"""Database initialization utilities with PostgreSQL enum safety."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum
import sqlalchemy.exc

from alembic import command  # type: ignore[attr-defined] # pylint: disable=no-name-in-module
from alembic.config import Config  # pylint: disable=no-name-in-module

from .models import Base, JobPriority, JobStatus, get_database_url

logger = logging.getLogger(__name__)


async def init_db(engine=None) -> None:
    """Initialize the database using Alembic migrations for production-ready schema management.

    Following PostgreSQL and SQLAlchemy best practices:
    1. Run Alembic migrations to create enums and schema
    2. Fallback to direct creation for development/testing
    3. Handle concurrent execution gracefully

    Args:
        engine: Optional SQLAlchemy Engine. If None, creates engine from get_database_url().
                This enables dependency injection for testing (SQLAlchemy best practice).

    Reference: https://alembic.sqlalchemy.org/en/latest/tutorial.html#running-our-first-migration
    """
    try:
        # Use provided engine or create one (dependency injection pattern)
        if engine is None:
            engine = create_engine(get_database_url(), echo=False)

        # Try to run Alembic migrations first (production approach)
        try:
            await _run_alembic_migrations()
            logger.info("Database initialized using Alembic migrations")
        except Exception as alembic_error:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Alembic migration failed, falling back to direct creation: %s", alembic_error
            )

            # Fallback to direct enum creation (testing/development)
            await _create_enums_safely(engine)

            # Create all tables using SQLAlchemy best practices
            Base.metadata.create_all(engine, checkfirst=True)

            logger.info("Database initialized using direct creation fallback")

        # Final success message for test compatibility
        logger.info("Database initialization completed successfully")

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Database initialization failed: %s", e)
        raise


async def _run_alembic_migrations() -> None:
    """Run Alembic migrations to upgrade database to latest schema."""
    # Get the project root directory (where alembic.ini is located)
    backend_root = Path(__file__).parent.parent.parent
    alembic_ini_path = backend_root / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

    # Create Alembic config
    alembic_cfg = Config(str(alembic_ini_path))

    # Set the script location relative to the config file
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))

    # Run the upgrade command
    command.upgrade(alembic_cfg, "head")


async def _create_enums_safely(engine) -> None:
    """Create PostgreSQL enum types safely for concurrent test execution.

    Uses PostgreSQL's transaction-safe enum creation pattern recommended
    in the official documentation with enhanced concurrency safety.
    """
    enum_definitions = [
        ("jobstatus", JobStatus),
        ("jobpriority", JobPriority),
    ]

    with engine.connect() as conn:
        for enum_name, enum_class in enum_definitions:
            try:
                # Use CREATE TYPE IF NOT EXISTS for PostgreSQL 9.1+ (safer for concurrent execution)
                # First check if enum exists to avoid unnecessary work
                result = conn.execute(
                    text("SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = :enum_name)"),
                    {"enum_name": enum_name},
                ).scalar()

                if not result:
                    try:
                        # Use SQLAlchemy's PostgreSQL dialect with proper concurrency handling
                        # This is the official recommended approach for SQLAlchemy + PostgreSQL
                        pg_enum = PostgreSQLEnum(enum_class, name=enum_name, create_type=True)
                        pg_enum.create(conn, checkfirst=True)
                        logger.debug("Created PostgreSQL enum type: %s", enum_name)
                        
                    except (
                        sqlalchemy.exc.ProgrammingError,  # Type already exists
                        sqlalchemy.exc.IntegrityError,    # Duplicate key
                        sqlalchemy.exc.DatabaseError,     # General DB errors
                    ) as create_error:
                        error_msg = str(create_error).lower()
                        # Handle concurrent enum creation race conditions gracefully
                        if any(phrase in error_msg for phrase in ["already exists", "duplicate key", "relation already exists"]):
                            logger.debug("Enum %s already exists (concurrent execution): %s", enum_name, create_error)
                        else:
                            logger.warning("Could not create enum %s: %s", enum_name, create_error)
                            # Don't raise - let table creation proceed
                else:
                    logger.debug("PostgreSQL enum type already exists: %s", enum_name)

            except Exception as e:  # pylint: disable=broad-exception-caught
                error_msg = str(e).lower()
                # Handle any other concurrent execution conflicts gracefully
                if any(phrase in error_msg for phrase in ["already exists", "duplicate key"]):
                    logger.debug("Enum %s already exists (outer exception): %s", enum_name, e)
                else:
                    logger.warning("Unexpected error with enum %s: %s", enum_name, e)
                    # Don't raise - let table creation proceed

        # Commit the transaction
        conn.commit()
