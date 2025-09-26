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

from src.utils.logging import get_logger

from ...dependencies import DBSession
from ...services.health_service import health_service

logger = get_logger(__name__)

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
        try:
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

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected from health stream")
                    break

                # Wait for update interval
                await asyncio.sleep(update_interval)

                # Send updated health status
                try:
                    async for event in _send_health_update(db):
                        yield event
                except Exception as update_error:
                    logger.warning("Failed to send health update", error=str(update_error))
                    # Send keepalive on error
                    keepalive_data = {
                        "type": "keepalive",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    yield f"event: keepalive\ndata: {json.dumps(keepalive_data)}\n\n"

        except asyncio.CancelledError:
            logger.info("Health stream cancelled")
        except Exception as e:
            logger.error("Health stream error", error=str(e))
            # Send final error
            error_data = {
                "type": "error",
                "message": f"Stream error: {str(e)}",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        finally:
            logger.info("Health stream cleanup completed")

    async def _send_initial_health_status(db: DBSession) -> AsyncGenerator[str]:
        """Send initial health status for all services."""
        services = ["frontend", "backend", "database", "cache"]

        try:
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
                        "status": (
                            "healthy" if service_info.get("status") == "healthy" else "unhealthy"
                        ),
                        "timestamp": datetime.now(UTC).isoformat(),
                        "data": service_info,
                    }
                else:
                    # Unknown service - skip
                    logger.debug("Skipping unknown service", service=service_name)
                    continue

                yield f"event: service-update\ndata: {json.dumps(service_data)}\n\n"
                logger.debug(
                    "Sent initial status", service=service_name, status=service_data["status"]
                )

        except Exception as e:
            logger.error("Failed to send initial health status", error=str(e))
            # Send error event if health check fails
            error_data = {
                "type": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    async def _send_health_update(db: DBSession) -> AsyncGenerator[str]:
        """Send updated health status."""
        try:
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

        except Exception as e:
            logger.error("Failed to get health status for update", error=str(e))
            raise

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
