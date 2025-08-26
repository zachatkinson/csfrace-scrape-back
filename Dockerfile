# Multi-stage Dockerfile for production deployment using UV

#########################
# Build stage
#########################
FROM python:3.13-slim as builder

# Install UV from official image (production best practice)
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/

# Set environment variables for UV and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/.uv-cache

# Install system dependencies for building (including lxml requirements for Python 3.13)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    pkg-config \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /build

# Copy dependency files for optimal layer caching
COPY uv.lock pyproject.toml ./

# Install dependencies (system Python, no venv overhead)
RUN --mount=type=cache,target=/tmp/.uv-cache \
    uv sync --frozen --no-editable --no-dev

#########################
# Production stage
#########################
FROM python:3.13-slim as production

# Copy UV binary from builder
COPY --from=builder /uv /uvx /bin/

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src:$PYTHONPATH" \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install runtime dependencies and apply security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

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

# Health check using uv
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD uv run python -c "import sys; sys.exit(0)" || exit 1

# Switch to non-root user
USER scraper

# Expose port (if running API mode)
EXPOSE 8000

# Set entrypoint using uv
ENTRYPOINT ["uv", "run", "python", "-m", "src.main"]

# Default command
CMD ["--help"]

# Labels for metadata
LABEL org.opencontainers.image.title="CSFrace Scraper" \
      org.opencontainers.image.description="WordPress to Shopify content converter" \
      org.opencontainers.image.source="https://github.com/zachatkinson/csfrace-scrape" \
      org.opencontainers.image.vendor="CSFrace Development Team" \
      org.opencontainers.image.version="1.0.0"