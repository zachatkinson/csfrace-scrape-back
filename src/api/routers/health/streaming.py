"""Health streaming endpoints following Single Responsibility Principle.

This module provides test endpoints for health streaming verification.
The actual health streaming endpoint is in health_stream.py (/health/stream).

This module handles:
- Stream testing (/stream-test) - Simple test endpoint to verify routing
"""

from fastapi import APIRouter

from src.core.logging_hierarchy import get_api_logger

logger = get_api_logger()

router = APIRouter()


@router.get("/stream-test")
async def health_stream_test() -> dict[str, str]:
    """Simple test endpoint to verify routing works."""
    logger.info("Health stream test endpoint accessed")
    return {"message": "SSE endpoint test", "status": "ok"}
