"""Health check and monitoring API endpoints."""

import importlib.metadata
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
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
