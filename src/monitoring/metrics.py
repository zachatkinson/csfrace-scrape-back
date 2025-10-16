"""System and application metrics collection with Prometheus integration."""

from __future__ import annotations

import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import asyncio
import psutil

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

logger = get_monitoring_logger()

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = CollectorRegistry = generate_latest = None  # type: ignore[misc,assignment]


@dataclass
class MetricsConfig:
    """Configuration for metrics collection.

    Prometheus Metrics Strategy:
    - SSE Health Monitoring: Real-time service status (database health via SSE)
    - Prometheus Metrics: Historical trends, capacity planning, performance analysis
    - Database metrics disabled in Prometheus to avoid async SQLAlchemy connection pool conflicts
    """

    enabled: bool = True
    collection_interval: float = 30.0  # seconds
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    system_metrics_enabled: bool = True  # CPU, memory, disk, network - historical trends
    application_metrics_enabled: bool = True  # HTTP requests, response times, batch jobs
    cache_metrics_enabled: bool = True  # Cache hit rates, sizes - performance optimization
    database_metrics_enabled: bool = False  # Disabled - use SSE health monitoring instead
    custom_labels: dict[str, str] = field(default_factory=dict)
    retention_hours: int = 24


class MetricsCollector:
    """Comprehensive metrics collector with Prometheus export."""

    def __init__(self, config: MetricsConfig | None = None):
        """Initialize metrics collector.

        Args:
            config: Metrics configuration
        """
        self.config = config or MetricsConfig()
        self.registry: CollectorRegistry | None = None
        self.metrics: dict[str, Any] = {}
        self.system_metrics: dict[str, float] = {}
        self.application_metrics: dict[str, float | str | int] = {}
        self._collection_task: asyncio.Task[None] | None = None
        self._collecting = False
        self._lock = threading.Lock()
        self._start_time = time.time()  # Track application start time

        # Response time tracking for application metrics
        self._response_times: list[float] = []
        self._max_response_time = 0.0
        self._active_connections = 0
        self._queue_length = 0  # Track request queue length

        # Initialize application metrics with default values
        self._initialize_application_metrics()

        if self.config.enabled and PROMETHEUS_AVAILABLE:
            self._initialize_prometheus()

    def _initialize_application_metrics(self) -> None:
        """Initialize application metrics with default values."""
        uptime_seconds = time.time() - self._start_time
        uptime_hours = uptime_seconds / 3600
        uptime_str = f"{int(uptime_hours)}h {int((uptime_seconds % 3600) / 60)}m"

        self.application_metrics.update(
            {
                "avg_response": 0.0,
                "p95_response": 0.0,
                "max_response": 0.0,
                "active_connections": 0,
                "queue_length": self._queue_length,
                "uptime": uptime_str,
                "total_requests": 0,
                "timestamp": time.time(),
            }
        )

        logger.info(
            "Metrics collector initialized",
            prometheus=PROMETHEUS_AVAILABLE and self.config.prometheus_enabled,
        )

    def _initialize_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available, metrics export disabled")
            return

        self.registry = CollectorRegistry()

        # System metrics
        if self.config.system_metrics_enabled:
            self.metrics["cpu_usage"] = Gauge(
                "system_cpu_usage_percent", "CPU usage percentage", registry=self.registry
            )
            self.metrics["memory_usage"] = Gauge(
                "system_memory_usage_bytes", "Memory usage in bytes", registry=self.registry
            )
            self.metrics["memory_usage_percent"] = Gauge(
                "system_memory_usage_percent", "Memory usage percentage", registry=self.registry
            )
            self.metrics["disk_usage"] = Gauge(
                "system_disk_usage_percent", "Disk usage percentage", registry=self.registry
            )
            self.metrics["network_io"] = Counter(
                "system_network_io_bytes_total",
                "Network I/O bytes total",
                ["direction"],
                registry=self.registry,
            )

        # Application metrics
        if self.config.application_metrics_enabled:
            self.metrics["requests_total"] = Counter(
                "app_requests_total",
                "Total number of requests",
                ["method", "status", "endpoint"],
                registry=self.registry,
            )
            self.metrics["request_duration"] = Histogram(
                "app_request_duration_seconds",
                "Request duration in seconds",
                ["method", "endpoint"],
                registry=self.registry,
            )
            self.metrics["active_requests"] = Gauge(
                "app_active_requests", "Number of active requests", registry=self.registry
            )
            self.metrics["batch_jobs_processed"] = Counter(
                "app_batch_jobs_processed_total",
                "Total batch jobs processed",
                ["status"],
                registry=self.registry,
            )
            self.metrics["batch_processing_duration"] = Histogram(
                "app_batch_processing_duration_seconds",
                "Batch processing duration in seconds",
                registry=self.registry,
            )

        # Cache metrics
        if self.config.cache_metrics_enabled:
            self.metrics["cache_hits"] = Counter(
                "cache_hits_total", "Total cache hits", ["cache_type"], registry=self.registry
            )
            self.metrics["cache_misses"] = Counter(
                "cache_misses_total", "Total cache misses", ["cache_type"], registry=self.registry
            )
            self.metrics["cache_size"] = Gauge(
                "cache_size_bytes", "Cache size in bytes", ["cache_type"], registry=self.registry
            )
            self.metrics["cache_entries"] = Gauge(
                "cache_entries_count",
                "Number of cache entries",
                ["cache_type"],
                registry=self.registry,
            )

        # Database metrics
        if self.config.database_metrics_enabled:
            self.metrics["db_connections"] = Gauge(
                "database_connections",
                "Number of database connections",
                ["state"],
                registry=self.registry,
            )
            self.metrics["db_queries"] = Counter(
                "database_queries_total",
                "Total database queries",
                ["operation", "status"],
                registry=self.registry,
            )
            self.metrics["db_query_duration"] = Histogram(
                "database_query_duration_seconds",
                "Database query duration in seconds",
                ["operation"],
                registry=self.registry,
            )

    async def start_collection(self) -> None:
        """Start periodic metrics collection."""
        if not self.config.enabled or self._collecting:
            return

        self._collecting = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Started metrics collection", interval=self.config.collection_interval)

    async def stop_collection(self) -> None:
        """Stop metrics collection."""
        if not self._collecting:
            return

        self._collecting = False
        if self._collection_task:
            self._collection_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._collection_task

        logger.info("Stopped metrics collection")

    @monitoring_error_handler("metrics collection loop")
    async def _collection_loop(self) -> None:
        """Main metrics collection loop."""
        while self._collecting:
            await self.collect_system_metrics()
            await asyncio.sleep(self.config.collection_interval)

    @monitoring_error_handler("system metrics collection")
    async def collect_system_metrics(self) -> None:
        """Collect system resource metrics."""
        if not self.config.system_metrics_enabled:
            return

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()

        # Disk usage (for root filesystem)
        disk = psutil.disk_usage("/")

        # Network I/O
        network = psutil.net_io_counters()

        with self._lock:
            self.system_metrics.update(
                {
                    "cpu_percent": cpu_percent,
                    "memory_total": memory.total,
                    "memory_used": memory.used,
                    "memory_percent": memory.percent,
                    "disk_total": disk.total,
                    "disk_used": disk.used,
                    "disk_percent": (disk.used / disk.total) * 100,
                    "network_bytes_sent": network.bytes_sent,
                    "network_bytes_recv": network.bytes_recv,
                    "timestamp": time.time(),
                }
            )

        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE and self.registry:
            self.metrics["cpu_usage"].set(cpu_percent)
            self.metrics["memory_usage"].set(memory.used)
            self.metrics["memory_usage_percent"].set(memory.percent)
            self.metrics["disk_usage"].set((disk.used / disk.total) * 100)

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float) -> None:
        """Record HTTP request metrics.

        Args:
            method: HTTP method
            endpoint: Request endpoint
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        # Update application metrics data for frontend consumption
        with self._lock:
            # Track response times (convert to milliseconds)
            duration_ms = duration * 1000
            self._response_times.append(duration_ms)

            # Keep only last 100 response times for sliding window calculations
            if len(self._response_times) > 100:
                self._response_times = self._response_times[-100:]

            # Update max response time
            self._max_response_time = max(self._max_response_time, duration_ms)

            # Calculate application metrics
            if self._response_times:
                avg_response = sum(self._response_times) / len(self._response_times)
                # Calculate P95 (95th percentile)
                sorted_times = sorted(self._response_times)
                p95_index = int(0.95 * len(sorted_times))
                p95_response = (
                    sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
                )
            else:
                avg_response = 0
                p95_response = 0

            # Update application metrics dictionary
            uptime_seconds = time.time() - self._start_time
            uptime_hours = uptime_seconds / 3600
            uptime_str = f"{int(uptime_hours)}h {int((uptime_seconds % 3600) / 60)}m"

            self.application_metrics.update(
                {
                    "avg_response": avg_response,
                    "p95_response": p95_response,
                    "max_response": self._max_response_time,
                    "active_connections": self._active_connections,
                    "queue_length": self._queue_length,
                    "uptime": uptime_str,
                    "total_requests": len(self._response_times),
                    "timestamp": time.time(),
                }
            )

        if not self.config.application_metrics_enabled or not PROMETHEUS_AVAILABLE:
            return

        self._record_prometheus_request_metrics(method, status_code, endpoint, duration)

    @monitoring_error_handler("record request metrics")
    def _record_prometheus_request_metrics(
        self, method: str, status_code: int, endpoint: str, duration: float
    ) -> None:
        """Record request metrics to Prometheus."""
        self.metrics["requests_total"].labels(
            method=method, status=str(status_code), endpoint=endpoint
        ).inc()

        self.metrics["request_duration"].labels(method=method, endpoint=endpoint).observe(duration)

    def increment_active_connections(self) -> None:
        """Increment active connections counter."""
        with self._lock:
            self._active_connections += 1

    def decrement_active_connections(self) -> None:
        """Decrement active connections counter."""
        with self._lock:
            self._active_connections = max(0, self._active_connections - 1)

    def increment_queue_length(self) -> None:
        """Increment request queue length counter."""
        with self._lock:
            self._queue_length += 1

    def decrement_queue_length(self) -> None:
        """Decrement request queue length counter."""
        with self._lock:
            self._queue_length = max(0, self._queue_length - 1)

    def record_batch_job(self, status: str, duration: float | None = None) -> None:
        """Record batch job metrics.

        Args:
            status: Job status (completed, failed, cancelled)
            duration: Processing duration in seconds
        """
        if not self.config.application_metrics_enabled or not PROMETHEUS_AVAILABLE:
            return

        self._record_prometheus_batch_metrics(status, duration)

    @monitoring_error_handler("record batch job metrics")
    def _record_prometheus_batch_metrics(self, status: str, duration: float | None) -> None:
        """Record batch job metrics to Prometheus."""
        self.metrics["batch_jobs_processed"].labels(status=status).inc()

        if duration is not None:
            self.metrics["batch_processing_duration"].observe(duration)

    def record_cache_hit(self, cache_type: str) -> None:
        """Record cache hit.

        Args:
            cache_type: Type of cache (html, image, metadata, etc.)
        """
        if not self.config.cache_metrics_enabled or not PROMETHEUS_AVAILABLE:
            return

        self._record_prometheus_cache_hit(cache_type)

    @monitoring_error_handler("record cache hit")
    def _record_prometheus_cache_hit(self, cache_type: str) -> None:
        """Record cache hit to Prometheus."""
        self.metrics["cache_hits"].labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str) -> None:
        """Record cache miss.

        Args:
            cache_type: Type of cache (html, image, metadata, etc.)
        """
        if not self.config.cache_metrics_enabled or not PROMETHEUS_AVAILABLE:
            return

        self._record_prometheus_cache_miss(cache_type)

    @monitoring_error_handler("record cache miss")
    def _record_prometheus_cache_miss(self, cache_type: str) -> None:
        """Record cache miss to Prometheus."""
        self.metrics["cache_misses"].labels(cache_type=cache_type).inc()

    def update_cache_metrics(self, cache_type: str, size_bytes: int, entry_count: int) -> None:
        """Update cache size metrics.

        Args:
            cache_type: Type of cache
            size_bytes: Cache size in bytes
            entry_count: Number of cache entries
        """
        if not self.config.cache_metrics_enabled or not PROMETHEUS_AVAILABLE:
            return

        self._update_prometheus_cache_metrics(cache_type, size_bytes, entry_count)

    @monitoring_error_handler("update cache metrics")
    def _update_prometheus_cache_metrics(
        self, cache_type: str, size_bytes: int, entry_count: int
    ) -> None:
        """Update cache metrics in Prometheus."""
        self.metrics["cache_size"].labels(cache_type=cache_type).set(size_bytes)
        self.metrics["cache_entries"].labels(cache_type=cache_type).set(entry_count)

    def record_database_query(
        self, operation: str, status: str, duration: float | None = None
    ) -> None:
        """Record database query metrics.

        Args:
            operation: Database operation (select, insert, update, delete)
            status: Query status (success, error)
            duration: Query duration in seconds
        """
        if not self.config.database_metrics_enabled or not PROMETHEUS_AVAILABLE:
            return

        self._record_prometheus_database_metrics(operation, status, duration)

    @monitoring_error_handler("record database query metrics")
    def _record_prometheus_database_metrics(
        self, operation: str, status: str, duration: float | None
    ) -> None:
        """Record database query metrics to Prometheus."""
        self.metrics["db_queries"].labels(operation=operation, status=status).inc()

        if duration is not None:
            self.metrics["db_query_duration"].labels(operation=operation).observe(duration)

    def get_metrics_snapshot(self) -> dict[str, Any]:
        """Get current metrics snapshot.

        Returns:
            Dictionary containing current metrics
        """
        with self._lock:
            # Ensure application metrics are always populated
            if not self.application_metrics:
                self._initialize_application_metrics()

            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "system_metrics": self.system_metrics.copy(),
                "application_metrics": self.application_metrics.copy(),
                "config": {
                    "enabled": self.config.enabled,
                    "collection_interval": self.config.collection_interval,
                    "prometheus_enabled": self.config.prometheus_enabled,
                },
            }

    def export_prometheus_metrics(self) -> bytes:
        """Export metrics in Prometheus format.

        Returns:
            Prometheus metrics data
        """
        if not PROMETHEUS_AVAILABLE or not self.registry:
            return b"# Prometheus not available\n"

        return self._export_prometheus_data()

    @monitoring_error_handler("export Prometheus metrics")
    def _export_prometheus_data(self) -> bytes:
        """Export Prometheus metrics data."""
        if self.registry is None:
            raise RuntimeError("Registry not initialized")
        return generate_latest(self.registry)

    async def shutdown(self) -> None:
        """Shutdown metrics collector."""
        await self.stop_collection()
        logger.info("Metrics collector shutdown")


# Global metrics collector instance
metrics_collector = MetricsCollector()
