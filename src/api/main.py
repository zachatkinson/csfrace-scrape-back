"""Main FastAPI application for the CSFrace scraper API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .. import __version__
from ..auth.models import MessageResponse
from ..auth.router import router as auth_router
from ..constants import CONSTANTS
from ..database.init_db import init_db
from ..monitoring.background_health_monitor import (
    start_background_monitoring,
    stop_background_monitoring,
)
from ..monitoring.metrics import metrics_collector
from ..monitoring.observability import observability_manager
from .errors import APIErrorFactory
from .routers import batches, health, health_stream, jobs

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    # Startup
    try:
        await init_db()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Database initialization failed: {e}")
        # Don't raise - allow app to start for health checks

    # Initialize observability system
    try:
        await observability_manager.initialize()
        print("Observability system initialized successfully")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Observability initialization failed: {e}")
        # Don't raise - allow app to start for health checks

    # Start background health monitoring for real-time events
    try:
        await start_background_monitoring(check_interval=30)
        print("Background health monitoring started successfully")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Background health monitoring failed to start: {e}")
        # Don't raise - allow app to start without background monitoring

    yield

    # Shutdown
    try:
        await stop_background_monitoring()
        print("Background health monitoring stopped")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Background health monitoring shutdown failed: {e}")

    try:
        await observability_manager.shutdown()
        print("Observability system shutdown completed")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Observability shutdown failed: {e}")
        # Continue shutdown even if observability fails


# Rate limiter for global application endpoints with proper header injection
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

app = FastAPI(
    title="CSFrace Scraper API",
    description="API for managing WordPress to Shopify content conversion jobs",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware - secure configuration
allowed_origins = CONSTANTS.ALLOWED_ORIGINS_DEFAULT.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods only
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

# Attach rate limiter to app
app.state.limiter = limiter


# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Any:
    """Add comprehensive security headers to all responses."""
    response = await call_next(request)

    # X-Frame-Options: Prevent clickjacking attacks
    response.headers["X-Frame-Options"] = "DENY"

    # X-Content-Type-Options: Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # X-XSS-Protection: Enable browser XSS filtering (legacy support)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Referrer-Policy: Control referrer information sent
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # X-Permitted-Cross-Domain-Policies: Control Flash/PDF cross-domain policies
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    # Content-Security-Policy: API CSP with Swagger UI support
    csp_directives = [
        "default-src 'none'",  # Deny all by default
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Allow Swagger UI scripts
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Allow Swagger UI styles
        "img-src 'self' data: https:",  # Allow images from same origin, data URLs, HTTPS
        "font-src 'self' https: https://cdn.jsdelivr.net",  # Allow fonts including CDN
        "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000",  # API calls to same origin and localhost
        "frame-ancestors 'none'",  # Prevent framing (redundant with X-Frame-Options)
        "base-uri 'none'",  # Prevent base tag injection
        "form-action 'none'",  # No form submissions (API only)
        "frame-src 'none'",  # No frames allowed
        "object-src 'none'",  # No plugins allowed
        "media-src 'none'",  # No media elements
        "manifest-src 'none'",  # No web app manifests
        "worker-src 'none'",  # No web workers
        "child-src 'none'",  # No child browsing contexts
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    # Strict-Transport-Security: Force HTTPS (only add if HTTPS detected)
    if _is_https_request(request):
        # 1 year max-age, include subdomains, allow preloading
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    # Permissions-Policy: Control browser features
    permissions_policy = [
        "accelerometer=()",
        "camera=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "payment=()",
        "usb=()",
    ]
    response.headers["Permissions-Policy"] = ", ".join(permissions_policy)

    # X-Robots-Tag: Prevent search engine indexing of API endpoints
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response


def _is_https_request(request: Request) -> bool:
    """Check if request is over HTTPS (including reverse proxy detection)."""
    return (
        request.url.scheme == "https"
        or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
        or request.headers.get("X-Forwarded-SSL", "").lower() == "on"
    )


# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded exceptions with proper headers using APIErrorFactory."""
    http_exc = APIErrorFactory.rate_limit_exceeded(f"Rate limit exceeded: {exc.detail}")

    response = JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)
    # Headers are automatically injected by SlowAPI when headers_enabled=True
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors using APIErrorFactory."""
    http_exc = APIErrorFactory.internal_server_error(
        "An unexpected error occurred", original_error=exc
    )

    # Add request path to error details for debugging
    if isinstance(http_exc.detail, dict):
        http_exc.detail["path"] = str(request.url.path)

    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


# Note: Using built-in nord theme instead of external library

# Include routers
app.include_router(health.router)
app.include_router(health_stream.router)  # Real-time health events via SSE
app.include_router(auth_router)  # Authentication endpoints
app.include_router(jobs.router)
app.include_router(batches.router)


@app.get("/", response_model=MessageResponse, tags=["Root"])
async def root() -> MessageResponse:
    """Root endpoint with API information."""
    return MessageResponse(
        message=f"CSFrace Scraper API v{__version__} - Docs: /docs, Health: /health"
    )


@app.get("/metrics", response_class=PlainTextResponse, tags=["Monitoring"])
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics data in plain text format

    Raises:
        HTTPException: If metrics collection fails
    """
    try:
        metrics_data = metrics_collector.export_prometheus_metrics()
        return metrics_data.decode("utf-8")
    except Exception as e:
        # Use APIErrorFactory for consistent error handling
        raise APIErrorFactory.internal_server_error(
            f"Failed to export Prometheus metrics: {str(e)}", original_error=e
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=CONSTANTS.LOCALHOST_IP, port=CONSTANTS.DEFAULT_API_PORT)
