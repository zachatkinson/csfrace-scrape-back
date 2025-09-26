"""Core health check endpoints following Single Responsibility Principle.

This module handles the primary health check functionality including:
- Comprehensive health checks (/)
- Liveness checks (/live)
- Readiness checks (/ready)
"""

import time

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.utils.logging import get_logger

from ....auth.models import StatusResponse
from ...dependencies import DBSession
from ...errors import APIErrorFactory
from ...schemas import HealthCheckResponse
from ...services.health_service import health_service
from ...utils import handle_api_exceptions

logger = get_logger(__name__)

# Track service startup time for uptime calculation
_startup_time = time.time()

router = APIRouter()


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
    logger.info("Performing comprehensive health check")

    # Use the dedicated health service following SOLID principles
    health_data = await health_service.get_comprehensive_health_status(db)

    response = HealthCheckResponse(**health_data)

    # Return appropriate HTTP status based on overall health
    if health_data["status"] == "unhealthy":
        logger.warning("Service is unhealthy", health_data=health_data)
        raise APIErrorFactory.service_unavailable(
            "Service is unhealthy", details=response.model_dump(mode="json")
        )

    logger.info("Health check completed successfully", status=health_data["status"])
    return response


@router.get("/live", response_model=StatusResponse)
async def liveness_check() -> StatusResponse:
    """Simple liveness check for container orchestration.

    Returns:
        Basic status indicating the service is running with uptime information
    """
    uptime_seconds = int(time.time() - _startup_time)
    logger.debug("Liveness check", uptime_seconds=uptime_seconds)

    return StatusResponse(
        status="alive",
        uptime_seconds=uptime_seconds,
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
    logger.info("Performing readiness check")

    try:
        # Check critical dependencies
        await db.execute(text("SELECT 1"))
        logger.info("Readiness check passed")

        return StatusResponse(status="ready")

    except SQLAlchemyError as db_error:
        logger.error("Readiness check failed", error=str(db_error))
        raise APIErrorFactory.service_unavailable(f"Service not ready: {str(db_error)}")
