"""Health check and monitoring API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from ...monitoring.health import health_checker
from ...monitoring.metrics import metrics_collector
from ...monitoring.observability import observability_manager
from ..dependencies import DBSession
from ..schemas import HealthCheckResponse, MetricsResponse

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


@router.get("/", response_model=HealthCheckResponse)
async def health_check(db: DBSession) -> HealthCheckResponse:
    """Comprehensive health check endpoint.

    Args:
        db: Database session

    Returns:
        Health status of all system components

    Raises:
        HTTPException: If critical components are unhealthy
    """
    try:
        # Check database connectivity
        try:
            await db.execute(text("SELECT 1"))
            database_status = {"status": "healthy", "connected": True}
        except Exception as e:
            database_status = {"status": "unhealthy", "connected": False, "error": str(e)}

        # Get health checker status
        health_summary = health_checker.get_health_summary()

        # Get cache status (if available)
        cache_status = {"status": "not_configured"}
        try:
            from ...caching.manager import cache_manager

            await cache_manager.initialize()
            cache_status = {
                "status": "healthy",
                "backend": getattr(cache_manager, "backend_type", "unknown"),
            }
        except Exception as e:
            cache_status = {"status": "error", "error": str(e)}

        # Get monitoring status
        monitoring_status = observability_manager.get_component_status()

        # Determine overall status
        overall_status = "healthy"
        if database_status["status"] != "healthy":
            overall_status = "unhealthy"
        elif (
            health_summary.get("status") not in ["healthy", "degraded"]
            or cache_status["status"] == "error"
        ):
            overall_status = "degraded"

        response = HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            version="1.0.0",  # TODO: Get from package metadata
            database=database_status,
            cache=cache_status,
            monitoring=monitoring_status,
        )

        # Return appropriate HTTP status
        if overall_status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response.model_dump()
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Get system metrics.

    Returns:
        Current system and application metrics

    Raises:
        HTTPException: If metrics collection fails
    """
    try:
        # Get metrics snapshot
        metrics_snapshot = metrics_collector.get_metrics_snapshot()

        # Get performance summary if available
        performance_summary = {}
        try:
            from ...monitoring.performance import performance_monitor

            performance_summary = performance_monitor.get_performance_summary()
        except (ImportError, AttributeError):
            # Performance monitoring may not be initialized - this is expected
            pass

        return MetricsResponse(
            timestamp=datetime.now(timezone.utc),
            system_metrics=metrics_snapshot.get("system_metrics", {}),
            application_metrics={
                **metrics_snapshot.get("application_metrics", {}),
                **performance_summary,
            },
            database_metrics=metrics_snapshot.get("database_metrics", {}),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect metrics: {str(e)}",
        )


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Simple liveness check for container orchestration.

    Returns:
        Basic status indicating the service is running
    """
    return {"status": "alive"}


@router.get("/ready")
async def readiness_check(db: DBSession) -> dict[str, str]:
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

        return {"status": "ready"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Service not ready: {str(e)}"
        )


@router.get("/prometheus")
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics data
    """
    try:
        # Export Prometheus metrics
        metrics_data = metrics_collector.export_prometheus_metrics()
        return metrics_data.decode("utf-8")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export Prometheus metrics: {str(e)}",
        )
