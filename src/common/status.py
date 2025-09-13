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


class BatchStatus(Enum):
    """Status enumeration specifically for batch operations."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobPriority(Enum):
    """Priority enumeration for jobs (1-10 scale)."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 15


# For backward compatibility, alias the most commonly used status
CommonStatus = JobStatus
