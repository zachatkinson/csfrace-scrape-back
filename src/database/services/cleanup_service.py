"""Database cleanup and maintenance service.

This module provides cleanup operations for the database,
following Single Responsibility Principle.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import DatabaseError
from src.utils.logging import get_logger

from ...database.models import ContentResult as JobContent, JobLog, ScrapingJob as Job

logger = get_logger(__name__)


class CleanupService:
    """Service for database cleanup and maintenance operations."""

    def __init__(self, session: AsyncSession):
        """Initialize cleanup service.

        Args:
            session: Database session
        """
        self.session = session

    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """Delete jobs older than specified days.

        Args:
            days: Number of days to keep jobs

        Returns:
            Number of jobs deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            # Delete old jobs (cascade will handle related records)
            result = await self.session.execute(delete(Job).where(Job.created_at < cutoff_date))

            deleted_count = result.rowcount
            await self.session.commit()

            logger.info("Cleaned up old jobs", deleted_count=deleted_count, cutoff_days=days)

            return deleted_count

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to cleanup old jobs", error=str(e))
            raise DatabaseError(operation="cleanup old jobs", original_error=e) from e

    async def cleanup_failed_jobs(self, days: int = 3) -> int:
        """Delete failed jobs older than specified days.

        Args:
            days: Number of days to keep failed jobs

        Returns:
            Number of jobs deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            result = await self.session.execute(
                delete(Job).where(Job.status == "failed").where(Job.created_at < cutoff_date)
            )

            deleted_count = result.rowcount
            await self.session.commit()

            logger.info("Cleaned up failed jobs", deleted_count=deleted_count, cutoff_days=days)

            return deleted_count

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to cleanup failed jobs", error=str(e))
            raise DatabaseError(operation="cleanup failed jobs", original_error=e) from e

    async def cleanup_orphaned_content(self) -> int:
        """Delete content records without associated jobs.

        Returns:
            Number of content records deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        try:
            # Find orphaned content
            orphaned_content = await self.session.execute(
                select(JobContent.id)
                .outerjoin(Job, JobContent.job_id == Job.id)
                .where(Job.id.is_(None))
            )

            orphaned_ids = [row[0] for row in orphaned_content]

            if orphaned_ids:
                result = await self.session.execute(
                    delete(JobContent).where(JobContent.id.in_(orphaned_ids))
                )
                deleted_count = result.rowcount
                await self.session.commit()
            else:
                deleted_count = 0

            logger.info("Cleaned up orphaned content", deleted_count=deleted_count)

            return deleted_count

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to cleanup orphaned content", error=str(e))
            raise DatabaseError(operation="cleanup orphaned content", original_error=e) from e

    async def cleanup_orphaned_logs(self) -> int:
        """Delete log records without associated jobs.

        Returns:
            Number of log records deleted

        Raises:
            DatabaseError: If cleanup fails
        """
        try:
            # Find orphaned logs
            orphaned_logs = await self.session.execute(
                select(JobLog.id).outerjoin(Job, JobLog.job_id == Job.id).where(Job.id.is_(None))
            )

            orphaned_ids = [row[0] for row in orphaned_logs]

            if orphaned_ids:
                result = await self.session.execute(
                    delete(JobLog).where(JobLog.id.in_(orphaned_ids))
                )
                deleted_count = result.rowcount
                await self.session.commit()
            else:
                deleted_count = 0

            logger.info("Cleaned up orphaned logs", deleted_count=deleted_count)

            return deleted_count

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to cleanup orphaned logs", error=str(e))
            raise DatabaseError(operation="cleanup orphaned logs", original_error=e) from e

    async def vacuum_database(self) -> None:
        """Run VACUUM on database to reclaim space.

        Note: This operation may not be available on all database backends.

        Raises:
            DatabaseError: If vacuum fails
        """
        try:
            # Note: VACUUM requires autocommit mode in PostgreSQL
            await self.session.execute(text("VACUUM ANALYZE"))

            logger.info("Database vacuum completed")

        except Exception as e:
            logger.warning("Failed to vacuum database", error=str(e))
            # Don't raise as this is optional maintenance

    async def cleanup_all(
        self, old_jobs_days: int = 7, failed_jobs_days: int = 3
    ) -> dict[str, Any]:
        """Run all cleanup operations.

        Args:
            old_jobs_days: Days to keep normal jobs
            failed_jobs_days: Days to keep failed jobs

        Returns:
            Summary of cleanup operations

        Raises:
            DatabaseError: If any cleanup operation fails
        """
        try:
            results = {
                "old_jobs_deleted": 0,
                "failed_jobs_deleted": 0,
                "orphaned_content_deleted": 0,
                "orphaned_logs_deleted": 0,
                "vacuum_performed": False,
            }

            # Cleanup old jobs
            results["old_jobs_deleted"] = await self.cleanup_old_jobs(old_jobs_days)

            # Cleanup failed jobs
            results["failed_jobs_deleted"] = await self.cleanup_failed_jobs(failed_jobs_days)

            # Cleanup orphaned records
            results["orphaned_content_deleted"] = await self.cleanup_orphaned_content()
            results["orphaned_logs_deleted"] = await self.cleanup_orphaned_logs()

            # Try to vacuum
            try:
                await self.vacuum_database()
                results["vacuum_performed"] = True
            except Exception:  # pylint: disable=broad-exception-caught
                pass  # Vacuum is optional

            logger.info("Database cleanup completed", **results)

            return results

        except Exception as e:
            logger.error("Failed to perform full cleanup", error=str(e))
            raise DatabaseError(operation="perform full cleanup", original_error=e) from e

    async def get_database_size(self) -> dict[str, Any]:
        """Get database size information.

        Returns:
            Dictionary with size information

        Raises:
            DatabaseError: If query fails
        """
        try:
            # PostgreSQL specific query
            result = await self.session.execute(
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

        except Exception as e:
            logger.warning("Failed to get database size", error=str(e))
            # Return empty dict if not PostgreSQL or query fails
            return {}

    async def get_table_sizes(self) -> list[dict[str, Any]]:
        """Get size information for all tables.

        Returns:
            List of table size information

        Raises:
            DatabaseError: If query fails
        """
        try:
            # PostgreSQL specific query
            result = await self.session.execute(
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

        except Exception as e:
            logger.warning("Failed to get table sizes", error=str(e))
            return []
