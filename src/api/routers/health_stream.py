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
async def health_stream(db: DBSession) -> StreamingResponse:
    """Real-time SSE endpoint with actual health checks and response times."""

    async def generate():
        import time
        from datetime import UTC, datetime

        import aiohttp

        # Helper function to check frontend health
        async def check_frontend_health():
            try:
                start_time = time.time()
                timeout = aiohttp.ClientTimeout(total=5)
                async with (
                    aiohttp.ClientSession(timeout=timeout) as session,
                    session.get("http://frontend:3000/") as response,
                ):
                    response_time_ms = round((time.time() - start_time) * 1000, 2)
                    return {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "response_time_ms": response_time_ms,
                    }
            except Exception:
                return {"status": "unhealthy", "response_time_ms": 0}

        # Send connection event
        yield (
            'event: connection\ndata: {"type": "connection", "message": "Real-time health monitoring connected", "timestamp": "'
            + datetime.now(UTC).isoformat()
            + '"}\n\n'
        )

        # Get actual health data
        backend_start = time.time()
        current_health = await health_service.get_comprehensive_health_status(db)
        backend_response_time = round((time.time() - backend_start) * 1000, 2)

        # Check frontend health
        frontend_health = await check_frontend_health()

        # Send frontend update with real response time
        frontend_data = {
            "service": "frontend",
            "status": frontend_health["status"],
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "version": "5.13.7",
                "framework": "Astro + React + TypeScript",
                "response_time_ms": frontend_health["response_time_ms"],
            },
        }
        yield f"event: service-update\ndata: {safe_json_dumps(frontend_data)}\n\n"

        # Send backend update with real response time
        backend_data = {
            "service": "backend",
            "status": current_health.get("status", "healthy"),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "version": current_health.get("version", "1.0.0"),
                "framework": "FastAPI + Python 3.13",
                "response_time_ms": backend_response_time,
            },
        }
        yield f"event: service-update\ndata: {safe_json_dumps(backend_data)}\n\n"

        # Send database update with real data
        if "database" in current_health:
            db_data = {
                "service": "database",
                "status": "healthy"
                if current_health["database"].get("status") == "healthy"
                else "unhealthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": current_health["database"],
            }
            yield f"event: service-update\ndata: {safe_json_dumps(db_data)}\n\n"

        # Send cache update with real data
        if "cache" in current_health:
            cache_data = {
                "service": "cache",
                "status": "healthy"
                if current_health["cache"].get("status") == "healthy"
                else "unhealthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": current_health["cache"],
            }
            yield f"event: service-update\ndata: {safe_json_dumps(cache_data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
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
