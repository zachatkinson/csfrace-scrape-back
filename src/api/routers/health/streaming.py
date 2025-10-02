"""Health streaming endpoints following Single Responsibility Principle.

This module handles real-time health monitoring including:
- SSE health streaming (/stream)
- Stream testing (/stream-test)
- Real-time service status updates
"""

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.core.logging_hierarchy import get_api_logger

from ...dependencies import DBSession
from ...services.health_service import health_service

logger = get_api_logger()

router = APIRouter()


@router.get("/stream-test")
async def health_stream_test() -> dict[str, str]:
    """Simple test endpoint to verify routing works."""
    logger.info("Health stream test endpoint accessed")
    return {"message": "SSE endpoint test", "status": "ok"}


@router.get("/stream-original")
async def health_stream(request: Request, db: DBSession) -> StreamingResponse:
    """Simple SSE endpoint for real-time health monitoring.

    This is a minimal implementation that provides basic health updates
    without complex dependencies like Redis pub/sub.

    Args:
        request: FastAPI request object for disconnect detection
        db: Database session for health checks

    Returns:
        StreamingResponse: SSE stream of health events
    """
    logger.info("Health SSE stream connection established")

    async def event_generator() -> AsyncGenerator[str]:
        """Generate SSE events with health updates."""
        # Send initial connection message
        connection_data = {
            "type": "connection",
            "message": "Real-time health monitoring connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        yield f"event: connection\ndata: {json.dumps(connection_data)}\n\n"
        logger.debug("Sent connection event")

        # Send initial health status for all services
        async for event in _send_initial_health_status(db):
            yield event

        # Keep connection alive with periodic updates
        update_interval = 30  # seconds
        logger.debug("Starting periodic health updates", interval_seconds=update_interval)

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected from health stream")
                    break

                # Wait for update interval
                await asyncio.sleep(update_interval)

                # Send updated health status with safe handling
                async for event in _send_health_update(db):
                    yield event

        except asyncio.CancelledError:
            logger.info("Health stream cancelled")
        finally:
            logger.info("Health stream cleanup completed")

    async def _send_initial_health_status(db: DBSession) -> AsyncGenerator[str]:
        """Send initial health status for all services."""
        try:
            async for event in _generate_initial_health_events_safe(db):
                yield event
        except Exception as e:
            logger.error("Failed to generate initial health events", error=str(e))
            # Send error event if health check fails
            error_data = {
                "type": "error",
                "message": "Health check failed",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    async def _send_health_update(db: DBSession) -> AsyncGenerator[str]:
        """Send updated health status."""
        try:
            async for event in _generate_health_update_events_safe(db):
                yield event
        except Exception as e:
            logger.error("Failed to generate health update events", error=str(e))
            # Send error event if health check fails
            error_data = {
                "service": "backend",
                "status": "error",
                "message": "Health check temporarily unavailable",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

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


async def _generate_initial_health_events_safe(db: DBSession) -> AsyncGenerator[str]:
    """Safely generate initial health events."""
    services = ["frontend", "backend", "database", "cache"]

    # Get current health data using the existing health service
    current_health = await health_service.get_comprehensive_health_status(db)
    logger.debug("Retrieved current health status for initial broadcast")

    for service_name in services:
        if service_name == "frontend":
            # Frontend is always assumed healthy since we're in the backend
            service_data = {
                "service": "frontend",
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "version": "5.13.7",
                    "port": "3000",
                    "framework": "Astro + React + TypeScript",
                    "response_time_ms": 0,
                },
            }
        elif service_name == "backend":
            # Backend status from current health
            service_data = {
                "service": "backend",
                "status": current_health.get("status", "healthy"),
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "version": current_health.get("version", "1.0.0"),
                    "framework": "FastAPI + Python 3.13",
                    "port": "8000",
                    "response_time_ms": 1,
                },
            }
        elif service_name in current_health:
            # Database and cache status from health check
            service_info = current_health[service_name]
            service_data = {
                "service": service_name,
                "status": ("healthy" if service_info.get("status") == "healthy" else "unhealthy"),
                "timestamp": datetime.now(UTC).isoformat(),
                "data": service_info,
            }
        else:
            # Unknown service - skip
            logger.debug("Skipping unknown service", service=service_name)
            continue

        yield f"event: service-update\ndata: {json.dumps(service_data)}\n\n"
        logger.debug("Sent initial status", service=service_name, status=service_data["status"])


async def _generate_health_update_events_safe(db: DBSession) -> AsyncGenerator[str]:
    """Safely generate health update events."""
    current_health = await health_service.get_comprehensive_health_status(db)

    # Send updated backend status
    backend_update = {
        "service": "backend",
        "status": current_health.get("status", "healthy"),
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "version": current_health.get("version", "1.0.0"),
            "framework": "FastAPI + Python 3.13",
            "port": "8000",
            "response_time_ms": 1,
        },
    }
    yield f"event: service-update\ndata: {json.dumps(backend_update)}\n\n"
    logger.debug("Sent health update", status=backend_update["status"])
