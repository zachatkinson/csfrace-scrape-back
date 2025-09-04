# Multi-stage Dockerfile for production deployment using UV

#########################
# Build stage
#########################
FROM python:3.13-slim-bookworm AS builder

# Install UV from official image (production best practice)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables for UV and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/.uv-cache

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
# Production stage
#########################
FROM python:3.13-slim-bookworm AS production

# Copy UV binary from official UV image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src" \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install minimal runtime dependencies with version pinning and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl=7.* \
    ca-certificates=2* \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/archives/*

# Create non-root user
RUN groupadd -r scraper && useradd -r -g scraper scraper

# Copy the Python environment from builder (system Python installation)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set work directory
WORKDIR /app

# Copy application code
COPY --chown=scraper:scraper . .

# Create necessary directories
RUN mkdir -p /app/output /app/logs && \
    chown -R scraper:scraper /app

# Health check for API mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER scraper

# Expose port for API mode
EXPOSE 8000

# Set flexible entrypoint that supports both CLI and API modes
ENTRYPOINT ["uv", "run"]

# Default to API server mode in production
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Labels for metadata
LABEL org.opencontainers.image.title="CSFrace Scraper" \
      org.opencontainers.image.description="WordPress to Shopify content converter" \
      org.opencontainers.image.source="https://github.com/zachatkinson/csfrace-scrape" \
      org.opencontainers.image.vendor="CSFrace Development Team" \
      org.opencontainers.image.version="1.3.0"