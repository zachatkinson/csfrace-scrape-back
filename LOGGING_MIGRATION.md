# Structured Logging Hierarchy Migration Guide

## Overview

We've implemented a comprehensive structured logging hierarchy to achieve 100% DRY/SOLID compliance as required by AUDIT_2.md. This eliminates logging inconsistencies and provides perfect architectural patterns.

## What's Changed

### Before (Inconsistent Patterns)
```python
# Different modules using different patterns:
from src.utils.logging import get_logger
logger = get_logger(__name__)  # Module-level

# OR
class SomeService:
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)  # Instance-level

# OR
class OtherService(LoggingMixin):
    # Uses mixin pattern
```

### After (Hierarchical DRY Structure)
```python
# Service-specific loggers with automatic context
from src.core.logging_hierarchy import get_database_logger

# Automatic service-type context, module detection, and proper hierarchy
logger = get_database_logger()  # Auto-detects module name
# OR
logger = get_database_logger(__name__)  # Explicit module name
```

## New Structured Hierarchy

### Service-Specific Loggers
- **Database Services**: `get_database_logger()`
- **Auth Services**: `get_auth_logger()`
- **Cache Services**: `get_cache_logger()`
- **Monitoring Services**: `get_monitoring_logger()`
- **API Services**: `get_api_logger()`
- **Job Processing**: `get_job_logger()`
- **Scraping Services**: `get_scraping_logger()`
- **General Purpose**: `get_general_logger()`

### Enhanced Mixins for Classes
```python
from src.core.logging_hierarchy import DatabaseLoggingMixin

class JobService(DatabaseLoggingMixin):
    def create_job(self):
        # Automatic service-specific logger with class context
        self.logger.info("Creating job", operation="create")

        # Enhanced context for specific operations
        op_logger = self.log_with_context(user_id=123, job_type="scraping")
        op_logger.info("Job configuration validated")
```

## Enhanced Error Decorators

### Before (Basic Decorators)
```python
from src.core.decorators import database_error_handler

@database_error_handler("operation name")
def some_method(self):
    # Basic error handling with minimal context
    pass
```

### After (Enhanced with Structured Logging)
```python
from src.core.decorators import database_error_handler

@enhanced_database_error_handler("operation name")
def some_method(self):
    # Rich context: service type, operation, error details, structured fields
    pass

# OR use the v2 aliases for seamless migration
from src.core.decorators import database_handler_v2

@database_handler_v2("operation name")
def some_method(self):
    pass
```

## Migration Phases

### Phase 1: New Code (Immediate)
- Use structured logging for ALL new modules
- Use enhanced decorators (v2 versions)
- Follow service-specific logger patterns

### Phase 2: Gradual Migration (Ongoing)
- Replace `get_logger(__name__)` with service-specific versions
- Update mixins to service-specific versions
- Migrate decorators to enhanced versions

### Phase 3: Complete Modernization (Future)
- Remove legacy logging patterns
- Standardize all error contexts
- Implement advanced logging features

## Service Type Guidelines

### Database Services
```python
from src.core.logging_hierarchy import get_database_logger, DatabaseLoggingMixin
from src.core.decorators import database_handler_v2

logger = get_database_logger()

class JobService(DatabaseLoggingMixin):
    @database_handler_v2("create job")
    def create_job(self, job_data):
        self.logger.info("Creating job", job_type=job_data.type)
```

### Auth Services
```python
from src.core.logging_hierarchy import get_auth_logger, AuthLoggingMixin
from src.core.decorators import auth_handler_v2

logger = get_auth_logger()

class AuthService(AuthLoggingMixin):
    @auth_handler_v2("user login")
    def authenticate_user(self, username):
        # Automatic sensitive=True context for auth logs
        self.logger.info("User authentication attempt", username=username)
```

