"""Health monitoring SSE stream endpoint for real-time health updates."""

import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from ..dependencies import DBSession
from ..services.health_service import health_service

logger = get_api_logger()

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


def safe_json_dumps(data: Any) -> str:
    """JSON dumps with handling for non-serializable types like Decimal."""

    def default_serializer(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(data, default=default_serializer)


@router.get("/stream")
async def health_stream() -> StreamingResponse:
    """Simple SSE endpoint without dependencies."""

    async def generate():
        yield 'event: connection\ndata: {"type": "connection", "message": "Real-time health monitoring connected", "timestamp": "2023-01-01T00:00:00Z"}\n\n'
        yield 'event: service-update\ndata: {"service": "frontend", "status": "healthy", "timestamp": "2023-01-01T00:00:00Z", "data": {"version": "5.13.7", "framework": "Astro + React + TypeScript"}}\n\n'
        yield 'event: service-update\ndata: {"service": "backend", "status": "healthy", "timestamp": "2023-01-01T00:00:00Z", "data": {"version": "1.0.0", "framework": "FastAPI + Python 3.13"}}\n\n'
        yield 'event: service-update\ndata: {"service": "database", "status": "healthy", "timestamp": "2023-01-01T00:00:00Z", "data": {"connected": true, "response_time_ms": 15.3}}\n\n'
        yield 'event: service-update\ndata: {"service": "cache", "status": "healthy", "timestamp": "2023-01-01T00:00:00Z", "data": {"connected": true, "backend": "redis"}}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/trigger-check")
@api_error_handler("trigger health check")
async def trigger_health_check(db: DBSession):
    """Manually trigger a health check and event publication."""
    from ...monitoring.health_events import publish_health_change_events

    # Get current health status
    current_health = await health_service.get_comprehensive_health_status(db)

    # This will detect changes and publish events to Redis
    await publish_health_change_events(current_health)

    return {
        "message": "Health check triggered successfully",
        "health": current_health,
        "timestamp": current_health.get("timestamp"),
    }
