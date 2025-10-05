"""
Real-time event system for scraper application.

This module provides a pub/sub event bus architecture following SOLID principles:
- Single Responsibility: Each class has one clear purpose
- Open/Closed: Extensible via interfaces
- Liskov Substitution: All event types follow same contract
- Interface Segregation: Focused interfaces for different concerns
- Dependency Inversion: Depend on abstractions, not implementations

Modern 2025 best practices:
- SSE for server→client updates (primary transport)
- WebSocket for bidirectional communication (when needed)
- Shared event bus (DRY principle)
- Type-safe event models with Pydantic
- Async-first design
"""

from .base import Event, EventPublisher, EventSubscriber
from .bus import EventBus, get_event_bus
from .models import (
    HealthEvent,
    NotificationEvent,
    ScrapingProgressEvent,
    SystemEvent,
)
from .store import EventStore, InMemoryEventStore

__all__ = [
    # Base interfaces
    "Event",
    "EventSubscriber",
    "EventPublisher",
    # Event bus
    "EventBus",
    "get_event_bus",
    # Event models
    "HealthEvent",
    "ScrapingProgressEvent",
    "NotificationEvent",
    "SystemEvent",
    # Event storage
    "EventStore",
    "InMemoryEventStore",
]
