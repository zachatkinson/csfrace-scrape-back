"""Database initialization service for Docker container startup.

This module ensures all database schema, tables, and data are created automatically
when the backend container starts, without requiring manual migrations.

Following best practices:
- Idempotent operations (safe to run multiple times)
- Complete schema creation from models
- Proper error handling and logging
- Domain field population for existing data
"""

import logging
import sys

from sqlalchemy import text

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_database_logger
from src.database.models.base import Base
from src.database.services.base import BaseService
from src.utils.url_utils import URLError, extract_domain

logger = get_database_logger()


class DatabaseInitializer:
    """Handles complete database initialization for container startup."""

    def __init__(self, service: BaseService | None = None):
        """Initialize with optional service (for testing)."""
        self.service = service or BaseService()
        self.logger = logger

    @database_error_handler("initialize complete database schema")
    def initialize_complete_schema(self) -> bool:
        """Initialize complete database schema automatically.

        This method creates all tables, indexes, and populates required data.
        It's designed to be run on container startup.

        Returns:
            True if initialization was successful

        Raises:
            Exception: If critical initialization fails
        """
        self.logger.info("Starting complete database schema initialization")

        # Step 1: Create all tables from SQLAlchemy models
        self._create_all_tables()

        # Step 2: Ensure all required indexes exist
        self._create_required_indexes()

        # Step 3: Populate domain field for any existing jobs
        self._populate_domain_fields()

        # Step 4: Verify schema integrity
        self._verify_schema_integrity()

        self.logger.info("Database schema initialization completed successfully")
        return True

    @database_error_handler("create all database tables")
    def _create_all_tables(self) -> None:
        """Create all database tables from SQLAlchemy models."""
        self.logger.info("Creating all database tables from models")

        # Use SQLAlchemy's create_all which is idempotent
        Base.metadata.create_all(self.service.engine)

        self.logger.info("All database tables created successfully")

    @database_error_handler("create required database indexes")
    def _create_required_indexes(self) -> None:
        """Create all required database indexes for performance."""
        self.logger.info("Creating required database indexes")

        with self.service.get_session() as session:
            # Create domain-related indexes for jobs table
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_jobs_domain
                ON jobs(domain);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_jobs_domain_status
                ON jobs(domain, status);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_jobs_domain_created_at
                ON jobs(domain, created_at);
            """)
            )

            # Create user-related indexes
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_jobs_user_id
                ON jobs(user_id);
            """)
            )

            # Create OAuth-related indexes
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_oauth_accounts_user_id
                ON oauth_linked_accounts(user_id);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_oauth_accounts_provider
                ON oauth_linked_accounts(provider, provider_user_id);
            """)
            )

            # Create revoked tokens indexes
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_revoked_tokens_user_id
                ON revoked_tokens(user_id);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at
                ON revoked_tokens(expires_at);
            """)
            )

        self.logger.info("All required indexes created successfully")

    @database_error_handler("populate domain fields for existing jobs")
    def _populate_domain_fields(self) -> None:
        """Populate domain fields for any existing jobs that don't have them."""
        self.logger.info("Checking and populating domain fields for existing jobs")

        with self.service.get_session() as session:
            # Check if there are any jobs without domain fields
            result = session.execute(
                text("""
                SELECT COUNT(*) FROM jobs
                WHERE domain IS NULL OR domain = '';
            """)
            ).scalar()

            if result and result > 0:
                self.logger.info(f"Found {result} jobs without domain fields, populating...")

                # Get all jobs without domains
                jobs_result = session.execute(
                    text("""
                    SELECT id, source_url FROM jobs
                    WHERE domain IS NULL OR domain = '';
                """)
                ).fetchall()

                # Process in batches for better performance
                batch_size = 100
                updated_count = 0

                for i in range(0, len(jobs_result), batch_size):
                    batch = jobs_result[i : i + batch_size]

                    for job_id, source_url in batch:
                        try:
                            # Extract domain using our utility
                            domain = extract_domain(source_url)

                            # Update the job with the extracted domain
                            session.execute(
                                text("""
                                UPDATE jobs SET domain = :domain
                                WHERE id = :job_id;
                            """),
                                {"domain": domain, "job_id": job_id},
                            )

                            updated_count += 1

                        except (URLError, Exception) as e:
                            # Log the error but continue processing
                            self.logger.warning(
                                f"Failed to extract domain from URL '{source_url}' "
                                f"for job {job_id}: {e}. Setting to 'unknown'."
                            )

                            # Set to 'unknown' as fallback
                            session.execute(
                                text("""
                                UPDATE jobs SET domain = 'unknown'
                                WHERE id = :job_id;
                            """),
                                {"job_id": job_id},
                            )

                            updated_count += 1

                    # Commit batch
                    session.commit()

                    self.logger.debug(
                        f"Processed batch {i // batch_size + 1}, updated {updated_count} jobs so far"
                    )

                self.logger.info(f"Successfully populated domain fields for {updated_count} jobs")
            else:
                self.logger.info("All jobs already have domain fields populated")

    @database_error_handler("verify database schema integrity")
    def _verify_schema_integrity(self) -> None:
        """Verify that the database schema is complete and correct."""
        self.logger.info("Verifying database schema integrity")

        with self.service.get_session() as session:
            # Check that all required tables exist
            required_tables = {
                "users",
                "jobs",
                "content_results",
                "job_logs",
                "oauth_linked_accounts",
                "revoked_tokens",
            }

            for table_name in required_tables:
                result = session.execute(
                    text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = :table_name
                    );
                """),
                    {"table_name": table_name},
                ).scalar()

                if not result:
                    raise RuntimeError(f"Required table '{table_name}' is missing")

            # Check that jobs table has domain field
            result = session.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = 'jobs' AND column_name = 'domain'
                );
            """)
            ).scalar()

            if not result:
                raise RuntimeError("Jobs table is missing required 'domain' column")

            # Check that no jobs have NULL domain fields
            result = session.execute(
                text("""
                SELECT COUNT(*) FROM jobs WHERE domain IS NULL;
            """)
            ).scalar()

            if result and result > 0:
                raise RuntimeError(f"Found {result} jobs with NULL domain fields")

        self.logger.info("Database schema integrity verification passed")


@database_error_handler("initialize database on startup")
def initialize_database_on_startup() -> bool:
    """Main entry point for database initialization on container startup.

    This function is called from the application startup sequence.

    Returns:
        True if initialization was successful

    Raises:
        SystemExit: If initialization fails critically
    """
    initializer = DatabaseInitializer()
    success = initializer.initialize_complete_schema()

    if not success:
        logger.critical("Critical database initialization failure")
        # Exit with error code to prevent container from starting with broken DB
        sys.exit(1)

    return success


@database_error_handler("main CLI database initialization")
def main() -> None:
    """CLI entry point for manual database initialization."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Starting manual database initialization")

    success = initialize_database_on_startup()
    if success:
        logger.info("Database initialization completed successfully")
        sys.exit(0)
    else:
        logger.error("Database initialization failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
