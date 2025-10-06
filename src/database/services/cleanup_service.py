"""Database cleanup and maintenance service.

This module provides cleanup operations for the database,
following Single Responsibility Principle.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_database_logger

from ...database.models.jobs import ContentResult as JobContent, JobLog, ScrapingJob as Job
from ..queries import QueryBuilder

logger = get_database_logger(__name__).logger


class CleanupService:
    """Service for database cleanup and maintenance operations."""

    def __init__(self, session: Session):
        """Initialize cleanup service.

        Args:
            session: Database session
        """
        self.session = session

    @database_error_handler("cleanup jobs")
    def cleanup_jobs(self, days: int = 7) -> int:
        """Delete jobs older than specified days.

        Args:
            days: Number of days to keep jobs

        Returns:
            Number of jobs deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Use centralized query pattern for DRY compliance
        from ...common.status import JobStatus

        stmt = QueryBuilder.bulk_update(
            Job, Job.created_at < cutoff_date, {"status": JobStatus.CANCELLED.value}
        )
        result = self.session.execute(stmt)
        deleted_count: int = result.rowcount or 0
        self.session.commit()

        logger.info("Cleaned up old jobs", deleted_count=deleted_count, cutoff_days=days)

        return deleted_count

    @database_error_handler("cleanup failed jobs")
    def cleanup_failed_jobs(self, days: int = 3) -> int:
        """Delete failed jobs older than specified days.

        Args:
            days: Number of days to keep failed jobs

        Returns:
            Number of jobs deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Use centralized query pattern for DRY compliance
        from sqlalchemy import and_

        where_clause = and_(Job.status == "failed", Job.created_at < cutoff_date)
        stmt = QueryBuilder.bulk_delete(Job, where_clause)

        result = self.session.execute(stmt)
        deleted_count: int = result.rowcount or 0
        self.session.commit()

        logger.info("Cleaned up failed jobs", deleted_count=deleted_count, cutoff_days=days)

        return deleted_count

    @database_error_handler("cleanup orphaned content")
    def cleanup_orphaned_content(self) -> int:
        """Delete content records without associated jobs.

        Returns:
            Number of content records deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        # Find orphaned content
        orphaned_content = self.session.execute(
            select(JobContent.id)
            .outerjoin(Job, JobContent.job_id == Job.id)
            .where(Job.id.is_(None))
        )

        orphaned_ids = [row[0] for row in orphaned_content]

        if orphaned_ids:
            result = self.session.execute(delete(JobContent).where(JobContent.id.in_(orphaned_ids)))
            deleted_count = result.rowcount
            self.session.commit()
        else:
            deleted_count = 0

        logger.info("Cleaned up orphaned content", deleted_count=deleted_count)

        return deleted_count

    @database_error_handler("cleanup orphaned logs")
    def cleanup_orphaned_logs(self) -> int:
        """Delete log records without associated jobs.

        Returns:
            Number of log records deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        # Find orphaned logs
        orphaned_logs = self.session.execute(
            select(JobLog.id).outerjoin(Job, JobLog.job_id == Job.id).where(Job.id.is_(None))
        )

        orphaned_ids = [row[0] for row in orphaned_logs]

        if orphaned_ids:
            result = self.session.execute(delete(JobLog).where(JobLog.id.in_(orphaned_ids)))
            deleted_count = result.rowcount
            self.session.commit()
        else:
            deleted_count = 0

        logger.info("Cleaned up orphaned logs", deleted_count=deleted_count)

        return deleted_count

    @database_error_handler("vacuum database")
    def vacuum_database(self) -> None:
        """Run VACUUM on database to reclaim space.

        PostgreSQL requires autocommit mode for VACUUM operations.
        This method properly handles the autocommit requirement following
        PostgreSQL best practices.

        Note: VACUUM cannot run inside a transaction block in PostgreSQL.
        This implementation commits any pending transaction first, then
        uses autocommit for the VACUUM operation.

        Raises:
            DatabaseError: If vacuum fails
        """
        # MANDATORY PostgreSQL requirement: VACUUM must run outside transaction
        # Following PostgreSQL documentation best practices

        # Commit any pending transaction first
        self.session.commit()

        # Get bind (could be Engine or Connection depending on fixture setup)
        bind = self.session.get_bind()

        # Determine if bind is Engine or Connection and handle appropriately
        from sqlalchemy.engine import Connection as SQLConnection

        # Get engine from connection or use bind directly if it's already an engine
        engine = bind.engine if isinstance(bind, SQLConnection) else bind

        # When using nested transactions (SAVEPOINT fixture), we need to get a raw psycopg connection
        # directly from the pool and set autocommit mode before any SQLAlchemy session interaction
        if isinstance(bind, SQLConnection):
            # For nested transactions, get the underlying psycopg connection directly
            # This bypasses SQLAlchemy's transaction management
            raw_conn = engine.raw_connection()
            try:
                # Set autocommit at the psycopg level
                raw_conn.connection.autocommit = True
                # Execute VACUUM using the raw cursor
                cursor = raw_conn.cursor()
                cursor.execute("VACUUM ANALYZE")
                cursor.close()
            finally:
                # Return connection to pool
                raw_conn.close()
        else:
            # Normal path for production/non-test scenarios
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text("VACUUM ANALYZE"))

        logger.info("Database vacuum completed")

    @database_error_handler("perform full cleanup")
    def cleanup_all(self, old_jobs_days: int = 7, failed_jobs_days: int = 3) -> dict[str, Any]:
        """Run all cleanup operations.

        Args:
            old_jobs_days: Days to keep normal jobs
            failed_jobs_days: Days to keep failed jobs

        Returns:
            Summary of cleanup operations

        Raises:
            DatabaseError: If any cleanup operation fails
        """
        results = {
            "old_jobs_deleted": 0,
            "failed_jobs_deleted": 0,
            "orphaned_content_deleted": 0,
            "orphaned_logs_deleted": 0,
            "vacuum_performed": False,
        }

        # Cleanup old jobs
        results["old_jobs_deleted"] = self.cleanup_jobs(old_jobs_days)

        # Cleanup failed jobs
        results["failed_jobs_deleted"] = self.cleanup_failed_jobs(failed_jobs_days)

        # Cleanup orphaned records
        results["orphaned_content_deleted"] = self.cleanup_orphaned_content()
        results["orphaned_logs_deleted"] = self.cleanup_orphaned_logs()

        # Try to vacuum
        try:
            self.vacuum_database()
            results["vacuum_performed"] = True
        except Exception:  # pylint: disable=broad-exception-caught
            pass  # Vacuum is optional

        logger.info("Database cleanup completed", **results)

        return results

    @database_error_handler("get database size")
    def get_database_size(self) -> dict[str, Any]:
        """Get database size information.

        Returns:
            Dictionary with size information

        Raises:
            DatabaseError: If query fails
        """
        # PostgreSQL specific query
        result = self.session.execute(
            text(
                """
            SELECT
                pg_database_size(current_database()) as total_size,
                pg_size_pretty(pg_database_size(current_database())) as total_size_pretty
            """
            )
        )

        row = result.first()
        if row:
            return {"total_size_bytes": row[0], "total_size_pretty": row[1]}

        return {"total_size_bytes": 0, "total_size_pretty": "0 bytes"}

    @database_error_handler("get table sizes")
    def get_table_sizes(self) -> list[dict[str, Any]]:
        """Get size information for all tables.

        Returns:
            List of table size information

        Raises:
            DatabaseError: If query fails
        """
        # PostgreSQL specific query
        result = self.session.execute(
            text(
                """
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """
            )
        )

        return [
            {"schema": row[0], "table": row[1], "size_pretty": row[2], "size_bytes": row[3]}
            for row in result
        ]
