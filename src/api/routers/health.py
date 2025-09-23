"""Health check and monitoring API endpoints."""

import importlib.metadata
import json
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...auth.models import StatusResponse
from ...monitoring.metrics import metrics_collector
from ..dependencies import DBSession
from ..errors import APIErrorFactory
from ..schemas import HealthCheckResponse, MetricsResponse
from ..services.health_service import health_service
from ..utils import handle_api_exceptions

# Optional imports with graceful fallbacks
try:
    from ...caching.manager import cache_manager
except ImportError:
    cache_manager = None  # type: ignore[assignment]

try:
    from ...monitoring.performance import performance_monitor
except ImportError:
    performance_monitor = None  # type: ignore[assignment]

# Get version from package metadata
try:
    __version__ = importlib.metadata.version("csfrace-scraper")
except importlib.metadata.PackageNotFoundError:
    __version__ = "1.0.0"  # Fallback version

# Track service startup time for uptime calculation
_startup_time = time.time()

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


@router.get("/", response_model=HealthCheckResponse)
@handle_api_exceptions("Health check failed")
async def health_check(db: DBSession) -> HealthCheckResponse:
    """Comprehensive health check endpoint using SOLID principles.

    Args:
        db: Database session

    Returns:
        Health status of all system components

    Raises:
        HTTPException: If critical components are unhealthy
    """
    # Use the dedicated health service following SOLID principles
    health_data = await health_service.get_comprehensive_health_status(db)

    response = HealthCheckResponse(**health_data)

    # Return appropriate HTTP status based on overall health
    if health_data["status"] == "unhealthy":
        raise APIErrorFactory.service_unavailable(
            "Service is unhealthy", details=response.model_dump(mode="json")
        )

    return response


@router.get("/metrics", response_model=MetricsResponse)
@handle_api_exceptions("Failed to collect metrics")
async def get_metrics() -> MetricsResponse:
    """Get system metrics.

    Returns:
        Current system and application metrics

    Raises:
        HTTPException: If metrics collection fails
    """
    # Get metrics snapshot
    metrics_snapshot = metrics_collector.get_metrics_snapshot()

    # Get performance summary if available
    performance_summary = _get_performance_summary()

    return MetricsResponse(
        timestamp=datetime.now(UTC),
        system_metrics=metrics_snapshot.get("system_metrics", {}),
        application_metrics={
            **metrics_snapshot.get("application_metrics", {}),
            **performance_summary,
        },
        database_metrics=metrics_snapshot.get("database_metrics", {}),
    )


@router.get("/live", response_model=StatusResponse)
async def liveness_check() -> StatusResponse:
    """Simple liveness check for container orchestration.

    Returns:
        Basic status indicating the service is running with uptime information
    """
    uptime_seconds = int(time.time() - _startup_time)
    return StatusResponse(
        status="alive",
        uptime_seconds=uptime_seconds,
        message=f"Service running for {uptime_seconds} seconds",
    )


@router.get("/ready", response_model=StatusResponse)
async def readiness_check(db: DBSession) -> StatusResponse:
    """Readiness check for container orchestration.

    Args:
        db: Database session

    Returns:
        Status indicating the service is ready to serve requests

    Raises:
        HTTPException: If service is not ready
    """
    try:
        # Check critical dependencies
        await db.execute(text("SELECT 1"))

        return StatusResponse(status="ready")

    except SQLAlchemyError as db_error:
        raise APIErrorFactory.service_unavailable(f"Service not ready: {str(db_error)}")


@router.get("/prometheus", response_class=PlainTextResponse)
@handle_api_exceptions("Failed to export Prometheus metrics")
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics data in plain text format
    """
    # Export Prometheus metrics
    metrics_data = metrics_collector.export_prometheus_metrics()
    return metrics_data.decode("utf-8")


async def _get_cache_status() -> dict[str, Any]:
    """Get cache status with proper error handling.

    Returns:
        Dictionary containing cache status information
    """
    if cache_manager is None:
        return {"status": "not_configured"}

    try:
        await cache_manager.initialize()

        # Get detailed backend type following Redis best practices
        try:
            detailed_backend = await cache_manager.get_detailed_backend_type()
        except Exception:
            # Fallback to basic backend type
            detailed_backend = cache_manager.backend_type

        return {
            "status": "healthy",
            "backend": detailed_backend,
        }
    except (ConnectionError, TimeoutError) as cache_error:
        return {"status": "error", "error": str(cache_error)}
    except (AttributeError, ImportError, ValueError) as config_error:
        return {"status": "error", "error": f"Cache configuration error: {str(config_error)}"}
    except Exception as general_error:
        return {"status": "error", "error": str(general_error)}


def _get_performance_summary() -> dict[str, Any]:
    """Get performance summary with proper error handling.

    Returns:
        Dictionary containing performance metrics or empty dict if unavailable
    """
    if performance_monitor is None:
        return {}

    try:
        return performance_monitor.get_performance_summary()
    except AttributeError:
        # Performance monitoring may not be fully initialized - this is expected
        return {}


@router.get("/stream-test")
async def health_stream_test() -> dict[str, str]:
    """Simple test endpoint to verify routing works."""
    return {"message": "SSE endpoint test", "status": "ok"}


@router.get("/stream")
async def health_stream(request: Request, db: DBSession) -> StreamingResponse:
    """Simple SSE endpoint for real-time health monitoring.

    This is a minimal implementation that provides basic health updates
    without complex dependencies like Redis pub/sub.

    Returns:
        StreamingResponse: SSE stream of health events
    """

    async def event_generator() -> AsyncGenerator[str]:
        """Generate SSE events with health updates."""

        # Send initial connection message
        connection_data = {
            "type": "connection",
            "message": "Real-time health monitoring connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        yield f"event: connection\ndata: {json.dumps(connection_data)}\n\n"

        # Send initial health status for all services
        services = ["frontend", "backend", "database", "cache"]

        try:
            # Get current health data using the existing health service
            current_health = await health_service.get_comprehensive_health_status(db)

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
                    continue

                yield f"event: service-update\ndata: {json.dumps(service_data)}\n\n"

        except Exception as e:
            # Send error event if health check fails
            error_data = {
                "type": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

        # Keep connection alive with periodic updates
        update_interval = 30  # seconds

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Wait for update interval
                await asyncio.sleep(update_interval)

                # Send keepalive or updated health status
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

                except Exception:
                    # Send keepalive on error
                    keepalive_data = {
                        "type": "keepalive",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    yield f"event: keepalive\ndata: {json.dumps(keepalive_data)}\n\n"

        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            # Send final error
            error_data = {
                "type": "error",
                "message": f"Stream error: {str(e)}",
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
