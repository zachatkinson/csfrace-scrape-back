"""Comprehensive test suite for StatisticsService following TEST_BUILDING.md standards.

This module tests all statistics-related database operations:
- Job statistics calculation with status breakdown
- Performance metrics and percentiles
- Hourly distribution analysis
- Retry statistics
- Size statistics
- Domain-specific filtering
- Edge cases and validation
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.common.status import JobStatus
from src.database.models.auth import (
    User,  # noqa: F401 - Import at module level for test_database_engine
)
from src.database.models.jobs import ScrapingJob
from src.database.services.job_service import JobService
from src.database.services.statistics_service import StatisticsService
from tests.conftest import JobFactory


class TestStatisticsServiceJobStatistics:
    """Test job statistics calculation."""

    @pytest.mark.database
    def test_get_job_statistics_basic(self, test_session):
        """Test basic job statistics calculation."""
        # Arrange
        # Cleanup any existing jobs from other tests to ensure isolation
        test_session.query(ScrapingJob).delete()
        test_session.commit()

        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs with different statuses
        completed_job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(
            completed_job.id, JobStatus.COMPLETED, processing_time_ms=1000
        )

        failed_job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(failed_job.id, JobStatus.FAILED)

        pending_job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        assert stats["total_jobs"] == 3
        assert stats["status_breakdown"]["COMPLETED"] == 1
        assert stats["status_breakdown"]["FAILED"] == 1
        assert stats["status_breakdown"]["PENDING"] == 1
        assert stats["success_rate"] == 33.33  # 1/3 * 100
        assert stats["average_processing_time_ms"] == 1000.0
        assert "period_days" in stats
        assert "start_date" in stats
        assert "end_date" in stats

    @pytest.mark.database
    def test_get_job_statistics_no_jobs(self, test_session):
        """Test statistics with no jobs."""
        # Arrange
        # Cleanup any existing jobs to ensure zero-job scenario
        test_session.query(ScrapingJob).delete()
        test_session.commit()

        stats_service = StatisticsService(test_session)

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        assert stats["total_jobs"] == 0
        assert stats["success_rate"] == 0
        assert stats["average_processing_time_ms"] == 0
        assert stats["top_domains"] == []
        assert len(stats["hourly_distribution"]) == 24  # Full 24-hour distribution

    @pytest.mark.database
    def test_get_job_statistics_custom_period(self, test_session):
        """Test statistics with custom time period."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create old job (outside period)
        old_job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        old_job.created_at = datetime.now(UTC) - timedelta(days=31)
        test_session.commit()

        # Create recent job (inside period)
        recent_job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=30)

        # Assert
        assert stats["total_jobs"] == 1  # Only recent job
        assert stats["period_days"] == 30

    @pytest.mark.database
    def test_get_job_statistics_top_domains(self, test_session):
        """Test top domains calculation."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs for different domains
        for _ in range(3):
            job_service.create_job(
                JobFactory.create_job_request(session=test_session, url="https://example.com/test")
            )

        for _ in range(2):
            job_service.create_job(
                JobFactory.create_job_request(session=test_session, url="https://test.com/page")
            )

        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        assert len(stats["top_domains"]) == 2
        assert stats["top_domains"][0]["domain"] == "example.com"
        assert stats["top_domains"][0]["count"] == 3
        assert stats["top_domains"][1]["domain"] == "test.com"
        assert stats["top_domains"][1]["count"] == 2

    @pytest.mark.database
    def test_get_job_statistics_hourly_distribution(self, test_session):
        """Test hourly distribution calculation."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs at different times
        for _ in range(5):
            job_service.create_job(JobFactory.create_job_request(session=test_session))

        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        assert "hourly_distribution" in stats
        assert len(stats["hourly_distribution"]) == 24
        # Should have all hours 00-23
        for hour in range(24):
            assert str(hour).zfill(2) in stats["hourly_distribution"]

    @pytest.mark.database
    def test_get_job_statistics_retry_stats(self, test_session):
        """Test retry statistics calculation."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs with retries
        job1 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job1.retry_count = 2
        job2 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job2.retry_count = 1
        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        retry_stats = stats["retry_statistics"]
        assert retry_stats["jobs_with_retries"] == 2
        assert retry_stats["average_retry_count"] == 1.5  # (2+1)/2
        assert retry_stats["max_retry_count"] == 2

    @pytest.mark.database
    def test_get_job_statistics_size_stats(self, test_session):
        """Test size statistics calculation."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create completed jobs with sizes
        job1 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job1.output_size_bytes = 1000
        job1.download_size_bytes = 2000
        job_service.update_job_status(job1.id, JobStatus.COMPLETED)

        job2 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job2.output_size_bytes = 500
        job2.download_size_bytes = 1500
        job_service.update_job_status(job2.id, JobStatus.COMPLETED)

        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        assert stats["total_content_size_bytes"] == 1500  # 1000 + 500
        assert stats["total_download_size_bytes"] == 3500  # 2000 + 1500


