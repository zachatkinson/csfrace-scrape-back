"""Performance metrics SSE stream endpoint for real-time performance monitoring."""

import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from ...monitoring.metrics import metrics_collector

logger = get_api_logger()

router = APIRouter(prefix="/performance", tags=["Performance Monitoring"])


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
async def performance_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time performance monitoring.

    This endpoint provides dedicated performance metrics streaming following SOLID principles:
    - Single Responsibility: Only handles performance metrics
    - Interface Segregation: Clients only get performance data they need
    - Dependency Inversion: Depends on metrics_collector abstraction

    Args:
        request: FastAPI request object for connection management

    Returns:
        StreamingResponse with SSE performance metrics
    """

    async def performance_event_generator() -> AsyncGenerator[str]:
        """Generate performance metrics events via Server-Sent Events.

        Yields:
            Formatted SSE events with performance data
        """
        logger.info("Performance SSE stream started")

        async for event in _performance_event_stream_safe(request):
            yield event

    return StreamingResponse(
        performance_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


@api_error_handler("send initial performance metrics")
def _send_initial_performance_metrics_safe() -> str:
    """Safely get initial performance metrics for SSE."""
    metrics_snapshot = metrics_collector.get_metrics_snapshot()
    performance_event = {
        "type": "performance_metrics",
        "timestamp": metrics_snapshot.get("timestamp", "2025-09-18T00:00:00Z"),
        "data": {
            "system_metrics": metrics_snapshot.get("system_metrics", {}),
            "application_metrics": metrics_snapshot.get("application_metrics", {}),
            "database_metrics": metrics_snapshot.get("database_metrics", {}),
        },
    }
    return f"event: performance-update\ndata: {safe_json_dumps(performance_event)}\n\n"


@api_error_handler("send performance metrics update")
def _send_performance_metrics_update_safe() -> str:
    """Safely get performance metrics update for SSE."""
    metrics_snapshot = metrics_collector.get_metrics_snapshot()
    performance_event = {
        "type": "performance_metrics",
        "timestamp": metrics_snapshot.get("timestamp", "2025-09-18T00:00:00Z"),
        "data": {
            "system_metrics": metrics_snapshot.get("system_metrics", {}),
            "application_metrics": metrics_snapshot.get("application_metrics", {}),
            "database_metrics": metrics_snapshot.get("database_metrics", {}),
        },
    }
    return f"event: performance-update\ndata: {safe_json_dumps(performance_event)}\n\n"


async def _performance_event_stream_safe(request: Request) -> AsyncGenerator[str]:
    """Safely generate performance event stream with proper exception handling."""
    try:
        # Send initial connection event
        connection_data = {
            "type": "connection",
            "message": "Real-time performance monitoring connected",
            "timestamp": "2025-09-18T00:00:00Z",  # Will be updated with real timestamp
        }
        yield f"event: connection\ndata: {safe_json_dumps(connection_data)}\n\n"

        # Send initial performance metrics
        initial_metrics = _send_initial_performance_metrics_safe()
        if initial_metrics is not None:
            yield initial_metrics
            logger.info("Initial performance metrics sent via SSE")

        # Performance metrics update loop
        async for event in _performance_metrics_update_loop_safe(request):
            yield event

        logger.info("Performance SSE stream ended")
    except Exception as e:
        logger.error("Performance event stream error", error=str(e))
        error_event = {
            "type": "error",
            "message": "Performance monitoring error",
            "timestamp": "2025-09-18T00:00:00Z",
        }
        yield f"event: error\ndata: {safe_json_dumps(error_event)}\n\n"


async def _performance_metrics_update_loop_safe(request: Request) -> AsyncGenerator[str]:
    """Safely run performance metrics update loop with asyncio control flow."""
    while True:
        try:
            # Check if client is still connected
            if await request.is_disconnected():
                logger.info("Performance SSE client disconnected")
                break

            # Wait 30 seconds before sending next update
            await asyncio.sleep(30.0)

            # Send performance metrics update
            update_metrics = _send_performance_metrics_update_safe()
            if update_metrics is not None:
                yield update_metrics
                logger.debug("Performance metrics update sent via SSE")

        except asyncio.CancelledError:
            logger.info("Performance SSE stream cancelled")
            break
        except Exception as e:
            # Log full error details internally for debugging
            logger.error("Performance SSE stream error", error=str(e), exc_info=True)
            # Send sanitized error to client without exposing internal details
            error_event = {
                "type": "error",
                "message": "Performance monitoring temporarily unavailable",
                "timestamp": "2025-09-18T00:00:00Z",
            }
            yield f"event: error\ndata: {safe_json_dumps(error_event)}\n\n"
            break
