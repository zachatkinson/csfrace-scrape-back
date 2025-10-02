"""FastAPI metrics endpoints following Single Responsibility Principle.

This module contains all metrics-related endpoints including:
- Prometheus metrics endpoint
- Application metrics configuration
- Metrics export functionality
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

logger = get_api_logger()

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics", response_class=PlainTextResponse)
@api_error_handler("export prometheus metrics")
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics data in plain text format

    Raises:
        HTTPException: If metrics collection fails
    """
    from ..monitoring.metrics import metrics_collector

    logger.info("Exporting Prometheus metrics")

    metrics_data = metrics_collector.export_prometheus_metrics()

    logger.debug("Prometheus metrics exported successfully", metrics_size_bytes=len(metrics_data))

    return metrics_data.decode("utf-8")
    # Enhanced decorator handles exceptions and API error responses


class MetricsConfiguration:
    """Configuration and setup for application metrics."""

    @staticmethod
    def setup_metrics() -> None:
        """Setup application metrics collection."""
        from ..monitoring.metrics import metrics_collector

        logger.info("Setting up application metrics")

        # Initialize metrics collector if needed
        if not metrics_collector.metrics:
            logger.warning("Metrics collector not initialized, metrics may be unavailable")

        logger.info("Application metrics setup completed")
