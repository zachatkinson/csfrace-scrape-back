"""Database health check implementation."""

import time
from typing import TYPE_CHECKING

from sqlalchemy import text

from ...api.dependencies import get_db_session
from ...core.decorators import monitoring_error_handler
from ...core.logging_hierarchy import get_monitoring_logger
from .base import HealthCheck, HealthCheckResult, HealthStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_monitoring_logger()


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity and basic operations."""

    def __init__(self, name: str = "database", timeout_seconds: float = 5.0):
        super().__init__(name, timeout_seconds)
        self._session: AsyncSession | None = None

    @monitoring_error_handler("database health check")
    async def check(self) -> HealthCheckResult:
        """Check database connectivity and perform basic query."""
        start_time = time.time()

        async for session in get_db_session():
            self._session = session
            # Simple query to test database connectivity
            result = await session.execute(text("SELECT 1 as health_check"))
            row = result.fetchone()

            if row and row.health_check == 1:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                    duration_ms=duration_ms,
                )
            else:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Database query returned unexpected result",
                    duration_ms=duration_ms,
                    details={"query_result": str(row) if row else None},
                )
            break  # Exit after first iteration

        # If no session available
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.UNHEALTHY,
            message="No database session available",
            duration_ms=duration_ms,
        )
        # Enhanced decorator will handle Exception case


class DatabaseTableHealthCheck(HealthCheck):
    """Health check for specific database table accessibility."""

    def __init__(self, table_name: str, name: str | None = None, timeout_seconds: float = 5.0):
        super().__init__(name or f"database_table_{table_name}", timeout_seconds)
        self.table_name = table_name

    @monitoring_error_handler("database table health check")
    async def check(self) -> HealthCheckResult:
        """Check if specific table exists and is accessible."""
        start_time = time.time()

        async for session in get_db_session():
            # Check if table exists and is accessible
            query = text(f"SELECT COUNT(*) FROM {self.table_name} LIMIT 1")  # noqa: S608
            await session.execute(query)

            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"Table '{self.table_name}' is accessible",
                duration_ms=duration_ms,
                details={"table_name": self.table_name, "accessible": True},
            )
            break  # Exit after first iteration

        # If no session available
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.UNHEALTHY,
            message=f"No database session available for table '{self.table_name}'",
            duration_ms=duration_ms,
            details={"table_name": self.table_name, "accessible": False},
        )
        # Enhanced decorator will handle Exception case
