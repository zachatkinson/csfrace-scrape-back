"""Performance monitoring with request tracing and bottleneck identification."""

import secrets
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring."""

    enabled: bool = True
    trace_requests: bool = True
    trace_sampling_rate: float = 1.0  # 1.0 = trace all requests
    slow_request_threshold: float = 5.0  # seconds
    memory_profiling_enabled: bool = False
    detailed_metrics: bool = True
    max_trace_history: int = 1000


@dataclass
class RequestTrace:
    """Represents a request trace with timing information."""

    trace_id: str
    operation: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)
    spans: list["Span"] = field(default_factory=list)
    error: str | None = None
    correlation_id: str | None = None

    @property
    def duration(self) -> float | None:
        """Get duration in seconds (compatibility alias for duration_ms)."""
        return self.duration_ms / 1000 if self.duration_ms is not None else None


@dataclass
class Span:
    """Represents a span within a trace."""

    span_id: str
    parent_span_id: str | None
    operation_name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    status: str = "running"
    tags: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float | None:
        """Get duration in seconds (compatibility alias for duration_ms)."""
        return self.duration_ms / 1000 if self.duration_ms is not None else None


class PerformanceMonitor:
    """Performance monitoring with distributed tracing capabilities."""

    def __init__(self, config: PerformanceConfig | None = None):
        """Initialize performance monitor.

        Args:
            config: Performance monitoring configuration
        """
        self.config = config or PerformanceConfig()
        self.active_traces: dict[str, RequestTrace] = {}
        self.completed_traces: list[RequestTrace] = []
        self.active_spans: dict[str, Span] = {}

        # Performance metrics
        self.request_counts: dict[str, int] = {}
        self.request_durations: dict[str, list[float]] = {}
        self.slow_requests: list[RequestTrace] = []

        logger.info(
            "Performance monitor initialized",
            enabled=self.config.enabled,
            tracing=self.config.trace_requests,
        )

    def start_trace(
        self, operation: str, metadata: dict[str, Any] | None = None
    ) -> str | None:
        """Start a new request trace.

        Args:
            operation: Name of the operation being traced
            metadata: Additional metadata for the trace

        Returns:
            Trace ID
        """
        if not self.config.enabled or not self.config.trace_requests:
            return None

        # Sample based on configured rate
        if (
            self.config.trace_sampling_rate < 1.0
            and secrets.SystemRandom().random() > self.config.trace_sampling_rate
        ):
            return None

        trace_id = str(uuid.uuid4())
        metadata = metadata or {}

        trace = RequestTrace(
            trace_id=trace_id,
            operation=operation,
            start_time=datetime.now(UTC),
            metadata=metadata,
            correlation_id=metadata.get("correlation_id"),
        )

        self.active_traces[trace_id] = trace

        logger.debug("Started trace", trace_id=trace_id, operation=operation)

        return trace_id

    def finish_trace(
        self, trace_id: str, status: str = "success", error: str | None = None
    ) -> RequestTrace | None:
        """Finish a request trace.

        Args:
            trace_id: Trace ID to finish
            status: Final status of the trace
            error: Error message if trace failed

        Returns:
            Completed trace or None if not found
        """
        if not trace_id or trace_id not in self.active_traces:
            return None

        trace = self.active_traces[trace_id]
        trace.end_time = datetime.now(UTC)
        trace.duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
        trace.status = status
        trace.error = error

        # Move to completed traces
        del self.active_traces[trace_id]
        self.completed_traces.append(trace)

        # Maintain history limit
        if len(self.completed_traces) > self.config.max_trace_history:
            self.completed_traces = self.completed_traces[-self.config.max_trace_history :]

        # Update metrics
        operation = trace.operation
        if operation not in self.request_counts:
            self.request_counts[operation] = 0
            self.request_durations[operation] = []

        self.request_counts[operation] += 1
        self.request_durations[operation].append(trace.duration_ms)

        # Keep recent durations only
        if len(self.request_durations[operation]) > 100:
            self.request_durations[operation] = self.request_durations[operation][-100:]

        # Check for slow requests
        if trace.duration_ms > (self.config.slow_request_threshold * 1000):
            self.slow_requests.append(trace)
            # Keep recent slow requests only
            if len(self.slow_requests) > 50:
                self.slow_requests = self.slow_requests[-50:]

            logger.warning(
                "Slow request detected",
                trace_id=trace_id,
                operation=operation,
                duration_ms=trace.duration_ms,
                threshold_ms=self.config.slow_request_threshold * 1000,
            )

        logger.debug(
            "Finished trace",
            trace_id=trace_id,
            operation=operation,
            duration_ms=trace.duration_ms,
            status=status,
        )

        return trace

    def start_span(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> str | None:
        """Start a new span within a trace.

        Args:
            trace_id: Parent trace ID
            operation_name: Name of the operation
            parent_span_id: Parent span ID if nested
            tags: Additional tags for the span

        Returns:
            Span ID
        """
        if not self.config.enabled or not trace_id:
            return None

        span_id = str(uuid.uuid4())
        span = Span(
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=datetime.now(UTC),
            tags=tags or {},
        )

        self.active_spans[span_id] = span

        # Add to trace
        if trace_id in self.active_traces:
            self.active_traces[trace_id].spans.append(span)

        return span_id

    def finish_span(self, span_id: str, tags: dict[str, Any] | None = None) -> None:
        """Finish a span.

        Args:
            span_id: Span ID to finish
            tags: Additional tags to add
        """
        if not span_id or span_id not in self.active_spans:
            return

        span = self.active_spans[span_id]
        span.end_time = datetime.now(UTC)
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000

        # Set status to success if not error
        if tags and "error" in tags:
            span.status = "error"
        else:
            span.status = "success"

        if tags:
            span.tags.update(tags)

        del self.active_spans[span_id]

        logger.debug(
            "Finished span",
            span_id=span_id,
            operation=span.operation_name,
            duration_ms=span.duration_ms,
        )

    def add_span_log(
        self, span_id: str, message: str, data: dict[str, Any] | None = None
    ) -> None:
        """Add a log entry to a span.

        Args:
            span_id: Span ID to add log to
            message: Log message
            data: Additional log data
        """
        if not span_id or span_id not in self.active_spans:
            return

        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "message": message,
            "data": data or {},
        }

        self.active_spans[span_id].logs.append(log_entry)

    @asynccontextmanager
    async def trace_request(
        self, operation: str, metadata: dict[str, Any] | None = None
    ) -> AsyncGenerator[str | None]:
        """Context manager for tracing requests.

        Args:
            operation: Operation name
            metadata: Additional metadata

        Yields:
            Trace ID
        """
        trace_id = self.start_trace(operation, metadata)

        if trace_id is None:
            # Tracing is disabled or sampled out
            yield None
            return

        try:
            yield trace_id
            self.finish_trace(trace_id, "success")
        except Exception as e:
            self.finish_trace(trace_id, "error", str(e))
            raise

    @asynccontextmanager
    async def trace_span(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str | None]:
        """Context manager for tracing spans.

        Args:
            trace_id: Parent trace ID
            operation_name: Span operation name
            parent_span_id: Parent span ID
            tags: Span tags

        Yields:
            Span ID
        """
        span_id = self.start_span(trace_id, operation_name, parent_span_id, tags)

        if span_id is None:
            # Tracing is disabled
            yield None
            return

        try:
            yield span_id
            self.finish_span(span_id)
        except Exception as e:
            self.finish_span(span_id, {"error": str(e)})
            raise

    async def profile_memory_usage(self, trace_id: str) -> dict[str, Any]:
        """Profile memory usage during a trace.

        Args:
            trace_id: Trace ID to profile

        Returns:
            Memory usage information
        """
        if not self.config.memory_profiling_enabled:
            return {}

        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            profile = {
                "rss_bytes": memory_info.rss,
                "vms_bytes": memory_info.vms,
                "percent": process.memory_percent(),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Add to trace metadata
            if trace_id in self.active_traces:
                if "memory_profile" not in self.active_traces[trace_id].metadata:
                    self.active_traces[trace_id].metadata["memory_profile"] = []
                self.active_traces[trace_id].metadata["memory_profile"].append(profile)

            return profile

        except Exception as e:
            logger.error("Memory profiling failed", error=str(e))
            return {}

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance monitoring summary.

        Returns:
            Performance summary dictionary
        """
        # Calculate overall statistics
        all_durations = []
        total_requests = 0
        for durations in self.request_durations.values():
            all_durations.extend(durations)
            total_requests += len(durations)

        summary: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "active_traces": len(self.active_traces),
            "completed_traces": len(self.completed_traces),
            "total_traces": total_requests,
            "slow_requests": len(self.slow_requests),
            "avg_duration": sum(all_durations) / len(all_durations) if all_durations else 0,
            "p95_duration": self._percentile(all_durations, 95) if all_durations else 0,
            "p99_duration": self._percentile(all_durations, 99) if all_durations else 0,
            "operations": {},
        }

        # Calculate operation statistics
        for operation, count in self.request_counts.items():
            durations = self.request_durations.get(operation, [])
            if durations:
                summary["operations"][operation] = {
                    "count": count,
                    "avg_duration_ms": sum(durations) / len(durations),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "p95_duration_ms": self._percentile(durations, 95),
                    "p99_duration_ms": self._percentile(durations, 99),
                }

        # Recent slow requests
        summary["recent_slow_requests"] = [
            {
                "trace_id": trace.trace_id,
                "operation": trace.operation,
                "duration_ms": trace.duration_ms,
                "timestamp": trace.start_time.isoformat(),
            }
            for trace in self.slow_requests[-10:]  # Last 10
        ]

        return summary

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of a list of values.

        Args:
            data: List of values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))

        if index >= len(sorted_data):
            return sorted_data[-1]

        return sorted_data[index]

    def get_trace_details(self, trace_id: str) -> dict[str, Any] | None:
        """Get detailed information about a specific trace.

        Args:
            trace_id: Trace ID to get details for

        Returns:
            Trace details or None if not found
        """
        # Check active traces first
        trace = self.active_traces.get(trace_id)
        if not trace:
            # Check completed traces
            for completed_trace in self.completed_traces:
                if completed_trace.trace_id == trace_id:
                    trace = completed_trace
                    break

        if not trace:
            return None

        return {
            "trace_id": trace.trace_id,
            "operation": trace.operation,
            "start_time": trace.start_time.isoformat(),
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "duration_ms": trace.duration_ms,
            "status": trace.status,
            "error": trace.error,
            "metadata": trace.metadata,
            "spans": [
                {
                    "span_id": span.span_id,
                    "parent_span_id": span.parent_span_id,
                    "operation_name": span.operation_name,
                    "start_time": span.start_time.isoformat(),
                    "end_time": span.end_time.isoformat() if span.end_time else None,
                    "duration_ms": span.duration_ms,
                    "tags": span.tags,
                    "logs": span.logs,
                }
                for span in trace.spans
            ],
        }

    def identify_bottlenecks(self) -> dict[str, Any]:
        """Identify performance bottlenecks based on collected data.

        Returns:
            Bottleneck analysis
        """
        bottlenecks: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "slow_operations": [],
            "high_variance_operations": [],
            "frequent_errors": [],
            "recommendations": [],
        }

        # Analyze slow operations
        for operation, durations in self.request_durations.items():
            if not durations:
                continue

            avg_duration = sum(durations) / len(durations)
            if avg_duration > (
                self.config.slow_request_threshold * 500
            ):  # Half threshold for warnings
                bottlenecks["slow_operations"].append(
                    {
                        "operation": operation,
                        "avg_duration_ms": avg_duration,
                        "sample_count": len(durations),
                        "p95_duration_ms": self._percentile(durations, 95),
                    }
                )

        # Analyze variance (inconsistent performance)
        for operation, durations in self.request_durations.items():
            if len(durations) < 5:  # Need minimum samples
                continue

            avg_duration = sum(durations) / len(durations)
            variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
            std_dev = variance**0.5

            # High variance indicates inconsistent performance
            if std_dev > avg_duration * 0.5:  # Standard deviation > 50% of mean
                bottlenecks["high_variance_operations"].append(
                    {
                        "operation": operation,
                        "avg_duration_ms": avg_duration,
                        "std_dev_ms": std_dev,
                        "coefficient_of_variation": std_dev / avg_duration
                        if avg_duration > 0
                        else 0,
                    }
                )

        # Generate recommendations
        if bottlenecks["slow_operations"]:
            bottlenecks["recommendations"].append(
                "Consider optimizing slow operations or increasing timeout thresholds"
            )

        if bottlenecks["high_variance_operations"]:
            bottlenecks["recommendations"].append(
                "Investigate operations with high variance - may indicate resource contention"
            )

        if len(self.slow_requests) > 10:
            bottlenecks["recommendations"].append(
                "High number of slow requests detected - consider scaling or optimization"
            )

        return bottlenecks

    def cleanup_old_traces(self, max_age_hours: float = 24.0) -> None:
        """Clean up old completed traces.

        Args:
            max_age_hours: Maximum age in hours for keeping traces
        """
        from datetime import timedelta

        cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

        # Filter out old traces
        self.completed_traces = [
            trace for trace in self.completed_traces if trace.start_time >= cutoff_time
        ]

        # Also clean up old slow requests
        self.slow_requests = [
            trace for trace in self.slow_requests if trace.start_time >= cutoff_time
        ]

    def get_slow_requests_summary(self) -> dict[str, Any]:
        """Get summary of slow requests.

        Returns:
            Summary of slow request statistics
        """
        summary = {
            "count": len(self.slow_requests),
            "threshold": self.config.slow_request_threshold,
            "operations": {},
            "recent_requests": [],
        }

        # Group by operation
        operation_counts = {}
        for trace in self.slow_requests:
            if trace.operation not in operation_counts:
                operation_counts[trace.operation] = 0
            operation_counts[trace.operation] += 1

        summary["operations"] = operation_counts

        # Recent requests (last 10)
        summary["recent_requests"] = [
            {
                "trace_id": trace.trace_id,
                "operation": trace.operation,
                "duration_ms": trace.duration_ms,
                "timestamp": trace.start_time.isoformat(),
            }
            for trace in self.slow_requests[-10:]
        ]

        return summary

    async def shutdown(self) -> None:
        """Shutdown performance monitor."""
        # Finish any active traces
        for trace_id in list(self.active_traces.keys()):
            self.finish_trace(trace_id, "shutdown", "System shutdown")

        logger.info("Performance monitor shutdown")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
