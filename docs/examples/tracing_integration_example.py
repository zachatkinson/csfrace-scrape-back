"""Example of integrating OpenTelemetry distributed tracing with FastAPI application.

This example shows how to properly initialize and use the enhanced observability
system with distributed tracing in a FastAPI application.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.requests import Request

# Import monitoring components
from src.api.middleware import EnhancedTracingMiddleware
from src.monitoring import (
    ObservabilityConfig, 
    ObservabilityManager,
    TracingConfig,
    observability_manager,
)
from src.utils.tracing_utils import (
    trace,
    trace_database_operation,
    trace_http_request,
    add_trace_event,
    set_trace_attribute,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan for observability system initialization."""
    # Configure enhanced observability with distributed tracing
    observability_config = ObservabilityConfig(
        enabled=True,
        startup_health_check=True,
        enable_correlation_ids=True,
        tracing_config=TracingConfig(
            enabled=True,
            service_name="csfrace-scraper-api",
            service_version="2.2.2",
            environment="production",  # or get from env
            sampling_rate=1.0,  # Trace all requests
            export_to_console=False,
            export_to_otlp=True,
            otlp_endpoint="http://otel-collector:4317",
            instrument_fastapi=True,
            instrument_aiohttp=True,
            instrument_sqlalchemy=True,
        ),
    )

    # Initialize observability system
    global_observability = ObservabilityManager(observability_config)
    
    try:
        await global_observability.initialize()
        print("✅ Observability system initialized successfully")
        yield
    finally:
        await global_observability.shutdown()
        print("📊 Observability system shutdown complete")


# Create FastAPI app with observability lifespan
app = FastAPI(
    title="CSFrace Scraper API",
    version="2.2.2",
    lifespan=lifespan
)

# Add enhanced tracing middleware
app.add_middleware(
    EnhancedTracingMiddleware,
    correlation_header="X-Correlation-ID"
)


# Example endpoints demonstrating tracing usage


@app.get("/")
async def root():
    """Root endpoint with automatic tracing."""
    add_trace_event("root_endpoint_accessed")
    return {"message": "CSFrace Scraper API", "version": "2.2.2"}


@app.get("/health")
async def health_check():
    """Health check endpoint - typically filtered from traces."""
    return {"status": "healthy", "service": "csfrace-scraper"}


@trace("scrape_wordpress_content", attributes={"component": "scraper"})
@app.post("/scrape")
async def scrape_content(request: dict):
    """Example endpoint with custom tracing."""
    url = request.get("url")
    if not url:
        set_trace_attribute("error.type", "validation_error")
        raise HTTPException(status_code=400, detail="URL is required")

    # Add custom trace attributes
    set_trace_attribute("scrape.url", url)
    set_trace_attribute("scrape.format", request.get("format", "html"))

    # Simulate scraping process with sub-operations
    result = await perform_scraping(url)
    
    # Add completion event
    add_trace_event("scraping_completed", {
        "pages_scraped": result.get("page_count", 0),
        "success": True
    })

    return result


@trace_http_request("GET", "external_api")
async def fetch_external_data(url: str) -> dict:
    """Example function with HTTP request tracing."""
    # Simulate external API call
    await asyncio.sleep(0.1)  # Simulate network delay
    
    add_trace_event("external_api_response_received")
    return {"data": "external_content", "source": url}


@trace_database_operation("content", "insert")
async def save_scraped_content(content: dict) -> bool:
    """Example function with database operation tracing."""
    # Simulate database save
    add_trace_event("content_validation_started")
    
    if not content.get("title"):
        set_trace_attribute("validation.error", "missing_title")
        add_trace_event("validation_failed", {"reason": "missing_title"})
        return False

    # Simulate database insertion
    await asyncio.sleep(0.05)
    
    set_trace_attribute("db.record_id", "12345")
    add_trace_event("content_saved_successfully")
    
    return True


async def perform_scraping(url: str) -> dict:
    """Example complex operation with multiple traced sub-operations."""
    # This will be part of the parent "scrape_wordpress_content" trace
    
    # Step 1: Fetch external data
    external_data = await fetch_external_data(url)
    set_trace_attribute("external_data.size", len(str(external_data)))
    
    # Step 2: Process content
    processed_content = {
        "title": "Example Article",
        "content": "Processed content here",
        "url": url,
        "external_refs": external_data,
    }
    
    add_trace_event("content_processed", {
        "word_count": len(processed_content["content"].split()),
        "has_external_refs": bool(external_data)
    })
    
    # Step 3: Save to database
    save_success = await save_scraped_content(processed_content)
    set_trace_attribute("save.success", save_success)
    
    if not save_success:
        set_trace_attribute("error", True)
        add_trace_event("scraping_failed", {"reason": "save_failed"})
        raise HTTPException(status_code=500, detail="Failed to save content")

    return {
        "success": True,
        "page_count": 1,
        "content": processed_content,
        "trace_id": None,  # Will be populated by middleware
    }


@app.get("/observability/status")
async def get_observability_status():
    """Get current observability system status."""
    return observability_manager.get_system_overview()


@app.get("/observability/tracing")
async def get_tracing_status():
    """Get current distributed tracing status."""
    from src.monitoring import distributed_tracer
    return distributed_tracer.get_tracing_status()


@app.get("/observability/metrics")
async def get_metrics():
    """Export Prometheus metrics."""
    from src.monitoring import observability_manager
    metrics_data = observability_manager.export_metrics()
    return {"metrics": metrics_data.decode('utf-8')}


if __name__ == "__main__":
    import uvicorn
    
    # Run with proper configuration for tracing
    uvicorn.run(
        "tracing_integration_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
    )