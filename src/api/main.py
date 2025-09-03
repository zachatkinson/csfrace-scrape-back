"""Main FastAPI application for the CSFrace scraper API."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import __version__
from ..constants import CONSTANTS
from ..database.init_db import init_db
from .routers import batches, health, jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    # Startup
    try:
        await init_db()
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # Don't raise - allow app to start for health checks

    yield

    # Shutdown
    # Add cleanup logic here if needed


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


# Exception handlers
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
app.include_router(jobs.router)
app.include_router(batches.router)


@app.get("/", tags=["Root"])
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "message": "CSFrace Scraper API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=CONSTANTS.LOCALHOST_IP, port=CONSTANTS.DEFAULT_API_PORT)
