"""Health check and monitoring API endpoints."""

import importlib.metadata
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...auth.models import StatusResponse
from ...monitoring.health import health_checker
from ...monitoring.metrics import metrics_collector
from ...monitoring.observability import observability_manager
from ..dependencies import DBSession
from ..schemas import HealthCheckResponse, MetricsResponse
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

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


@router.get("/", response_model=HealthCheckResponse)
@handle_api_exceptions("Health check failed")
async def health_check(db: DBSession) -> HealthCheckResponse:
    """Comprehensive health check endpoint.

    Args:
        db: Database session

    Returns:
        Health status of all system components

    Raises:
        HTTPException: If critical components are unhealthy
    """
    # Check database connectivity
    try:
        await db.execute(text("SELECT 1"))
        database_status = {"status": "healthy", "connected": True}
    except SQLAlchemyError as db_error:
        database_status = {"status": "unhealthy", "connected": False, "error": str(db_error)}

    # Get health checker status
    health_summary = health_checker.get_health_summary()

    # Get cache status (if available)
    cache_status = await _get_cache_status()

    # Get monitoring status
    monitoring_status = observability_manager.get_component_status()

    # Determine overall status
    overall_status = "healthy"
    if database_status["status"] != "healthy":
        overall_status = "unhealthy"
    elif (
        health_summary.get("status") == "degraded"
        or health_summary.get("status") not in ["healthy", "degraded"]
        or cache_status["status"] == "error"
    ):
        overall_status = "degraded"

    response = HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.now(UTC),
        version=__version__,
        database=database_status,
        cache=cache_status,
        monitoring=monitoring_status,
    )

    # Return appropriate HTTP status
    if overall_status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(mode="json"),
        ) from None  # Suppress original exception chain for clean HTTP response

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
        Basic status indicating the service is running
    """
    return StatusResponse(status="alive")


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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(db_error)}",
        ) from db_error


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
        return {
            "status": "healthy",
            "backend": getattr(cache_manager, "backend_type", "unknown"),
        }
    except (ConnectionError, TimeoutError) as cache_error:
        return {"status": "error", "error": str(cache_error)}
    except (AttributeError, ImportError, ValueError) as config_error:
        return {"status": "error", "error": f"Cache configuration error: {str(config_error)}"}


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
