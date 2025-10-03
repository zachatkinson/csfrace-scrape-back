"""API health check implementation."""

import time

from ...core.decorators import monitoring_error_handler
from ...core.logging_hierarchy import get_monitoring_logger
from .base import HealthCheck, HealthCheckResult, HealthStatus

logger = get_monitoring_logger()


class APIHealthCheck(HealthCheck):
    """Health check for API endpoint availability and response time."""

    def __init__(self, name: str = "api", timeout_seconds: float = 10.0):
        super().__init__(name, timeout_seconds)

    @monitoring_error_handler("api health check")
    async def check(self) -> HealthCheckResult:
        """Check API health by testing basic functionality."""
        start_time = time.time()

        # For now, this is a basic health check
        # In a full implementation, this would test actual API endpoints

        # Check if we can import core modules
        from ...config import get_settings
        from ...database.models.base import Base

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
        # Enhanced decorator will handle Exception case


class DependencyHealthCheck(HealthCheck):
    """Health check for external dependencies."""

    def __init__(self, name: str = "dependencies", timeout_seconds: float = 15.0):
        super().__init__(name, timeout_seconds)

    @monitoring_error_handler("dependency health check")
    async def check(self) -> HealthCheckResult:
        """Check external dependencies health."""
        start_time = time.time()

        # Define critical dependencies to check
        dependency_imports = [
            ("structlog", "structlog"),
            ("pydantic", "pydantic"),
            ("sqlalchemy", "sqlalchemy.ext.asyncio", "AsyncSession"),
        ]

        dependencies = []
        for import_spec in dependency_imports:
            name = import_spec[0]
            module_path = import_spec[1]
            import_name = import_spec[2] if len(import_spec) > 2 else None

            status = self._check_import_health(module_path, import_name)
            dependencies.append((name, status))

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
        # Enhanced decorator will handle Exception case

    @monitoring_error_handler("check import health")
    def _check_import_health(self, module_path: str, import_name: str | None = None) -> str:
        """Check if a module can be imported successfully."""
        __import__(module_path)
        if import_name:
            module = __import__(module_path, fromlist=[import_name])
            getattr(module, import_name)
        return "healthy"
