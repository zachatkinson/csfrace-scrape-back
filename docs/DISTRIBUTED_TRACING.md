# OpenTelemetry Distributed Tracing Guide

This guide explains how to use the enhanced observability system with OpenTelemetry distributed tracing in the CSFrace Scraper backend.

## Overview

The distributed tracing system provides:

- **OpenTelemetry-compliant distributed tracing** for industry-standard observability
- **Automatic instrumentation** for FastAPI, aiohttp, and SQLAlchemy
- **Custom tracing utilities** for easy integration in any function
- **Correlation ID tracking** across distributed requests
- **Integration** with existing metrics and monitoring infrastructure

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App  │───▶│ Enhanced Tracing │───▶│  OpenTelemetry  │
│                │    │   Middleware     │    │     SDK         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     Jaeger      │◀───│ OTLP Collector  │◀───│   Exporters     │
│   (Tracing UI)  │    │   (Optional)     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Quick Start

### 1. Install Dependencies

The tracing dependencies are included in the `monitoring` extras:

```bash
# Install with monitoring dependencies
uv sync --extra monitoring

# Or install specific tracing packages
uv add opentelemetry-api opentelemetry-sdk
uv add opentelemetry-exporter-otlp
uv add opentelemetry-instrumentation-fastapi
uv add opentelemetry-instrumentation-aiohttp-client
uv add opentelemetry-instrumentation-sqlalchemy
```

### 2. Basic Configuration

```python
from src.monitoring import TracingConfig, distributed_tracer

# Configure tracing
config = TracingConfig(
    enabled=True,
    service_name="my-service",
    service_version="1.0.0",
    environment="production",
    sampling_rate=1.0,  # Trace all requests
    export_to_console=True,  # For development
    export_to_otlp=True,     # For production
    otlp_endpoint="http://localhost:4317"
)

# Initialize
distributed_tracer.config = config
distributed_tracer.initialize()
```

### 3. FastAPI Integration

```python
from fastapi import FastAPI
from src.api.middleware import EnhancedTracingMiddleware

app = FastAPI()

# Add tracing middleware
app.add_middleware(
    EnhancedTracingMiddleware,
    correlation_header="X-Correlation-ID"
)
```

## Usage Examples

### Automatic Tracing with Decorators

```python
from src.utils.tracing_utils import trace, trace_database_operation

@trace("process_user_data", attributes={"component": "user_service"})
async def process_user_data(user_id: str) -> dict:
    # Function automatically traced
    return await fetch_user_data(user_id)

@trace_database_operation("users", "select")
async def fetch_user_data(user_id: str) -> dict:
    # Database operation automatically tagged
    result = await db.query("SELECT * FROM users WHERE id = ?", user_id)
    return result
```

### Manual Span Management

```python
from src.utils.tracing_utils import TraceContextManager

async def complex_operation():
    async with TraceContextManager("data_processing", {"batch_size": 100}) as span:
        # Process data
        data = await fetch_data()
        
        # Add custom attributes and events
        span.set_attribute("records_processed", len(data))
        span.add_event("processing_completed")
        
        return processed_data
```

### Adding Context to Existing Spans

```python
from src.utils.tracing_utils import add_trace_event, set_trace_attribute

async def api_endpoint():
    # Add events during execution
    add_trace_event("validation_started")
    
    # Validate input
    if not valid_input:
        set_trace_attribute("error.type", "validation_failed")
        add_trace_event("validation_failed", {"reason": "missing_required_field"})
        raise ValueError("Invalid input")
    
    add_trace_event("validation_passed")
    set_trace_attribute("user.role", user.role)
    
    return process_request()
```

### HTTP Request Tracing

```python
from src.utils.tracing_utils import trace_http_request

@trace_http_request("GET", "https://api.external.com")
async def call_external_api():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.external.com/data") as response:
            return await response.json()
```

## Configuration Options

### TracingConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `True` | Enable/disable tracing |
| `service_name` | str | `"csfrace-scraper"` | Service name in traces |
| `service_version` | str | `"2.2.2"` | Service version |
| `environment` | str | `"production"` | Environment (prod/staging/dev) |
| `sampling_rate` | float | `1.0` | Trace sampling rate (0.0-1.0) |
| `export_to_console` | bool | `False` | Export traces to console |
| `export_to_otlp` | bool | `False` | Export to OTLP collector |
| `otlp_endpoint` | str | `"http://localhost:4317"` | OTLP endpoint URL |
| `instrument_fastapi` | bool | `True` | Auto-instrument FastAPI |
| `instrument_aiohttp` | bool | `True` | Auto-instrument aiohttp |
| `instrument_sqlalchemy` | bool | `True` | Auto-instrument SQLAlchemy |

### Environment Variables

Set these environment variables to configure tracing:

