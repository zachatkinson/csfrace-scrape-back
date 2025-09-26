"""Job logging service following Single Responsibility Principle.

This module handles all logging-related database operations including:
- Adding job log entries
- Retrieving job logs
- Managing log retention
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select

from src.utils.logging import get_logger

from ...core.exceptions import DatabaseError, ValidationError
from ..models import JobLog
from .base import BaseService

logger = get_logger(__name__)


@dataclass
class JobLogRequest:
    """Request object for creating job log entries."""

    job_id: str
    level: str
    message: str
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate log request data."""
        if not self.job_id:
            raise ValidationError("Job ID is required", field="job_id")

        if not self.message or not self.message.strip():
            raise ValidationError("Log message is required", field="message")

        # Normalize log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        self.level = self.level.upper()
        if self.level not in valid_levels:
            raise ValidationError(
                f"Invalid log level. Must be one of: {valid_levels}",
                field="level",
                value=self.level,
            )

        self.message = self.message.strip()
        self.details = self.details or {}


class LoggingService(BaseService):
    """Service for job logging operations."""

    def add_job_log(self, request: JobLogRequest) -> JobLog:
        """Add a log entry for a job.

        Args:
            request: Log request with job_id, level, message, and optional details

        Returns:
            Created log entry instance

        Raises:
            DatabaseError: If log creation fails
            ValidationError: If request data is invalid
        """
        logger.debug(
            "Adding job log",
            job_id=request.job_id,
            level=request.level,
            message=request.message[:50],
        )  # Log first 50 chars

        try:
            with self.get_session() as session:
                log_entry = JobLog(
                    job_id=request.job_id,
                    level=request.level,
                    message=request.message,
                    details=request.details,
                    created_at=datetime.now(UTC),
                )

                session.add(log_entry)
                session.flush()

                logger.debug(
                    "Job log added successfully",
                    job_id=request.job_id,
                    log_id=log_entry.id,
                    level=request.level,
                )
                return log_entry

        except Exception as e:
            logger.error("Failed to add job log", job_id=request.job_id, error=str(e))
            raise DatabaseError("add job log", e) from e

    def get_job_logs(self, job_id: str, level: str | None = None, limit: int = 100) -> list[JobLog]:
        """Get log entries for a job.

        Args:
            job_id: Job identifier
            level: Optional filter by log level
            limit: Maximum number of logs to return

        Returns:
            List of log entries ordered by creation time (newest first)
        """
        logger.debug("Getting job logs", job_id=job_id, level=level, limit=limit)

        try:
            with self.get_session() as session:
                stmt = (
                    select(JobLog)
                    .where(JobLog.job_id == job_id)
                    .order_by(desc(JobLog.timestamp))
                    .limit(limit)
                )

                if level:
                    stmt = stmt.where(JobLog.level == level.upper())

                logs = session.execute(stmt).scalars().all()

                logger.debug("Job logs retrieved", job_id=job_id, count=len(logs))
                return list(logs)

        except Exception as e:
            logger.error("Failed to get job logs", job_id=job_id, error=str(e))
            raise DatabaseError("get job logs", e) from e

    def get_recent_logs(self, limit: int = 100) -> list[JobLog]:
        """Get most recent log entries across all jobs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of recent log entries ordered by creation time
        """
        logger.debug("Getting recent logs", limit=limit)

        try:
            with self.get_session() as session:
                stmt = select(JobLog).order_by(desc(JobLog.timestamp)).limit(limit)

                logs = session.execute(stmt).scalars().all()

                logger.debug("Recent logs retrieved", count=len(logs))
                return list(logs)

        except Exception as e:
            logger.error("Failed to get recent logs", error=str(e))
            raise DatabaseError("get recent logs", e) from e

    def get_error_logs(self, limit: int = 50) -> list[JobLog]:
        """Get error-level log entries.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of error log entries ordered by creation time
        """
        logger.debug("Getting error logs", limit=limit)

        try:
            with self.get_session() as session:
                stmt = (
                    select(JobLog)
                    .where(JobLog.level.in_(["ERROR", "CRITICAL"]))
                    .order_by(desc(JobLog.timestamp))
                    .limit(limit)
                )

                logs = session.execute(stmt).scalars().all()

                logger.debug("Error logs retrieved", count=len(logs))
                return list(logs)

        except Exception as e:
            logger.error("Failed to get error logs", error=str(e))
            raise DatabaseError("get error logs", e) from e

    def count_logs_by_level(self, job_id: str | None = None) -> dict[str, int]:
        """Count log entries by level.

        Args:
            job_id: Optional job ID to filter by

        Returns:
            Dictionary with log level counts
        """
        logger.debug("Counting logs by level", job_id=job_id)

        try:
            with self.get_session() as session:
                from sqlalchemy import func

                query = session.query(JobLog.level, func.count(JobLog.id).label("count"))

                if job_id:
                    query = query.filter(JobLog.job_id == job_id)

                query = query.group_by(JobLog.level)

                results = query.all()
                counts: dict[str, int] = {row[0]: row[1] for row in results}

                logger.debug("Log counts by level", job_id=job_id, counts=counts)
                return counts

        except Exception as e:
            logger.error("Failed to count logs by level", job_id=job_id, error=str(e))
            raise DatabaseError("count logs by level", e) from e
