"""Background health monitoring service for continuous health tracking."""


import asyncio
import structlog

from ..caching.manager import cache_manager
from ..database.service import DatabaseService
from .health_events import (
    initialize_health_events,
)

logger = structlog.get_logger(__name__)


class BackgroundHealthMonitor:
    """Background service for continuous health monitoring and event emission."""

    def __init__(self, check_interval: int = 30):
        """Initialize background health monitor.

        Args:
            check_interval: Interval between health checks in seconds
        """
        self.check_interval = check_interval
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._health_service = None
        self._initialized = False

    async def start(self):
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

    async def stop(self):
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

    async def _initialize_event_system(self):
        """Initialize the health event system with Redis connection."""
        if self._initialized:
            return

        try:
            # Initialize cache manager to get Redis connection
            await cache_manager.initialize()

            # Get Redis client from cache backend
            if hasattr(cache_manager.backend, '_get_client'):
                redis_client = await cache_manager.backend._get_client()
                await initialize_health_events(redis_client)
                self._initialized = True
                logger.info("Health event system initialized successfully")

            else:
                logger.warning("Redis cache backend not available, health events disabled")

        except Exception as e:
            logger.error("Failed to initialize health event system", error=str(e))
            # Continue without events rather than failing completely

    async def _monitoring_loop(self):
        """Main monitoring loop that runs health checks periodically."""
        from ..api.services.health_service import health_service

        logger.info("Background health monitoring loop started")

        while self._running:
            try:
                # Create database service instance
                database_service = DatabaseService()
                # Get database session
                with database_service.get_session() as db_session:
                    # Perform health check
                    logger.debug("Performing scheduled health check")
                    current_health = await health_service.get_comprehensive_health_status(db_session)

                    # Health service automatically publishes events now
                    logger.debug("Health check completed", status=current_health.get("status"))

            except Exception as e:
                logger.error("Health check failed in background monitor", error=str(e))

            # Wait for next check interval
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.debug("Health monitor sleep interrupted")
                break

        logger.info("Background health monitoring loop ended")

    async def trigger_immediate_check(self):
        """Trigger an immediate health check outside the normal schedule."""
        try:
            from ..api.services.health_service import health_service

            # Create database service instance
            database_service = DatabaseService()
            with database_service.get_session() as db_session:
                current_health = await health_service.get_comprehensive_health_status(db_session)
                logger.info("Immediate health check triggered", status=current_health.get("status"))
                return current_health

        except Exception as e:
            logger.error("Immediate health check failed", error=str(e))
            raise


# Global instance
background_health_monitor = BackgroundHealthMonitor()


async def start_background_monitoring(check_interval: int = 30):
    """Start background health monitoring with specified interval.

    Args:
        check_interval: Interval between health checks in seconds
    """
    if background_health_monitor._running:
        logger.warning("Background health monitoring already running")
        return

    background_health_monitor.check_interval = check_interval
    await background_health_monitor.start()


async def stop_background_monitoring():
    """Stop background health monitoring."""
    await background_health_monitor.stop()

