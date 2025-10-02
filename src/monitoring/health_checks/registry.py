"""Health check registry for managing and coordinating health checks."""

from typing import Any

import asyncio

from src.core.logging_hierarchy import get_monitoring_logger

from .base import HealthCheck, HealthCheckResult, HealthStatus

logger = get_monitoring_logger()


class HealthCheckRegistry:
    """Registry for managing and coordinating health checks."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}
        self._tags: dict[str, list[str]] = {}  # tag -> check names

    def register(self, check: HealthCheck, tags: list[str] | None = None) -> None:
        """Register a health check with optional tags."""
        if check.name in self._checks:
            logger.warning(f"Health check '{check.name}' is already registered, overwriting")

        self._checks[check.name] = check

        # Register tags
        if tags:
            for tag in tags:
                if tag not in self._tags:
                    self._tags[tag] = []
                if check.name not in self._tags[tag]:
                    self._tags[tag].append(check.name)

        logger.info(f"Registered health check: {check.name}", tags=tags or [])

    def unregister(self, name: str) -> bool:
        """Unregister a health check by name."""
        if name not in self._checks:
            logger.warning(f"Health check '{name}' not found for unregistration")
            return False

        # Remove from checks
        del self._checks[name]

        # Remove from tags
        for tag, check_names in self._tags.items():
            if name in check_names:
                check_names.remove(name)

        # Clean up empty tag lists
        self._tags = {tag: names for tag, names in self._tags.items() if names}

        logger.info(f"Unregistered health check: {name}")
        return True

    def get_check(self, name: str) -> HealthCheck | None:
        """Get a specific health check by name."""
        return self._checks.get(name)

    def get_checks_by_tag(self, tag: str) -> list[HealthCheck]:
        """Get all health checks with a specific tag."""
        check_names = self._tags.get(tag, [])
        return [self._checks[name] for name in check_names if name in self._checks]

    def list_checks(self) -> list[str]:
        """List all registered health check names."""
        return list(self._checks.keys())

    def list_tags(self) -> list[str]:
        """List all registered tags."""
        return list(self._tags.keys())

    async def run_check(self, name: str) -> HealthCheckResult | None:
        """Run a specific health check by name."""
        import time

        check = self.get_check(name)
        if not check:
            logger.error(f"Health check '{name}' not found")
            return None

        start_time = time.time()
        try:
            result = await asyncio.wait_for(check.check(), timeout=check.timeout_seconds)
            logger.debug(f"Health check '{name}' completed", status=result.status.value)
            return result
        except TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check '{name}' timed out after {check.timeout_seconds}s")
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {check.timeout_seconds} seconds",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check '{name}' failed with exception: {e}")
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error_type": type(e).__name__},
            )

    async def run_checks_by_tag(self, tag: str) -> list[HealthCheckResult]:
        """Run all health checks with a specific tag."""
        checks = self.get_checks_by_tag(tag)
        if not checks:
            logger.warning(f"No health checks found for tag: {tag}")
            return []

        logger.info(f"Running {len(checks)} health checks for tag: {tag}")
        tasks = [self.run_check(check.name) for check in checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        valid_results = []
        for result in results:
            if isinstance(result, HealthCheckResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Health check task failed: {result}")

        return valid_results

    async def run_all_checks(self, parallel: bool = True) -> list[HealthCheckResult]:
        """Run all registered health checks."""
        if not self._checks:
            logger.warning("No health checks registered")
            return []

        logger.info(f"Running {len(self._checks)} health checks", parallel=parallel)

        if parallel:
            # Run all checks in parallel
            tasks = [self.run_check(name) for name in self._checks]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out None results and exceptions
            valid_results: list[HealthCheckResult] = []
            for result in parallel_results:
                if isinstance(result, HealthCheckResult):
                    valid_results.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Health check task failed: {result}")

            return valid_results
        else:
            # Run checks sequentially
            sequential_results: list[HealthCheckResult] = []
            for name in self._checks:
                result = await self.run_check(name)
                if result is not None:
                    sequential_results.append(result)
            return sequential_results

    def get_health_summary(self, results: list[HealthCheckResult]) -> dict[str, Any]:
        """Generate a summary of health check results."""
        if not results:
            return {
                "status": "UNKNOWN",
                "total_checks": 0,
                "healthy": 0,
                "degraded": 0,
                "unhealthy": 0,
                "checks": [],
            }

        healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for r in results if r.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)

        # Determine overall status
        if unhealthy_count > 0:
            overall_status = "UNHEALTHY"
        elif degraded_count > 0:
            overall_status = "DEGRADED"
        else:
            overall_status = "HEALTHY"

        return {
            "status": overall_status,
            "total_checks": len(results),
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
            "checks": [
                {
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                    "response_time_ms": result.duration_ms,
                    "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                    "details": result.details,
                }
                for result in results
            ],
        }


# Global registry instance
health_registry = HealthCheckRegistry()
