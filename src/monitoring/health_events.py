"""Health event system for real-time health monitoring using Redis pub/sub."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import asyncio

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from redis.asyncio import Redis

logger = get_monitoring_logger()


class SafeJSONEncoder(json.JSONEncoder):
    """Enterprise-grade JSON encoder that handles datetime and other objects safely.

    This follows DRY principles by centralizing all datetime serialization logic
    and SOLID principles by having a single responsibility for JSON encoding.
    """

    def default(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format.

        This method handles all common non-serializable objects in one place,
        following the DRY principle and ensuring consistent serialization.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            # Handle dataclasses and other objects with __dict__
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        elif isinstance(obj, Enum):
            return obj.value
        else:
            # Let the base class handle any other types
            return super().default(obj)


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Safely serialize objects to JSON using the SafeJSONEncoder.

    This is the DRY way to handle JSON serialization throughout the application.
    Always use this instead of json.dumps() directly when datetime objects might be present.
    """
    return json.dumps(obj, cls=SafeJSONEncoder, **kwargs)


class HealthEventType(Enum):
    """Health event types."""

    SERVICE_STATUS_CHANGE = "service_status_change"
    SERVICE_ERROR = "service_error"
    SERVICE_RECOVERY = "service_recovery"
    SYSTEM_ALERT = "system_alert"


