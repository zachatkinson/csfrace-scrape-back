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
from sqlalchemy.orm import Session

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_database_logger

from ...core.exceptions import ValidationError
from ..models import JobLog

logger = get_database_logger(__name__).logger


@dataclass
class JobLogRequest:
    """Request object for creating job log entries."""

    job_id: str
    level: str
    message: str
    component: str | None = None
    operation: str | None = None
    context_data: dict[str, Any] | None = None

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
        # Keep context_data as None if not provided, don't convert to empty dict
        if self.context_data is None:
            self.context_data = None
        else:
            self.context_data = self.context_data or {}


class LoggingService:
    """Service for job logging operations."""

    def __init__(self, session: Session):
        """Initialize with provided database session.

        Args:
            session: SQLAlchemy session to use for database operations
        """
        self.session = session

    @database_error_handler("add job log")
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

        log_entry = JobLog(
            job_id=request.job_id,
            level=request.level,
            message=request.message,
            component=request.component,
            operation=request.operation,
            context_data=request.context_data,
            timestamp=datetime.now(UTC),
        )

        self.session.add(log_entry)
        self.session.flush()

        # Eagerly load all attributes to prevent DetachedInstanceError
        _ = (
            log_entry.id,
            log_entry.job_id,
            log_entry.level,
            log_entry.message,
            log_entry.component,
            log_entry.operation,
            log_entry.context_data,
            log_entry.timestamp,
            log_entry.exception_type,
            log_entry.exception_traceback,
        )

        # Detach from session for safe return
        self.session.expunge(log_entry)

        logger.debug(
            "Job log added successfully",
            job_id=request.job_id,
            log_id=log_entry.id,
            level=request.level,
        )
        return log_entry

    @database_error_handler("get job logs")
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

        session = self.session
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

    @database_error_handler("get recent logs")
    def get_recent_logs(self, limit: int = 100) -> list[JobLog]:
        """Get most recent log entries across all jobs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of recent log entries ordered by creation time
        """
        logger.debug("Getting recent logs", limit=limit)

        session = self.session
        stmt = select(JobLog).order_by(desc(JobLog.timestamp)).limit(limit)

        logs = session.execute(stmt).scalars().all()

        logger.debug("Recent logs retrieved", count=len(logs))
        return list(logs)

    @database_error_handler("get error logs")
    def get_error_logs(self, limit: int = 50) -> list[JobLog]:
        """Get error-level log entries.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of error log entries ordered by creation time
        """
        logger.debug("Getting error logs", limit=limit)

        session = self.session
        stmt = (
            select(JobLog)
            .where(JobLog.level.in_(["ERROR", "CRITICAL"]))
            .order_by(desc(JobLog.timestamp))
            .limit(limit)
        )

        logs = session.execute(stmt).scalars().all()

        logger.debug("Error logs retrieved", count=len(logs))
        return list(logs)

    @database_error_handler("count logs by level")
    def count_logs_by_level(self, job_id: str | None = None) -> dict[str, int]:
        """Count log entries by level.

        Args:
            job_id: Optional job ID to filter by

        Returns:
            Dictionary with log level counts
        """
        logger.debug("Counting logs by level", job_id=job_id)

        session = self.session
        from sqlalchemy import func

        query = session.query(JobLog.level, func.count(JobLog.id).label("count"))

        if job_id:
            query = query.filter(JobLog.job_id == job_id)

        query = query.group_by(JobLog.level)

        results = query.all()
        counts: dict[str, int] = {row[0]: row[1] for row in results}

        logger.debug("Log counts by level", job_id=job_id, counts=counts)
        return counts
