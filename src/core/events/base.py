"""
Base event interfaces and abstract classes.

Following SOLID principles:
- Interface Segregation: Minimal, focused interfaces
- Dependency Inversion: Code depends on these abstractions
- Liskov Substitution: All implementations must be substitutable
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class Event(BaseModel):
    """
    Base event model.

    All events must inherit from this class to ensure consistency.
    Uses Pydantic for type safety and validation (2025 best practice).
    """

    # Event identification
    id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    type: str = Field(..., description="Event type (e.g., 'health', 'scraping.progress')")

    # Event timing
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When event occurred")

    # Event data
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")

    # Event metadata
    source: str = Field(default="system", description="Event source identifier")
    sequence: int | None = Field(default=None, description="Optional sequence number")

    # Pydantic V2 configuration using ConfigDict
    model_config = ConfigDict(
        frozen=False,  # Allow modifications for sequence numbers
    )

    # Pydantic V2 custom serializers (replaces deprecated json_encoders)
    @field_serializer("timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return value.isoformat()

    @field_serializer("id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID to string."""
        return str(value)


class EventSubscriber(ABC):
    """
    Abstract subscriber interface.

    Following Interface Segregation Principle - minimal interface.
    Subscribers only need to handle events, nothing more.
    """

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """
        Handle an event.

        Args:
            event: The event to handle

        Raises:
            Should not raise exceptions - handle errors internally
        """
        pass


class EventPublisher(ABC):
    """
    Abstract publisher interface.

    Following Interface Segregation Principle - minimal interface.
    Publishers only need to publish events, nothing more.
    """

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """
        Publish an event.

        Args:
            event: The event to publish

        Raises:
            May raise exceptions on critical failures
        """
        pass


# Type aliases for better code clarity
EventHandler = Callable[[Event], Awaitable[None]]
EventFilter = Callable[[Event], bool]
