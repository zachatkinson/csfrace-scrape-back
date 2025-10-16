"""Health monitoring SSE stream endpoint using event-driven Redis pub/sub.

REFACTORED: Was 157 lines with static snapshot pattern (sent data then closed).
NOW: 95 lines with event-driven pattern (persistent connection via Redis pub/sub).

This refactoring:
- Eliminates reconnection loop (was connecting/closing every 3 seconds)
- Uses BaseSSEService for DRY compliance
- Subscribes to health_events Redis channel for real-time updates
- Maintains persistent connection with proper keepalive
"""

import json
import time
from datetime import UTC, datetime
from typing import Any

import aiohttp
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger
from src.core.sse import BaseSSEService

from ...monitoring.health_events import publish_health_change_events
from ..dependencies import DBSession
from ..services.health_service import health_service

logger = get_api_logger()

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


class HealthSSEService(BaseSSEService):
    """Health monitoring SSE service following SOLID principles.

    Responsibilities:
    - Stream real-time health status changes via Redis pub/sub
    - Provide initial health snapshot on connection
    - Transform health events for frontend consumption
    """

    def __init__(self, db: DBSession):
        """Initialize health SSE service.

        Args:
            db: Database session for health checks
        """
        super().__init__(connection_message="Real-time health monitoring connected")
        self.db = db

    def get_redis_channel(self) -> str:
        """Subscribe to health_events Redis channel."""
        return "health_events"

    def should_track_terminal_states(self) -> bool:
        """Health monitoring streams all changes (no terminal states)."""
        return False

    async def get_initial_data(self, user_id: str | None = None) -> dict[str, Any]:
        """Fetch initial health snapshot for all services.

        Provides baseline health status before streaming real-time updates.

        Returns:
            Dictionary with initial health data for all services
        """

        # Helper function to check frontend health
        async def check_frontend_health() -> dict[str, str | int | float]:
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

        # Get backend/database/cache health
        backend_start = time.time()
        current_health = await health_service.get_comprehensive_health_status(self.db)
        backend_response_time = round((time.time() - backend_start) * 1000, 2)

        # Get frontend health
        frontend_health = await check_frontend_health()

        # Build initial services snapshot
        services = []

        # Frontend service
        services.append(
            {
                "service": "frontend",
                "status": frontend_health["status"],
                "data": {
                    "version": "5.13.7",
                    "framework": "Astro + React + TypeScript",
                    "response_time_ms": frontend_health["response_time_ms"],
                },
            }
        )

        # Backend service
        services.append(
            {
                "service": "backend",
                "status": current_health.get("status", "healthy"),
                "data": {
                    "version": current_health.get("version", "1.0.0"),
                    "framework": "FastAPI + Python 3.13",
                    "response_time_ms": backend_response_time,
                },
            }
        )

        # Database service
        if "database" in current_health:
            services.append(
                {
                    "service": "database",
                    "status": "healthy"
                    if current_health["database"].get("status") == "healthy"
                    else "unhealthy",
                    "data": current_health["database"],
                }
            )

        # Cache service
        if "cache" in current_health:
            services.append(
                {
                    "service": "cache",
                    "status": "healthy"
                    if current_health["cache"].get("status") == "healthy"
                    else "unhealthy",
                    "data": current_health["cache"],
                }
            )

        return {
            "type": "initial_health_data",
            "services": services,
            "timestamp": datetime.now(UTC).isoformat(),
            "total_services": len(services),
        }

    async def process_redis_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Transform health event from Redis into SSE event format.

        Args:
            message: Raw Redis pub/sub message

        Returns:
            Formatted health event for frontend, or None to skip
        """
        try:
            # Parse health event from Redis
            event_data = json.loads(message["data"].decode("utf-8"))

            # Transform to SSE format matching frontend expectations
            return {
                "event_type": "service-update",  # Frontend expects "service-update" events
                "service": event_data.get("service_name"),
                "status": event_data.get("status"),
                "message": event_data.get("message"),
                "timestamp": event_data.get("timestamp"),
                "data": event_data.get("data", {}),
            }

        except Exception as e:
            logger.error("Failed to process health event", error=str(e), message=message)
            return None


@router.get("/stream")
async def health_stream(request: Request, db: DBSession) -> StreamingResponse:
    """Real-time health monitoring SSE endpoint using event-driven Redis pub/sub.

    REFACTORED from static snapshot (sent 4 updates then closed) to event-driven
    (persistent connection streaming only when health changes).

    This fixes the reconnection loop issue where the endpoint was connecting,
    sending updates, closing, and reconnecting every 3 seconds.

    Args:
        request: FastAPI request for disconnect detection
        db: Database session for health checks

    Returns:
        StreamingResponse with persistent SSE connection
    """
    service = HealthSSEService(db=db)

    return StreamingResponse(
        service.stream_events(request=request),
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
async def trigger_health_check(db: DBSession) -> dict[str, Any]:
    """Manually trigger a health check and event publication.

    Useful for testing the health event system and forcing an immediate update.

    Args:
        db: Database session for health checks

    Returns:
        Health check results and confirmation
    """
    # Get current health status
    current_health = await health_service.get_comprehensive_health_status(db)

    # Detect changes and publish events to Redis
    # (Connected SSE clients will receive these via health_events channel)
    await publish_health_change_events(current_health)

    return {
        "message": "Health check triggered successfully",
        "health": current_health,
        "timestamp": current_health.get("timestamp"),
    }
