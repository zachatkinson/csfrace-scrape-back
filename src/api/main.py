"""Main FastAPI application for the CSFrace scraper API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .. import __version__
from ..auth.models import MessageResponse
from ..auth.router import router as auth_router
from ..constants import CONSTANTS
from ..database.init_db import init_db
from .routers import batches, health, jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    # Startup
    try:
        await init_db()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Database initialization failed: {e}")
        # Don't raise - allow app to start for health checks

    yield

    # Shutdown
    # Add cleanup logic here if needed


# Rate limiter for global application endpoints with proper header injection
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

app = FastAPI(
    title="CSFrace Scraper API",
    description="API for managing WordPress to Shopify content conversion jobs",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
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
async def add_security_headers(request: Request, call_next):
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

    # Content-Security-Policy: Comprehensive CSP for API
    csp_directives = [
        "default-src 'none'",  # Deny all by default
        "script-src 'none'",  # No scripts allowed
        "style-src 'unsafe-inline'",  # Allow inline styles for docs
        "img-src 'self' data: https:",  # Allow images from same origin, data URLs, HTTPS
        "font-src 'self' https:",  # Allow fonts from same origin and HTTPS
        "connect-src 'self'",  # API calls to same origin only
        "frame-ancestors 'none'",  # Prevent framing (redundant with X-Frame-Options)
        "base-uri 'none'",  # Prevent base tag injection
        "form-action 'none'",  # No form submissions (API only)
        "frame-src 'none'",  # No frames allowed
        "object-src 'none'",  # No plugins allowed
        "media-src 'none'",  # No media elements
        "manifest-src 'none'",  # No web app manifests
        "worker-src 'none'",  # No web workers
        "child-src 'none'",  # No child browsing contexts
        "upgrade-insecure-requests",  # Upgrade HTTP to HTTPS
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
async def rate_limit_handler(_request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded exceptions with proper headers."""
    response = JSONResponse(
        status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )
    # Headers are automatically injected by SlowAPI when headers_enabled=True
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    return JSONResponse(
        status_code=CONSTANTS.HTTP_STATUS_SERVER_ERROR,
        content={
            "detail": CONSTANTS.ERROR_INTERNAL_SERVER,
            "type": CONSTANTS.ERROR_TYPE_INTERNAL,
            "path": str(request.url.path),
        },
    )


# Include routers
app.include_router(health.router)
app.include_router(auth_router)  # Authentication endpoints
app.include_router(jobs.router)
app.include_router(batches.router)


@app.get("/", response_model=MessageResponse, tags=["Root"])
async def root() -> MessageResponse:
    """Root endpoint with API information."""
    return MessageResponse(
        message=f"CSFrace Scraper API v{__version__} - Docs: /docs, Health: /health"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=CONSTANTS.LOCALHOST_IP, port=CONSTANTS.DEFAULT_API_PORT)
