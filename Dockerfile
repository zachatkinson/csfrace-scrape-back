# Multi-stage Dockerfile for production deployment

#########################
# Build stage
#########################
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /build

# Copy requirements
COPY requirements/prod.txt ./requirements.txt

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r requirements.txt

#########################
# Production stage
#########################
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src:$PYTHONPATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r scraper && useradd -r -g scraper scraper

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set work directory
WORKDIR /app

# Copy application code
COPY --chown=scraper:scraper . .

# Create necessary directories
RUN mkdir -p /app/output /app/logs && \
    chown -R scraper:scraper /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Switch to non-root user
USER scraper

# Expose port (if running API mode)
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["python", "-m", "src.main"]

# Default command
CMD ["--help"]

# Labels for metadata
LABEL org.opencontainers.image.title="CSFrace Scraper" \
      org.opencontainers.image.description="WordPress to Shopify content converter" \
      org.opencontainers.image.source="https://github.com/zachatkinson/csfrace-scrape" \
      org.opencontainers.image.vendor="CSFrace Development Team" \
      org.opencontainers.image.version="1.0.0"