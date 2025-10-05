"""Scraper API router wrapping job management endpoints.

This router provides the /scraper namespace for the API contract.
"""

from fastapi import APIRouter

from .jobs import router as jobs_router

# Create the scraper router with /scraper prefix
router = APIRouter(prefix="/scraper", tags=["Scraper"])

# Include the jobs router without additional prefix
# This makes jobs available at /scraper/jobs instead of /jobs
router.include_router(jobs_router, prefix="")

__all__ = ["router"]
