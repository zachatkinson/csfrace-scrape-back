"""
Event bus implementation.

Central pub/sub system following the Observer pattern.
Following SOLID principles:
- Single Responsibility: Only manages event pub/sub
- Open/Closed: Extensible via event types and subscribers
- Dependency Inversion: Uses abstract interfaces
"""

from collections import defaultdict

import asyncio
import structlog

from .base import Event, EventFilter, EventHandler, EventPublisher
from .store import EventStore, InMemoryEventStore

logger = structlog.get_logger(__name__)


class EventBus(EventPublisher):
    """
    Central event bus for pub/sub messaging.

    Thread-safe, async-first event distribution system.
    Following Single Responsibility Principle - only manages event distribution.

    Modern 2025 design:
    - Async-first (all operations are async)
    - Type-safe (Pydantic event models)
    - Observable (structured logging)
    - Persistent (events stored for replay)
    """

    def __init__(self, event_store: EventStore | None = None):
        """
        Initialize event bus.

        Args:
            event_store: Optional event store for persistence
        """
        # Subscribers organized by event type
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

        # Wildcard subscribers (receive all events)
        self._wildcard_subscribers: list[EventHandler] = []

        # Event store for persistence
        self._event_store = event_store or InMemoryEventStore()

        # Event sequence counter
        self._sequence_counter = 0
        self._sequence_lock = asyncio.Lock()

        logger.info("event_bus_initialized")

    async def publish(self, event: Event) -> None:
        """
        Publish event to all subscribers.

        Following Open/Closed Principle - can add new event types without modification.

        Args:
            event: Event to publish
        """
        # Assign sequence number
        async with self._sequence_lock:
            self._sequence_counter += 1
            event.sequence = self._sequence_counter

        # Store event
        await self._event_store.store(event)

        # Get subscribers for this event type
        event_subscribers = self._subscribers.get(event.type, [])

        # Combine with wildcard subscribers
        all_subscribers = [*event_subscribers, *self._wildcard_subscribers]

        if not all_subscribers:
            logger.debug("no_subscribers", event_type=event.type)
            return

        # Publish to all subscribers concurrently
        tasks = [handler(event) for handler in all_subscribers]

        # Execute all handlers, catching errors to prevent one failure from affecting others
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "event_handler_error",
                    event_type=event.type,
                    error=str(result),
                    handler_index=i,
                )

        logger.debug(
            "event_published",
            event_id=str(event.id),
            event_type=event.type,
            subscriber_count=len(all_subscribers),
        )

    def subscribe(
        self,
        event_type: str | None,
        handler: EventHandler,
        filter_func: EventFilter | None = None,
    ) -> None:
        """
        Subscribe to events.

        Args:
            event_type: Event type to subscribe to (None for all events)
            handler: Async function to handle events
            filter_func: Optional filter function
        """
        # Wrap handler with filter if provided
        if filter_func:
            original_handler = handler

            async def filtered_handler(event: Event) -> None:
                if filter_func(event):
                    await original_handler(event)

            handler = filtered_handler

        # Add to appropriate subscriber list
        if event_type is None:
            self._wildcard_subscribers.append(handler)
            logger.info("wildcard_subscriber_added")
        else:
            self._subscribers[event_type].append(handler)
            logger.info("subscriber_added", event_type=event_type)

    def unsubscribe(self, event_type: str | None, handler: EventHandler) -> None:
        """
        Unsubscribe from events.

        Args:
            event_type: Event type to unsubscribe from (None for wildcard)
            handler: Handler function to remove
        """
        if event_type is None:
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
                logger.info("wildcard_subscriber_removed")
        else:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.info("subscriber_removed", event_type=event_type)

    async def get_recent_events(
        self,
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[Event]:
        """
        Get recent events from store.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)

        Returns:
            List of recent events
        """
        return await self._event_store.get_recent(limit=limit, event_type=event_type)

    @property
    def event_store(self) -> EventStore:
        """Get the event store."""
        return self._event_store


# Global event bus instance (singleton pattern)
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Get the global event bus instance.

    Following Dependency Inversion Principle - code depends on abstraction.
    Singleton pattern ensures single event bus across application.

    Returns:
        Global EventBus instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def reset_event_bus() -> None:
    """
    Reset the global event bus.

    Primarily for testing - allows clean slate between tests.
    """
    global _event_bus
    if _event_bus is not None:
        await _event_bus._event_store.clear()
    _event_bus = None
    logger.info("event_bus_reset")
