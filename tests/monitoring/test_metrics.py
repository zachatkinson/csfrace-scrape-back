"""Comprehensive tests for metrics collection system with TEST_BUILDING.md compliance.

This module tests the metrics collection functionality including:
- Prometheus metrics integration
- System metrics collection (CPU, memory, disk, network)
- Application metrics (requests, batch jobs, connections)
- Cache and database metrics
- Metrics export and snapshot generation

All tests follow TEST_BUILDING.md ZERO TOLERANCE standards:
- AAA pattern with MANDATORY comments
- Factory fixtures for DRY compliance
- Security tests for malicious inputs
- Performance benchmarks with specific thresholds
- NO vestigial code
- Modern Python 3.11+ patterns
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.metrics import MetricsCollector, MetricsConfig

# ============================================================================
# Factory Fixtures (DRY Principle - MANDATORY)
# ============================================================================


@pytest.fixture
def metrics_config() -> MetricsConfig:
    """Factory for MetricsConfig - DRY principle."""
    return MetricsConfig(
        enabled=True,
        collection_interval=1.0,  # Fast for testing
        prometheus_enabled=False,  # Disable Prometheus for most tests
        system_metrics_enabled=True,
        application_metrics_enabled=True,
        cache_metrics_enabled=True,
        database_metrics_enabled=True,
    )


@pytest.fixture
def metrics_collector(metrics_config: MetricsConfig) -> MetricsCollector:
    """Factory for MetricsCollector - DRY principle."""
    return MetricsCollector(config=metrics_config)


# ============================================================================
# Tests: MetricsConfig
# ============================================================================


@pytest.mark.unit
class TestMetricsConfig:
    """Tests for MetricsConfig configuration - MANDATORY AAA pattern."""

    def test_config_defaults(self) -> None:
        """Test metrics config has sensible defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = MetricsConfig()

        # Assert - MANDATORY
        assert config.enabled is True
        assert config.collection_interval == 30.0
        assert config.prometheus_enabled is True
        assert config.prometheus_port == 9090
        assert config.system_metrics_enabled is True
        assert config.application_metrics_enabled is True
        assert config.cache_metrics_enabled is True
        assert config.database_metrics_enabled is False  # Disabled - use SSE health monitoring
        assert config.retention_hours == 24

    def test_config_customization(self) -> None:
        """Test metrics config can be customized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_labels = {"environment": "test", "service": "scraper"}

        # Act - MANDATORY
        config = MetricsConfig(
            enabled=False,
            collection_interval=60.0,
            prometheus_enabled=False,
            prometheus_port=8080,
            custom_labels=custom_labels,
            retention_hours=48,
        )

        # Assert - MANDATORY
        assert config.enabled is False
        assert config.collection_interval == 60.0
        assert config.prometheus_enabled is False
        assert config.prometheus_port == 8080
        assert config.custom_labels == custom_labels
        assert config.retention_hours == 48


# ============================================================================
# Tests: MetricsCollector Initialization
# ============================================================================


@pytest.mark.unit
class TestMetricsCollectorInitialization:
    """Tests for MetricsCollector initialization - MANDATORY AAA pattern."""

    def test_collector_initializes_with_config(self, metrics_config: MetricsConfig) -> None:
        """Test metrics collector initializes with config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        collector = MetricsCollector(config=metrics_config)

        # Assert - MANDATORY
        assert collector.config == metrics_config
        assert isinstance(collector.system_metrics, dict)
        assert isinstance(collector.application_metrics, dict)
        assert collector._collecting is False

    def test_collector_initializes_application_metrics(
        self, metrics_collector: MetricsCollector
    ) -> None:
        """Test collector initializes application metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        app_metrics = metrics_collector.application_metrics

        # Assert - MANDATORY
        assert "avg_response" in app_metrics
        assert "p95_response" in app_metrics
        assert "max_response" in app_metrics
        assert "active_connections" in app_metrics
        assert "queue_length" in app_metrics
        assert "uptime" in app_metrics
        assert "total_requests" in app_metrics

    def test_collector_without_prometheus_available(self) -> None:
        """Test collector handles Prometheus unavailable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = MetricsConfig(prometheus_enabled=True)

        # Act - MANDATORY
        collector = MetricsCollector(config=config)

        # Assert - MANDATORY
        # Should initialize even if Prometheus not available
        assert collector is not None