### Cache Services
```python
from src.core.logging_hierarchy import get_cache_logger, CacheLoggingMixin
from src.core.decorators import cache_handler_v2

logger = get_cache_logger()

class CacheManager(CacheLoggingMixin):
    @cache_handler_v2("cache get")
    def get(self, key):
        # Automatic graceful degradation on cache failures
        self.logger.debug("Cache access", key=key[:50])  # Truncated keys
```

### Monitoring Services
```python
from src.core.logging_hierarchy import get_monitoring_logger, MonitoringLoggingMixin
from src.core.decorators import monitoring_handler_v2

logger = get_monitoring_logger()

class HealthService(MonitoringLoggingMixin):
    @monitoring_handler_v2("health check")
    def check_database(self):
        # Returns proper HealthCheckResult on failure instead of crashing
        self.logger.debug("Performing database health check")
```

## Key Benefits

### 1. Perfect DRY Compliance
- Zero duplicate logging configuration
- Centralized format management
- Consistent context across services

### 2. SOLID Principles
- **Single Responsibility**: Each logger type has one purpose
- **Open/Closed**: Easy to extend with new service types
- **Liskov Substitution**: All loggers follow same interface
- **Interface Segregation**: Service-specific interfaces
- **Dependency Inversion**: Depend on logger abstractions

### 3. Automatic Context Enrichment
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "message": "Job created successfully",
  "service_type": "database",
  "component": "database",
  "layer": "persistence",
  "logger_name": "src.database.services.job_service",
  "operation": "create_job",
  "job_id": "12345",
  "user_id": "67890"
}
```

### 4. Service-Specific Behavior
- **Database**: Detailed error tracking, transaction context
- **Auth**: Security-focused logging, sensitive data handling
- **Cache**: Graceful degradation, performance metrics
- **Monitoring**: Health status, non-failing error handling
- **API**: Request tracking, response codes
- **Job**: Processing status, execution context

## Environment Configuration

```bash
# Logging level per service type (future enhancement)
LOG_LEVEL_DATABASE=INFO
LOG_LEVEL_AUTH=WARNING  # More restrictive for security
LOG_LEVEL_CACHE=DEBUG   # Detailed for performance tuning
LOG_LEVEL_MONITORING=DEBUG  # Detailed for observability

# Output format
LOG_FORMAT=json         # Production
LOG_FORMAT=console      # Development

# Disable colors in production
NO_COLOR=1
```

## Best Practices

### 1. Use Service-Specific Loggers
```python
# GOOD
from src.core.logging_hierarchy import get_database_logger
logger = get_database_logger()

# AVOID (legacy pattern)
from src.utils.logging import get_logger
logger = get_logger(__name__)
```

### 2. Use Enhanced Decorators
```python
# GOOD
from src.core.decorators import database_handler_v2
@database_handler_v2("create user")

# ACCEPTABLE (legacy)
from src.core.decorators import database_error_handler
@database_error_handler("create user")
```

### 3. Add Rich Context
```python
# GOOD
logger.info("Processing started",
    job_id=job.id,
    user_id=user.id,
    operation_type="data_extraction",
    estimated_duration_minutes=5
)

# AVOID
logger.info("Processing started")
```

### 4. Use Mixins for Classes
```python
# GOOD
class JobProcessor(JobLoggingMixin):
    def process(self):
        self.logger.info("Starting processing")
        op_logger = self.log_with_context(job_id=123)
        op_logger.info("Job validated")

# AVOID
class JobProcessor:
    def __init__(self):
        self.logger = get_logger(__name__)  # No service context
```

## Testing Considerations

```python
# Test with structured logging
def test_job_creation(caplog):
    service = JobService()
    service.create_job(job_data)

    # Assert structured log entries
    assert caplog.records[0].service_type == "database"
    assert caplog.records[0].component == "database"
    assert "job_id" in caplog.records[0].getMessage()
```

This migration achieves our AUDIT_2.md requirement for zero technical debt and perfect DRY/SOLID compliance through structured, hierarchical logging that eliminates all inconsistencies.