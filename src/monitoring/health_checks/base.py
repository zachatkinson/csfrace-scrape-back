"""Base health check interface and types."""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import asyncio

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import MonitoringLoggingMixin, get_monitoring_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_monitoring_logger()


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check execution."""

    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def is_healthy(self) -> bool:
        """Check if this result indicates health."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "tags": self.tags,
        }


class HealthCheck(abc.ABC, MonitoringLoggingMixin):
    """Base class for health checks."""

    def __init__(
        self,
        name: str,
        timeout_seconds: float = 30.0,
        tags: list[str] | None = None,
        enabled: bool = True,
    ):
        """Initialize health check.

        Args:
            name: Unique name for this health check
            timeout_seconds: Maximum execution time
            tags: Optional tags for grouping/filtering
            enabled: Whether this check is enabled
        """
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.tags = tags or []
        self.enabled = enabled
        # Use inherited logging from MonitoringLoggingMixin
        # self.logger will be available automatically

    @abc.abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check.

        Returns:
            Health check result
        """
        ...

    @monitoring_error_handler("execute health check")
    async def execute(self) -> HealthCheckResult:
        """Execute the health check with timeout and error handling."""
        if not self.enabled:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Health check disabled",
                duration_ms=0.0,
                tags=self.tags,
            )

        start_time = time.time()

        # Handle TimeoutError specifically for monitoring
        try:
            # Execute with timeout
            result = await asyncio.wait_for(self.check(), timeout=self.timeout_seconds)

            # Ensure result has correct metadata
            result.name = self.name
            result.tags = self.tags
            result.duration_ms = (time.time() - start_time) * 1000

            self.logger.debug(
                "Health check completed", status=result.status.value, duration_ms=result.duration_ms
            )

            return result

        except TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.warning(
                "Health check timed out",
                timeout_seconds=self.timeout_seconds,
                duration_ms=duration_ms,
            )

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout_seconds}s",
                duration_ms=duration_ms,
                tags=self.tags,
            )
        # Enhanced decorator will handle the generic Exception case


class FunctionHealthCheck(HealthCheck):
    """Health check that wraps a simple function."""

    def __init__(
        self,
        name: str,
        check_func: Callable[[], HealthCheckResult] | Callable[[], bool] | Callable[[], str],
        timeout_seconds: float = 30.0,
        tags: list[str] | None = None,
        enabled: bool = True,
    ):
        """Initialize function-based health check.

        Args:
            name: Health check name
            check_func: Function to execute (can return HealthCheckResult, bool, or str)
            timeout_seconds: Maximum execution time
            tags: Optional tags
            enabled: Whether enabled
        """
        super().__init__(name, timeout_seconds, tags, enabled)
        self.check_func = check_func

    @monitoring_error_handler("execute function health check")
    async def check(self) -> HealthCheckResult:
        """Execute the wrapped function."""
        if asyncio.iscoroutinefunction(self.check_func):
            result = await self.check_func()
        else:
            result = self.check_func()

        # Convert different result types to HealthCheckResult
        if isinstance(result, HealthCheckResult):
            return result
        elif isinstance(result, bool):
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                message="OK" if result else "Check failed",
                duration_ms=0.0,  # Will be set by execute()
                tags=self.tags,
            )
        elif isinstance(result, str):
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=result,
                duration_ms=0.0,  # Will be set by execute()
                tags=self.tags,
            )
        else:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=str(result),
                duration_ms=0.0,  # Will be set by execute()
                tags=self.tags,
            )
