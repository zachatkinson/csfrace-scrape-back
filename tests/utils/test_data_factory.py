"""Test data factory utilities following SOLID principles and DRY standards.

This module provides utilities for creating isolated test data that prevents
data bleeding between concurrent tests, following PostgreSQL and pytest best practices.
"""

from dataclasses import dataclass
from typing import Any

from src.database.models import JobPriority


@dataclass(frozen=True)
class DataSpec:
    """Specification for test data creation following Single Responsibility Principle."""

    base_url: str
    test_id: str
    priority: JobPriority = JobPriority.NORMAL
    output_directory: str = "/tmp/test"

    @property
    def unique_url(self) -> str:
        """Generate unique URL for test isolation."""
        return f"{self.base_url}-{self.test_id}"


class JobFactory:
    """Factory for creating test jobs following Factory Pattern and DRY principles.

    This class ensures consistent job creation across all tests while maintaining
    data isolation through unique identifiers.
    """

    def __init__(self, test_id: str):
        """Initialize factory with unique test identifier.

        Args:
            test_id: Unique identifier for test isolation
        """
        self.test_id = test_id

    def create_job_spec(
        self,
        base_url: str,
        priority: JobPriority = JobPriority.NORMAL,
        output_directory: str = "/tmp/test",
    ) -> DataSpec:
        """Create job specification with unique identifier.

        Args:
            base_url: Base URL for the job
            priority: Job priority level
            output_directory: Output directory path

        Returns:
            DataSpec: Immutable specification for job creation
        """
        return DataSpec(
            base_url=base_url,
            test_id=self.test_id,
            priority=priority,
            output_directory=output_directory,
        )

    def create_priority_test_jobs(self) -> list[DataSpec]:
        """Create complete set of priority test jobs following DRY principles.

        Returns:
            List[DataSpec]: Specifications for all priority levels
        """
        return [
            self.create_job_spec("https://example.com/priority-test-urgent", JobPriority.URGENT),
            self.create_job_spec("https://example.com/priority-test-high", JobPriority.HIGH),
            self.create_job_spec("https://example.com/priority-test-normal", JobPriority.NORMAL),
            self.create_job_spec("https://example.com/priority-test-low", JobPriority.LOW),
        ]

    def create_status_test_jobs(self) -> dict[str, DataSpec]:
        """Create jobs for status testing following DRY principles.

        Returns:
            Dict[str, DataSpec]: Named job specifications for status tests
        """
        return {
            "pending": self.create_job_spec("https://example.com/exclude-test-pending"),
            "running": self.create_job_spec("https://example.com/exclude-test-running"),
            "completed": self.create_job_spec("https://example.com/exclude-test-completed"),
        }

    def create_statistics_test_jobs(self) -> dict[str, list[DataSpec]]:
        """Create jobs for statistics testing following DRY principles.

        Returns:
            Dict[str, List[DataSpec]]: Categorized job specifications
        """
        completed_jobs = [
            self.create_job_spec(f"https://example.com/stats-completed-{i}") for i in range(5)
        ]

        failed_jobs = [
            self.create_job_spec(f"https://example.com/stats-failed-{i}") for i in range(3)
        ]

        return {"completed": completed_jobs, "failed": failed_jobs}


class DataMatcher:
    """Utility for filtering test data following Single Responsibility Principle."""

    @staticmethod
    def filter_jobs_by_test_id(jobs: list[Any], test_id: str) -> list[Any]:
        """Filter jobs to only those belonging to current test.

        Args:
            jobs: List of job objects
            test_id: Test isolation identifier

        Returns:
            List[Any]: Jobs belonging to current test only
        """
        return [job for job in jobs if test_id in job.url]

    @staticmethod
    def assert_job_count(
        actual_jobs: list[Any], expected_count: int, test_context: str = "test"
    ) -> None:
        """Assert job count with detailed error message.

        Args:
            actual_jobs: Actual jobs found
            expected_count: Expected number of jobs
            test_context: Context description for error messages
        """
        actual_count = len(actual_jobs)
        if actual_count != expected_count:
            job_urls = [job.url for job in actual_jobs]
            raise AssertionError(
                f"{test_context}: Expected {expected_count} jobs, got {actual_count}. "
                f"Job URLs: {job_urls}"
            )
