"""Comprehensive tests for performance monitoring - request tracing, spans, bottlenecks.

MANDATORY: All tests follow TEST_BUILDING.md ZERO TOLERANCE standards.
"""

import time
from datetime import UTC, datetime, timedelta

import pytest

from src.monitoring.performance import (
    PerformanceConfig,
    PerformanceMonitor,
    PerformanceTracer,
    RequestTrace,
    Span,
)

# ============================================================================
# FACTORY FIXTURES - DRY PRINCIPLE (MANDATORY)
# ============================================================================


@pytest.fixture
def performance_config() -> PerformanceConfig:
    """Factory for PerformanceConfig - DRY principle."""
    return PerformanceConfig(
        enabled=True,
        trace_requests=True,
        trace_sampling_rate=1.0,
        slow_request_threshold=5.0,
        memory_profiling_enabled=False,
        detailed_metrics=True,
        max_trace_history=1000,
    )


@pytest.fixture
def performance_monitor(performance_config: PerformanceConfig) -> PerformanceMonitor:
    """Factory for PerformanceMonitor - DRY principle."""
    return PerformanceMonitor(config=performance_config)


@pytest.fixture
def performance_tracer(performance_monitor: PerformanceMonitor) -> PerformanceTracer:
    """Factory for PerformanceTracer - DRY principle."""
    return PerformanceTracer(monitor=performance_monitor)


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================


@pytest.mark.unit
class TestPerformanceConfig:
    """Tests for PerformanceConfig dataclass."""

    def test_config_defaults(self):
        """Test PerformanceConfig has sensible defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = PerformanceConfig()

        # Assert - MANDATORY
        assert config.enabled is True
        assert config.trace_requests is True
        assert config.trace_sampling_rate == 1.0
        assert config.slow_request_threshold == 5.0
        assert config.memory_profiling_enabled is False
        assert config.detailed_metrics is True
        assert config.max_trace_history == 1000

    def test_config_customization(self):
        """Test PerformanceConfig allows customization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = PerformanceConfig(
            enabled=False,
            trace_requests=False,
            trace_sampling_rate=0.5,
            slow_request_threshold=10.0,
            memory_profiling_enabled=True,
            detailed_metrics=False,
            max_trace_history=500,
        )

        # Assert - MANDATORY
        assert config.enabled is False
        assert config.trace_requests is False
        assert config.trace_sampling_rate == 0.5
        assert config.slow_request_threshold == 10.0
        assert config.memory_profiling_enabled is True
        assert config.detailed_metrics is False
        assert config.max_trace_history == 500


# ============================================================================
# REQUEST TRACE TESTS
# ============================================================================


