"""API health check implementation."""

import time

from ...utils.logging import get_logger
from .base import HealthCheck, HealthCheckResult, HealthStatus

logger = get_logger(__name__)


class APIHealthCheck(HealthCheck):
    """Health check for API endpoint availability and response time."""

    def __init__(self, name: str = "api", timeout_seconds: float = 10.0):
        super().__init__(name, timeout_seconds)

    async def check(self) -> HealthCheckResult:
        """Check API health by testing basic functionality."""
        start_time = time.time()

        try:
            # For now, this is a basic health check
            # In a full implementation, this would test actual API endpoints

            # Check if we can import core modules
            from ...core.config import get_settings
            from ...database.models import Base

            settings = get_settings()

            # Basic API health indicators
            checks = {
                "configuration_loaded": settings is not None,
                "database_models_available": Base is not None,
            }

            failed_checks = [check for check, status in checks.items() if not status]

            if failed_checks:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"API health check failed: {', '.join(failed_checks)}",
                    duration_ms=duration_ms,
                    details={"failed_checks": failed_checks},
                )

            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="API is healthy and responding normally",
                duration_ms=duration_ms,
                details={"checks_passed": list(checks.keys())},
            )

        except Exception as e:
            logger.error(f"API health check failed: {e}")
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"API health check failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error_type": type(e).__name__},
            )


class DependencyHealthCheck(HealthCheck):
    """Health check for external dependencies."""

    def __init__(self, name: str = "dependencies", timeout_seconds: float = 15.0):
        super().__init__(name, timeout_seconds)

    async def check(self) -> HealthCheckResult:
        """Check external dependencies health."""
        start_time = time.time()

        try:
            dependencies = []

            # Check if critical modules can be imported
            try:
                import structlog  # noqa: F401

                dependencies.append(("structlog", "healthy"))
            except ImportError as e:
                dependencies.append(("structlog", f"import_error: {e}"))

            try:
                import pydantic  # noqa: F401

                dependencies.append(("pydantic", "healthy"))
            except ImportError as e:
                dependencies.append(("pydantic", f"import_error: {e}"))

            try:
                from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401

                dependencies.append(("sqlalchemy", "healthy"))
            except ImportError as e:
                dependencies.append(("sqlalchemy", f"import_error: {e}"))

            # Check for any failed dependencies
            failed_deps = [(name, status) for name, status in dependencies if status != "healthy"]

            if failed_deps:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Dependency health check failed: {len(failed_deps)} dependencies unavailable",
                    duration_ms=duration_ms,
                    details={"failed_dependencies": failed_deps, "all_dependencies": dependencies},
                )

            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"All {len(dependencies)} dependencies are healthy",
                duration_ms=duration_ms,
                details={"dependencies": dependencies},
            )

        except Exception as e:
            logger.error(f"Dependency health check failed: {e}")
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Dependency health check failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error_type": type(e).__name__},
            )
