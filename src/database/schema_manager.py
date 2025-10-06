"""
Enterprise-Grade SQLAlchemy Schema Manager

Follows modern SQLAlchemy best practices for schema migrations:
- Idempotent operations that can run multiple times safely
- Environment-aware configuration
- Proper error handling and logging
- Transaction safety with rollback on failures
- Alembic integration for versioned migrations
"""

import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from alembic import command
from src.core.decorators import database_error_handler

logger = logging.getLogger(__name__)


class SchemaManager:
    """Enterprise-grade schema manager following SQLAlchemy best practices."""

    def __init__(self, engine: AsyncEngine, alembic_ini_path: Path | None = None):
        self.engine = engine
        self.alembic_ini_path = alembic_ini_path or Path("alembic.ini")

    @database_error_handler("ensure database readiness")
    async def ensure_database_ready(self, environment: str = "development") -> bool:
        """
        Ensure database schema is ready for application use.

        NOTE: This function DOES NOT run migrations - migrations are handled by init_db().
        This function only validates schema readiness following Single Responsibility Principle.

        Args:
            environment: Target environment (development, staging, production)

        Returns:
            bool: True if database is ready, False if critical errors occurred
        """
        logger.info(f"Starting database readiness check for {environment}")

        # Step 1: Test database connectivity
        await self._test_connectivity()

        # Step 2: REMOVED - Migrations are handled by init_db() to follow DRY principle
        # await self._run_migrations()

        # Step 3: Ensure critical schema elements exist (idempotent fallback)
        await self._ensure_critical_schema()

        # Step 4: Validate schema consistency
        await self._validate_schema()

        logger.info(f"Database is ready for {environment}")
        return True

    async def _test_connectivity(self) -> None:
        """Test database connectivity."""
        async with self.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Database connectivity validated")

    @database_error_handler("run database migrations")
    async def _run_migrations(self) -> None:
        """Run Alembic migrations to bring schema to latest version."""
        import asyncio

        # Configure Alembic
        alembic_cfg = Config(str(self.alembic_ini_path))

        # Set the database URL for Alembic
        alembic_cfg.set_main_option("sqlalchemy.url", str(self.engine.url))

        # FIXED: Run synchronous Alembic command in thread pool to avoid blocking async event loop
        # Alembic's command.upgrade() is synchronous and must be run in a separate thread
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully")

    async def _ensure_critical_schema(self) -> None:
        """Ensure critical schema elements exist (idempotent fallback)."""
        logger.info("Ensuring critical schema elements exist")

        async with self.engine.begin() as conn:
            # Add user_id column to jobs table if missing
            await conn.execute(
                text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'jobs' AND column_name = 'user_id'
                    ) THEN
                        ALTER TABLE jobs ADD COLUMN user_id VARCHAR;
                        RAISE NOTICE 'Added user_id column to jobs table';
                    END IF;
                END $$;
            """)
            )

            # Create revoked_tokens table
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    jti VARCHAR PRIMARY KEY,
                    user_id VARCHAR,
                    token_type VARCHAR,
                    issued_at TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    revoked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    revocation_reason VARCHAR,
                    revoked_by VARCHAR,
                    client_ip VARCHAR,
                    user_agent TEXT
                );
            """)
            )

            # Create oauth_linked_accounts table
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS oauth_linked_accounts (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    provider VARCHAR NOT NULL,
                    provider_user_id VARCHAR NOT NULL,
                    provider_username VARCHAR,
                    provider_email VARCHAR,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    scope VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider, provider_user_id)
                );
            """)
            )

            # Create indexes if they don't exist
            await self._create_indexes(conn)

            logger.info("Critical schema elements ensured successfully")

    async def _create_indexes(self, conn: AsyncConnection) -> None:
        """Create indexes if they don't exist."""
        indexes = [
            ("idx_jobs_user_id", "jobs", "user_id"),
            ("idx_revoked_tokens_user_id", "revoked_tokens", "user_id"),
            ("idx_oauth_accounts_user_id", "oauth_linked_accounts", "user_id"),
        ]

        for index_name, table_name, column_name in indexes:
            await self._create_single_index_safe(conn, index_name, table_name, column_name)

    async def _validate_schema(self) -> None:
        """Validate schema consistency."""
        logger.info("Validating schema consistency")

        async with self.engine.begin() as conn:
            # Check critical tables exist
            result = await conn.execute(
                text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('users', 'jobs', 'revoked_tokens', 'oauth_linked_accounts')
            """)
            )
            existing_tables = {row[0] for row in result.fetchall()}

            expected_tables = {"users", "jobs", "revoked_tokens", "oauth_linked_accounts"}
            missing_tables = expected_tables - existing_tables

            if missing_tables:
                raise SQLAlchemyError(f"Missing critical tables: {missing_tables}")

            # Check critical columns exist
            result = await conn.execute(
                text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'jobs' AND column_name = 'user_id'
            """)
            )

            if not result.fetchone():
                raise SQLAlchemyError("jobs.user_id column missing after creation attempt")

            logger.info("Schema consistency validation passed")

    @database_error_handler("create database index")
    async def _create_single_index_safe(
        self, conn: AsyncConnection, index_name: str, table_name: str, column_name: str
    ) -> None:
        """Create a single index with error handling.

        FIXED: PostgreSQL doesn't support parameters in DO $$ blocks for DDL.
        Using safe string interpolation with validated identifiers instead.
        """
        # Validate identifiers are safe (alphanumeric + underscore only) to prevent SQL injection
        if not all(
            identifier.replace("_", "").isalnum()
            for identifier in [index_name, table_name, column_name]
        ):
            logger.error(
                f"Invalid identifier in index creation: {index_name}, {table_name}, {column_name}"
            )
            return

        # Safe to use f-strings after validation - identifiers are alphanumeric only
        await conn.execute(
            text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = '{index_name}' AND n.nspname = 'public'
                ) THEN
                    EXECUTE 'CREATE INDEX {index_name} ON {table_name}({column_name})';
                    RAISE NOTICE 'Created index {index_name}';
                END IF;
            END $$;
            """)
        )


async def ensure_database_ready(engine: AsyncEngine, environment: str = "development") -> bool:
    """
    Convenience function to ensure database is ready.

    Args:
        engine: SQLAlchemy async engine
        environment: Target environment

    Returns:
        bool: True if database is ready
    """
    manager = SchemaManager(engine)
    return await manager.ensure_database_ready(environment)
