"""Job management API router package.

This package splits the monolithic jobs router into focused modules
following the Single Responsibility Principle.
"""

from fastapi import APIRouter

from .control import router as control_router
from .crud import router as crud_router
from .download import router as download_router
from .execution import router as execution_router
from .streaming import router as streaming_router

# Create the main jobs router by combining all sub-routers
router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Include all focused routers
# CRITICAL: streaming_router MUST be first to prevent /jobs/{job_id} from matching /jobs/stream
# FastAPI matches routes in registration order - specific routes before path parameters
router.include_router(streaming_router)  # /jobs/stream (specific literal path)
router.include_router(crud_router)  # /jobs/{job_id} (path parameter - matches anything)
router.include_router(download_router)  # /jobs/{job_id}/download (specific path after parameter)
router.include_router(execution_router)
router.include_router(control_router)

__all__ = ["router"]
