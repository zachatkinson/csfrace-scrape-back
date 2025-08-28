"""Tests for performance monitoring system."""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.monitoring.performance import (
    PerformanceConfig,
    PerformanceMonitor,
    RequestTrace,
    Span,
    performance_monitor,
)


class TestPerformanceConfig:
    """Test performance monitoring configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PerformanceConfig()

        assert config.enabled is True
        assert config.trace_requests is True
        assert config.trace_sampling_rate == 1.0
        assert config.slow_request_threshold == 5.0
        assert config.memory_profiling_enabled is False
        assert config.detailed_metrics is True
        assert config.max_trace_history == 1000

    def test_custom_config(self):
        """Test custom configuration."""
        config = PerformanceConfig(
            enabled=False,
            trace_requests=False,
            slow_request_threshold=2.5,
            trace_sampling_rate=0.1,
            memory_profiling_enabled=True,
            detailed_metrics=False,
            max_trace_history=500,
        )

        assert config.enabled is False
        assert config.trace_requests is False
        assert config.slow_request_threshold == 2.5
        assert config.trace_sampling_rate == 0.1
        assert config.memory_profiling_enabled is True
        assert config.detailed_metrics is False
        assert config.max_trace_history == 500


class TestSpan:
    """Test trace span functionality."""

    def test_span_creation(self):
        """Test creating a trace span."""
        span_id = str(uuid4())
        start_time = datetime.now(timezone.utc)
        span = Span(
            span_id=span_id,
            parent_span_id=None,
            operation_name="test_operation",
            start_time=start_time,
        )

        assert span.span_id == span_id
        assert span.operation_name == "test_operation"
        assert span.start_time == start_time
        assert span.end_time is None
        assert span.duration_ms is None
        assert span.tags == {}

    def test_span_completion(self):
        """Test completing a trace span."""
        start_time = datetime.now(timezone.utc)
        span = Span(
            span_id=str(uuid4()),
            parent_span_id=None,
            operation_name="test_operation",
            start_time=start_time,
        )

        time.sleep(0.1)  # Small delay
        end_time = datetime.now(timezone.utc)
        span.end_time = end_time
        span.duration_ms = (end_time - start_time).total_seconds() * 1000

        assert span.end_time == end_time
        assert span.duration_ms is not None
        assert span.duration_ms > 0

    def test_span_with_metadata(self):
        """Test span with tags."""
        tags = {"user_id": "123", "endpoint": "/api/test"}
        span = Span(
            span_id=str(uuid4()),
            parent_span_id=None,
            operation_name="api_request",
            start_time=datetime.now(timezone.utc),
            tags=tags,
        )

        assert span.tags == tags


class TestRequestTrace:
    """Test request trace functionality."""

    def test_trace_creation(self):
        """Test creating a request trace."""
        trace_id = str(uuid4())
        trace = RequestTrace(trace_id=trace_id, operation="test_request", start_time=time.time())

        assert trace.trace_id == trace_id
        assert trace.operation == "test_request"
        assert trace.status == "running"
        assert trace.spans == []
        assert trace.correlation_id is None

    def test_adding_spans(self):
        """Test adding spans to a trace."""
        trace = RequestTrace(
            trace_id=str(uuid4()), operation="test_request", start_time=time.time()
        )

        span1 = Span(
            span_id=str(uuid4()),
            parent_span_id=None,
            operation_name="database_query",
            start_time=datetime.now(timezone.utc),
        )

        span2 = Span(
            span_id=str(uuid4()),
            parent_span_id=None,
            operation_name="cache_lookup",
            start_time=datetime.now(timezone.utc),
        )

        trace.spans.append(span1)
        trace.spans.append(span2)

        assert len(trace.spans) == 2
        assert trace.spans[0] == span1
        assert trace.spans[1] == span2

    def test_trace_completion(self):
        """Test completing a trace."""
        start_time = time.time()
        trace = RequestTrace(
            trace_id=str(uuid4()),
            operation="test_request",
            start_time=datetime.fromtimestamp(start_time, timezone.utc),
        )

        time.sleep(0.1)
        end_time = time.time()
        trace.end_time = datetime.fromtimestamp(end_time, timezone.utc)
        trace.duration_ms = (end_time - start_time) * 1000
        trace.status = "success"

        assert trace.status == "success"
        assert trace.end_time is not None
        assert trace.duration is not None
        assert trace.duration > 0


class TestPerformanceMonitor:
    """Test performance monitor functionality."""

    @pytest.fixture
    def monitor(self):
        """Create performance monitor for testing."""
        config = PerformanceConfig(
            enabled=True, trace_requests=True, slow_request_threshold=0.1, max_trace_history=100
        )
        return PerformanceMonitor(config)

    @pytest.fixture
    def disabled_monitor(self):
        """Create disabled performance monitor."""
        config = PerformanceConfig(enabled=False)
        return PerformanceMonitor(config)

    def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.config.enabled is True
        assert monitor.active_traces == {}
        assert monitor.completed_traces == []
        assert monitor.slow_requests == []

    def test_initialization_disabled(self, disabled_monitor):
        """Test disabled monitor initialization."""
        assert disabled_monitor.config.enabled is False

    @pytest.mark.asyncio
    async def test_shutdown(self, monitor):
        """Test shutting down monitor."""
        await monitor.shutdown()
        # Shutdown should complete without error

    def test_start_trace(self, monitor):
        """Test starting a trace."""
        trace_id = monitor.start_trace("test_operation")

        assert trace_id is not None
        assert trace_id in monitor.active_traces

        trace = monitor.active_traces[trace_id]
        assert trace.operation == "test_operation"
        assert trace.status == "running"

    def test_start_trace_with_metadata(self, monitor):
        """Test starting trace with metadata."""
        metadata = {"user": "test", "method": "GET"}
        trace_id = monitor.start_trace("api_request", metadata)

        trace = monitor.active_traces[trace_id]
        assert trace.metadata == metadata

    def test_start_trace_disabled(self, disabled_monitor):
        """Test starting trace when disabled."""
        trace_id = disabled_monitor.start_trace("test_operation")
        assert trace_id is None

    def test_finish_trace_success(self, monitor):
        """Test finishing trace successfully."""
        trace_id = monitor.start_trace("test_operation")

        # Simulate some processing time
        time.sleep(0.05)

        monitor.finish_trace(trace_id, "success")

        # Trace should be moved to completed
        assert trace_id not in monitor.active_traces
        assert len(monitor.completed_traces) == 1

        completed = monitor.completed_traces[0]
        assert completed.trace_id == trace_id
        assert completed.status == "success"
        assert completed.duration is not None

    def test_finish_trace_error(self, monitor):
        """Test finishing trace with error."""
        trace_id = monitor.start_trace("test_operation")

        monitor.finish_trace(trace_id, "error", "Test error message")

        completed = monitor.completed_traces[0]
        assert completed.status == "error"
        assert completed.error == "Test error message"

    def test_finish_trace_nonexistent(self, monitor):
        """Test finishing non-existent trace."""
        # Should not raise exception
        monitor.finish_trace("nonexistent", "success")

    def test_start_span(self, monitor):
        """Test starting a span."""
        trace_id = monitor.start_trace("test_request")
        span_id = monitor.start_span(trace_id, "database_query")

        assert span_id is not None

        trace = monitor.active_traces[trace_id]
        assert len(trace.spans) == 1
        assert trace.spans[0].operation_name == "database_query"
        assert trace.spans[0].status == "running"

    def test_start_span_nonexistent_trace(self, monitor):
        """Test starting span for non-existent trace."""
        span_id = monitor.start_span("nonexistent", "operation")
        assert span_id is None

    def test_finish_span(self, monitor):
        """Test finishing a span."""
        trace_id = monitor.start_trace("test_request")
        span_id = monitor.start_span(trace_id, "database_query")

        time.sleep(0.05)
        monitor.finish_span(trace_id, span_id, "success")

        trace = monitor.active_traces[trace_id]
        span = trace.spans[0]
        assert span.status == "success"
        assert span.duration is not None

    def test_finish_span_nonexistent(self, monitor):
        """Test finishing non-existent span."""
        trace_id = monitor.start_trace("test_request")

        # Should not raise exception
        monitor.finish_span(trace_id, "nonexistent", "success")
        monitor.finish_span("nonexistent", "nonexistent", "success")

    @pytest.mark.asyncio
    async def test_trace_request_context_manager(self, monitor):
        """Test trace request context manager."""
        async with monitor.trace_request("test_operation") as trace_id:
            assert trace_id is not None
            assert trace_id in monitor.active_traces

            # Simulate some work
            await asyncio.sleep(0.05)

        # After context exit, trace should be completed
        assert trace_id not in monitor.active_traces
        assert len(monitor.completed_traces) == 1

    @pytest.mark.asyncio
    async def test_trace_request_context_manager_with_exception(self, monitor):
        """Test context manager handles exceptions."""
        trace_id = None

        try:
            async with monitor.trace_request("test_operation") as tid:
                trace_id = tid
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Trace should still be completed with error status
        assert trace_id not in monitor.active_traces
        assert len(monitor.completed_traces) == 1

        completed = monitor.completed_traces[0]
        assert completed.status == "error"

    @pytest.mark.asyncio
    async def test_trace_span_context_manager(self, monitor):
        """Test trace span context manager."""
        trace_id = monitor.start_trace("test_request")

        async with monitor.trace_span(trace_id, "database_query") as span_id:
            assert span_id is not None
            await asyncio.sleep(0.05)

        trace = monitor.active_traces[trace_id]
        assert len(trace.spans) == 1
        assert trace.spans[0].status == "success"

    def test_record_slow_request(self, monitor):
        """Test recording slow requests."""
        # Create a slow request
        trace_id = monitor.start_trace("slow_operation")
        time.sleep(0.15)  # Longer than threshold (0.1s)
        monitor.finish_trace(trace_id, "success")

        # Should be recorded as slow
        assert len(monitor.slow_requests) == 1
        assert monitor.slow_requests[0].trace_id == trace_id

    def test_max_trace_history_limit(self, monitor):
        """Test maximum traces limit."""
        monitor.config.max_trace_history = 3

        # Create more traces than limit
        for i in range(5):
            trace_id = monitor.start_trace(f"operation_{i}")
            monitor.finish_trace(trace_id, "success")

        # Should only keep the most recent traces
        assert len(monitor.completed_traces) == 3

    def test_trace_sampling(self):
        """Test trace sampling."""
        config = PerformanceConfig(trace_sampling_rate=0.0)  # No sampling
        monitor = PerformanceMonitor(config)

        # Should not create traces due to sampling
        with patch("random.random", return_value=0.5):
            trace_id = monitor.start_trace("test_operation")
            assert trace_id is None

    def test_get_performance_summary(self, monitor):
        """Test getting performance summary."""
        # Create some traces
        for i in range(3):
            trace_id = monitor.start_trace(f"operation_{i}")
            time.sleep(0.02)
            monitor.finish_trace(trace_id, "success")

        summary = monitor.get_performance_summary()

        assert summary["total_traces"] == 3
        assert summary["active_traces"] == 0
        assert summary["completed_traces"] == 3
        assert summary["slow_requests"] == 0
        assert "avg_duration" in summary
        assert "p95_duration" in summary
        assert "p99_duration" in summary

    def test_get_trace_details(self, monitor):
        """Test getting trace details."""
        trace_id = monitor.start_trace("test_operation")
        span_id = monitor.start_span(trace_id, "database_query")
        monitor.finish_span(trace_id, span_id, "success")
        monitor.finish_trace(trace_id, "success")

        details = monitor.get_trace_details(trace_id)

        assert details is not None
        assert details["trace_id"] == trace_id
        assert details["operation"] == "test_operation"
        assert details["status"] == "success"
        assert len(details["spans"]) == 1
        assert details["spans"][0]["operation"] == "database_query"

    def test_get_trace_details_nonexistent(self, monitor):
        """Test getting details for non-existent trace."""
        details = monitor.get_trace_details("nonexistent")
        assert details is None

    def test_cleanup_old_traces(self, monitor):
        """Test cleaning up old traces."""
        # Create traces with old timestamps
        old_time = time.time() - (25 * 3600)  # 25 hours ago

        trace = RequestTrace(trace_id=str(uuid4()), operation="old_operation", start_time=old_time)
        trace.end_time = old_time + 1
        trace.status = "success"

        monitor.completed_traces.append(trace)

        # Cleanup should remove old traces
        monitor.cleanup_old_traces()

        assert len(monitor.completed_traces) == 0

    def test_get_slow_requests_summary(self, monitor):
        """Test getting slow requests summary."""
        # Create slow requests
        for i in range(3):
            trace_id = monitor.start_trace(f"slow_operation_{i}")
            time.sleep(0.15)
            monitor.finish_trace(trace_id, "success")

        summary = monitor.get_slow_requests_summary()

        assert summary["count"] == 3
        assert summary["threshold"] == 0.1
        assert "operations" in summary
        assert len(summary["recent_requests"]) == 3

    @pytest.mark.asyncio
    async def test_concurrent_tracing(self, monitor):
        """Test concurrent trace operations."""

        async def create_trace(operation_id):
            async with monitor.trace_request(f"operation_{operation_id}"):
                await asyncio.sleep(0.05)
                return operation_id

        # Run multiple traces concurrently
        tasks = [create_trace(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert len(monitor.completed_traces) == 5

    def test_correlation_id_tracking(self, monitor):
        """Test correlation ID tracking."""
        correlation_id = str(uuid4())
        metadata = {"correlation_id": correlation_id}

        trace_id = monitor.start_trace("test_operation", metadata)
        monitor.finish_trace(trace_id, "success")

        completed = monitor.completed_traces[0]
        assert completed.correlation_id == correlation_id

    def test_global_performance_monitor(self):
        """Test global performance monitor instance."""
        assert performance_monitor is not None
        assert isinstance(performance_monitor, PerformanceMonitor)