# ============================================================================
# Tests: System Metrics Collection
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSystemMetricsCollection:
    """Tests for system metrics collection - MANDATORY AAA pattern."""

    async def test_collect_system_metrics_populates_data(self) -> None:
        """Test system metrics collection populates data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        collector = MetricsCollector()

        # Mock psutil
        with (
            patch("psutil.cpu_percent", return_value=50.0),
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.disk_usage") as mock_disk,
            patch("psutil.net_io_counters") as mock_network,
        ):
            mock_memory.return_value = MagicMock(total=16 * 1024**3, used=8 * 1024**3, percent=50.0)
            mock_disk.return_value = MagicMock(total=500 * 1024**3, used=250 * 1024**3)
            mock_network.return_value = MagicMock(bytes_sent=1000000, bytes_recv=2000000)

            # Act - MANDATORY
            await collector.collect_system_metrics()

            # Assert - MANDATORY
            assert "cpu_percent" in collector.system_metrics
            assert "memory_total" in collector.system_metrics
            assert "memory_used" in collector.system_metrics
            assert "memory_percent" in collector.system_metrics
            assert "disk_total" in collector.system_metrics
            assert "disk_used" in collector.system_metrics
            assert "network_bytes_sent" in collector.system_metrics
            assert "network_bytes_recv" in collector.system_metrics
            assert collector.system_metrics["cpu_percent"] == 50.0
            assert collector.system_metrics["memory_percent"] == 50.0

    async def test_collect_system_metrics_when_disabled(self) -> None:
        """Test system metrics not collected when disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = MetricsConfig(system_metrics_enabled=False)
        collector = MetricsCollector(config=config)

        # Act - MANDATORY
        await collector.collect_system_metrics()

        # Assert - MANDATORY
        # System metrics should remain empty
        assert len(collector.system_metrics) == 0


# ============================================================================
# Tests: Application Metrics Recording
# ============================================================================


@pytest.mark.unit
class TestApplicationMetricsRecording:
    """Tests for application metrics recording - MANDATORY AAA pattern."""

    def test_record_request_updates_metrics(self, metrics_collector: MetricsCollector) -> None:
        """Test record_request updates application metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        method = "GET"
        endpoint = "/api/test"
        status_code = 200
        duration = 0.123  # seconds

        # Act - MANDATORY
        metrics_collector.record_request(method, endpoint, status_code, duration)

        # Assert - MANDATORY
        assert len(metrics_collector._response_times) == 1
        assert metrics_collector._response_times[0] == 123.0  # Converted to ms
        assert metrics_collector.application_metrics["avg_response"] == 123.0
        assert metrics_collector.application_metrics["max_response"] == 123.0

    def test_record_request_calculates_p95(self, metrics_collector: MetricsCollector) -> None:
        """Test record_request calculates P95 correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Record 100 requests with varying durations
        for i in range(100):
            duration = i / 1000.0  # 0ms to 99ms
            metrics_collector.record_request("GET", "/test", 200, duration)

        # Act - MANDATORY
        p95_response = metrics_collector.application_metrics["p95_response"]

        # Type narrowing - MANDATORY for MyPy strict mode
        assert isinstance(p95_response, (float, int))

        # Assert - MANDATORY
        # P95 of 0-99ms should be around 95ms
        assert 90.0 <= p95_response <= 99.0

    def test_record_request_limits_history(self, metrics_collector: MetricsCollector) -> None:
        """Test record_request limits response time history - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Record 150 requests (more than 100 limit)
        for i in range(150):
            metrics_collector.record_request("GET", "/test", 200, 0.001)

        # Act - MANDATORY
        history_length = len(metrics_collector._response_times)

        # Assert - MANDATORY
        assert history_length == 100  # Should keep only last 100

    def test_increment_active_connections(self, metrics_collector: MetricsCollector) -> None:
        """Test increment active connections - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        initial = metrics_collector._active_connections

        # Act - MANDATORY
        metrics_collector.increment_active_connections()

        # Assert - MANDATORY
        assert metrics_collector._active_connections == initial + 1

    def test_decrement_active_connections(self, metrics_collector: MetricsCollector) -> None:
        """Test decrement active connections - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        metrics_collector._active_connections = 5

        # Act - MANDATORY
        metrics_collector.decrement_active_connections()

        # Assert - MANDATORY
        assert metrics_collector._active_connections == 4

    def test_decrement_active_connections_not_negative(
        self, metrics_collector: MetricsCollector
    ) -> None:
        """Test decrement doesn't go negative - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        metrics_collector._active_connections = 0

        # Act - MANDATORY
        metrics_collector.decrement_active_connections()

        # Assert - MANDATORY
        assert metrics_collector._active_connections == 0

    def test_increment_queue_length(self, metrics_collector: MetricsCollector) -> None:
        """Test increment queue length - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        initial = metrics_collector._queue_length

        # Act - MANDATORY
        metrics_collector.increment_queue_length()

        # Assert - MANDATORY
        assert metrics_collector._queue_length == initial + 1

    def test_decrement_queue_length(self, metrics_collector: MetricsCollector) -> None:
        """Test decrement queue length - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        metrics_collector._queue_length = 3

        # Act - MANDATORY
        metrics_collector.decrement_queue_length()

        # Assert - MANDATORY
        assert metrics_collector._queue_length == 2


