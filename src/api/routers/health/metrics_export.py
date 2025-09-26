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

from src.utils.logging import get_logger

from ....monitoring.metrics import metrics_collector
from ...schemas import MetricsResponse
from ...utils import handle_api_exceptions

# Optional imports with graceful fallbacks
try:
    from ....caching.manager import cache_manager
except ImportError:
    cache_manager = None  # type: ignore

try:
    from ....monitoring.performance import performance_monitor
except ImportError:
    performance_monitor = None  # type: ignore

logger = get_logger(__name__)

router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
@handle_api_exceptions("Failed to collect metrics")
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
@handle_api_exceptions("Failed to export Prometheus metrics")
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

    try:
        await cache_manager.initialize()

        # Get detailed backend type following Redis best practices
        try:
            detailed_backend = await cache_manager.get_detailed_backend_type()
        except Exception:
            # Fallback to basic backend type
            detailed_backend = cache_manager.backend_type
            logger.debug("Using fallback cache backend type", backend=detailed_backend)

        logger.debug("Cache status retrieved", backend=detailed_backend, status="healthy")
        return {
            "status": "healthy",
            "backend": detailed_backend,
        }
    except (ConnectionError, TimeoutError) as cache_error:
        logger.warning("Cache connection error", error=str(cache_error))
        return {"status": "error", "error": str(cache_error)}
    except (AttributeError, ImportError, ValueError) as config_error:
        logger.error("Cache configuration error", error=str(config_error))
        return {"status": "error", "error": f"Cache configuration error: {str(config_error)}"}
    except Exception as general_error:
        logger.error("Unexpected cache error", error=str(general_error))
        return {"status": "error", "error": str(general_error)}


def _get_performance_summary() -> dict[str, Any]:
    """Get performance summary with proper error handling.

    Returns:
        Dictionary containing performance metrics or empty dict if unavailable
    """
    if performance_monitor is None:
        logger.debug("Performance monitor not configured")
        return {}

    try:
        performance_data = performance_monitor.get_performance_summary()
        logger.debug("Performance summary retrieved", metrics_count=len(performance_data))
        return performance_data
    except AttributeError:
        # Performance monitoring may not be fully initialized - this is expected
        logger.debug("Performance monitor not fully initialized")
        return {}
