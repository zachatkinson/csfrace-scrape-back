"""Health monitoring SSE stream endpoint for real-time health updates."""

import contextlib
import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import asyncio
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ...caching.manager import cache_manager
from ...monitoring.health_events import (
    HealthEvent,
    health_event_subscriber,
    initialize_health_events,
)
from ..dependencies import DBSession
from ..services.health_service import health_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


def safe_json_dumps(data: Any) -> str:
    """JSON dumps with handling for non-serializable types like Decimal."""
    def default_serializer(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(data, default=default_serializer)


@router.get("/stream")
async def health_stream(request: Request, db: DBSession) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time health monitoring.

    This endpoint provides a true event-driven health monitoring stream using Redis pub/sub.
    Instead of polling the backend on intervals, it listens for actual health change events
    and streams them to the client in real-time.

    Returns:
        StreamingResponse: SSE stream of health events
    """
    logger.info("Health SSE stream connection established")

    async def event_generator() -> AsyncGenerator[str]:
        """Generate SSE events from Redis health event stream."""

        # Initialize Redis connection for events if not done
        try:
            if health_event_subscriber is None:
                await cache_manager.initialize()
                redis_client = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]
                await initialize_health_events(redis_client)

        except Exception as e:
            logger.error("Failed to initialize health event system", error=str(e))
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Failed to initialize event system'})}\n\n"
            return

        # Send initial connection message
        connection_data = {
            "type": "connection",
            "message": "Real-time health monitoring connected",
            "timestamp": "2023-01-01T00:00:00Z",
        }
        yield f"event: connection\ndata: {safe_json_dumps(connection_data)}\n\n"

        # Get initial health status and send initial events
        try:
            current_health = await health_service.get_comprehensive_health_status(db)
            logger.debug("Raw health data retrieved", health_keys=list(current_health.keys()))

            # Send initial service status events
            services = ["frontend", "backend", "database", "cache"]

            for service_name in services:
                if service_name == "frontend":
                    service_data = {
                        "service": "frontend",
                        "status": "healthy",
                        "timestamp": (
                            current_health["timestamp"].isoformat()
                            if hasattr(current_health["timestamp"], "isoformat")
                            else str(current_health["timestamp"])
                        ),
                        "data": {
                            "version": "5.13.7",
                            "port": "3000",
                            "framework": "Astro + React + TypeScript",
                            "response_time_ms": 0,
                        },
                    }
                elif service_name == "backend":
                    service_data = {
                        "service": "backend",
                        "status": current_health["status"],
                        "timestamp": (
                            current_health["timestamp"].isoformat()
                            if hasattr(current_health["timestamp"], "isoformat")
                            else str(current_health["timestamp"])
                        ),
                        "data": {
                            "version": current_health["version"],
                            "framework": "FastAPI + Python 3.13",
                            "port": "8000",
                            "response_time_ms": 1,
                        },
                    }
                elif service_name in current_health:
                    service_info = current_health[service_name]
                    service_data = {
                        "service": service_name,
                        "status": service_info.get("status", "unknown"),
                        "timestamp": (
                            current_health["timestamp"].isoformat()
                            if hasattr(current_health["timestamp"], "isoformat")
                            else str(current_health["timestamp"])
                        ),
                        "data": service_info,
                    }
                else:
                    continue

                yield f"event: service-update\ndata: {safe_json_dumps(service_data)}\n\n"

        except Exception as e:
            logger.error("Failed to send initial health status", error=str(e))
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Failed to get initial health status'})}\n\n"

        # Set up event listener for Redis pub/sub health events from Health Service Registry
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Direct Redis pub/sub listener for service health data
        async def redis_health_listener():
            """Listen directly to Redis health_events channel for service updates."""
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe("health_events")

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            # Parse service health data from Health Service Registry
                            service_data = json.loads(message["data"].decode("utf-8"))

                            # Format for SSE client (consistent with existing format)
                            service_update = {
                                "service": service_data["service"],
                                "status": service_data["status"],
                                "timestamp": service_data["timestamp"],
                                "data": {
                                    "version": service_data.get("version"),
                                    "framework": service_data.get("framework"),
                                    "port": service_data.get("port"),
                                    "response_time_ms": service_data["response_time_ms"],
                                    **service_data["details"]
                                }
                            }
                            await event_queue.put(service_update)

                        except Exception as e:
                            logger.error("Failed to process service health data", error=str(e))

            except Exception as e:
                logger.error("Redis health listener failed", error=str(e))

        # Start Redis listener task
        listener_task = asyncio.create_task(redis_health_listener())

        # Legacy event callback for backwards compatibility
        async def health_event_callback(event: HealthEvent):
            """Callback for health events from legacy pub/sub."""
            try:
                # Convert health event to service update format
                service_update = {
                    "service": event.service_name,
                    "status": event.status,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data.get("current_status", {}),
                    "message": event.message,
                    "event_type": event.event_type.value,
                }
                await event_queue.put(service_update)

            except Exception as e:
                logger.error(
                    "Failed to process health event",
                    event_id=getattr(event, "event_id", "unknown"),
                    error=str(e),
                )

        # Subscribe to legacy health events (for backwards compatibility)
        if health_event_subscriber:
            await health_event_subscriber.subscribe(health_event_callback)

        # Stream events from queue
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Health SSE client disconnected")
                    break

                try:
                    # Wait for events with timeout to periodically check connection
                    service_update = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    yield f"event: service-update\ndata: {safe_json_dumps(service_update)}\n\n"

                except TimeoutError:
                    # Send keepalive ping every 30 seconds
                    yield f"event: keepalive\ndata: {safe_json_dumps({'timestamp': '2023-01-01T00:00:00Z'})}\n\n"
                    continue

        except asyncio.CancelledError:
            logger.info("Health SSE stream cancelled")
        except Exception as e:
            logger.error("Health SSE stream error", error=str(e))
            yield f"event: error\ndata: {safe_json_dumps({'error': str(e)})}\n\n"
        finally:
            # Cleanup Redis listener task
            if 'listener_task' in locals():
                listener_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listener_task

            # Cleanup legacy subscription
            if health_event_subscriber:
                health_event_subscriber.unsubscribe(health_event_callback)
            logger.info("Health SSE stream cleanup completed")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


@router.post("/trigger-check")
async def trigger_health_check(db: DBSession):
    """Manually trigger a health check and event publication.

    This endpoint allows forcing a health check which will detect changes
    and emit events if any service status has changed.

    Returns:
        Health status and any events that were published
    """
    from ...monitoring.health_events import publish_health_change_events

    try:
        # Get current health status
        current_health = await health_service.get_comprehensive_health_status(db)

        # This will detect changes and publish events to Redis
        await publish_health_change_events(current_health)

        return {
            "message": "Health check triggered successfully",
            "health": current_health,
            "timestamp": current_health.get("timestamp"),
        }

    except Exception as e:
        logger.error("Failed to trigger health check", error=str(e))
        return {"error": str(e), "message": "Failed to trigger health check"}
