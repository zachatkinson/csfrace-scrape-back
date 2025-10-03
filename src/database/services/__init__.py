"""Database services package.

This package contains focused database services following Single Responsibility Principle.
Each service handles a specific domain of database operations.

Services:
- JobService: Job management operations (CRUD, batch processing, status updates)
- ContentService: Content and result management operations
- LoggingService: Job logging operations
- StatisticsService: Analytics and metrics operations
- CleanupService: Database maintenance and cleanup operations
"""

from .base import BaseService
from .cleanup_service import CleanupService
from .content_service import ContentService
from .job_service import JobService
from .logging_service import LoggingService
from .statistics_service import StatisticsService

__all__ = [
    "BaseService",
    "CleanupService",
    "ContentService",
    "JobService",
    "LoggingService",
    "StatisticsService",
]
