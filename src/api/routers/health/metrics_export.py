"""Metrics export endpoints following Single Responsibility Principle.

This module handles metrics collection and export including:
- Application metrics (/metrics)
- Prometheus metrics export (/prometheus)
- Performance monitoring integration
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

# Import optional dependencies with fallback
from ....caching.manager import cache_manager
from ....monitoring.metrics import metrics_collector
from ....monitoring.performance import performance_monitor
from ...schemas import MetricsResponse

logger = get_api_logger()

router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
@api_error_handler("collect metrics")
async def get_metrics() -> MetricsResponse:
    """Get system metrics.

    Returns:
        Current system and application metrics

    Raises:
        HTTPException: If metrics collection fails
    """
    logger.info("Collecting system metrics")

    # Get metrics snapshot
    metrics_snapshot = metrics_collector.get_metrics_snapshot()

    # Get performance summary if available
    performance_summary = _get_performance_summary()

    # Get cache status for additional metrics
    cache_status = await _get_cache_status()

    response = MetricsResponse(
        timestamp=datetime.now(UTC),
        system_metrics=metrics_snapshot.get("system_metrics", {}),
        application_metrics={
            **metrics_snapshot.get("application_metrics", {}),
            **performance_summary,
            "cache": cache_status,
        },
        database_metrics=metrics_snapshot.get("database_metrics", {}),
    )

    logger.info(
        "Metrics collected successfully",
        system_metrics_count=len(response.system_metrics),
        app_metrics_count=len(response.application_metrics),
    )

    return response


@router.get("/prometheus", response_class=PlainTextResponse)
@api_error_handler("export Prometheus metrics")
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics data in plain text format
    """
    logger.info("Exporting Prometheus metrics")

    # Export Prometheus metrics
    metrics_data = metrics_collector.export_prometheus_metrics()

    logger.info("Prometheus metrics exported", data_size_bytes=len(metrics_data))

    return metrics_data.decode("utf-8")


async def _get_cache_status() -> dict[str, Any]:
    """Get cache status with proper error handling.

    Returns:
        Dictionary containing cache status information
    """
    if cache_manager is None:
        logger.debug("Cache manager not configured")
        return {"status": "not_configured"}

    # Initialize cache and get status
    cache_status = await _get_cache_status_safe()
    return (
        cache_status
        if cache_status is not None
        else {"status": "error", "error": "Cache status check failed"}
    )


def _get_performance_summary() -> dict[str, Any]:
    """Get performance summary with proper error handling.

    Returns:
        Dictionary containing performance metrics or empty dict if unavailable
    """
    if performance_monitor is None:
        logger.debug("Performance monitor not configured")
        return {}

    # Get performance data with decorator error handling
    performance_data = _get_performance_data_safe()
    return performance_data if performance_data is not None else {}


@api_error_handler("get cache status")
async def _get_cache_status_safe() -> dict[str, Any]:
    """Safely get cache status."""
    await cache_manager.initialize()

    # Get detailed backend type with fallback mechanism
    detailed_backend = await _get_cache_backend_type_safe()
    if detailed_backend is None:
        # Fallback to basic backend type if detailed fails
        detailed_backend = cache_manager.backend_type
        logger.debug("Using fallback cache backend type", backend=detailed_backend)

    logger.debug("Cache status retrieved", backend=detailed_backend, status="healthy")
    return {
        "status": "healthy",
        "backend": detailed_backend,
    }


@api_error_handler("get cache backend type")
async def _get_cache_backend_type_safe() -> str | None:
    """Safely get cache backend type with decorator-handled errors."""
    return await cache_manager.get_detailed_backend_type()


@api_error_handler("get performance data")
def _get_performance_data_safe() -> dict[str, Any]:
    """Safely get performance data."""
    performance_data = performance_monitor.get_performance_summary()
    logger.debug("Performance summary retrieved", metrics_count=len(performance_data))
    return performance_data