```bash
# Basic configuration
TRACING_ENABLED=true
TRACING_SERVICE_NAME=csfrace-scraper
TRACING_ENVIRONMENT=production
TRACING_SAMPLING_RATE=1.0

# Export configuration
TRACING_EXPORT_TO_CONSOLE=false
TRACING_EXPORT_TO_OTLP=true
TRACING_OTLP_ENDPOINT=http://otel-collector:4317

# Auto-instrumentation
TRACING_INSTRUMENT_FASTAPI=true
TRACING_INSTRUMENT_AIOHTTP=true
TRACING_INSTRUMENT_SQLALCHEMY=true
```

## Deployment with Docker

### Basic Setup (Jaeger Only)

```bash
# Start Jaeger for trace visualization
docker run -d \
  --name jaeger \
  -p 16686:16686 \
  -p 14268:14268 \
  jaegertracing/all-in-one:latest

# Configure your app to export to Jaeger
export TRACING_OTLP_ENDPOINT=http://localhost:14268/api/traces
```

### Advanced Setup (with OpenTelemetry Collector)

```bash
# Start the full tracing stack
docker compose -f docker-compose.yml \
               -f docker-compose.monitoring.yml \
               -f docker-compose.tracing.yml up -d

# Access Jaeger UI
open http://localhost:16686

# Check OpenTelemetry Collector health
curl http://localhost:13133
```

## Observability Integration

The tracing system integrates with existing monitoring:

```python
from src.monitoring import observability_manager

# Get complete system overview including tracing
overview = observability_manager.get_system_overview()
print(overview["tracing"])  # Tracing-specific status

# Get detailed component status
components = observability_manager.get_component_status()
print(components["distributed_tracer"])  # Tracer status
```

## Best Practices

### 1. Meaningful Operation Names

```python
# Good - specific and descriptive
@trace("scrape_wordpress_post")
async def scrape_post(url: str): ...

@trace("validate_oauth_token")
def validate_token(token: str): ...

# Avoid - too generic
@trace("process_data")
async def process(data): ...
```

### 2. Appropriate Attributes

```python
# Good - relevant business context
@trace("user_authentication", attributes={
    "auth.method": "oauth2",
    "auth.provider": "google",
    "user.role": user.role
})

# Avoid - sensitive information
@trace("user_login", attributes={
    "password": password,  # Never include secrets!
    "token": auth_token    # Don't log tokens!
})
```

### 3. Correlation IDs

```python
# Correlation IDs are automatically managed by middleware
# Access current correlation in logs:
from src.utils.tracing_utils import get_current_trace_context

context = get_current_trace_context()
logger.info("Processing request", **context)
```

### 4. Sampling in Production

```python
# For high-traffic services, use sampling
config = TracingConfig(
    sampling_rate=0.1,  # Trace 10% of requests
    # Critical operations can force sampling
)

# Or use head-based sampling for specific operations
@trace("critical_operation", attributes={"force_sample": True})
async def critical_func(): ...
```

### 5. Error Handling

```python
@trace("risky_operation")
async def risky_operation():
    try:
        return await external_call()
    except ExternalServiceError as e:
        # Errors are automatically recorded in spans
        set_trace_attribute("error.category", "external_service")
        set_trace_attribute("error.recoverable", True)
        
        # Add recovery context
        add_trace_event("attempting_retry", {"attempt": 1})
        return await retry_external_call()
```

## Troubleshooting

### Common Issues

1. **Traces not appearing**:
   ```python
   # Check if tracing is enabled and initialized
   from src.monitoring import distributed_tracer
   status = distributed_tracer.get_tracing_status()
   print(status["initialized"])  # Should be True
   ```

2. **Missing auto-instrumentation**:
   ```python
   # Ensure instrumentation is enabled in config
   config.instrument_fastapi = True
   config.instrument_aiohttp = True
   config.instrument_sqlalchemy = True
   ```

3. **OTLP export failures**:
   ```bash
   # Check collector endpoint
   curl http://localhost:4317/v1/traces -v
   
   # Check collector logs
   docker logs otel-collector
   ```

### Debug Configuration

```python
# Enable debug logging for tracing
config = TracingConfig(
    export_to_console=True,  # See traces in console
    # ... other settings
)

# Or check tracing status programmatically
status = distributed_tracer.get_tracing_status()
print(f"Tracing initialized: {status['initialized']}")
print(f"Current trace: {status['current_trace_id']}")
```

## Performance Considerations

- **Sampling**: Use appropriate sampling rates for production
- **Attribute limits**: OpenTelemetry has limits on attribute count/size
- **Batch export**: Traces are batched automatically for efficiency
- **Memory usage**: High-frequency tracing can impact memory usage

## Integration with Existing Code

The tracing system is designed to integrate seamlessly:

```python
# Existing functions work unchanged
async def existing_function(data):
    return process_data(data)

# Add tracing with minimal changes
@trace("data_processing")
async def existing_function(data):
    return process_data(data)

# Or use context manager for partial tracing
async def existing_function(data):
    # Existing code...
    
    async with TraceContextManager("critical_section"):
        result = await critical_processing(data)
    
    # More existing code...
    return result
```

For more examples, see `docs/examples/tracing_integration_example.py`.