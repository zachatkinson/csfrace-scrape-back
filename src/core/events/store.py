"""
Event storage implementations.

Following Single Responsibility Principle - only responsible for event persistence.
Following Open/Closed Principle - easily extensible with new storage backends.
"""

from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime
from uuid import UUID

import structlog

from .base import Event

logger = structlog.get_logger(__name__)


class EventStore(ABC):
    """
    Abstract event store interface.

    Following Dependency Inversion Principle - code depends on this interface.
    Allows swapping storage implementations (in-memory, Redis, PostgreSQL).
    """

    @abstractmethod
    async def store(self, event: Event) -> None:
        """Store an event."""
        pass

    @abstractmethod
    async def get_recent(
        self,
        limit: int = 100,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[Event]:
        """
        Get recent events.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)
            since: Only return events after this timestamp (optional)

        Returns:
            List of events, newest first
        """
        pass

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> Event | None:
        """Get event by ID."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all events (for testing)."""
        pass


class InMemoryEventStore(EventStore):
    """
    In-memory event store implementation.

    Uses deque for efficient FIFO operations.
    Good for development and testing - not for production at scale.

    Following Single Responsibility Principle - only manages event storage.
    """

    def __init__(self, max_events: int = 1000):
        """
        Initialize in-memory event store.

        Args:
            max_events: Maximum number of events to keep in memory
        """
        self._events: deque[Event] = deque(maxlen=max_events)
        self._max_events = max_events

    async def store(self, event: Event) -> None:
        """Store event in memory."""
        self._events.append(event)
        logger.debug("event_stored", event_id=str(event.id), event_type=event.type)

    async def get_recent(
        self,
        limit: int = 100,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[Event]:
        """Get recent events with optional filtering."""
        # Convert deque to list for easier manipulation
        all_events = list(self._events)

        # Filter by type if specified
        if event_type:
            all_events = [e for e in all_events if e.type == event_type]

        # Filter by timestamp if specified
        if since:
            all_events = [e for e in all_events if e.timestamp >= since]

        # Sort by timestamp (newest first) and limit
        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        return all_events[:limit]

    async def get_by_id(self, event_id: UUID) -> Event | None:
        """Get event by ID."""
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    async def clear(self) -> None:
        """Clear all stored events."""
        self._events.clear()
        logger.info("event_store_cleared")
