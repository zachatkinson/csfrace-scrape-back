"""
Real-time event endpoints for SSE and WebSocket connections.

Following 2025 modern best practices:
- SSE for server→client updates (primary)
- WebSocket for bidirectional communication
- Shared event bus (DRY principle)
- Type-safe events

Usage:
    # In FastAPI app
    from src.api.routers.events import events_router
    app.include_router(events_router)
"""

# Combine all event routers into a single router for easier registration
from fastapi import APIRouter

from .endpoints import router as http_router
from .sse import router as sse_router
from .websocket import router as websocket_router

events_router = APIRouter()

# Include sub-routers
events_router.include_router(sse_router)  # /events/stream, /events/health
events_router.include_router(http_router)  # /events/recent
events_router.include_router(websocket_router)  # /ws

__all__ = ["events_router", "sse_router", "websocket_router", "http_router"]
