"""System information endpoints following Single Responsibility Principle.

This module handles system information gathering including:
- Detailed system information (/system)
- Platform and runtime details
- Application version and uptime tracking
"""

import importlib.metadata
import platform
import sys
import time
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.utils.logging import get_logger

from ...utils import handle_api_exceptions

logger = get_logger(__name__)

# Get version from package metadata
try:
    __version__ = importlib.metadata.version("csfrace-scraper")
except importlib.metadata.PackageNotFoundError:
    __version__ = "1.0.0"  # Fallback version

# Track service startup time for uptime calculation
_startup_time = time.time()


class SystemInfoResponse(BaseModel):
    """System information response model."""

    platform: str
    platform_release: str
    platform_version: str
    architecture: str
    processor: str
    python_version: str
    python_implementation: str
    app_version: str
    uptime_seconds: int
    startup_time: datetime


router = APIRouter()


@router.get("/system", response_model=SystemInfoResponse)
@handle_api_exceptions("Failed to get system information")
async def system_info() -> SystemInfoResponse:
    """Get detailed system information for monitoring and debugging.

    Returns:
        Comprehensive system and runtime information

    Note:
        This endpoint is useful for:
        - Debugging deployment issues
        - Monitoring Python version compatibility
        - Tracking application uptime
        - Verifying deployment configurations
    """
    logger.info("Gathering system information")

    uptime_seconds = int(time.time() - _startup_time)
    startup_datetime = datetime.fromtimestamp(_startup_time, tz=UTC)

    system_data = SystemInfoResponse(
        platform=platform.system(),
        platform_release=platform.release(),
        platform_version=platform.version(),
        architecture=platform.machine(),
        processor=platform.processor() or "Unknown",
        python_version=sys.version,
        python_implementation=platform.python_implementation(),
        app_version=__version__,
        uptime_seconds=uptime_seconds,
        startup_time=startup_datetime,
    )

    logger.info(
        "System information gathered",
        platform=system_data.platform,
        python_version=system_data.python_implementation,
        uptime_seconds=uptime_seconds,
    )

    return system_data
