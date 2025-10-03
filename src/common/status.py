"""Common status definitions shared across the application.

This module provides centralized status enumerations to eliminate
duplication and ensure consistency across different components.
"""

from enum import Enum


class JobStatus(Enum):
    """Status enumeration for jobs (scraping jobs, batch jobs, etc.)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # For partially completed jobs


class JobPriority(Enum):
    """Priority enumeration for jobs."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Database mapping for priority field (INTEGER in database, string in enum)
PRIORITY_TO_DB_MAP = {
    JobPriority.LOW: 1,
    JobPriority.NORMAL: 5,
    JobPriority.HIGH: 8,
    JobPriority.URGENT: 10,
}

# Reverse mapping for converting database integer back to enum
DB_TO_PRIORITY_MAP = {v: k for k, v in PRIORITY_TO_DB_MAP.items()}


def priority_to_db(priority: JobPriority | str) -> int:
    """Convert priority enum or string to database integer value.

    Args:
        priority: JobPriority enum instance or string value

    Returns:
        Integer value for database storage

    Raises:
        ValueError: If priority value is invalid
    """
    if isinstance(priority, str):
        # Convert string to enum first
        try:
            priority = JobPriority(priority)
        except ValueError as e:
            raise ValueError(f"Invalid priority string: {priority}") from e

    return PRIORITY_TO_DB_MAP[priority]


def db_to_priority(db_value: int) -> JobPriority:
    """Convert database integer value to priority enum.

    Args:
        db_value: Integer value from database

    Returns:
        JobPriority enum instance

    Raises:
        ValueError: If database value is invalid
    """
    if db_value not in DB_TO_PRIORITY_MAP:
        raise ValueError(f"Invalid priority database value: {db_value}")

    return DB_TO_PRIORITY_MAP[db_value]
