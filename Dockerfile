# Multi-stage Dockerfile for production deployment using UV

#########################
# Build stage
#########################
FROM python:3.13-slim-bookworm AS builder

# Install UV from official image (production best practice)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables for UV and Python (Official UV best practices)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/.uv-cache \
    UV_PROJECT_ENVIRONMENT=/build/.venv

# Install only essential build dependencies with security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.* \
    libxml2-dev=2.* \
    libxslt1-dev=1.* \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/archives/*

# Set work directory
WORKDIR /build

# Copy dependency files for optimal layer caching
COPY uv.lock pyproject.toml ./

# Install dependencies (system Python, no venv overhead)
# Include dev dependencies in builder stage for development
RUN --mount=type=cache,target=/tmp/.uv-cache \
    uv sync --frozen --no-editable

# Copy application code for development
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /build/output /build/logs /tmp/.uv-cache && \
    chmod -R 777 /tmp/.uv-cache

# Health check for development
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port for API mode
EXPOSE 8000

# Set flexible entrypoint for development
ENTRYPOINT ["uv", "run"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

#########################
# Production stage (Distroless for security - Official UV approach)
#########################
FROM gcr.io/distroless/cc-debian12:latest AS production

# Copy Python from builder stage (UV managed Python installation)
COPY --from=builder --chown=65532:65532 /usr/local /usr/local

# Set work directory
WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder --chown=65532:65532 /build/.venv /app/.venv

# Copy application code
COPY --chown=65532:65532 . .

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src" \
    PATH="/app/.venv/bin:$PATH"

# Run as non-root user
USER 65532

# Expose port for API mode
EXPOSE 8000

# Note: No healthcheck in distroless (no curl), health checks handled by orchestrator

# Default to API server mode in production (using venv Python in distroless)
ENTRYPOINT ["/app/.venv/bin/python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Labels for metadata
LABEL org.opencontainers.image.title="CSFrace Scraper" \
      org.opencontainers.image.description="WordPress to Shopify content converter" \
      org.opencontainers.image.source="https://github.com/zachatkinson/csfrace-scrape" \
      org.opencontainers.image.vendor="CSFrace Development Team" \
      org.opencontainers.image.version="1.3.0"