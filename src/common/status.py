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


# For backward compatibility, alias the most commonly used status
CommonStatus = JobStatus
