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


class MockSessionFactory:
    """Factory for creating mock database sessions following DRY principles.

    This class provides standardized mock session creation for unit testing,
    following the SOLID principle of Single Responsibility.
    """

    @staticmethod
    def create_mock_session(mocker, commit_side_effect=None) -> Any:
        """Create a mock database session with standard behavior.

        Args:
            mocker: pytest-mock fixture
            commit_side_effect: Optional exception to raise on commit

        Returns:
            MagicMock: Configured mock session
        """
        mock_session = mocker.MagicMock()

        # Configure context manager behavior
        mock_session.__enter__ = mocker.MagicMock(return_value=mock_session)
        mock_session.__exit__ = mocker.MagicMock(return_value=None)

        # Configure standard session methods
        mock_session.add = mocker.MagicMock()
        mock_session.commit = mocker.MagicMock()
        mock_session.rollback = mocker.MagicMock()
        mock_session.close = mocker.MagicMock()
        mock_session.flush = mocker.MagicMock()
        mock_session.query = mocker.MagicMock()

        # Set up commit side effect if provided
        if commit_side_effect:
            mock_session.commit.side_effect = commit_side_effect

        return mock_session

    @staticmethod
    def create_mock_service(mocker, commit_side_effect=None) -> tuple[Any, Any]:
        """Create a DatabaseService with mocked session factory.

        Args:
            mocker: pytest-mock fixture
            commit_side_effect: Optional exception to raise on commit

        Returns:
            Tuple[Any, Any]: (mocked_service, mock_session)
        """
        from src.database.service import DatabaseService

        # Create mock session using DRY factory method
        mock_session = MockSessionFactory.create_mock_session(mocker, commit_side_effect)

        # Create mock session factory that returns our mock session
        mock_session_factory = mocker.MagicMock(return_value=mock_session)

        # Create service with mocked dependencies
        service = DatabaseService()
        service.SessionLocal = mock_session_factory

        return service, mock_session
