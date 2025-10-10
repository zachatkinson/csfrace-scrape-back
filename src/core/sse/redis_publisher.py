"""Redis pub/sub helpers for SSE event distribution following DRY principles.

Provides reusable Redis event publishing patterns used across all SSE endpoints.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.caching.manager import cache_manager
from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_core_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_core_logger(__name__)


class RedisEventPublisher:
    """Redis event publisher following Single Responsibility Principle.

    Responsibilities:
    - Initialize Redis connection for pub/sub
    - Publish events to Redis channels
    - Handle serialization and error logging

    Does NOT handle:
    - Event listening (that's the SSE endpoint's job)
    - Event formatting (that's events.py's job)
    """

    def __init__(self, channel_name: str):
        """Initialize publisher for specific Redis channel.

        Args:
            channel_name: Redis channel to publish to (e.g., "job_events", "health_events")
        """
        self.channel_name = channel_name
        self._redis_client: Redis | None = None
        self._initialized = False

    @api_error_handler("initialize Redis event publisher")
    async def initialize(self) -> None:
        """Initialize Redis connection for publishing.

        Must be called before publishing events.
        """
        if self._initialized:
            logger.debug("Redis publisher already initialized", channel=self.channel_name)
            return

        self._redis_client = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]
        self._initialized = True
        logger.info("Redis event publisher initialized", channel=self.channel_name)

    @api_error_handler("publish event to Redis")
    async def publish_event(
        self,
        event_type: str,
        data: dict[str, Any],
        event_id: str | None = None,
    ) -> bool:
        """Publish event to Redis channel.

        Args:
            event_type: Type of event (e.g., "status_update", "created", "health_change")
            data: Event payload as dictionary
            event_id: Optional event ID for tracking

        Returns:
            True if event published successfully, False otherwise
        """
        if not self._initialized or self._redis_client is None:
            logger.error("Cannot publish event: Redis not initialized", channel=self.channel_name)
            return False

        # Build event payload
        event_payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data,
        }

        if event_id is not None:
            event_payload["event_id"] = event_id

        # Serialize and publish
        try:
            event_json = json.dumps(event_payload)
            await self._redis_client.publish(self.channel_name, event_json)

            logger.debug(
                "Event published to Redis",
                channel=self.channel_name,
                event_type=event_type,
                event_id=event_id,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to publish event to Redis",
                channel=self.channel_name,
                event_type=event_type,
                error=str(e),
            )
            return False

    async def close(self) -> None:
        """Close Redis connection.

        Call this during cleanup.
        """
        if self._redis_client is not None:
            # Note: cache_manager owns the Redis client, so we don't close it here
            self._redis_client = None
            self._initialized = False
            logger.info("Redis event publisher closed", channel=self.channel_name)


# Singleton instances for each channel (DRY pattern)
_publishers: dict[str, RedisEventPublisher] = {}


def get_publisher(channel_name: str) -> RedisEventPublisher:
    """Get or create Redis publisher for channel.

    DRY: Single instance per channel across the application.

    Args:
        channel_name: Redis channel name

    Returns:
        RedisEventPublisher instance for the channel
    """
    if channel_name not in _publishers:
        _publishers[channel_name] = RedisEventPublisher(channel_name)
        logger.debug("Created new Redis publisher", channel=channel_name)

    return _publishers[channel_name]


async def cleanup_publishers() -> None:
    """Close all Redis publishers.

    Call during application shutdown.
    """
    for channel_name, publisher in _publishers.items():
        await publisher.close()
        logger.info("Cleaned up Redis publisher", channel=channel_name)

    _publishers.clear()
