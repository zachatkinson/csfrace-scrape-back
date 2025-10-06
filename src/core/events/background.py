"""
Background tasks for event publishing.

Following Single Responsibility Principle - only manages background event publishing.
"""

from datetime import datetime

import asyncio
import structlog

from .bus import get_event_bus
from .models import HealthEvent

logger = structlog.get_logger(__name__)


class BackgroundEventPublisher:
    """
    Manages background tasks for periodic event publishing.

    Following Single Responsibility Principle - only publishes events on schedule.
    """

    def __init__(self) -> None:
        """Initialize background publisher."""
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    async def start(self) -> None:
        """Start all background publishing tasks."""
        if self._running:
            logger.warning("background_publisher_already_running")
            return

        self._running = True
        logger.info("background_publisher_starting")

        # Start health event publisher
        self._tasks.append(asyncio.create_task(self._publish_health_events()))

        logger.info("background_publisher_started", task_count=len(self._tasks))

    async def stop(self) -> None:
        """Stop all background publishing tasks."""
        if not self._running:
            return

        self._running = False
        logger.info("background_publisher_stopping")

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        logger.info("background_publisher_stopped")

    async def _publish_health_events(self) -> None:
        """Periodically publish health events."""
        event_bus = get_event_bus()

        while self._running:
            try:
                # Create health event
                # Note: This is a simplified version
                # In production, this would fetch actual health data
                health_event = HealthEvent(
                    data={
                        "status": "healthy",
                        "timestamp": datetime.utcnow().isoformat(),
                        "services": {
                            "api": "healthy",
                            "database": "healthy",
                            "cache": "healthy",
                        },
                    }
                )

                # Publish to event bus
                await event_bus.publish(health_event)

                logger.debug("health_event_published")

                # Wait before next publish (30 seconds)
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_event_publish_error", error=str(e))
                # Continue running despite errors
                await asyncio.sleep(30)


# Global instance
_publisher: BackgroundEventPublisher | None = None


async def start_event_publishing() -> None:
    """Start background event publishing."""
    global _publisher
    if _publisher is None:
        _publisher = BackgroundEventPublisher()
    await _publisher.start()


async def stop_event_publishing() -> None:
    """Stop background event publishing."""
    global _publisher
    if _publisher is not None:
        await _publisher.stop()
        _publisher = None