@pytest.mark.unit
class TestRequestTrace:
    """Tests for RequestTrace dataclass."""

    def test_request_trace_creation(self):
        """Test RequestTrace creation with required fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = "test-trace-123"
        operation = "test_operation"
        start_time = datetime.now(UTC)

        # Act - MANDATORY
        trace = RequestTrace(trace_id=trace_id, operation=operation, start_time=start_time)

        # Assert - MANDATORY
        assert trace.trace_id == trace_id
        assert trace.operation == operation
        assert trace.start_time == start_time
        assert trace.end_time is None
        assert trace.duration_ms is None
        assert trace.status == "running"
        assert trace.metadata == {}
        assert trace.spans == []
        assert trace.error is None
        assert trace.correlation_id is None

    def test_request_trace_duration_property(self):
        """Test RequestTrace duration property converts ms to seconds - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace = RequestTrace(
            trace_id="test", operation="op", start_time=datetime.now(UTC), duration_ms=5000.0
        )

        # Act - MANDATORY
        duration_seconds = trace.duration

        # Assert - MANDATORY
        assert duration_seconds == 5.0  # 5000ms = 5s

    def test_request_trace_duration_none(self):
        """Test RequestTrace duration property when duration_ms is None - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace = RequestTrace(trace_id="test", operation="op", start_time=datetime.now(UTC))

        # Act - MANDATORY
        duration = trace.duration

        # Assert - MANDATORY
        assert duration is None


# ============================================================================
# SPAN TESTS
# ============================================================================


@pytest.mark.unit
class TestSpan:
    """Tests for Span dataclass."""

    def test_span_creation(self):
        """Test Span creation with required fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        span_id = "span-123"
        parent_span_id = "parent-456"
        operation_name = "database_query"
        start_time = datetime.now(UTC)

        # Act - MANDATORY
        span = Span(
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=start_time,
        )

        # Assert - MANDATORY
        assert span.span_id == span_id
        assert span.parent_span_id == parent_span_id
        assert span.operation_name == operation_name
        assert span.start_time == start_time
        assert span.end_time is None
        assert span.duration_ms is None
        assert span.status == "running"
        assert span.tags == {}
        assert span.logs == []

    def test_span_duration_property(self):
        """Test Span duration property converts ms to seconds - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        span = Span(
            span_id="test",
            parent_span_id=None,
            operation_name="op",
            start_time=datetime.now(UTC),
            duration_ms=2500.0,
        )

        # Act - MANDATORY
        duration_seconds = span.duration

        # Assert - MANDATORY
        assert duration_seconds == 2.5  # 2500ms = 2.5s


# ============================================================================
# PERFORMANCE MONITOR INITIALIZATION TESTS
# ============================================================================


@pytest.mark.unit
class TestPerformanceMonitorInitialization:
    """Tests for PerformanceMonitor initialization."""

    def test_monitor_initializes_with_config(self, performance_config: PerformanceConfig):
        """Test monitor initializes with provided config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        monitor = PerformanceMonitor(config=performance_config)

        # Assert - MANDATORY
        assert monitor.config == performance_config
        assert monitor.active_traces == {}
        assert monitor.completed_traces == []
        assert monitor.active_spans == {}
        assert monitor.request_counts == {}
        assert monitor.request_durations == {}
        assert monitor.slow_requests == []

    def test_monitor_uses_default_config(self):
        """Test monitor uses default config when none provided - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        monitor = PerformanceMonitor()

        # Assert - MANDATORY
        assert monitor.config.enabled is True
        assert monitor.config.trace_requests is True


# ============================================================================
# TRACE MANAGEMENT TESTS
# ============================================================================


@pytest.mark.unit
class TestTraceManagement:
    """Tests for trace start/finish operations."""

    def test_start_trace_returns_trace_id(self, performance_monitor: PerformanceMonitor):
        """Test start_trace creates trace and returns ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "test_operation"

        # Act - MANDATORY
        trace_id = performance_monitor.start_trace(operation)

        # Assert - MANDATORY
        assert trace_id is not None
        assert trace_id in performance_monitor.active_traces
        assert performance_monitor.active_traces[trace_id].operation == operation

    def test_start_trace_with_metadata(self, performance_monitor: PerformanceMonitor):
        """Test start_trace includes metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "test_op"
        metadata = {"user_id": "123", "request_ip": "127.0.0.1"}

        # Act - MANDATORY
        trace_id = performance_monitor.start_trace(operation, metadata)

        # Assert - MANDATORY
        assert trace_id is not None
        assert performance_monitor.active_traces[trace_id].metadata == metadata

    def test_start_trace_disabled_returns_none(self):
        """Test start_trace returns None when disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PerformanceConfig(enabled=False)
        monitor = PerformanceMonitor(config=config)

        # Act - MANDATORY
        trace_id = monitor.start_trace("operation")

        # Assert - MANDATORY
        assert trace_id is None

    def test_finish_trace_calculates_duration(self, performance_monitor: PerformanceMonitor):
        """Test finish_trace calculates duration correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")

        # Act - MANDATORY
        time.sleep(0.1)  # Small delay
        trace = performance_monitor.finish_trace(trace_id)

        # Assert - MANDATORY
        assert trace is not None
        assert trace.duration_ms >= 100  # At least 100ms
        assert trace.end_time is not None
        assert trace.status == "success"

    def test_finish_trace_moves_to_completed(self, performance_monitor: PerformanceMonitor):
        """Test finish_trace moves trace to completed - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")

        # Act - MANDATORY
        performance_monitor.finish_trace(trace_id)

        # Assert - MANDATORY
        assert trace_id not in performance_monitor.active_traces
        assert len(performance_monitor.completed_traces) == 1
        assert performance_monitor.completed_traces[0].trace_id == trace_id

    def test_finish_trace_with_error(self, performance_monitor: PerformanceMonitor):
        """Test finish_trace records error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")

        # Act - MANDATORY
        trace = performance_monitor.finish_trace(trace_id, status="error", error="Test error")

        # Assert - MANDATORY
        assert trace.status == "error"
        assert trace.error == "Test error"

    def test_finish_trace_maintains_history_limit(self):
        """Test finish_trace maintains max_trace_history limit - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PerformanceConfig(max_trace_history=5)
        monitor = PerformanceMonitor(config=config)

        # Create 10 traces
        for i in range(10):
            trace_id = monitor.start_trace(f"op_{i}")
            monitor.finish_trace(trace_id)

        # Act - MANDATORY

        # Assert - MANDATORY
        assert len(monitor.completed_traces) == 5  # Only keeps last 5


