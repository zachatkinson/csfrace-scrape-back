"""Main FastAPI application for the CSFrace scraper API."""

from __future__ import annotations

from fastapi import FastAPI
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.logging_hierarchy import get_api_logger

from .. import __version__
from ..auth.models import MessageResponse
from ..auth.router import router as auth_router
from ..constants import ALLOWED_ORIGINS_DEFAULT, DEFAULT_API_PORT, LOCALHOST_IP
from ..database.service import DatabaseService  # noqa: F401 - Used by tests
from .exception_handlers import setup_exception_handlers
from .lifecycle import lifespan
from .metrics_endpoints import router as metrics_router
from .middleware_setup import setup_middleware
from .routers import health, health_stream, jobs, performance_stream, scraper, user_settings
from .routers.events import events_router

logger = get_api_logger()


# Lifespan manager is now imported from lifecycle module


# Rate limiter for global application endpoints with proper header injection
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

# Create FastAPI application with structured lifecycle management
app = FastAPI(
    title="CSFrace Scraper API",
    description="API for managing WordPress to Shopify content conversion jobs",
    version=__version__,
    lifespan=lifespan,
)

# Attach rate limiter to app
app.state.limiter = limiter

# Setup middleware using extracted module
allowed_origins = ALLOWED_ORIGINS_DEFAULT.split(",")
setup_middleware(app, allowed_origins)

# Setup exception handlers using extracted module
setup_exception_handlers(app)


# Middleware is now configured in middleware module


# Security headers middleware is now configured in middleware module


# Exception handlers are now configured in exception_handlers module


# Include routers
app.include_router(health.router)
app.include_router(health_stream.router)  # Real-time health events via SSE
app.include_router(performance_stream.router)  # Real-time performance metrics via SSE
app.include_router(events_router)  # Unified real-time events (SSE + WebSocket + HTTP)
app.include_router(auth_router)  # Authentication endpoints
app.include_router(user_settings.router, prefix="/auth")  # User settings under /auth
app.include_router(jobs.router)
app.include_router(scraper.router)  # Scraper endpoints (/scraper/jobs for API contract)
app.include_router(metrics_router)  # Metrics endpoints


@app.get("/", response_model=MessageResponse, tags=["Root"])
async def root() -> MessageResponse:
    """Root endpoint with API information."""
    return MessageResponse(
        message=f"CSFrace Scraper API v{__version__} - Docs: /docs, Health: /health"
    )


# Metrics endpoints are now in metrics_endpoints module


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=LOCALHOST_IP, port=DEFAULT_API_PORT)
