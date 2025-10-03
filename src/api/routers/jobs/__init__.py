"""Job management API router package.

This package splits the monolithic jobs router into focused modules
following the Single Responsibility Principle.
"""

from fastapi import APIRouter

from .control import router as control_router
from .crud import router as crud_router
from .execution import router as execution_router
from .streaming import router as streaming_router

# Create the main jobs router by combining all sub-routers
router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Include all focused routers
router.include_router(crud_router)
router.include_router(execution_router)
router.include_router(control_router)
router.include_router(streaming_router)

__all__ = ["router"]
