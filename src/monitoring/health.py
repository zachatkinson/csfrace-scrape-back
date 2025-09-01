"""Health check system with dependency validation and status monitoring."""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthConfig:
    """Configuration for health checking system."""

    enabled: bool = True
    check_interval: float = 30.0  # seconds
    timeout_seconds: float = 10.0
    critical_checks: list[str] = field(default_factory=list)
    warning_checks: list[str] = field(default_factory=list)
    endpoint_path: str = "/health"
    detailed_endpoint_path: str = "/health/detailed"


class HealthChecker:
    """Comprehensive health checking system."""

    def __init__(self, config: HealthConfig | None = None):
        """Initialize health checker.

        Args:
            config: Health check configuration
        """
        self.config = config or HealthConfig()
        self._checks: dict[str, Callable] = {}
        self._results: dict[str, HealthCheckResult] = {}
        self._check_task: asyncio.Task | None = None
        self._checking = False

        # Register built-in health checks
        self._register_builtin_checks()

        logger.info("Health checker initialized", interval=self.config.check_interval)

    def _register_builtin_checks(self) -> None:
        """Register built-in health checks."""
        self.register_check("system_resources", self._check_system_resources)
        self.register_check("database_connection", self._check_database)
        self.register_check("cache_backend", self._check_cache)
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("memory_usage", self._check_memory_usage)

    def register_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function.

        Args:
            name: Name of the health check
            check_func: Async function that performs the check
        """
        self._checks[name] = check_func
        logger.debug("Registered health check", name=name)

    def unregister_check(self, name: str) -> bool:
        """Unregister a health check.

        Args:
            name: Name of health check to remove

        Returns:
            True if check was removed
        """
        if name in self._checks:
            del self._checks[name]
            if name in self._results:
                del self._results[name]
            logger.debug("Unregistered health check", name=name)
            return True
        return False

    async def start_monitoring(self) -> None:
        """Start periodic health monitoring."""
        if not self.config.enabled or self._checking:
            return

        self._checking = True
        self._check_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started health monitoring")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        if not self._checking:
            return

        self._checking = False
        if self._check_task:
            self._check_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._check_task

        logger.info("Stopped health monitoring")

    async def _monitoring_loop(self) -> None:
        """Main health monitoring loop."""
        while self._checking:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health monitoring failed", error=str(e))
                await asyncio.sleep(5.0)

    async def run_all_checks(self) -> dict[str, HealthCheckResult]:
        """Run all registered health checks.

        Returns:
            Dictionary of health check results
        """
        results = {}

        for name, check_func in self._checks.items():
            try:
                result = await self._run_single_check(name, check_func)
                results[name] = result
                self._results[name] = result
            except Exception as e:
                logger.error("Health check failed", name=name, error=str(e))
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {str(e)}",
                    duration_ms=0,
                    timestamp=datetime.now(UTC),
                )

        return results

    async def _run_single_check(self, name: str, check_func: Callable) -> HealthCheckResult:
        """Run a single health check with timeout.

        Args:
            name: Name of the check
            check_func: Check function to run

        Returns:
            Health check result
        """
        start_time = time.time()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(check_func(), timeout=self.config.timeout_seconds)

            duration_ms = (time.time() - start_time) * 1000

            if isinstance(result, HealthCheckResult):
                result.duration_ms = duration_ms
                return result
            elif isinstance(result, bool):
                return HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    message="OK" if result else "Check failed",
                    duration_ms=duration_ms,
                    timestamp=datetime.now(UTC),
                )
            else:
                return HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=str(result) if result else "OK",
                    duration_ms=duration_ms,
                    timestamp=datetime.now(UTC),
                )

        except TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {self.config.timeout_seconds}s",
                duration_ms=duration_ms,
                timestamp=datetime.now(UTC),
            )

    async def _check_system_resources(self) -> HealthCheckResult:
        """Check system resource availability."""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
            }

            # Determine status based on resource usage
            if cpu_percent > 90 or memory.percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"High resource usage (CPU: {cpu_percent}%, Memory: {memory.percent}%)"
            elif cpu_percent > 75 or memory.percent > 75:
                status = HealthStatus.DEGRADED
                message = (
                    f"Elevated resource usage (CPU: {cpu_percent}%, Memory: {memory.percent}%)"
                )
            else:
                status = HealthStatus.HEALTHY
                message = f"Resource usage normal (CPU: {cpu_percent}%, Memory: {memory.percent}%)"

            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=message,
                duration_ms=0,  # Will be set by caller
                timestamp=datetime.now(UTC),
                details=details,
            )

        except ImportError:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
                duration_ms=0,
                timestamp=datetime.now(UTC),
            )

    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        try:
            from ..database.service import DatabaseService

            # Create a test database service
            db_service = DatabaseService(echo=False)

            # Try to get a connection
            with db_service.get_session() as session:
                # Simple query to test connectivity
                result = session.execute("SELECT 1 as test").fetchone()

                if result and result[0] == 1:
                    return HealthCheckResult(
                        name="database_connection",
                        status=HealthStatus.HEALTHY,
                        message="Database connection successful",
                        duration_ms=0,
                        timestamp=datetime.now(UTC),
                        details={"query_result": result[0]},
                    )
                else:
                    return HealthCheckResult(
                        name="database_connection",
                        status=HealthStatus.UNHEALTHY,
                        message="Database query failed",
                        duration_ms=0,
                        timestamp=datetime.now(UTC),
                    )

        except Exception as e:
            return HealthCheckResult(
                name="database_connection",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                duration_ms=0,
                timestamp=datetime.now(UTC),
            )

    async def _check_cache(self) -> HealthCheckResult:
        """Check cache backend availability."""
        try:
            from ..caching.manager import cache_manager

            # Initialize cache manager
            await cache_manager.initialize()

            # Test cache with a simple key
            test_key = "health_check_test"
            test_value = f"test_{int(time.time())}"

            # Check if backend is available
            if cache_manager.backend is None:
                return HealthCheckResult(
                    name="cache_backend",
                    status=HealthStatus.UNHEALTHY,
                    message="Cache backend not initialized",
                    duration_ms=0.0,
                    timestamp=datetime.now(UTC),
                    details={"error": "Backend is None"},
                )

            # Try to set and get a value
            success = await cache_manager.backend.set(test_key, test_value, ttl=10)
            if success:
                retrieved = await cache_manager.backend.get(test_key)
                if retrieved and retrieved.value == test_value:
                    # Cleanup test key
                    await cache_manager.backend.delete(test_key)

                    return HealthCheckResult(
                        name="cache_backend",
                        status=HealthStatus.HEALTHY,
                        message="Cache backend operational",
                        duration_ms=0,
                        timestamp=datetime.now(UTC),
                        details={"backend": cache_manager.config.backend.value},
                    )

            return HealthCheckResult(
                name="cache_backend",
                status=HealthStatus.UNHEALTHY,
                message="Cache set/get operation failed",
                duration_ms=0,
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            return HealthCheckResult(
                name="cache_backend",
                status=HealthStatus.UNHEALTHY,
                message=f"Cache check failed: {str(e)}",
                duration_ms=0,
                timestamp=datetime.now(UTC),
            )

    async def _check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        try:
            import psutil

            disk = psutil.disk_usage("/")
            free_percent = (disk.free / disk.total) * 100
            free_gb = disk.free / (1024**3)

            details = {
                "free_percent": free_percent,
                "free_gb": free_gb,
                "total_gb": disk.total / (1024**3),
            }

            if free_percent < 5:
                status = HealthStatus.UNHEALTHY
                message = (
                    f"Critical: Only {free_percent:.1f}% ({free_gb:.1f}GB) disk space remaining"
                )
            elif free_percent < 15:
                status = HealthStatus.DEGRADED
                message = f"Warning: {free_percent:.1f}% ({free_gb:.1f}GB) disk space remaining"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {free_percent:.1f}% ({free_gb:.1f}GB) available"

            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                duration_ms=0,
                timestamp=datetime.now(UTC),
                details=details,
            )

        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Disk check failed: {str(e)}",
                duration_ms=0,
                timestamp=datetime.now(UTC),
            )

    async def _check_memory_usage(self) -> HealthCheckResult:
        """Check memory usage specifically."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)

            details = {
                "used_percent": memory.percent,
                "available_gb": available_gb,
                "total_gb": memory.total / (1024**3),
            }

            if memory.percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: {memory.percent:.1f}% memory used, only {available_gb:.1f}GB available"
            elif memory.percent > 85:
                status = HealthStatus.DEGRADED
                message = (
                    f"Warning: {memory.percent:.1f}% memory used, {available_gb:.1f}GB available"
                )
            else:
                status = HealthStatus.HEALTHY
                message = (
                    f"Memory usage OK: {memory.percent:.1f}% used, {available_gb:.1f}GB available"
                )

            return HealthCheckResult(
                name="memory_usage",
                status=status,
                message=message,
                duration_ms=0,
                timestamp=datetime.now(UTC),
                details=details,
            )

        except Exception as e:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                duration_ms=0,
                timestamp=datetime.now(UTC),
            )

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status.

        Returns:
            Overall health status based on all checks
        """
        if not self._results:
            return HealthStatus.UNKNOWN

        # Check critical checks first
        critical_unhealthy = any(
            result.status == HealthStatus.UNHEALTHY
            for name, result in self._results.items()
            if name in self.config.critical_checks
        )

        if critical_unhealthy:
            return HealthStatus.UNHEALTHY

        # Check for any unhealthy checks
        any_unhealthy = any(
            result.status == HealthStatus.UNHEALTHY for result in self._results.values()
        )

        if any_unhealthy:
            return HealthStatus.UNHEALTHY

        # Check for degraded status
        any_degraded = any(
            result.status == HealthStatus.DEGRADED for result in self._results.values()
        )

        if any_degraded:
            return HealthStatus.DEGRADED

        # All checks healthy
        return HealthStatus.HEALTHY

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for API responses.

        Returns:
            Health summary dictionary
        """
        overall_status = self.get_overall_status()

        return {
            "status": overall_status.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp.isoformat(),
                }
                for name, result in self._results.items()
            },
            "summary": {
                "total_checks": len(self._results),
                "healthy": sum(
                    1 for r in self._results.values() if r.status == HealthStatus.HEALTHY
                ),
                "degraded": sum(
                    1 for r in self._results.values() if r.status == HealthStatus.DEGRADED
                ),
                "unhealthy": sum(
                    1 for r in self._results.values() if r.status == HealthStatus.UNHEALTHY
                ),
                "unknown": sum(
                    1 for r in self._results.values() if r.status == HealthStatus.UNKNOWN
                ),
            },
        }

    def get_detailed_health(self) -> dict[str, Any]:
        """Get detailed health information including check details.

        Returns:
            Detailed health information
        """
        summary = self.get_health_summary()

        # Add detailed information for each check
        for name, result in self._results.items():
            if name in summary["checks"]:
                summary["checks"][name]["details"] = result.details

        return summary

    async def shutdown(self) -> None:
        """Shutdown health checker."""
        await self.stop_monitoring()
        logger.info("Health checker shutdown")


# Global health checker instance
health_checker = HealthChecker()