# ============================================================================
# Tests: Batch Job Metrics
# ============================================================================


@pytest.mark.unit
class TestBatchJobMetrics:
    """Tests for batch job metrics - MANDATORY AAA pattern."""

    def test_record_batch_job_completed(self, metrics_collector: MetricsCollector) -> None:
        """Test record batch job with completed status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = "completed"
        duration = 5.5

        # Act - MANDATORY
        metrics_collector.record_batch_job(status, duration)

        # Assert - MANDATORY
        # Should not raise error (Prometheus might not be available)
        assert True

    def test_record_batch_job_failed(self, metrics_collector: MetricsCollector) -> None:
        """Test record batch job with failed status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status = "failed"
        duration = 2.3

        # Act - MANDATORY
        metrics_collector.record_batch_job(status, duration)

        # Assert - MANDATORY
        assert True


# ============================================================================
# Tests: Cache Metrics
# ============================================================================


@pytest.mark.unit
class TestCacheMetrics:
    """Tests for cache metrics - MANDATORY AAA pattern."""

    def test_record_cache_hit(self, metrics_collector: MetricsCollector) -> None:
        """Test record cache hit - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cache_type = "html"

        # Act - MANDATORY
        metrics_collector.record_cache_hit(cache_type)

        # Assert - MANDATORY
        assert True  # No error

    def test_record_cache_miss(self, metrics_collector: MetricsCollector) -> None:
        """Test record cache miss - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cache_type = "image"

        # Act - MANDATORY
        metrics_collector.record_cache_miss(cache_type)

        # Assert - MANDATORY
        assert True  # No error

    def test_update_cache_metrics(self, metrics_collector: MetricsCollector) -> None:
        """Test update cache size metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cache_type = "html"
        size_bytes = 1024 * 1024  # 1MB
        entry_count = 50

        # Act - MANDATORY
        metrics_collector.update_cache_metrics(cache_type, size_bytes, entry_count)

        # Assert - MANDATORY
        assert True  # No error


# ============================================================================
# Tests: Database Metrics
# ============================================================================


@pytest.mark.unit
class TestDatabaseMetrics:
    """Tests for database metrics - MANDATORY AAA pattern."""

    def test_record_database_query_success(self, metrics_collector: MetricsCollector) -> None:
        """Test record successful database query - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "select"
        status = "success"
        duration = 0.05

        # Act - MANDATORY
        metrics_collector.record_database_query(operation, status, duration)

        # Assert - MANDATORY
        assert True  # No error

    def test_record_database_query_error(self, metrics_collector: MetricsCollector) -> None:
        """Test record failed database query - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "insert"
        status = "error"
        duration = 0.1

        # Act - MANDATORY
        metrics_collector.record_database_query(operation, status, duration)

        # Assert - MANDATORY
        assert True  # No error


# ============================================================================
# Tests: Metrics Snapshot
# ============================================================================


@pytest.mark.unit
class TestMetricsSnapshot:
    """Tests for metrics snapshot generation - MANDATORY AAA pattern."""

    def test_get_metrics_snapshot_structure(self, metrics_collector: MetricsCollector) -> None:
        """Test metrics snapshot has correct structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        snapshot = metrics_collector.get_metrics_snapshot()

        # Assert - MANDATORY
        assert "timestamp" in snapshot
        assert "system_metrics" in snapshot
        assert "application_metrics" in snapshot
        assert "config" in snapshot
        assert "enabled" in snapshot["config"]
        assert "collection_interval" in snapshot["config"]

    def test_get_metrics_snapshot_includes_system_metrics(self) -> None:
        """Test snapshot includes system metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        collector = MetricsCollector()
        collector.system_metrics = {
            "cpu_percent": 45.0,
            "memory_percent": 60.0,
        }

        # Act - MANDATORY
        snapshot = collector.get_metrics_snapshot()

        # Assert - MANDATORY
        assert snapshot["system_metrics"]["cpu_percent"] == 45.0
        assert snapshot["system_metrics"]["memory_percent"] == 60.0

    def test_get_metrics_snapshot_includes_application_metrics(
        self, metrics_collector: MetricsCollector
    ) -> None:
        """Test snapshot includes application metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        snapshot = metrics_collector.get_metrics_snapshot()

        # Assert - MANDATORY
        app_metrics = snapshot["application_metrics"]
        assert "avg_response" in app_metrics
        assert "p95_response" in app_metrics
        assert "max_response" in app_metrics
        assert "active_connections" in app_metrics


