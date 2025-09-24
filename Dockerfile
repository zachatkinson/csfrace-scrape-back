# Modern Dockerfile following Docker best practices
# Single stage with environment-variable driven behavior
# UV-based Python package management (40% faster builds)

FROM python:3.13-slim-bookworm

# Install UV from official image (production best practice)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Docker best practice: Use build args with defaults
ARG ENVIRONMENT=production
ENV ENVIRONMENT=${ENVIRONMENT}

# Set environment variables for UV and Python (Official UV best practices)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/.uv-cache \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install essential build dependencies and curl for health checks with security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.* \
    libxml2-dev=2.* \
    libxslt1-dev=1.* \
    curl=7.* \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/archives/*

# Set work directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r csfrace && useradd -r -g csfrace csfrace

# Copy dependency files for optimal layer caching
COPY uv.lock pyproject.toml ./

# Install dependencies based on ENVIRONMENT
# In development: all dependencies, in production: optimized build + pruning
RUN --mount=type=cache,target=/tmp/.uv-cache \
    if [ "$ENVIRONMENT" = "development" ]; then \
        uv sync --frozen --no-editable; \
    else \
        uv sync --frozen --no-editable --no-dev; \
    fi

# Copy application code
COPY --chown=csfrace:csfrace . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/output /app/logs && \
    chown -R csfrace:csfrace /app

# Switch to non-root user
USER csfrace

# Set default environment variables
ENV HOST=0.0.0.0
ENV PORT=8000

# Expose port for API mode
EXPOSE 8000

# Health check that works for both dev and prod
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD if [ "$ENVIRONMENT" = "production" ]; then \
            /app/.venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=10)"; \
        else \
            curl -f http://localhost:8000/health || exit 1; \
        fi

# Start the application based on ENVIRONMENT
# Docker best practice: Use exec form for better signal handling
CMD ["sh", "-c", "if [ \"$ENVIRONMENT\" = \"development\" ]; then uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload; else uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000; fi"]

# Labels for metadata
LABEL org.opencontainers.image.title="CSFrace Scraper" \
      org.opencontainers.image.description="WordPress to Shopify content converter" \
      org.opencontainers.image.source="https://github.com/zachatkinson/csfrace-scrape" \
      org.opencontainers.image.vendor="CSFrace Development Team" \
      org.opencontainers.image.version="1.3.0"