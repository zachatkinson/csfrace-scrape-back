"""Health and monitoring API router package.

This package splits the monolithic health router into focused modules
following the Single Responsibility Principle.
"""

from fastapi import APIRouter

from .checks import router as checks_router
from .metrics_export import router as metrics_router
from .streaming import router as streaming_router
from .system_info import router as system_info_router

# Create the main health router by combining all sub-routers
router = APIRouter(prefix="/health", tags=["Health & Monitoring"])

# Include all focused routers
router.include_router(checks_router)
router.include_router(system_info_router)
router.include_router(metrics_router)
router.include_router(streaming_router)

__all__ = ["router"]
