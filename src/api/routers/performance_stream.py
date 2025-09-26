"""Performance metrics SSE stream endpoint for real-time performance monitoring."""

import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.utils.logging import get_logger

from ...monitoring.metrics import metrics_collector

logger = get_logger(__name__)

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

        try:
            # Send initial connection event
            connection_data = {
                "type": "connection",
                "message": "Real-time performance monitoring connected",
                "timestamp": "2025-09-18T00:00:00Z",  # Will be updated with real timestamp
            }
            yield f"event: connection\ndata: {safe_json_dumps(connection_data)}\n\n"

            # Send initial performance metrics
            try:
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
                yield f"event: performance-update\ndata: {safe_json_dumps(performance_event)}\n\n"
                logger.info("Initial performance metrics sent via SSE")
            except Exception as e:
                logger.warning("Failed to get initial performance metrics", error=str(e))

            # Performance metrics update loop
            while True:
                try:
                    # Check if client is still connected
                    if await request.is_disconnected():
                        logger.info("Performance SSE client disconnected")
                        break

                    # Wait 30 seconds before sending next update
                    await asyncio.sleep(30.0)

                    # Send performance metrics update
                    try:
                        metrics_snapshot = metrics_collector.get_metrics_snapshot()
                        performance_event = {
                            "type": "performance_metrics",
                            "timestamp": metrics_snapshot.get("timestamp", "2025-09-18T00:00:00Z"),
                            "data": {
                                "system_metrics": metrics_snapshot.get("system_metrics", {}),
                                "application_metrics": metrics_snapshot.get(
                                    "application_metrics", {}
                                ),
                                "database_metrics": metrics_snapshot.get("database_metrics", {}),
                            },
                        }
                        yield f"event: performance-update\ndata: {safe_json_dumps(performance_event)}\n\n"
                        logger.debug("Performance metrics update sent via SSE")
                    except Exception as e:
                        logger.warning("Failed to send performance metrics update", error=str(e))

                except asyncio.CancelledError:
                    logger.info("Performance SSE stream cancelled")
                    break
                except Exception as e:
                    logger.error("Performance SSE stream error", error=str(e))
                    # Send error event to client
                    error_event = {
                        "type": "error",
                        "message": f"Performance monitoring error: {str(e)}",
                        "timestamp": "2025-09-18T00:00:00Z",
                    }
                    yield f"event: error\ndata: {safe_json_dumps(error_event)}\n\n"
                    break

        except Exception as e:
            logger.error("Performance SSE stream fatal error", error=str(e))
        finally:
            logger.info("Performance SSE stream ended")

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
