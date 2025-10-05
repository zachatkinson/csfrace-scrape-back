"""
Server-Sent Events (SSE) endpoint for real-time updates.

Following SOLID principles:
- Single Responsibility: Only handles SSE transport
- Dependency Inversion: Depends on event bus abstraction
- Interface Segregation: Minimal SSE-specific interface

Modern 2025 best practices:
- Auto-reconnect support
- Event IDs for replay
- Type-safe event serialization
- Structured logging
"""

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import asyncio
import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.core.events import Event, get_event_bus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events", tags=["Real-Time Events"])


def serialize_sse_event(event: Event) -> str:
    """
    Serialize event to SSE format.

    SSE format:
    id: <event-id>
    event: <event-type>
    data: <json-payload>
    <blank-line>

    Args:
        event: Event to serialize

    Returns:
        SSE-formatted string
    """
    try:
        # Serialize event data to JSON
        data_json = json.dumps(
            {
                "id": str(event.id),
                "type": event.type,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
                "source": event.source,
                "sequence": event.sequence,
            }
        )

        # Build SSE response
        sse_lines = [
            f"id: {event.sequence or event.id}",  # Use sequence for replay
            f"event: {event.type}",
            f"data: {data_json}",
            "",  # Blank line terminates event
        ]

        return "\n".join(sse_lines) + "\n"

    except Exception as e:
        logger.error("sse_serialization_error", error=str(e), event_id=str(event.id))
        # Return error event
        return f"id: error\nevent: error\ndata: {json.dumps({'error': 'Serialization failed'})}\n\n"


async def event_stream_generator(
    event_type: str | None = None,
) -> AsyncGenerator[str]:
    """
    Generate SSE stream from event bus.

    Args:
        event_type: Optional filter for specific event types

    Yields:
        SSE-formatted event strings
    """
    # Create queue for this connection
    event_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)

    # Event handler to push events to queue
    async def queue_event(event: Event) -> None:
        """Push event to queue without blocking."""
        try:
            # Non-blocking put with timeout
            await asyncio.wait_for(event_queue.put(event), timeout=0.1)
        except TimeoutError:
            logger.warning("event_queue_full", event_id=str(event.id))

    # Get event bus and subscribe
    event_bus = get_event_bus()
    event_bus.subscribe(event_type, queue_event)

    try:
        # Send connection event
        connection_event = {
            "type": "connection",
            "message": "Real-time event stream connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        yield f"event: connection\ndata: {json.dumps(connection_event)}\n\n"

        logger.info(
            "sse_client_connected",
            event_type=event_type or "all",
        )

        # Stream events from queue
        while True:
            try:
                # Wait for event with timeout for keep-alive
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                # Serialize and send event
                sse_data = serialize_sse_event(event)
                yield sse_data

            except TimeoutError:
                # Send keep-alive comment (prevents connection timeout)
                yield ": keep-alive\n\n"

    except asyncio.CancelledError:
        logger.info("sse_client_disconnected", event_type=event_type or "all")
        raise
    finally:
        # Cleanup: unsubscribe from event bus
        event_bus.unsubscribe(event_type, queue_event)


@router.get("/stream")
async def events_stream(event_type: str | None = None) -> StreamingResponse:
    """
    Server-Sent Events stream for real-time updates.

    This is the primary endpoint for server→client real-time communication.

    Query Parameters:
        event_type: Optional filter for specific event types
                   (e.g., "health", "scraping.progress", "notification")

    Returns:
        StreamingResponse with text/event-stream content type

    Example:
        # Connect to all events
        GET /events/stream

        # Connect to only health events
        GET /events/stream?event_type=health
    """
    return StreamingResponse(
        event_stream_generator(event_type),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/health")
async def events_health_stream() -> StreamingResponse:
    """
    SSE stream for health events only.

    Convenience endpoint for /events/stream?event_type=health

    Returns:
        StreamingResponse with health events
    """
    return await events_stream(event_type="health")