class TestStatisticsServicePerformanceMetrics:
    """Test performance metrics calculation."""

    @pytest.mark.database
    def test_get_performance_metrics_basic(self, test_session):
        """Test basic performance metrics calculation."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create completed jobs with processing times
        for time_ms in [1000, 2000, 3000, 4000, 5000]:
            job = job_service.create_job(JobFactory.create_job_request(session=test_session))
            job_service.update_job_status(job.id, JobStatus.COMPLETED, processing_time_ms=time_ms)

        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(days=30)

        # Assert
        assert metrics["min_processing_time_ms"] == 1000.0
        assert metrics["max_processing_time_ms"] == 5000.0
        assert metrics["avg_processing_time_ms"] == 3000.0
        assert metrics["sample_size"] == 5
        assert metrics["domain"] == "all"
        assert metrics["period_days"] == 30

    @pytest.mark.database
    def test_get_performance_metrics_no_completed_jobs(self, test_session):
        """Test performance metrics with no completed jobs."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create pending job only
        job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(days=30)

        # Assert
        assert metrics["min_processing_time_ms"] == 0
        assert metrics["max_processing_time_ms"] == 0
        assert metrics["avg_processing_time_ms"] == 0
        assert metrics["sample_size"] == 0

    @pytest.mark.database
    def test_get_performance_metrics_domain_filter(self, test_session):
        """Test performance metrics with domain filter."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs for different domains
        job1 = job_service.create_job(
            JobFactory.create_job_request(session=test_session, url="https://example.com/test")
        )
        job_service.update_job_status(job1.id, JobStatus.COMPLETED, processing_time_ms=1000)

        job2 = job_service.create_job(
            JobFactory.create_job_request(session=test_session, url="https://test.com/page")
        )
        job_service.update_job_status(job2.id, JobStatus.COMPLETED, processing_time_ms=2000)

        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(domain="example.com", days=30)

        # Assert
        assert metrics["domain"] == "example.com"
        assert metrics["sample_size"] == 1
        assert metrics["avg_processing_time_ms"] == 1000.0

    @pytest.mark.database
    def test_get_performance_metrics_percentiles(self, test_session):
        """Test percentiles calculation with sufficient data."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create 20 jobs with varying processing times (need >= 10 for percentiles)
        for i in range(20):
            job = job_service.create_job(JobFactory.create_job_request(session=test_session))
            job_service.update_job_status(
                job.id, JobStatus.COMPLETED, processing_time_ms=1000 + (i * 100)
            )

        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(days=30)

        # Assert
        assert "percentiles" in metrics
        assert "p50" in metrics["percentiles"]
        assert "p75" in metrics["percentiles"]
        assert "p90" in metrics["percentiles"]
        assert "p95" in metrics["percentiles"]
        assert "p99" in metrics["percentiles"]
        assert metrics["sample_size"] == 20

    @pytest.mark.database
    def test_get_performance_metrics_no_percentiles_small_sample(self, test_session):
        """Test that percentiles are not calculated with small sample size."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create only 5 jobs (< 10 threshold)
        for _ in range(5):
            job = job_service.create_job(JobFactory.create_job_request(session=test_session))
            job_service.update_job_status(job.id, JobStatus.COMPLETED, processing_time_ms=1000)

        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(days=30)

        # Assert
        assert "percentiles" not in metrics
        assert metrics["sample_size"] == 5


class TestStatisticsServiceHelperMethods:
    """Test helper methods."""

    @pytest.mark.database
    def test_calculate_hourly_distribution_empty(self, test_session):
        """Test hourly distribution with no jobs."""
        # Arrange
        stats_service = StatisticsService(test_session)
        start_date = datetime.now(UTC) - timedelta(days=7)
        end_date = datetime.now(UTC)

        # Act
        distribution = stats_service._calculate_hourly_distribution(
            test_session, start_date, end_date
        )

        # Assert
        assert len(distribution) == 24
        for hour in range(24):
            assert distribution[str(hour).zfill(2)] == 0

    @pytest.mark.database
    def test_calculate_retry_statistics_no_retries(self, test_session):
        """Test retry statistics with no retries."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs with no retries
        job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        start_date = datetime.now(UTC) - timedelta(days=7)

        # Act
        retry_stats = stats_service._calculate_retry_statistics(test_session, start_date)

        # Assert
        assert retry_stats["jobs_with_retries"] == 0
        assert retry_stats["average_retry_count"] == 0
        assert retry_stats["max_retry_count"] == 0

    @pytest.mark.database
    def test_calculate_size_statistics_no_sizes(self, test_session):
        """Test size statistics with no size data."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create completed job without sizes
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(job.id, JobStatus.COMPLETED)
        test_session.commit()

        start_date = datetime.now(UTC) - timedelta(days=7)

        # Act
        size_stats = stats_service._calculate_size_statistics(test_session, start_date)

        # Assert
        assert size_stats["total_output_size"] == 0
        assert size_stats["total_download_size"] == 0

    @pytest.mark.database
    def test_calculate_percentiles_empty(self, test_session):
        """Test percentiles calculation with no data."""
        # Arrange
        stats_service = StatisticsService(test_session)
        start_date = datetime.now(UTC) - timedelta(days=30)

        # Act
        percentiles = stats_service._calculate_percentiles(test_session, start_date, None)

        # Assert
        assert percentiles == {}

    @pytest.mark.database
    def test_calculate_percentiles_with_domain_filter(self, test_session):
        """Test percentiles calculation with domain filter."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs for specific domain
        for i in range(15):
            job = job_service.create_job(
                JobFactory.create_job_request(session=test_session, url="https://example.com/test")
            )
            job_service.update_job_status(
                job.id, JobStatus.COMPLETED, processing_time_ms=1000 + (i * 100)
            )

        # Create jobs for different domain
        for i in range(10):
            job = job_service.create_job(
                JobFactory.create_job_request(session=test_session, url="https://other.com/test")
            )
            job_service.update_job_status(job.id, JobStatus.COMPLETED, processing_time_ms=5000)

        test_session.commit()

        start_date = datetime.now(UTC) - timedelta(days=30)

        # Act
        percentiles = stats_service._calculate_percentiles(test_session, start_date, "example.com")

        # Assert
        assert "p50" in percentiles
        assert "p99" in percentiles
        # Should only include example.com jobs, not other.com