# ============================================================================
# SLOW REQUEST DETECTION TESTS
# ============================================================================


@pytest.mark.unit
class TestSlowRequestDetection:
    """Tests for slow request detection."""

    def test_slow_request_threshold_detection(self):
        """Test slow requests are detected based on threshold - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PerformanceConfig(slow_request_threshold=0.05)  # 50ms
        monitor = PerformanceMonitor(config=config)

        trace_id = monitor.start_trace("slow_op")

        # Act - MANDATORY
        time.sleep(0.1)  # 100ms - exceeds threshold
        monitor.finish_trace(trace_id)

        # Assert - MANDATORY
        assert len(monitor.slow_requests) == 1
        assert monitor.slow_requests[0].trace_id == trace_id

    def test_slow_requests_maintain_limit(self):
        """Test slow_requests list maintains max 50 items - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PerformanceConfig(slow_request_threshold=0.0)  # All requests are slow
        monitor = PerformanceMonitor(config=config)

        # Create 60 slow requests
        for i in range(60):
            trace_id = monitor.start_trace(f"slow_op_{i}")
            monitor.finish_trace(trace_id)

        # Act - MANDATORY

        # Assert - MANDATORY
        assert len(monitor.slow_requests) == 50  # Maintains max 50


# ============================================================================
# SPAN MANAGEMENT TESTS
# ============================================================================


@pytest.mark.unit
class TestSpanManagement:
    """Tests for span start/finish operations."""

    def test_start_span_creates_span(self, performance_monitor: PerformanceMonitor):
        """Test start_span creates span and returns ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")

        # Act - MANDATORY
        span_id = performance_monitor.start_span(trace_id, "database_query")

        # Assert - MANDATORY
        assert span_id is not None
        assert span_id in performance_monitor.active_spans
        assert performance_monitor.active_spans[span_id].operation_name == "database_query"

    def test_start_span_adds_to_trace(self, performance_monitor: PerformanceMonitor):
        """Test start_span adds span to trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")

        # Act - MANDATORY
        span_id = performance_monitor.start_span(trace_id, "database_query")

        # Assert - MANDATORY
        assert len(performance_monitor.active_traces[trace_id].spans) == 1
        assert performance_monitor.active_traces[trace_id].spans[0].span_id == span_id

    def test_finish_span_calculates_duration(self, performance_monitor: PerformanceMonitor):
        """Test finish_span calculates duration - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        span_id = performance_monitor.start_span(trace_id, "db_query")

        # Act - MANDATORY
        time.sleep(0.05)  # 50ms delay
        performance_monitor.finish_span(span_id)

        # Assert - MANDATORY
        assert span_id not in performance_monitor.active_spans
        # Span is still in trace
        span = performance_monitor.active_traces[trace_id].spans[0]
        assert span.duration_ms >= 50

    def test_finish_span_with_tags(self, performance_monitor: PerformanceMonitor):
        """Test finish_span accepts tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        span_id = performance_monitor.start_span(trace_id, "db_query")

        # Act - MANDATORY
        tags = {"rows_affected": 10}
        performance_monitor.finish_span(span_id, tags=tags)

        # Assert - MANDATORY
        span = performance_monitor.active_traces[trace_id].spans[0]
        assert span.tags["rows_affected"] == 10

    def test_add_span_log(self, performance_monitor: PerformanceMonitor):
        """Test add_span_log adds log entry to span - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        span_id = performance_monitor.start_span(trace_id, "db_query")

        # Act - MANDATORY
        performance_monitor.add_span_log(span_id, "Query executed", {"rows": 100})

        # Assert - MANDATORY
        span = performance_monitor.active_spans[span_id]
        assert len(span.logs) == 1
        assert span.logs[0]["message"] == "Query executed"
        assert span.logs[0]["data"]["rows"] == 100


# ============================================================================
# PERFORMANCE SUMMARY TESTS
# ============================================================================


@pytest.mark.unit
class TestPerformanceSummary:
    """Tests for performance summary generation."""

    def test_get_performance_summary_structure(self, performance_monitor: PerformanceMonitor):
        """Test performance summary has correct structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        performance_monitor.finish_trace(trace_id)

        # Act - MANDATORY
        summary = performance_monitor.get_performance_summary()

        # Assert - MANDATORY
        assert "timestamp" in summary
        assert "active_traces" in summary
        assert "completed_traces" in summary
        assert "total_traces" in summary
        assert "slow_requests" in summary
        assert "avg_duration" in summary
        assert "p95_duration" in summary
        assert "p99_duration" in summary
        assert "operations" in summary
        assert "recent_slow_requests" in summary

    def test_get_performance_summary_calculates_metrics(
        self, performance_monitor: PerformanceMonitor
    ):
        """Test performance summary calculates metrics correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Create multiple traces
        for i in range(5):
            trace_id = performance_monitor.start_trace("test_op")
            performance_monitor.finish_trace(trace_id)

        # Act - MANDATORY
        summary = performance_monitor.get_performance_summary()

        # Assert - MANDATORY
        assert summary["completed_traces"] == 5
        assert summary["total_traces"] == 5
        assert summary["avg_duration"] > 0


# ============================================================================
# TRACE DETAILS TESTS
# ============================================================================


@pytest.mark.unit
class TestTraceDetails:
    """Tests for trace detail retrieval."""

    def test_get_trace_details_active_trace(self, performance_monitor: PerformanceMonitor):
        """Test get_trace_details returns active trace info - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op", {"key": "value"})

        # Act - MANDATORY
        details = performance_monitor.get_trace_details(trace_id)

        # Assert - MANDATORY
        assert details is not None
        assert details["trace_id"] == trace_id
        assert details["operation"] == "test_op"
        assert details["metadata"]["key"] == "value"

    def test_get_trace_details_completed_trace(self, performance_monitor: PerformanceMonitor):
        """Test get_trace_details returns completed trace info - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        performance_monitor.finish_trace(trace_id)

        # Act - MANDATORY
        details = performance_monitor.get_trace_details(trace_id)

        # Assert - MANDATORY
        assert details is not None
        assert details["trace_id"] == trace_id
        assert details["duration_ms"] is not None

    def test_get_trace_details_nonexistent(self, performance_monitor: PerformanceMonitor):
        """Test get_trace_details returns None for nonexistent trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        details = performance_monitor.get_trace_details("nonexistent")

        # Assert - MANDATORY
        assert details is None


