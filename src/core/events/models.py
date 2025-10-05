"""
Concrete event models for different event types.

Following Single Responsibility Principle - each event type is separate.
All events inherit from base Event class (Liskov Substitution Principle).
"""

from enum import Enum
from typing import Any, Literal

from pydantic import Field

from .base import Event


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthEvent(Event):
    """
    Health check event.

    Used for system health monitoring and real-time health streams.
    """

    type: Literal["health"] = "health"
    data: dict[str, Any] = Field(
        default_factory=lambda: {
            "status": HealthStatus.HEALTHY.value,
            "services": {},
            "db_health": {},
            "cache_health": {},
        }
    )


class ScrapingProgressEvent(Event):
    """
    Scraping job progress event.

    Used for real-time progress updates during scraping operations.
    """

    type: Literal["scraping.progress"] = "scraping.progress"
    data: dict[str, Any] = Field(
        default_factory=lambda: {
            "job_id": "",
            "status": "pending",
            "progress": 0,
            "total": 100,
            "message": "",
        }
    )


class NotificationEvent(Event):
    """
    User notification event.

    Used for push notifications to frontend clients.
    """

    type: Literal["notification"] = "notification"
    data: dict[str, Any] = Field(
        default_factory=lambda: {
            "level": "info",  # info, warning, error, success
            "title": "",
            "message": "",
            "action": None,
        }
    )


class SystemEvent(Event):
    """
    System-level event.

    Used for system status changes, configuration updates, etc.
    """

    type: Literal["system"] = "system"
    data: dict[str, Any] = Field(
        default_factory=lambda: {
            "event_name": "",
            "details": {},
        }
    )


class MetricsEvent(Event):
    """
    System metrics event.

    Used for real-time metrics streaming.
    """

    type: Literal["metrics"] = "metrics"
    data: dict[str, Any] = Field(
        default_factory=lambda: {
            "metric_name": "",
            "value": 0,
            "unit": "",
            "tags": {},
        }
    )


# Event type registry for deserialization
EVENT_TYPE_REGISTRY: dict[str, type[Event]] = {
    "health": HealthEvent,
    "scraping.progress": ScrapingProgressEvent,
    "notification": NotificationEvent,
    "system": SystemEvent,
    "metrics": MetricsEvent,
}
