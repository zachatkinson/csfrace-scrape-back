"""Database initialization utilities with PostgreSQL enum safety."""

import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.core.decorators import database_error_handler

from .models import Base
from .utils import create_postgresql_enums, get_database_url, get_standard_enum_definitions

logger = logging.getLogger(__name__)

# Runtime imports with proper error handling
try:
    from alembic.config import Config as AlembicConfig

    from alembic import command

    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False
    # Set these to None for type checking - will be checked at runtime
    command = None  # type: ignore
    AlembicConfig = None  # type: ignore
    logger.warning("Alembic not available - migrations will use fallback method")


@database_error_handler("initialize database")
async def init_db(engine: Engine | None = None) -> None:
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


@database_error_handler("run Alembic migrations")
async def _run_alembic_migrations() -> None:
    """Run Alembic migrations to upgrade database to latest schema.

    Handles multiple head revisions properly to ensure all migrations
    are applied when using branched migration structures.

    FIXED: Uses asyncio.to_thread to run synchronous Alembic command in async context.
    """
    import asyncio

    if not ALEMBIC_AVAILABLE:
        raise ImportError("Alembic is not available - cannot run migrations")

    # Get the project root directory (where alembic.ini is located)
    backend_root = Path(__file__).parent.parent.parent
    alembic_ini_path = backend_root / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

    # Create Alembic config
    alembic_cfg = AlembicConfig(str(alembic_ini_path))

    # Set the script location relative to the config file
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))

    try:
        # FIXED: Run the synchronous upgrade command in thread pool to avoid blocking async event loop
        await asyncio.to_thread(command.upgrade, alembic_cfg, "heads")
        logger.info("All Alembic migrations applied successfully")
    except Exception as e:
        # If migration fails, log specific heads that need to be applied
        try:
            # Log current revision and all heads for debugging
            logger.error("Migration failed - error: %s", str(e))
            logger.error("Current revision:")
            command.current(alembic_cfg)
            logger.error("Available heads:")
            command.heads(alembic_cfg)
        except Exception:
            pass  # Don't let debugging code cause additional failures
        raise


@database_error_handler("create PostgreSQL enums safely")
async def _create_enums_safely(engine: Engine) -> None:
    """Create PostgreSQL enum types safely for concurrent test execution.

    Uses PostgreSQL's transaction-safe enum creation pattern recommended
    in the official documentation with enhanced concurrency safety.
    """
    with engine.connect() as conn:
        create_postgresql_enums(conn, get_standard_enum_definitions())
        # Commit the transaction
        conn.commit()
