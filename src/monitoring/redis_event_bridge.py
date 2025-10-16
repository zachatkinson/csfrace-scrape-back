"""
Redis-to-EventBus bridge for job events.

This module bridges Redis pub/sub to the in-memory event bus, enabling
job events published to Redis to reach SSE clients.

Architecture:
- Subscribes to Redis "job_events" channel
- Converts job events to Event objects
- Publishes to in-memory event bus for SSE distribution

Following SOLID principles:
- Single Responsibility: Only bridges Redis to EventBus
- Dependency Inversion: Depends on abstractions (event bus, Redis client)
"""

import contextlib
import json
from typing import TYPE_CHECKING

import asyncio

from src.caching.manager import cache_manager
from src.core.events import Event, get_event_bus
from src.core.logging_hierarchy import get_monitoring_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_monitoring_logger()


class RedisEventBridge:
    """
    Bridges Redis pub/sub to in-memory event bus.

    This enables job events published to Redis to reach SSE clients
    via the event bus.
    """

    def __init__(self) -> None:
        """Initialize the Redis event bridge."""
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._redis_client: Redis | None = None

    async def start(self) -> None:
        """Start the event bridge background task."""
        if self._running:
            logger.warning("Redis event bridge already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._bridge_events())
        logger.info("Redis event bridge started")

    async def stop(self) -> None:
        """Stop the event bridge background task."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        logger.info("Redis event bridge stopped")

    async def _bridge_events(self) -> None:
        """
        Main bridge loop: subscribe to Redis and forward to event bus.

        Runs continuously, reconnecting on errors.
        """
        while self._running:
            try:
                # Ensure cache manager (Redis) is initialized
                if not cache_manager._initialized:
                    await cache_manager.initialize()

                # Get Redis client from the backend (proper way to access Redis)
                redis_backend = cache_manager._ensure_backend()
                self._redis_client = await redis_backend._get_client()  # type: ignore[attr-defined]

                if self._redis_client is None:
                    logger.error("Redis client not available for event bridge")
                    await asyncio.sleep(5)
                    continue

                # Subscribe to job_events channel
                pubsub = self._redis_client.pubsub()
                await pubsub.subscribe("job_events")

                logger.info("Redis event bridge subscribed to job_events channel")

                # Listen for messages
                async for message in pubsub.listen():
                    if not self._running:
                        break

                    # Process message
                    if message["type"] == "message":
                        await self._handle_redis_message(message["data"])

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Redis event bridge error", error=str(e), exc_info=True)
                await asyncio.sleep(5)  # Wait before reconnecting

    async def _handle_redis_message(self, data: bytes | str) -> None:
        """
        Handle incoming Redis message and forward to event bus.

        Args:
            data: Raw message data from Redis
        """
        try:
            # Parse JSON message
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            job_event_data = json.loads(data)

            # Extract event type from job event
            event_type = job_event_data.get("event_type", "unknown")
            job_id = job_event_data.get("job_id", "unknown")

            # Map job event types to SSE event types
            sse_event_type = self._map_job_event_to_sse_event(event_type)

            # Create Event object for event bus
            event = Event(
                type=sse_event_type,
                data=job_event_data,
                source="job_events",
            )

            # Publish to event bus (which SSE clients are subscribed to)
            event_bus = get_event_bus()
            await event_bus.publish(event)

            logger.info(
                "Redis event bridged to event bus",
                job_id=job_id,
                event_type=event_type,
                sse_event_type=sse_event_type,
            )

        except Exception as e:
            logger.error("Error handling Redis message", error=str(e), exc_info=True)

    def _map_job_event_to_sse_event(self, job_event_type: str) -> str:
        """
        Map job event types to SSE event types.

        Args:
            job_event_type: Job event type (created, status_update, progress, etc.)

        Returns:
            SSE event type for the event bus
        """
        # Map job event types to SSE-friendly event types
        mapping = {
            "created": "job.created",
            "status_update": "job.status",
            "progress": "job.progress",
            "completed": "job.completed",
            "failed": "job.failed",
        }

        return mapping.get(job_event_type, f"job.{job_event_type}")


# Global bridge instance
_redis_event_bridge: RedisEventBridge | None = None


def get_redis_event_bridge() -> RedisEventBridge:
    """
    Get the global Redis event bridge instance.

    Returns:
        Global RedisEventBridge instance
    """
    global _redis_event_bridge
    if _redis_event_bridge is None:
        _redis_event_bridge = RedisEventBridge()
    return _redis_event_bridge
