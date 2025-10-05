"""
Additional event endpoints for HTTP requests.

Provides REST API for event data (not real-time).
Following SOLID principles - separate from real-time transports.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.core.events import get_event_bus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])


class EventResponse(BaseModel):
    """Event response model."""

    id: str
    type: str
    timestamp: str
    data: dict[str, Any]
    source: str
    sequence: int | None


class RecentEventsResponse(BaseModel):
    """Response model for recent events."""

    events: list[EventResponse]
    count: int
    limit: int
    event_type: str | None = None


@router.get("/recent", response_model=RecentEventsResponse)
async def get_recent_events(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum events to return"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
) -> RecentEventsResponse:
    """
    Get recent events from the event store.

    This endpoint provides historical event data via HTTP (not real-time).
    For real-time updates, use /events/stream (SSE) or /ws (WebSocket).

    Args:
        limit: Maximum number of events to return (1-1000)
        event_type: Optional filter for specific event types

    Returns:
        List of recent events with metadata
    """
    event_bus = get_event_bus()

    # Get recent events from store
    events = await event_bus.get_recent_events(limit=limit, event_type=event_type)

    # Convert to response models
    event_responses = [
        EventResponse(
            id=str(event.id),
            type=event.type,
            timestamp=event.timestamp.isoformat(),
            data=event.data,
            source=event.source,
            sequence=event.sequence,
        )
        for event in events
    ]

    logger.info(
        "recent_events_requested",
        count=len(event_responses),
        limit=limit,
        event_type=event_type,
    )

    return RecentEventsResponse(
        events=event_responses,
        count=len(event_responses),
        limit=limit,
        event_type=event_type,
    )
