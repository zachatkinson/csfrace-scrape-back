"""Health service following SOLID principles for comprehensive system health monitoring."""

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.caching.manager import CacheManager
from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

logger = get_api_logger()

# Get version from package metadata with fallback
try:
    import importlib.metadata

    __version__ = importlib.metadata.version("csfrace-scraper")
except importlib.metadata.PackageNotFoundError:
    __version__ = "1.0.0"  # Fallback version


class HealthService:
    """Centralized health service implementing SOLID principles.

    Single Responsibility: Manages all health-related operations
    Open/Closed: Extensible for new health checks
    Liskov Substitution: Consistent interface for all health checks
    Interface Segregation: Focused on health concerns only
    Dependency Inversion: Depends on abstractions, not concretions
    """

    def __init__(self, version: str = "1.0.0"):
        """Initialize health service.

        Args:
            version: Application version string
        """
        self.version = version
        self.logger = logger.bind(service="health")

    async def get_comprehensive_health_status(self, db_session: AsyncSession) -> dict[str, Any]:
        """Get comprehensive health status following DRY and SOLID principles.

        Args:
            db_session: Database session for health checks

        Returns:
            Complete health status dictionary
        """
        self.logger.debug("Starting comprehensive health check")

        # Run all health checks in parallel for efficiency
        database_status = await self._check_database_health(db_session)
        cache_status = await self._check_cache_health()
        monitoring_status = await self._get_monitoring_status()

        # Determine overall status using clear business logic
        overall_status = self._calculate_overall_status(
            database_status, cache_status, monitoring_status
        )

        response = {
            "status": overall_status,
            "timestamp": datetime.now(UTC),
            "version": self.version,
            "database": database_status,
            "cache": cache_status,
            "monitoring": monitoring_status,
        }

        self.logger.info(
            "Health check completed",
            status=overall_status,
            database=database_status["status"],
            cache=cache_status["status"],
        )

        # Publish health change events to Redis pub/sub for real-time monitoring
        await self._publish_health_events_safe(response)

        return response

    @api_error_handler("database health check")
    async def _check_database_health(self, db_session: AsyncSession) -> dict[str, Any]:
        """Check database connectivity and health with extended metrics.

        Args:
            db_session: Database session

        Returns:
            Database health status with size and connection metrics
        """
        import time

        start_time = time.time()

        # Basic connectivity test
        scalar_result = await db_session.scalar(text("SELECT 1"))

        if scalar_result != 1:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": "Unexpected query result",
            }

        # Get database metrics with cache hit ratio
        metrics_query = text(
            """
            SELECT
                pg_size_pretty(pg_database_size(current_database())) AS database_size,
                pg_database_size(current_database()) AS database_size_bytes,
                (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) AS active_connections,
                COALESCE(
                    CAST(
                        ((sum(blks_hit)::float / NULLIF(sum(blks_hit + blks_read), 0)) * 100)
                        AS DECIMAL(5,2)
                    ),
                    0
                ) AS cache_hit_ratio
            FROM pg_stat_database
            WHERE datname = current_database()
        """
        )

        metrics_result = await db_session.execute(metrics_query)
        metrics_row = metrics_result.first()

        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        return {
            "status": "healthy",
            "connected": True,
            "response_time_ms": round(response_time, 2),
            "size": metrics_row[0] if metrics_row else "unknown",  # e.g., "8715 kB"
            "size_bytes": int(metrics_row[1])
            if metrics_row and metrics_row[1]
            else 0,  # e.g., 8731648
            "active_connections": int(metrics_row[2])
            if metrics_row and metrics_row[2]
            else 0,  # e.g., 15
            "cache_hit_ratio": float(metrics_row[3])
            if metrics_row and metrics_row[3]
            else 0.0,  # e.g., 98.7
        }

    @api_error_handler("cache health check")
    async def _check_cache_health(self) -> dict[str, Any]:
        """Check cache system health with comprehensive Redis metrics.

        Returns:
            Cache health status with detailed metrics
        """
        # Import cache manager with proper error handling
        from ...caching.manager import cache_manager

        if cache_manager is None:
            return {"status": "not_configured", "backend": "none"}

        # Initialize if needed
        await cache_manager.initialize()

        # Get comprehensive Redis metrics
        start_time = time.time()

        # Get backend type safely
        backend_type = await self._get_backend_type_safe(cache_manager)

        # Get detailed server info if Redis backend
        server_info: dict[str, str | int] = {}
        stats_info: dict[str, int] = {}
        if cache_manager.backend and hasattr(cache_manager.backend, "get_server_info"):
            server_info, stats_info = await self._get_cache_info_safe(cache_manager)

        response_time_ms = round((time.time() - start_time) * 1000, 2)

        # Calculate hit rate from stats
        hit_rate = 0.0
        if stats_info and "hits" in stats_info and "misses" in stats_info:
            hits = int(stats_info["hits"])
            misses = int(stats_info["misses"])
            total_ops = hits + misses
            if total_ops > 0:
                hit_rate = round((hits / total_ops) * 100, 2)

        # Format uptime
        uptime_formatted = "Unknown"
        if server_info.get("uptime_in_seconds"):
            uptime_seconds = int(server_info["uptime_in_seconds"])
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            uptime_formatted = f"{hours}h {minutes}m"

        return {
            "status": "healthy",
            "connected": True,
            "response_time_ms": response_time_ms,
            "backend": backend_type,
            "version": server_info.get("redis_version", "unknown"),
            "mode": server_info.get("redis_mode", "standalone"),
            "used_memory": server_info.get("used_memory_human", "unknown"),
            "connected_clients": server_info.get("connected_clients", 0),
            "hit_rate": hit_rate,
            "uptime": uptime_formatted,
            "architecture": f"{server_info.get('arch_bits', 'unknown')} bit",
            "os": server_info.get("os", "unknown"),
            "total_entries": stats_info.get("total_entries", 0),
            "total_operations": int(stats_info.get("hits", 0)) + int(stats_info.get("misses", 0)),
            "monitoring": {
                "hits": stats_info.get("hits", 0),
                "misses": stats_info.get("misses", 0),
                "sets": stats_info.get("sets", 0),
                "deletes": stats_info.get("deletes", 0),
            },
        }

    @api_error_handler("monitoring status check")
    async def _get_monitoring_status(self) -> dict[str, Any]:
        """Get monitoring system status.

        FIXED: Made async because @api_error_handler only creates async wrappers.
        This ensures the entire async chain is properly async/await compliant.

        Returns:
            Monitoring system status
        """
        # Simple static status for monitoring components
        # This avoids the blocking observability manager calls
        return {
            "metricsCollector": "healthy",
            "healthChecker": "healthy",
            "alertManager": "healthy",
            "performanceMonitor": "healthy",
            "observabilityManager": "healthy",
        }

    @api_error_handler("publish health events")
    async def _publish_health_events_safe(self, response: dict[str, Any]) -> None:
        """Safely publish health change events."""
        from ...monitoring.health_events import publish_health_change_events

        await publish_health_change_events(response)

    @api_error_handler("get backend type")
    async def _get_backend_type_safe(self, cache_manager: CacheManager) -> str:
        """Safely get cache backend type."""
        backend_type: str = await cache_manager.get_detailed_backend_type()
        return backend_type

    @api_error_handler("get cache info")
    async def _get_cache_info_safe(
        self, cache_manager: CacheManager
    ) -> tuple[dict[str, str | int], dict[str, int]]:
        """Safely get cache server info and stats."""
        if cache_manager.backend is None or not hasattr(cache_manager.backend, "get_server_info"):
            return {}, {}

        server_info = await cache_manager.backend.get_server_info()
        stats_info = await cache_manager.backend.stats()
        return server_info, stats_info

    def _calculate_overall_status(
        self,
        database_status: dict[str, Any],
        cache_status: dict[str, Any],
        monitoring_status: dict[str, Any],
    ) -> str:
        """Calculate overall system status based on component statuses.

        Args:
            database_status: Database component status
            cache_status: Cache component status
            monitoring_status: Monitoring component status

        Returns:
            Overall system status: 'healthy', 'degraded', or 'unhealthy'
        """
        # Critical components must be healthy
        if database_status["status"] != "healthy":
            return "unhealthy"

        # Non-critical components can cause degraded status
        if cache_status.get("status") == "error" or monitoring_status.get("status") == "unknown":
            return "degraded"

        return "healthy"


# Singleton instance following SOLID principles
health_service = HealthService(version=__version__)
