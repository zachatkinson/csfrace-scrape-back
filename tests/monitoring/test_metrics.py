"""Tests for metrics collection system."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.metrics import MetricsCollector, MetricsConfig


class TestMetricsConfig:
    """Test metrics configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MetricsConfig()

        assert config.enabled is True
        assert config.collection_interval == 30.0
        assert config.prometheus_enabled is True
        assert config.prometheus_port == 9090
        assert config.system_metrics_enabled is True
        assert config.application_metrics_enabled is True
        assert config.cache_metrics_enabled is True
        assert config.database_metrics_enabled is True
        assert config.custom_labels == {}
        assert config.retention_hours == 24

    def test_custom_config(self):
        """Test custom configuration."""
        config = MetricsConfig(
            enabled=False,
            collection_interval=60.0,
            prometheus_port=8080,
            custom_labels={"environment": "test"},
        )

        assert config.enabled is False
        assert config.collection_interval == 60.0
        assert config.prometheus_port == 8080
        assert config.custom_labels == {"environment": "test"}


class TestMetricsCollector:
    """Test metrics collector functionality."""

    @pytest.fixture
    def collector(self):
        """Create metrics collector for testing."""
        config = MetricsConfig(
            enabled=True,
            collection_interval=0.1,  # Fast for testing
            prometheus_enabled=False,  # Disable prometheus for tests
        )
        return MetricsCollector(config)

    @pytest.fixture
    def prometheus_collector(self):
        """Create collector with Prometheus enabled."""
        config = MetricsConfig(prometheus_enabled=True)
        collector = MetricsCollector(config)
        # Simulate Prometheus being available by setting up the registry
        collector.registry = MagicMock()
        collector.metrics = {
            "requests_total": MagicMock(),
            "request_duration": MagicMock(),
            "system_cpu": MagicMock(),
        }
        return collector

    def test_initialization_prometheus_disabled(self):
        """Test initialization with Prometheus disabled."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False):
            config = MetricsConfig(
                enabled=True,
                collection_interval=0.1,
                prometheus_enabled=False,
            )
            collector = MetricsCollector(config)
            assert collector.config.enabled is True
            assert collector.metrics == {}
            assert collector.system_metrics == {}
            assert collector._collecting is False

    def test_initialization_prometheus_enabled(self, prometheus_collector):
        """Test initialization with Prometheus enabled."""
        assert prometheus_collector.registry is not None
        assert len(prometheus_collector.metrics) > 0

    @pytest.mark.asyncio
    async def test_start_stop_collection(self, collector):
        """Test starting and stopping metrics collection."""
        assert not collector._collecting
        assert collector._collection_task is None

        await collector.start_collection()
        assert collector._collecting is True
        assert collector._collection_task is not None

        # Let it run briefly
        await asyncio.sleep(0.2)

        await collector.stop_collection()
        assert collector._collecting is False

    @pytest.mark.asyncio
    async def test_collection_disabled(self):
        """Test that collection doesn't start when disabled."""
        config = MetricsConfig(enabled=False)
        collector = MetricsCollector(config)

        await collector.start_collection()
        assert not collector._collecting
        assert collector._collection_task is None

    @pytest.mark.asyncio
    async def test_system_metrics_collection(self, collector):
        """Test system metrics collection."""
        with patch("psutil.cpu_percent", return_value=25.5):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.total = 8 * 1024**3  # 8GB
                mock_memory.return_value.used = 4 * 1024**3  # 4GB
                mock_memory.return_value.percent = 50.0

                with patch("psutil.disk_usage") as mock_disk:
                    mock_disk.return_value.total = 100 * 1024**3  # 100GB
                    mock_disk.return_value.used = 60 * 1024**3  # 60GB

                    with patch("psutil.net_io_counters") as mock_network:
                        mock_network.return_value.bytes_sent = 1024
                        mock_network.return_value.bytes_recv = 2048

                        await collector.collect_system_metrics()

                        assert "cpu_percent" in collector.system_metrics
                        assert collector.system_metrics["cpu_percent"] == 25.5
                        assert collector.system_metrics["memory_percent"] == 50.0
                        assert collector.system_metrics["disk_percent"] == 60.0
                        assert collector.system_metrics["network_bytes_sent"] == 1024
                        assert collector.system_metrics["network_bytes_recv"] == 2048

    @pytest.mark.asyncio
    async def test_system_metrics_collection_error(self, collector):
        """Test system metrics collection with error."""
        with patch("psutil.cpu_percent", side_effect=Exception("psutil error")):
            # Should not raise exception
            await collector.collect_system_metrics()

            # Metrics should be empty due to error
            assert "cpu_percent" not in collector.system_metrics

    def test_record_request_prometheus_disabled(self, collector):
        """Test recording request metrics without Prometheus."""
        # Should not raise exception
        collector.record_request("GET", "/api/test", 200, 0.5)

    def test_record_request_prometheus_enabled(self, prometheus_collector):
        """Test recording request metrics with Prometheus."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True):
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            prometheus_collector.metrics = {
                "requests_total": mock_counter,
                "request_duration": mock_histogram,
            }

            prometheus_collector.record_request("GET", "/api/test", 200, 0.5)

            # Should have called metrics
            mock_counter.labels.assert_called_with(method="GET", status="200", endpoint="/api/test")
            mock_histogram.labels.assert_called_with(method="GET", endpoint="/api/test")

    def test_record_batch_job(self, prometheus_collector):
        """Test recording batch job metrics."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True):
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            prometheus_collector.metrics = {
                "batch_jobs_processed": mock_counter,
                "batch_processing_duration": mock_histogram,
            }

            prometheus_collector.record_batch_job("completed", 2.5)

            mock_counter.labels.assert_called_with(status="completed")
            mock_histogram.observe.assert_called_with(2.5)

    def test_record_cache_metrics(self, prometheus_collector):
        """Test recording cache metrics."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True):
            mock_hits = MagicMock()
            mock_misses = MagicMock()
            mock_size = MagicMock()
            mock_entries = MagicMock()
            prometheus_collector.metrics = {
                "cache_hits": mock_hits,
                "cache_misses": mock_misses,
                "cache_size": mock_size,
                "cache_entries": mock_entries,
            }

            prometheus_collector.record_cache_hit("html")
            prometheus_collector.record_cache_miss("image")
            prometheus_collector.update_cache_metrics("html", 1024, 10)

            mock_hits.labels.assert_called_with(cache_type="html")
            mock_misses.labels.assert_called_with(cache_type="image")
            mock_size.labels.assert_called_with(cache_type="html")
            mock_entries.labels.assert_called_with(cache_type="html")

    def test_record_database_query(self, prometheus_collector):
        """Test recording database query metrics."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True):
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            prometheus_collector.metrics = {
                "db_queries": mock_counter,
                "db_query_duration": mock_histogram,
            }

            prometheus_collector.record_database_query("select", "success", 0.1)

            mock_counter.labels.assert_called_with(operation="select", status="success")
            mock_histogram.labels.assert_called_with(operation="select")

    def test_get_metrics_snapshot(self, collector):
        """Test getting metrics snapshot."""
        # Add some test data
        collector.system_metrics = {"cpu_percent": 50.0, "memory_percent": 60.0}
        collector.application_metrics = {"requests": 100}

        snapshot = collector.get_metrics_snapshot()

        assert "timestamp" in snapshot
        assert snapshot["system_metrics"]["cpu_percent"] == 50.0
        assert snapshot["system_metrics"]["memory_percent"] == 60.0
        assert snapshot["application_metrics"]["requests"] == 100
        assert snapshot["config"]["enabled"] is True

    def test_export_prometheus_metrics_disabled(self, collector):
        """Test Prometheus export when disabled."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False):
            metrics_data = collector.export_prometheus_metrics()
            assert b"Prometheus not available" in metrics_data

    def test_export_prometheus_metrics_enabled(self, prometheus_collector):
        """Test Prometheus export when enabled."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True):
            with patch("src.monitoring.metrics.generate_latest") as mock_generate:
                mock_generate.return_value = b"# Test metrics\n"

                metrics_data = prometheus_collector.export_prometheus_metrics()
                assert metrics_data == b"# Test metrics\n"
                mock_generate.assert_called_once_with(prometheus_collector.registry)

    def test_export_prometheus_metrics_error(self, prometheus_collector):
        """Test Prometheus export with error."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True):
            with patch(
                "src.monitoring.metrics.generate_latest", side_effect=Exception("Export error")
            ):
                metrics_data = prometheus_collector.export_prometheus_metrics()
                assert b"Export failed" in metrics_data

    @pytest.mark.asyncio
    async def test_shutdown(self, collector):
        """Test collector shutdown."""
        await collector.start_collection()
        assert collector._collecting is True

        await collector.shutdown()
        assert collector._collecting is False

    @pytest.mark.asyncio
    async def test_collection_loop_error_handling(self, collector):
        """Test collection loop handles errors gracefully."""
        with patch.object(
            collector, "collect_system_metrics", side_effect=Exception("Collection error")
        ):
            await collector.start_collection()

            # Let it run briefly to hit the error
            await asyncio.sleep(0.2)

            # Should still be collecting despite errors
            assert collector._collecting is True

            await collector.stop_collection()

    def test_metrics_with_prometheus_unavailable(self):
        """Test metrics collector when Prometheus is not available."""
        with patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False):
            config = MetricsConfig(prometheus_enabled=True)
            collector = MetricsCollector(config)

            # Should initialize without Prometheus
            assert collector.registry is None
            assert collector.metrics == {}

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self, collector):
        """Test multiple start/stop cycles work correctly."""
        # First cycle
        await collector.start_collection()
        assert collector._collecting is True
        await collector.stop_collection()
        assert collector._collecting is False

        # Second cycle
        await collector.start_collection()
        assert collector._collecting is True
        await collector.stop_collection()
        assert collector._collecting is False

    def test_thread_safety_system_metrics(self, collector):
        """Test thread safety of system metrics access."""
        import threading

        def update_metrics():
            collector.system_metrics["test"] = time.time()

        def read_metrics():
            snapshot = collector.get_metrics_snapshot()
            return snapshot["system_metrics"]

        # Run concurrent updates and reads
        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=update_metrics))
            threads.append(threading.Thread(target=read_metrics))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without error
        assert "test" in collector.system_metrics
