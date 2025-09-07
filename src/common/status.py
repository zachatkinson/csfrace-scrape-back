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


# For backward compatibility, alias the most commonly used status
CommonStatus = JobStatus
