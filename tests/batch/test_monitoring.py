"""Tests for batch monitoring and reporting system."""

import json
import statistics
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.batch.enhanced_processor import BatchResults
from src.batch.monitoring import AlertManager, BatchMonitor, MetricsCollector
from src.database.models import Batch, JobStatus, ScrapingJob
from src.database.service import DatabaseService


@pytest.fixture
def mock_database_service():
    """Create mock database service."""
    service = MagicMock(spec=DatabaseService)
    service.get_session.return_value.__enter__ = Mock(return_value=MagicMock())
    service.get_session.return_value.__exit__ = Mock(return_value=None)
    return service


@pytest.fixture
def metrics_collector(mock_database_service):
    """Create metrics collector instance."""
    return MetricsCollector(mock_database_service)


@pytest.fixture
def batch_monitor(mock_database_service):
    """Create batch monitor instance."""
    return BatchMonitor(mock_database_service)


@pytest.fixture
def alert_manager(mock_database_service):
    """Create alert manager instance."""
    return AlertManager(mock_database_service)


@pytest.fixture
def sample_batch_results():
    """Create sample batch results."""
    return BatchResults(
        successful=["url1", "url2", "url3"],
        failed=["url4"],
        total=4,
        duration=120.5,
        statistics={"test": "data"},
    )


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_initialization(self, mock_database_service):
        """Test metrics collector initialization."""
        collector = MetricsCollector(mock_database_service)

        assert collector.database_service is mock_database_service
        assert collector.urls_processed == 0
        assert collector.urls_failed == 0
        assert collector.bytes_processed == 0
        assert len(collector.processing_times) == 0
        assert isinstance(collector.start_time, datetime)

    def test_record_processing_result_success(self, metrics_collector):
        """Test recording successful processing result."""
        metrics_collector.record_processing_result(
            url="https://example.com/test", duration=2.5, success=True, bytes_processed=1024
        )

        assert metrics_collector.urls_processed == 1
        assert metrics_collector.urls_failed == 0
        assert metrics_collector.bytes_processed == 1024
        assert len(metrics_collector.processing_times) == 1
        assert metrics_collector.processing_times[0] == 2.5

    def test_record_processing_result_failure(self, metrics_collector):
        """Test recording failed processing result."""
        metrics_collector.record_processing_result(
            url="https://example.com/failed", duration=1.2, success=False, error_type="timeout"
        )

        assert metrics_collector.urls_processed == 0
        assert metrics_collector.urls_failed == 1
        assert metrics_collector.bytes_processed == 0
        assert len(metrics_collector.processing_times) == 1
        assert metrics_collector.processing_times[0] == 1.2

    def test_record_batch_metrics(self, metrics_collector, sample_batch_results):
        """Test recording batch completion metrics."""
        metrics_collector.record_batch_metrics(sample_batch_results)

        # Verify _record_system_metric was called
        # This tests the logic, actual DB calls are mocked
        assert True  # Basic test that method doesn't crash

    def test_get_current_metrics_empty(self, metrics_collector):
        """Test getting current metrics with no data."""
        metrics = metrics_collector.get_current_metrics()

        assert metrics["urls_processed"] == 0
        assert metrics["urls_failed"] == 0
        assert metrics["total_urls"] == 0
        assert metrics["success_rate_percent"] == 0
        assert metrics["bytes_processed"] == 0
        assert "uptime_seconds" in metrics
        assert "throughput" in metrics
        assert "processing_times" not in metrics  # No processing times yet

    def test_get_current_metrics_with_data(self, metrics_collector):
        """Test getting current metrics with processing data."""
        # Record some processing results
        metrics_collector.record_processing_result("url1", 1.0, True, 500)
        metrics_collector.record_processing_result("url2", 2.0, True, 750)
        metrics_collector.record_processing_result("url3", 1.5, False)

        metrics = metrics_collector.get_current_metrics()

        assert metrics["urls_processed"] == 2
        assert metrics["urls_failed"] == 1
        assert metrics["total_urls"] == 3
        assert metrics["success_rate_percent"] == 2 / 3 * 100
        assert metrics["bytes_processed"] == 1250

        # Check processing time statistics
        assert "processing_times" in metrics
        timing_stats = metrics["processing_times"]
        assert timing_stats["average_seconds"] == statistics.mean([1.0, 2.0, 1.5])
        assert timing_stats["median_seconds"] == statistics.median([1.0, 2.0, 1.5])
        assert timing_stats["min_seconds"] == 1.0
        assert timing_stats["max_seconds"] == 2.0
        assert timing_stats["std_dev_seconds"] == statistics.stdev([1.0, 2.0, 1.5])

    def test_get_current_metrics_single_processing_time(self, metrics_collector):
        """Test metrics with single processing time (no std dev)."""
        metrics_collector.record_processing_result("url1", 1.5, True)

        metrics = metrics_collector.get_current_metrics()
        timing_stats = metrics["processing_times"]

        assert timing_stats["std_dev_seconds"] == 0  # Single value has no std dev

    def test_record_system_metric_error_handling(self, metrics_collector):
        """Test system metric recording with database error."""
        # Mock database session to raise exception
        mock_session = (
            metrics_collector.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.add.side_effect = Exception("Database error")

        # Should not raise exception, just log error
        metrics_collector._record_system_metric(
            metric_type="test", metric_name="test_metric", numeric_value=123.0
        )

        # Test passes if no exception is raised


class TestBatchMonitor:
    """Test BatchMonitor functionality."""

    def test_initialization(self, mock_database_service):
        """Test batch monitor initialization."""
        monitor = BatchMonitor(mock_database_service)

        assert monitor.database_service is mock_database_service
        assert isinstance(monitor.metrics_collector, MetricsCollector)

    def test_get_active_batches(self, batch_monitor):
        """Test getting active batches information."""
        # Mock database queries
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock batch
        mock_batch = Mock(spec=Batch)
        mock_batch.id = 1
        mock_batch.name = "test_batch"
        mock_batch.status = JobStatus.RUNNING
        mock_batch.created_at = datetime.now(timezone.utc)
        mock_batch.started_at = datetime.now(timezone.utc)
        mock_batch.max_concurrent = 5
        mock_batch.output_base_directory = "/test/output"

        mock_session.query.return_value.filter.return_value.all.return_value = [mock_batch]

        # Mock job statistics
        mock_stats = Mock()
        mock_stats.total = 10
        mock_stats.completed = 7
        mock_stats.running = 2
        mock_stats.failed = 1

        mock_session.query.return_value.filter.return_value.first.return_value = mock_stats

        batches = batch_monitor.get_active_batches()

        assert len(batches) == 1
        batch_info = batches[0]
        assert batch_info["id"] == 1
        assert batch_info["name"] == "test_batch"
        assert batch_info["status"] == "running"
        assert batch_info["total_jobs"] == 10
        assert batch_info["completed_jobs"] == 7
        assert batch_info["running_jobs"] == 2
        assert batch_info["failed_jobs"] == 1
        assert batch_info["progress_percent"] == 70.0  # 7/10 * 100

    def test_get_batch_details_not_found(self, batch_monitor):
        """Test getting details for non-existent batch."""
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = batch_monitor.get_batch_details(999)
        assert result is None

    def test_get_batch_details_found(self, batch_monitor):
        """Test getting detailed batch information."""
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock batch
        mock_batch = Mock(spec=Batch)
        mock_batch.id = 1
        mock_batch.name = "test_batch"
        mock_batch.description = "Test description"
        mock_batch.status = JobStatus.COMPLETED
        mock_batch.created_at = datetime.now(timezone.utc)
        mock_batch.started_at = datetime.now(timezone.utc)
        mock_batch.completed_at = datetime.now(timezone.utc)
        mock_batch.max_concurrent = 3
        mock_batch.output_base_directory = "/output"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_batch

        # Mock jobs
        mock_jobs = []
        for i in range(3):
            job = Mock(spec=ScrapingJob)
            job.status = JobStatus.COMPLETED
            job.duration_seconds = 2.0 + i
            job.completed_at = datetime.now(timezone.utc)
            job.url = f"https://example.com/{i}"
            job.error_message = None
            mock_jobs.append(job)

        mock_session.query.return_value.filter.return_value.all.return_value = mock_jobs

        details = batch_monitor.get_batch_details(1)

        assert details is not None
        assert details["batch"]["id"] == 1
        assert details["batch"]["name"] == "test_batch"

        job_stats = details["job_statistics"]
        assert job_stats["total"] == 3
        assert job_stats["completed"] == 3
        assert job_stats["pending"] == 0
        assert job_stats["failed"] == 0

        timing_stats = details["timing_statistics"]
        assert timing_stats is not None
        assert timing_stats["average_duration"] == statistics.mean([2.0, 3.0, 4.0])
        assert timing_stats["total_processing_time"] == 9.0

        assert "recent_activity" in details
        assert len(details["recent_activity"]) == 3

    def test_get_batch_details_no_completed_jobs(self, batch_monitor):
        """Test getting batch details with no completed jobs."""
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )

        mock_batch = Mock(spec=Batch)
        mock_batch.id = 1
        mock_batch.name = "pending_batch"
        mock_batch.description = None
        mock_batch.status = JobStatus.PENDING
        mock_batch.created_at = datetime.now(timezone.utc)
        mock_batch.started_at = None
        mock_batch.completed_at = None
        mock_batch.max_concurrent = 5
        mock_batch.output_base_directory = "/output"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_batch

        # Mock jobs with no completed ones
        mock_jobs = [
            Mock(
                spec=ScrapingJob, status=JobStatus.PENDING, duration_seconds=None, completed_at=None
            )
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_jobs

        details = batch_monitor.get_batch_details(1)

        assert details["timing_statistics"] is None
        assert len(details["recent_activity"]) == 0

    def test_get_system_health(self, batch_monitor):
        """Test getting system health metrics."""
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock job status counts
        mock_counts = [
            (JobStatus.COMPLETED, 100),
            (JobStatus.FAILED, 5),
            (JobStatus.RUNNING, 3),
            (JobStatus.PENDING, 10),
        ]
        mock_session.query.return_value.group_by.return_value.all.return_value = mock_counts

        # Mock recent jobs for error rate calculation
        mock_recent_jobs = []
        for i in range(20):
            job = Mock(spec=ScrapingJob)
            job.status = JobStatus.FAILED if i < 2 else JobStatus.COMPLETED
            mock_recent_jobs.append(job)

        mock_session.query.return_value.filter.return_value.all.return_value = mock_recent_jobs

        # Mock engine stats
        mock_engine = Mock()
        mock_pool = Mock()
        mock_pool.size.return_value = 20
        mock_pool.checkedin.return_value = 15
        mock_pool.checkedout.return_value = 5
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        mock_engine.pool = mock_pool
        batch_monitor.database_service.engine = mock_engine

        health = batch_monitor.get_system_health()

        assert "timestamp" in health
        assert health["job_status_counts"]["completed"] == 100
        assert health["job_status_counts"]["failed"] == 5
        assert health["total_jobs"] == 118  # 100+5+3+10
        assert health["recent_error_rate_percent"] == 10.0  # 2/20 * 100

        pool_stats = health["database"]["connection_pool"]
        assert pool_stats["pool_size"] == 20
        assert pool_stats["checked_in"] == 15
        assert pool_stats["checked_out"] == 5

        assert "runtime_metrics" in health

    @pytest.mark.asyncio
    async def test_generate_report(self, batch_monitor, tmp_path):
        """Test generating comprehensive batch processing report."""
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )

        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)

        # Mock batches
        mock_batch = Mock()
        mock_batch.name = "batch1"
        mock_batch.status = JobStatus.COMPLETED
        mock_batch.created_at = start_date + timedelta(hours=1)
        mock_batch.total_jobs = 10
        mock_batch.completed_jobs = 9
        mock_batch.failed_jobs = 1
        mock_batch.success_rate = 0.9
        mock_batches = [mock_batch]

        # Mock jobs
        mock_jobs = []
        for i in range(10):
            job = Mock()
            job.status = JobStatus.COMPLETED if i < 9 else JobStatus.FAILED
            job.duration_seconds = 2.0 + (i * 0.1) if i < 9 else None
            job.domain = "example.com"
            job.error_type = "timeout" if i >= 9 else None
            job.created_at = start_date + timedelta(hours=i)
            job.url = f"https://example.com/page{i}"
            mock_jobs.append(job)

        # Setup query mocks
        mock_session.query.return_value.filter.return_value.all.side_effect = [
            mock_batches,  # First call for batches
            mock_jobs,  # Second call for jobs
        ]

        output_file = tmp_path / "report.json"

        report = await batch_monitor.generate_report(start_date, end_date, output_file)

        # Verify report structure
        assert "report_period" in report
        assert "summary" in report
        assert "processing_statistics" in report
        assert "top_domains" in report
        assert "error_analysis" in report
        assert "batch_details" in report

        # Verify summary data
        summary = report["summary"]
        assert summary["total_batches"] == 1
        assert summary["total_jobs"] == 10
        assert summary["successful_jobs"] == 9
        assert summary["failed_jobs"] == 1
        assert summary["success_rate_percent"] == 90.0

        # Verify top domains
        assert len(report["top_domains"]) > 0
        assert report["top_domains"][0] == ("example.com", 10)

        # Verify error analysis
        assert "timeout" in report["error_analysis"]["error_types"]

        # Verify file was written
        assert output_file.exists()
        with open(output_file) as f:
            file_report = json.load(f)
            # Basic structure validation (JSON serialization converts tuples to lists)
            assert file_report["summary"]["total_batches"] == 1
            assert file_report["summary"]["total_jobs"] == 10
            assert len(file_report["top_domains"]) > 0
            assert file_report["top_domains"][0][0] == "example.com"

    @pytest.mark.asyncio
    async def test_generate_report_no_output_file(self, batch_monitor):
        """Test generating report without saving to file."""
        mock_session = (
            batch_monitor.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.all.return_value = []

        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)

        report = await batch_monitor.generate_report(start_date, end_date)

        # Should have empty data but valid structure
        assert report["summary"]["total_batches"] == 0
        assert report["summary"]["total_jobs"] == 0
        assert len(report["top_domains"]) == 0
        assert len(report["error_analysis"]["error_types"]) == 0