class TestStatisticsServiceEdgeCases:
    """Test edge cases and validation."""

    @pytest.mark.database
    def test_get_job_statistics_zero_days(self, test_session):
        """Test statistics with zero days period."""
        # Arrange
        stats_service = StatisticsService(test_session)

        # Act
        stats = stats_service.get_job_statistics(days=0)

        # Assert
        assert stats["period_days"] == 0
        assert stats["total_jobs"] == 0

    @pytest.mark.database
    def test_get_job_statistics_all_statuses(self, test_session):
        """Test statistics with all possible job statuses."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs for each status
        for status in [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED]:
            job = job_service.create_job(JobFactory.create_job_request(session=test_session))
            job_service.update_job_status(job.id, status)

        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=7)

        # Assert
        assert stats["total_jobs"] == 4
        assert stats["status_breakdown"]["PENDING"] == 1
        assert stats["status_breakdown"]["RUNNING"] == 1
        assert stats["status_breakdown"]["COMPLETED"] == 1
        assert stats["status_breakdown"]["FAILED"] == 1

    @pytest.mark.database
    def test_get_performance_metrics_null_processing_times(self, test_session):
        """Test performance metrics with null processing times."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create completed job without processing time
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(job.id, JobStatus.COMPLETED)
        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(days=30)

        # Assert
        assert metrics["sample_size"] == 0  # Null times excluded
        assert metrics["avg_processing_time_ms"] == 0

    @pytest.mark.database
    def test_get_job_statistics_large_period(self, test_session):
        """Test statistics with very large time period."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create job
        job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act
        stats = stats_service.get_job_statistics(days=365)

        # Assert
        assert stats["period_days"] == 365
        assert stats["total_jobs"] == 1

    @pytest.mark.database
    def test_get_performance_metrics_extreme_values(self, test_session):
        """Test performance metrics with extreme processing time values."""
        # Arrange
        job_service = JobService(test_session)
        stats_service = StatisticsService(test_session)

        # Create jobs with extreme values
        job1 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(
            job1.id, JobStatus.COMPLETED, processing_time_ms=1
        )  # Very fast

        job2 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job_service.update_job_status(
            job2.id, JobStatus.COMPLETED, processing_time_ms=1000000
        )  # Very slow

        test_session.commit()

        # Act
        metrics = stats_service.get_performance_metrics(days=30)

        # Assert
        assert metrics["min_processing_time_ms"] == 1.0
        assert metrics["max_processing_time_ms"] == 1000000.0
        assert metrics["sample_size"] == 2