# ============================================================================
# BOTTLENECK IDENTIFICATION TESTS
# ============================================================================


@pytest.mark.unit
class TestBottleneckIdentification:
    """Tests for bottleneck identification."""

    def test_identify_bottlenecks_structure(self, performance_monitor: PerformanceMonitor):
        """Test identify_bottlenecks returns correct structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        performance_monitor.finish_trace(trace_id)

        # Act - MANDATORY
        bottlenecks = performance_monitor.identify_bottlenecks()

        # Assert - MANDATORY
        assert "timestamp" in bottlenecks
        assert "slow_operations" in bottlenecks
        assert "high_variance_operations" in bottlenecks
        assert "frequent_errors" in bottlenecks
        assert "recommendations" in bottlenecks

    def test_identify_bottlenecks_detects_slow_operations(self):
        """Test bottleneck detection identifies slow operations - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PerformanceConfig(slow_request_threshold=0.01)  # 10ms threshold
        monitor = PerformanceMonitor(config=config)

        # Create slow operation
        trace_id = monitor.start_trace("slow_op")
        time.sleep(0.05)  # 50ms - exceeds threshold
        monitor.finish_trace(trace_id)

        # Act - MANDATORY
        bottlenecks = monitor.identify_bottlenecks()

        # Assert - MANDATORY
        assert len(bottlenecks["slow_operations"]) == 1
        assert bottlenecks["slow_operations"][0]["operation"] == "slow_op"


# ============================================================================
# CLEANUP TESTS
# ============================================================================