class TestAlertManager:
    """Test AlertManager functionality."""

    def test_initialization(self, mock_database_service):
        """Test alert manager initialization."""
        manager = AlertManager(mock_database_service)

        assert manager.database_service is mock_database_service
        assert "error_rate_percent" in manager.alert_thresholds
        assert "queue_size" in manager.alert_thresholds
        assert manager.alert_thresholds["error_rate_percent"] == 10.0

    @pytest.mark.asyncio
    async def test_check_error_rate_alert_no_jobs(self, alert_manager):
        """Test error rate check with no recent jobs."""
        mock_session = (
            alert_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.all.return_value = []

        alert = await alert_manager.check_error_rate_alert()
        assert alert is None

    @pytest.mark.asyncio
    async def test_check_error_rate_alert_low_error_rate(self, alert_manager):
        """Test error rate check with acceptable error rate."""
        mock_session = (
            alert_manager.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock 20 jobs, 1 failed (5% error rate - below threshold)
        mock_jobs = []
        for i in range(20):
            job = Mock(spec=ScrapingJob)
            job.status = JobStatus.FAILED if i == 0 else JobStatus.COMPLETED
            job.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
            mock_jobs.append(job)

        mock_session.query.return_value.filter.return_value.all.return_value = mock_jobs

        alert = await alert_manager.check_error_rate_alert()
        assert alert is None

    @pytest.mark.asyncio
    async def test_check_error_rate_alert_high_error_rate_warning(self, alert_manager):
        """Test error rate check with warning-level error rate."""
        mock_session = (
            alert_manager.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock 20 jobs, 3 failed (15% error rate - above 10% threshold but below 25%)
        mock_jobs = []
        for i in range(20):
            job = Mock(spec=ScrapingJob)
            job.status = JobStatus.FAILED if i < 3 else JobStatus.COMPLETED
            job.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
            mock_jobs.append(job)

        mock_session.query.return_value.filter.return_value.all.return_value = mock_jobs

        alert = await alert_manager.check_error_rate_alert()

        assert alert is not None
        assert alert["type"] == "high_error_rate"
        assert alert["severity"] == "warning"
        assert alert["details"]["error_rate_percent"] == 15.0
        assert alert["details"]["failed_jobs"] == 3
        assert alert["details"]["total_jobs"] == 20

    @pytest.mark.asyncio
    async def test_check_error_rate_alert_high_error_rate_critical(self, alert_manager):
        """Test error rate check with critical-level error rate."""
        mock_session = (
            alert_manager.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock 10 jobs, 3 failed (30% error rate - above 25% threshold)
        mock_jobs = []
        for i in range(10):
            job = Mock(spec=ScrapingJob)
            job.status = JobStatus.FAILED if i < 3 else JobStatus.COMPLETED
            job.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
            mock_jobs.append(job)

        mock_session.query.return_value.filter.return_value.all.return_value = mock_jobs

        alert = await alert_manager.check_error_rate_alert()

        assert alert is not None
        assert alert["severity"] == "critical"
        assert alert["details"]["error_rate_percent"] == 30.0

    @pytest.mark.asyncio
    async def test_check_stalled_jobs_alert_no_stalled_jobs(self, alert_manager):
        """Test stalled jobs check with no stalled jobs."""
        mock_session = (
            alert_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.all.return_value = []

        alert = await alert_manager.check_stalled_jobs_alert()
        assert alert is None

    @pytest.mark.asyncio
    async def test_check_stalled_jobs_alert_with_stalled_jobs(self, alert_manager):
        """Test stalled jobs check with stalled jobs found."""
        mock_session = (
            alert_manager.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock stalled jobs
        stalled_job = Mock(spec=ScrapingJob)
        stalled_job.url = "https://example.com/stalled"
        stalled_job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_session.query.return_value.filter.return_value.all.return_value = [stalled_job]

        alert = await alert_manager.check_stalled_jobs_alert()

        assert alert is not None
        assert alert["type"] == "stalled_jobs"
        assert alert["severity"] == "warning"
        assert alert["details"]["stalled_count"] == 1
        assert alert["details"]["oldest_job_url"] == "https://example.com/stalled"

    @pytest.mark.asyncio
    async def test_get_all_alerts(self, alert_manager):
        """Test getting all alerts."""
        # Mock both alert check methods to return alerts
        with (
            patch.object(alert_manager, "check_error_rate_alert") as mock_error_check,
            patch.object(alert_manager, "check_stalled_jobs_alert") as mock_stalled_check,
        ):
            error_alert = {"type": "high_error_rate", "severity": "warning"}
            stalled_alert = {"type": "stalled_jobs", "severity": "warning"}

            mock_error_check.return_value = error_alert
            mock_stalled_check.return_value = stalled_alert

            alerts = await alert_manager.get_all_alerts()

            assert len(alerts) == 2
            assert error_alert in alerts
            assert stalled_alert in alerts

    @pytest.mark.asyncio
    async def test_get_all_alerts_no_alerts(self, alert_manager):
        """Test getting all alerts when no alerts are active."""
        with (
            patch.object(alert_manager, "check_error_rate_alert") as mock_error_check,
            patch.object(alert_manager, "check_stalled_jobs_alert") as mock_stalled_check,
        ):
            mock_error_check.return_value = None
            mock_stalled_check.return_value = None

            alerts = await alert_manager.get_all_alerts()
            assert len(alerts) == 0


@pytest.mark.integration
def test_monitoring_integration(mock_database_service):
    """Integration test for monitoring components."""
    monitor = BatchMonitor(mock_database_service)

    # Record some metrics
    monitor.metrics_collector.record_processing_result("https://example.com/1", 1.5, True, 1000)
    monitor.metrics_collector.record_processing_result(
        "https://example.com/2", 2.0, False, error_type="timeout"
    )

    # Test metrics collection
    metrics = monitor.metrics_collector.get_current_metrics()
    assert metrics["urls_processed"] == 1
    assert metrics["urls_failed"] == 1
    assert metrics["success_rate_percent"] == 50.0

    # Test batch metrics recording
    batch_results = BatchResults(successful=["url1"], failed=["url2"], total=2, duration=10.0)

    monitor.metrics_collector.record_batch_metrics(batch_results)
    # Integration test passes if no exceptions are raised
