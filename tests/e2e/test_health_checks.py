"""Minimal E2E tests for critical backend health checks following audit_3.md standards.

Simple end-to-end tests for essential backend functionality that users depend on.
These tests verify that core services are working together correctly.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from src.common.status import JobStatus
from src.database.services.cleanup_service import CleanupService
from src.database.services.job_service import JobService
from tests.conftest import JobFactory


class TestCriticalHealthChecks:
    """E2E tests for critical backend health and functionality."""

    @pytest.mark.e2e
    @pytest.mark.database
    def test_database_connection_health(self, test_session):
        """Test that database connection is healthy and responsive."""
        # Arrange - Act
        # Simple query to verify database connectivity
        result = test_session.execute(text("SELECT 1 as health_check")).first()

        # Assert
        assert result is not None
        assert result[0] == 1

    @pytest.mark.e2e
    @pytest.mark.database
    def test_job_creation_and_retrieval_e2e(self, test_session):
        """Test complete job creation and retrieval workflow."""
        # Arrange
        job_service = JobService(session=test_session)
        job_request = JobFactory.create_job_request(
            session=test_session, url="https://example.com/e2e-test"
        )

        # Act - Create job
        created_job = job_service.create_job(job_request)

        # Act - Retrieve job
        retrieved_job = job_service.get_job(created_job.id)

        # Assert
        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.source_url == job_request.url

    @pytest.mark.e2e
    @pytest.mark.database
    def test_cleanup_service_basic_health(self, test_session):
        """Test that cleanup service can perform basic operations."""
        # Arrange
        cleanup_service = CleanupService(session=test_session)

        # Act - Run basic cleanup operations
        orphaned_content_deleted = cleanup_service.cleanup_orphaned_content()
        orphaned_logs_deleted = cleanup_service.cleanup_orphaned_logs()

        # Assert - Operations complete without errors
        assert isinstance(orphaned_content_deleted, int)
        assert isinstance(orphaned_logs_deleted, int)
        assert orphaned_content_deleted >= 0
        assert orphaned_logs_deleted >= 0

    @pytest.mark.e2e
    @pytest.mark.database
    def test_database_size_monitoring_health(self, test_session):
        """Test database size monitoring functionality."""
        # Arrange
        cleanup_service = CleanupService(session=test_session)

        # Act
        size_info = cleanup_service.get_database_size()
        table_sizes = cleanup_service.get_table_sizes()

        # Assert
        assert isinstance(size_info, dict)
        assert "total_size_bytes" in size_info
        assert "total_size_pretty" in size_info

        assert isinstance(table_sizes, list)
        # In test environment, there might be no tables or empty tables
        if table_sizes:
            for table_info in table_sizes:
                assert "schema" in table_info
                assert "table" in table_info
                assert "size_pretty" in table_info
                assert "size_bytes" in table_info

    @pytest.mark.e2e
    def test_service_initialization_health(self, test_session):
        """Test that core services can be initialized properly."""
        # Arrange - Act
        job_service = JobService(session=test_session)
        cleanup_service = CleanupService(session=test_session)

        # Assert
        assert job_service.session is test_session
        assert cleanup_service.session is test_session

    @pytest.mark.e2e
    @pytest.mark.database
    def test_comprehensive_workflow_health(self, test_session):
        """Test a comprehensive workflow that exercises multiple services."""
        # Arrange
        job_service = JobService(session=test_session)
        cleanup_service = CleanupService(session=test_session)

        # Act - Create multiple jobs
        urls = ["https://example.com/health-test-1", "https://example.com/health-test-2"]
        user_id = JobFactory._ensure_user_exists(test_session)
        batch_jobs = job_service.create_jobs(
            urls, user_id=user_id, output_directory="/tmp/health_test"
        )

        # Act - Update job statuses
        for job in batch_jobs:
            job_service.update_job_status(job.id, JobStatus.RUNNING)
            job_service.update_job_status(job.id, JobStatus.COMPLETED)

        # Act - Get pending jobs (should be none since all completed)
        pending_jobs = job_service.get_pending_jobs()

        # Act - Get batch summary
        batch_id = batch_jobs[0].batch_id
        summary = job_service.get_batch_summary(batch_id)

        # Act - Run cleanup
        cleanup_results = cleanup_service.cleanup_all()

        # Assert - All operations completed successfully
        assert len(batch_jobs) == 2
        assert all(job.batch_id == batch_id for job in batch_jobs)

        # Pending jobs should not include our completed jobs
        completed_job_ids = {job.id for job in batch_jobs}
        pending_job_ids = {job.id for job in pending_jobs}
        assert not completed_job_ids.intersection(pending_job_ids)

        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 2

        assert isinstance(cleanup_results, dict)
        assert all(
            key in cleanup_results
            for key in [
                "old_jobs_deleted",
                "failed_jobs_deleted",
                "orphaned_content_deleted",
                "orphaned_logs_deleted",
                "vacuum_performed",
            ]
        )


class TestSystemIntegrityChecks:
    """E2E tests for system integrity and data consistency."""

    @pytest.mark.e2e
    @pytest.mark.database
    def test_data_consistency_across_services(self, test_session):
        """Test data consistency when multiple services interact."""
        # Arrange
        job_service = JobService(session=test_session)

        # Act - Create job through service
        job_request = JobFactory.create_job_request(session=test_session)
        created_job = job_service.create_job(job_request)

        # Act - Retrieve through different service method
        retrieved_by_id = job_service.get_job(created_job.id)
        pending_jobs = job_service.get_pending_jobs()

        # Assert - Data consistency
        assert retrieved_by_id.id == created_job.id
        assert retrieved_by_id.source_url == created_job.source_url

        # Job should appear in pending jobs list
        pending_job_ids = [job.id for job in pending_jobs]
        assert created_job.id in pending_job_ids

    @pytest.mark.e2e
    @pytest.mark.database
    def test_foreign_key_integrity_across_operations(self, test_session):
        """Test that foreign key relationships remain intact across operations."""
        # Arrange
        job_service = JobService(session=test_session)
        cleanup_service = CleanupService(session=test_session)

        # Act - Create job and verify it exists
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_id = job.id

        # Act - Run cleanup (should not affect new job)
        cleanup_service.cleanup_orphaned_content()
        cleanup_service.cleanup_orphaned_logs()

        # Act - Verify job still exists after cleanup
        retrieved_job = job_service.get_job(job_id)

        # Assert - Job integrity maintained
        assert retrieved_job is not None
        assert retrieved_job.id == job_id

    @pytest.mark.e2e
    @pytest.mark.database
    @pytest.mark.performance
    def test_system_performance_under_load(self, test_session):
        """Test system performance with moderate load."""
        # Arrange
        job_service = JobService(session=test_session)
        start_time = datetime.now(UTC)

        # Act - Create multiple jobs rapidly
        urls = [f"https://example.com/load-test-{i}" for i in range(10)]
        user_id = JobFactory._ensure_user_exists(test_session)
        batch_jobs = job_service.create_jobs(
            urls, user_id=user_id, output_directory="/tmp/load_test"
        )

        # Act - Perform multiple operations
        for job in batch_jobs[:5]:
            job_service.update_job_status(job.id, JobStatus.RUNNING)
            job_service.update_job_status(job.id, JobStatus.COMPLETED)

        # Act - Query operations
        pending_jobs = job_service.get_pending_jobs(limit=20)
        completed_jobs = job_service.get_jobs_by_status(JobStatus.COMPLETED, limit=20)

        end_time = datetime.now(UTC)
        total_time = (end_time - start_time).total_seconds()

        # Assert - Performance within acceptable limits
        assert total_time < 5.0  # Should complete within 5 seconds
        assert len(batch_jobs) == 10
        assert len(completed_jobs) >= 5
        assert len(pending_jobs) >= 5

    @pytest.mark.e2e
    @pytest.mark.database
    def test_error_recovery_and_resilience(self, test_session):
        """Test system resilience and error recovery."""
        # Arrange
        job_service = JobService(session=test_session)

        # Act - Create job and simulate failure
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(job.id, JobStatus.RUNNING)
        failed_job = job_service.update_job_status(
            job.id, JobStatus.FAILED, error_message="Simulated failure for resilience test"
        )

        # Act - Verify system can handle and query failed jobs
        retry_jobs = job_service.get_retry_jobs()
        failed_jobs = job_service.get_jobs_by_status(JobStatus.FAILED)

        # Assert - System handles failures gracefully
        assert failed_job.status == "failed"
        assert failed_job.error_message == "Simulated failure for resilience test"

        # Job should appear in retry and failed job queries
        retry_job_ids = [j.id for j in retry_jobs]
        failed_job_ids = [j.id for j in failed_jobs]

        assert job.id in retry_job_ids
        assert job.id in failed_job_ids


class TestMinimalAPIHealthChecks:
    """Minimal E2E tests for API-level health checks."""

    @pytest.mark.e2e
    def test_service_dependencies_health(self, test_session):
        """Test that service dependencies are properly injected and working."""
        # Arrange
        job_service = JobService(session=test_session)
        cleanup_service = CleanupService(session=test_session)

        # Act - Verify services have required dependencies
        assert hasattr(job_service, "session")
        assert hasattr(cleanup_service, "session")
        assert job_service.session is not None
        assert cleanup_service.session is not None

        # Act - Verify services can perform basic operations
        # This tests that session dependency injection is working
        pending_jobs = job_service.get_pending_jobs(limit=1)
        size_info = cleanup_service.get_database_size()

        # Assert
        assert isinstance(pending_jobs, list)
        assert isinstance(size_info, dict)

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_system_stability_over_time(self, test_session):
        """Test system stability with repeated operations over time."""
        # Arrange
        job_service = JobService(session=test_session)
        cleanup_service = CleanupService(session=test_session)

        # Act - Perform repeated operations
        for cycle in range(3):
            # Create jobs
            urls = [f"https://example.com/stability-{cycle}-{i}" for i in range(3)]
            user_id = JobFactory._ensure_user_exists(test_session)
            jobs = job_service.create_jobs(
                urls, user_id=user_id, output_directory=f"/tmp/stability_{cycle}"
            )

            # Process jobs
            for job in jobs:
                job_service.update_job_status(job.id, JobStatus.RUNNING)
                job_service.update_job_status(job.id, JobStatus.COMPLETED)

            # Query operations
            pending = job_service.get_pending_jobs()
            completed = job_service.get_jobs_by_status(JobStatus.COMPLETED)

            # Cleanup operations
            cleanup_results = cleanup_service.cleanup_orphaned_content()

            # Assert - Each cycle completes successfully
            assert len(jobs) == 3
            assert isinstance(pending, list)
            assert isinstance(completed, list)
            assert isinstance(cleanup_results, int)

        # Final assertion - System remains stable
        final_pending = job_service.get_pending_jobs()
        assert isinstance(final_pending, list)
