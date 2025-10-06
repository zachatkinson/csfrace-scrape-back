"""
WebSocket endpoint for bidirectional real-time communication.

Following SOLID principles:
- Single Responsibility: Only handles WebSocket transport
- Dependency Inversion: Depends on event bus abstraction

Modern 2025 best practices:
- Ping/pong for connection health
- JSON message format
- Structured error handling
- Type-safe event serialization
"""

from datetime import UTC, datetime
from typing import Any

import asyncio
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from src.core.events import Event, get_event_bus

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Real-Time Events"])


class WebSocketMessage(BaseModel):
    """WebSocket message model for type safety."""

    type: str
    data: dict[str, Any] | None = None


class ConnectionManager:
    """
    Manages WebSocket connections.

    Following Single Responsibility Principle - only manages WS connections.
    """

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("websocket_connected", total_connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("websocket_disconnected", total_connections=len(self.active_connections))

    async def send_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Send JSON message to specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error("websocket_send_error", error=str(e))
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for bidirectional real-time communication.

    Supports:
    - Receiving client messages (ping, subscribe, unsubscribe)
    - Broadcasting server events
    - Connection health monitoring

    Message format (JSON):
    {
        "type": "ping" | "subscribe" | "unsubscribe" | "event",
        "data": { ... }
    }

    Example client messages:
        # Ping
        {"type": "ping"}

        # Subscribe to events
        {"type": "subscribe", "data": {"event_type": "health"}}

        # Unsubscribe
        {"type": "unsubscribe", "data": {"event_type": "health"}}
    """
    await manager.connect(websocket)

    # Create queue for this connection
    event_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)

    # Event handler to push events to this connection's queue
    async def queue_event(event: Event) -> None:
        """Push event to queue without blocking."""
        try:
            await asyncio.wait_for(event_queue.put(event), timeout=0.1)
        except TimeoutError:
            logger.warning("websocket_queue_full", event_id=str(event.id))

    # Get event bus
    event_bus = get_event_bus()

    # Track subscriptions for this connection
    subscriptions: set[str | None] = set()

    try:
        # Send welcome message
        await manager.send_message(
            websocket,
            {
                "type": "connected",
                "data": {
                    "message": "WebSocket connection established",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            },
        )

        # Create tasks for receiving and sending
        async def receive_messages() -> None:
            """Receive and handle client messages."""
            while True:
                try:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message = WebSocketMessage.model_validate_json(data)

                    logger.debug("websocket_message_received", message_type=message.type)

                    # Handle different message types
                    if message.type == "ping":
                        # Respond to ping
                        await manager.send_message(
                            websocket,
                            {
                                "type": "pong",
                                "data": {"timestamp": datetime.now(UTC).isoformat()},
                            },
                        )

                    elif message.type == "subscribe":
                        # Subscribe to event type
                        event_type = message.data.get("event_type") if message.data else None
                        if event_type not in subscriptions:
                            event_bus.subscribe(event_type, queue_event)
                            subscriptions.add(event_type)
                            await manager.send_message(
                                websocket,
                                {
                                    "type": "subscribed",
                                    "data": {"event_type": event_type or "all"},
                                },
                            )

                    elif message.type == "unsubscribe":
                        # Unsubscribe from event type
                        event_type = message.data.get("event_type") if message.data else None
                        if event_type in subscriptions:
                            event_bus.unsubscribe(event_type, queue_event)
                            subscriptions.remove(event_type)
                            await manager.send_message(
                                websocket,
                                {
                                    "type": "unsubscribed",
                                    "data": {"event_type": event_type or "all"},
                                },
                            )

                except ValidationError as e:
                    await manager.send_message(
                        websocket,
                        {"type": "error", "data": {"message": f"Invalid message format: {e}"}},
                    )
                except WebSocketDisconnect:
                    break

        async def send_events() -> None:
            """Send events from queue to WebSocket."""
            while True:
                try:
                    # Wait for event with timeout for keep-alive
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                    # Send event to client
                    await manager.send_message(
                        websocket,
                        {
                            "type": event.type,
                            "data": {
                                "id": str(event.id),
                                "timestamp": event.timestamp.isoformat(),
                                "sequence": event.sequence,
                                "source": event.source,
                                "payload": event.data,
                            },
                        },
                    )

                except TimeoutError:
                    # Send keep-alive ping
                    try:
                        await websocket.send_json({"type": "ping"})
                    except Exception:
                        break

        # Run both tasks concurrently
        await asyncio.gather(receive_messages(), send_events())

    except WebSocketDisconnect:
        logger.info("websocket_client_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e))
    finally:
        # Cleanup: unsubscribe from all event types
        for event_type in subscriptions:
            event_bus.unsubscribe(event_type, queue_event)
        manager.disconnect(websocket)