@dataclass
class HealthEvent:
    """Health event data structure."""

    event_type: HealthEventType
    service_name: str
    status: str
    timestamp: datetime
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    event_id: str | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        """Generate event ID if not provided."""
        if self.event_id is None:
            self.event_id = f"{self.service_name}_{int(time.time() * 1000)}"

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization.

        Uses the SafeJSONEncoder logic to ensure consistent serialization
        following DRY principles.
        """

        def serialize_value(value: Any) -> Any:
            """Recursively serialize objects using SafeJSONEncoder logic."""
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, Enum):
                return value.value
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple)):
                return [serialize_value(item) for item in value]
            elif hasattr(value, "__dict__"):
                # Handle dataclasses and other objects consistently
                return {
                    k: serialize_value(v)
                    for k, v in value.__dict__.items()
                    if not k.startswith("_")
                }
            return value

        return {
            "event_type": self.event_type.value,
            "service_name": self.service_name,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "data": serialize_value(self.data),
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HealthEvent:
        """Create event from dictionary."""
        return cls(
            event_type=HealthEventType(data["event_type"]),
            service_name=data["service_name"],
            status=data["status"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data["message"],
            data=data.get("data", {}),
            event_id=data.get("event_id"),
            correlation_id=data.get("correlation_id"),
        )


class HealthStateManager:
    """Manages health state tracking to detect changes."""

    def __init__(self) -> None:
        self._previous_states: dict[str, dict[str, Any]] = {}
        self._logger = logger.bind(component="health_state_manager")

    def detect_changes(self, current_health: dict[str, Any]) -> list[HealthEvent]:
        """Detect health state changes and generate events.

        Args:
            current_health: Current health status from health service

        Returns:
            List of health events for detected changes
        """
        events = []

        # Services to monitor
        services = ["backend", "database", "cache"]

        for service in services:
            # Handle backend specially - its data is at top level, not nested
            if service == "backend" or service in current_health:
                current_status = self._extract_service_status(current_health, service)
                previous_status = self._previous_states.get(service, {})

                # Detect status changes
                if self._has_status_changed(previous_status, current_status):
                    event = self._create_status_change_event(
                        service, previous_status, current_status
                    )
                    events.append(event)
                    self._logger.info(
                        "Health status change detected",
                        service=service,
                        old_status=previous_status.get("status", "unknown"),
                        new_status=current_status.get("status", "unknown"),
                    )

                # Update previous state
                self._previous_states[service] = current_status

        return events

    def _extract_service_status(self, health_data: dict[str, Any], service: str) -> dict[str, Any]:
        """Extract service status from health data."""
        if service == "backend":
            return {
                "status": health_data.get("status", "unknown"),
                "timestamp": health_data.get("timestamp"),
                "version": health_data.get("version"),
            }
        elif service in health_data:
            service_data = health_data[service]
            return {
                "status": service_data.get("status", "unknown"),
                "connected": service_data.get("connected", False),
                "response_time_ms": service_data.get("response_time_ms", 0),
                "timestamp": health_data.get("timestamp"),
            }

        return {"status": "unknown", "timestamp": health_data.get("timestamp")}

    def _has_status_changed(self, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        """Check if health status has changed significantly."""
        # Check primary status change
        if previous.get("status") != current.get("status"):
            return True

        # Check connection status change (for database/cache)
        if (
            "connected" in previous
            and "connected" in current
            and previous["connected"] != current["connected"]
        ):
            return True

        # Check significant response time changes (>50% increase/decrease)
        prev_time = previous.get("response_time_ms", 0)
        curr_time = current.get("response_time_ms", 0)
        if prev_time > 0 and curr_time > 0:
            change_ratio = abs(curr_time - prev_time) / prev_time
            if change_ratio > 0.5:  # 50% change threshold
                return True

        return False

    def _create_status_change_event(
        self, service: str, previous: dict[str, Any], current: dict[str, Any]
    ) -> HealthEvent:
        """Create a health event for status change."""
        old_status = previous.get("status", "unknown")
        new_status = current.get("status", "unknown")

        # Determine event type
        if old_status in ["unhealthy", "error"] and new_status == "healthy":
            event_type = HealthEventType.SERVICE_RECOVERY
            message = f"{service} service has recovered ('{old_status}' → '{new_status}')"
        elif old_status == "healthy" and new_status in ["unhealthy", "error"]:
            event_type = HealthEventType.SERVICE_ERROR
            message = f"{service} service is experiencing issues ('{old_status}' → '{new_status}')"
        else:
            event_type = HealthEventType.SERVICE_STATUS_CHANGE
            message = f"{service} status changed from '{old_status}' to '{new_status}'"

        return HealthEvent(
            event_type=event_type,
            service_name=service,
            status=new_status,
            timestamp=datetime.now(UTC),
            message=message,
            data={
                "previous_status": previous,
                "current_status": current,
                "change_detected_at": datetime.now(UTC).isoformat(),
            },
        )


class HealthEventPublisher:
    """Publishes health events to Redis pub/sub."""

    HEALTH_EVENTS_CHANNEL = "health_events"

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self._logger = logger.bind(component="health_event_publisher")

    @monitoring_error_handler("publish health event")
    async def publish_event(self, event: HealthEvent) -> bool:
        """Publish health event to Redis channel.

        Args:
            event: Health event to publish

        Returns:
            True if event was published successfully
        """
        event_json = safe_json_dumps(event.to_dict())
        subscribers = await self.redis_client.publish(self.HEALTH_EVENTS_CHANNEL, event_json)

        self._logger.debug(
            "Health event published",
            event_id=event.event_id,
            event_type=event.event_type.value,
            service=event.service_name,
            subscribers=subscribers,
        )

        return True

    async def publish_multiple(self, events: list[HealthEvent]) -> int:
        """Publish multiple health events.

        Args:
            events: List of health events to publish

        Returns:
            Number of events successfully published
        """
        if not events:
            return 0

        successful = 0
        for event in events:
            if await self.publish_event(event):
                successful += 1

        self._logger.info(
            "Batch event publishing completed",
            total_events=len(events),
            successful=successful,
            failed=len(events) - successful,
        )

        return successful


class HealthEventSubscriber:
    """Subscribes to health events from Redis pub/sub."""

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self._logger = logger.bind(component="health_event_subscriber")
        self._running = False
        self._subscribers: set[Any] = set()

    async def subscribe(self, callback: Callable[[HealthEvent], Coroutine[Any, Any, Any]]) -> None:
        """Subscribe to health events with a callback function.

        Args:
            callback: Async function to call when events are received
        """
        self._subscribers.add(callback)

        if not self._running:
            asyncio.create_task(self._listen_loop())

    def unsubscribe(self, callback: Callable[[HealthEvent], Coroutine[Any, Any, Any]]) -> None:
        """Unsubscribe a callback from health events."""
        self._subscribers.discard(callback)

    async def _listen_loop(self) -> None:
        """Main listening loop for Redis pub/sub."""
        if self._running:
            return

        self._running = True
        self._logger.info("Starting health event subscription")

        await _run_event_subscription_safe(self)

    @monitoring_error_handler("handle health event message")
    async def _handle_message(self, message_data: bytes) -> None:
        """Handle incoming health event message."""
        event_dict = json.loads(message_data.decode("utf-8"))
        event = HealthEvent.from_dict(event_dict)

        # Notify all subscribers
        for callback in self._subscribers:
            await _notify_event_callback_safe(callback, event, self._logger)


@monitoring_error_handler("run health event subscription")
async def _run_event_subscription_safe(subscriber: HealthEventSubscriber) -> None:
    """Safely run health event subscription loop."""
    try:
        pubsub = subscriber.redis_client.pubsub()
        await pubsub.subscribe(HealthEventPublisher.HEALTH_EVENTS_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] == "message":
                await subscriber._handle_message(message["data"])
    finally:
        subscriber._running = False
        subscriber._logger.info("Health event subscription stopped")


@monitoring_error_handler("notify event callback")
async def _notify_event_callback_safe(
    callback: Callable[[HealthEvent], Coroutine[Any, Any, Any]], event: HealthEvent, _logger: Any
) -> None:
    """Safely notify an event callback."""
    await callback(event)


# Global instances (will be initialized with Redis connection)
health_state_manager = HealthStateManager()
health_event_publisher: HealthEventPublisher | None = None
health_event_subscriber: HealthEventSubscriber | None = None


async def initialize_health_events(redis_client: Redis) -> None:
    """Initialize health event system with Redis client."""
    global health_event_publisher, health_event_subscriber

    health_event_publisher = HealthEventPublisher(redis_client)
    health_event_subscriber = HealthEventSubscriber(redis_client)

    logger.info("Health event system initialized")


async def publish_health_change_events(current_health: dict[str, Any]) -> None:
    """Detect and publish health change events."""
    if health_event_publisher is None:
        logger.warning("Health event publisher not initialized")
        return

    # Detect changes
    events = health_state_manager.detect_changes(current_health)

    # Publish events
    if events:
        await health_event_publisher.publish_multiple(events)