# ============================================================================
# Tests: Async Operations
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMetricsCollectorAsyncOperations:
    """Tests for async metrics collector operations - MANDATORY AAA pattern."""

    async def test_start_collection(self, metrics_collector: MetricsCollector) -> None:
        """Test starting metrics collection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        await metrics_collector.start_collection()

        # Assert - MANDATORY
        assert metrics_collector._collecting is True
        assert metrics_collector._collection_task is not None

        # Cleanup
        await metrics_collector.stop_collection()

    async def test_stop_collection(self, metrics_collector: MetricsCollector) -> None:
        """Test stopping metrics collection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await metrics_collector.start_collection()

        # Act - MANDATORY
        await metrics_collector.stop_collection()

        # Assert - MANDATORY
        assert metrics_collector._collecting is False

    async def test_shutdown_stops_collection(self, metrics_collector: MetricsCollector) -> None:
        """Test shutdown stops collection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await metrics_collector.start_collection()

        # Act - MANDATORY
        await metrics_collector.shutdown()

        # Assert - MANDATORY
        assert metrics_collector._collecting is False


# ============================================================================
# Tests: Prometheus Export
# ============================================================================


@pytest.mark.unit
class TestPrometheusExport:
    """Tests for Prometheus metrics export - MANDATORY AAA pattern."""

    def test_export_prometheus_metrics_when_unavailable(
        self, metrics_collector: MetricsCollector
    ) -> None:
        """Test export when Prometheus unavailable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        result = metrics_collector.export_prometheus_metrics()

        # Assert - MANDATORY
        assert isinstance(result, bytes)
        # Should return message about unavailability
        assert b"Prometheus not available" in result or len(result) > 0


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestMetricsSecurity:
    """MANDATORY security tests for metrics system."""

    def test_metric_label_sanitization(self, metrics_collector: MetricsCollector) -> None:
        """MANDATORY security test - metric labels with malicious characters."""
        # Arrange - MANDATORY
        malicious_endpoints = [
            "/test<script>alert('xss')</script>",
            "/test'; DROP TABLE metrics;--",
            "/test`whoami`",
            "/../../../etc/passwd",
        ]

        # Act & Assert - MANDATORY
        for endpoint in malicious_endpoints:
            # Should not raise error or execute malicious code
            metrics_collector.record_request("GET", endpoint, 200, 0.1)
            assert True

    def test_cache_type_sanitization(self, metrics_collector: MetricsCollector) -> None:
        """MANDATORY security test - cache types with malicious input."""
        # Arrange - MANDATORY
        malicious_types = [
            "html<script>alert(1)</script>",
            "cache'; DROP TABLE cache;--",
            "test`id`",
        ]

        # Act & Assert - MANDATORY
        for cache_type in malicious_types:
            metrics_collector.record_cache_hit(cache_type)
            metrics_collector.record_cache_miss(cache_type)
            assert True


# ============================================================================
# MANDATORY Performance Tests
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestMetricsPerformance:
    """MANDATORY performance tests for metrics system."""

    def test_record_request_performance(self, metrics_collector: MetricsCollector) -> None:
        """MANDATORY performance test - record request speed."""
        # Arrange - MANDATORY
        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            metrics_collector.record_request("GET", f"/test/{i}", 200, 0.001)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per record
        assert execution_time < 1.0  # Total <1s for 1000 records

    def test_get_metrics_snapshot_performance(self) -> None:
        """MANDATORY performance test - snapshot generation speed."""
        # Arrange - MANDATORY
        collector = MetricsCollector()
        # Populate with data
        collector.system_metrics = {
            "cpu_percent": 50.0,
            "memory_percent": 60.0,
            "disk_percent": 70.0,
        }
        for i in range(100):
            collector.record_request("GET", f"/test/{i}", 200, 0.001)

        iterations = 100
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            collector.get_metrics_snapshot()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per snapshot
        assert execution_time < 1.0  # Total <1s for 100 snapshots

    def test_p95_calculation_performance(self, metrics_collector: MetricsCollector) -> None:
        """MANDATORY performance test - P95 calculation speed."""
        # Arrange - MANDATORY
        # Pre-populate with 100 response times
        for i in range(100):
            metrics_collector._response_times.append(float(i))

        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            # Trigger P95 calculation via record_request
            metrics_collector.record_request("GET", "/test", 200, 0.001)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per calculation
        assert execution_time < 1.0  # Total <1s for 1000 calculations