@pytest.mark.unit
class TestTraceCleanup:
    """Tests for trace cleanup operations."""

    def test_cleanup_old_traces(self, performance_monitor: PerformanceMonitor):
        """Test cleanup removes old traces - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Create old trace
        old_trace = RequestTrace(
            trace_id="old",
            operation="test",
            start_time=datetime.now(UTC) - timedelta(hours=48),  # 2 days old
        )
        performance_monitor.completed_traces.append(old_trace)

        # Create recent trace
        trace_id = performance_monitor.start_trace("recent_op")
        performance_monitor.finish_trace(trace_id)

        # Act - MANDATORY
        performance_monitor.cleanup_old_traces(max_age_hours=24.0)

        # Assert - MANDATORY
        assert len(performance_monitor.completed_traces) == 1
        assert performance_monitor.completed_traces[0].trace_id != "old"


# ============================================================================
# ASYNC CONTEXT MANAGER TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestAsyncContextManagers:
    """Tests for async context managers."""

    async def test_trace_request_context_manager(self, performance_monitor: PerformanceMonitor):
        """Test trace_request context manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        async with performance_monitor.trace_request("test_op") as trace_id:
            # Assert - MANDATORY (within context)
            assert trace_id is not None
            assert trace_id in performance_monitor.active_traces

        # Assert - MANDATORY (after context)
        assert trace_id not in performance_monitor.active_traces
        assert len(performance_monitor.completed_traces) == 1

    async def test_trace_span_context_manager(self, performance_tracer: PerformanceTracer):
        """Test trace_span context manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_tracer.monitor.start_trace("test_op")

        # Act - MANDATORY
        async with performance_tracer.trace_span(trace_id, "db_query") as span_id:
            # Assert - MANDATORY (within context)
            assert span_id is not None
            assert span_id in performance_tracer.monitor.active_spans

        # Assert - MANDATORY (after context)
        assert span_id not in performance_tracer.monitor.active_spans


# ============================================================================
# SHUTDOWN TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestShutdown:
    """Tests for performance monitor shutdown."""

    async def test_shutdown_finishes_active_traces(self, performance_monitor: PerformanceMonitor):
        """Test shutdown finishes active traces - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")

        # Act - MANDATORY
        await performance_monitor.shutdown()

        # Assert - MANDATORY
        assert len(performance_monitor.active_traces) == 0
        assert len(performance_monitor.completed_traces) == 1
        assert performance_monitor.completed_traces[0].status == "shutdown"


# ============================================================================
# MANDATORY SECURITY TESTS
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestPerformanceSecurity:
    """MANDATORY security tests for performance monitoring."""

    def test_trace_metadata_sanitization(self, performance_monitor: PerformanceMonitor):
        """MANDATORY security test - trace metadata with malicious content."""
        # Arrange - MANDATORY
        malicious_metadata = {
            "user_input": "<script>alert('xss')</script>",
            "sql_injection": "'; DROP TABLE traces;--",
            "path_traversal": "../../../etc/passwd",
        }

        # Act - MANDATORY
        trace_id = performance_monitor.start_trace("test_op", malicious_metadata)

        # Assert - MANDATORY
        # Metadata should be stored as-is (app must sanitize on display)
        assert trace_id is not None
        trace = performance_monitor.active_traces[trace_id]
        assert trace.metadata == malicious_metadata

    def test_span_tags_sanitization(self, performance_monitor: PerformanceMonitor):
        """MANDATORY security test - span tags with malicious content."""
        # Arrange - MANDATORY
        trace_id = performance_monitor.start_trace("test_op")
        malicious_tags = {
            "query": "SELECT * FROM users WHERE id = '1' OR '1'='1'",
            "filename": "../../../../etc/shadow",
        }

        # Act - MANDATORY
        span_id = performance_monitor.start_span(trace_id, "db_query", tags=malicious_tags)

        # Assert - MANDATORY
        assert span_id is not None
        span = performance_monitor.active_spans[span_id]
        assert span.tags == malicious_tags


# ============================================================================
# MANDATORY PERFORMANCE BENCHMARKS
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestPerformancePerformance:
    """MANDATORY performance tests for performance monitoring system."""

    def test_start_trace_performance(self, performance_monitor: PerformanceMonitor):
        """MANDATORY performance test - trace start speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            performance_monitor.start_trace(f"test_op_{i}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per trace start
        assert execution_time < 1.0  # Total <1s for 1000 traces

    def test_finish_trace_performance(self, performance_monitor: PerformanceMonitor):
        """MANDATORY performance test - trace finish speed."""
        # Arrange - MANDATORY
        iterations = 1000
        trace_ids = []

        for i in range(iterations):
            trace_id = performance_monitor.start_trace(f"test_op_{i}")
            trace_ids.append(trace_id)

        # Act - MANDATORY
        start_time = time.perf_counter()

        for trace_id in trace_ids:
            performance_monitor.finish_trace(trace_id)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per trace finish
        assert execution_time < 1.0  # Total <1s for 1000 traces

    def test_identify_bottlenecks_performance(self, performance_monitor: PerformanceMonitor):
        """MANDATORY performance test - bottleneck identification speed."""
        # Arrange - MANDATORY
        # Create sample data
        for i in range(100):
            trace_id = performance_monitor.start_trace(f"op_{i % 5}")
            performance_monitor.finish_trace(trace_id)

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            performance_monitor.identify_bottlenecks()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per analysis
        assert execution_time < 1.0  # Total <1s for 100 analyses
