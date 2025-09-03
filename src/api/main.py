"""Main FastAPI application for the CSFrace scraper API."""

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import __version__
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
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:4321",  # Astro dev server ports
).split(",")

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
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error",
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
        "version": "1.1.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
