"""Background health monitoring service for continuous health tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import asyncio

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

from ..caching.manager import cache_manager
from .health_events import (
    initialize_health_events,
)

if TYPE_CHECKING:
    from ..api.services.health_service import HealthService

logger = get_monitoring_logger()


class BackgroundHealthMonitor:
    """Background service for continuous health monitoring and event emission."""

    def __init__(self, check_interval: int = 30):
        """Initialize background health monitor.

        Args:
            check_interval: Interval between health checks in seconds
        """
        self.check_interval = check_interval
        self._running = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._health_service = None
        self._initialized = False

    async def start(self) -> None:
        """Start the background health monitoring service."""
        if self._running:
            logger.warning("Background health monitor is already running")
            return

        logger.info("Starting background health monitor", interval=self.check_interval)
        self._running = True

        # Initialize Redis connection for events
        await self._initialize_event_system()

        # Start monitoring loop
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop the background health monitoring service."""
        if not self._running:
            return

        logger.info("Stopping background health monitor")
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                logger.debug("Monitor task cancelled successfully")

        logger.info("Background health monitor stopped")

    @monitoring_error_handler("initialize health event system")
    async def _initialize_event_system(self) -> None:
        """Initialize the health event system with Redis connection."""
        if self._initialized:
            return

        # Initialize cache manager to get Redis connection
        await cache_manager.initialize()

        # Get Redis client from cache backend
        if cache_manager.backend is not None and hasattr(cache_manager.backend, "_get_client"):
            redis_client = await cache_manager.backend._get_client()
            await initialize_health_events(redis_client)
            self._initialized = True
            logger.info("Health event system initialized successfully")

        else:
            logger.warning("Redis cache backend not available, health events disabled")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs health checks periodically."""
        from ..api.services.health_service import health_service

        logger.info("Background health monitoring loop started")

        while self._running:
            await _perform_health_check_safe(health_service)

            # Wait for next check interval
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.debug("Health monitor sleep interrupted")
                break

        logger.info("Background health monitoring loop ended")

    @monitoring_error_handler("trigger immediate health check")
    @staticmethod
    async def trigger_immediate_check() -> dict[str, Any] | None:
        """Trigger an immediate health check outside the normal schedule."""
        from ..api.dependencies import async_session
        from ..api.services.health_service import health_service

        async with async_session() as db_session:
            return await health_service.get_comprehensive_health_status(db_session)


@monitoring_error_handler("perform background health check")
async def _perform_health_check_safe(health_service: HealthService) -> None:
    """Safely perform a health check in the background monitor."""
    # Use the same async session factory as the API dependencies
    from ..api.dependencies import async_session

    async with async_session() as db_session:
        try:
            # Perform health check
            logger.debug("Performing scheduled health check")
            current_health = await health_service.get_comprehensive_health_status(db_session)

            # Health service automatically publishes events now
            logger.debug("Health check completed", status=current_health.get("status"))

            # Commit is handled automatically by context manager in dependencies.py
        except Exception:
            # Rollback is handled automatically by context manager in dependencies.py
            raise


# Global instance
background_health_monitor = BackgroundHealthMonitor()


async def start_background_monitoring(check_interval: int = 30) -> None:
    """Start background health monitoring with specified interval.

    Args:
        check_interval: Interval between health checks in seconds
    """
    if background_health_monitor._running:
        logger.warning("Background health monitoring already running")
        return

    background_health_monitor.check_interval = check_interval
    await background_health_monitor.start()


async def stop_background_monitoring() -> None:
    """Stop background health monitoring."""
    await background_health_monitor.stop()
