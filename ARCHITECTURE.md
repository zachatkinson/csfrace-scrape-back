# CSFrace Backend Architecture

## 🏗️ Architecture Overview

The CSFrace backend follows a **modular, domain-driven architecture** with clear separation of concerns and SOLID principles.

```
src/
├── api/              # FastAPI endpoints and routing
│   ├── routers/      # Feature-specific route modules
│   ├── errors.py     # Centralized error handling
│   └── dependencies.py # FastAPI dependencies
├── auth/             # Authentication & authorization
├── config/           # Centralized configuration
├── core/             # Core utilities and patterns
│   ├── container.py  # Dependency injection
│   ├── exceptions.py # Base exceptions
│   └── services.py   # Service interfaces
├── database/         # Data layer
│   ├── models/       # Domain-specific models
│   └── services/     # Data access services
├── monitoring/       # Health checks & observability
│   └── health_checks/ # Pluggable health checks
└── utils/            # Shared utilities
    └── logging.py    # Centralized logging
```

## 🎯 Key Architectural Principles

### 1. **Single Responsibility Principle**
Each module has one clear purpose:
- `auth/` → Authentication & user management
- `database/services/job_service.py` → Job operations only
- `utils/logging.py` → Logging configuration only

### 2. **Dependency Injection**
Services are loosely coupled through DI container:
```python
from src.core.container import DependencyContainer

container = DependencyContainer()
container.register_singleton(IJobService, JobService)
```

### 3. **Domain-Driven Design**
Models organized by business domain:
- `models/auth.py` → User, LinkedAccount, WebAuthn
- `models/jobs.py` → ScrapingJob, ContentResult, JobLog

## 🔧 Core Components

### Configuration System
```python
from src.config import get_settings

settings = get_settings()  # Auto-loads from environment
```

### Centralized Logging
```python
from src.utils.logging import get_logger

logger = get_logger(__name__)
logger.info("Structured logging", key="value")
```

### Error Handling
```python
from src.api.errors import APIErrorFactory

raise APIErrorFactory.bad_request("Invalid input")
```

### Health Checks
```python
from src.monitoring.health_checks import health_registry

await health_registry.run_all_checks()
```

## 🔄 Data Flow

```
Request → FastAPI Router → Service Layer → Database Layer → Response
             ↓              ↓              ↓
         Error Handler → DI Container → Health Checks
```

## 📊 Service Architecture

### Service Layer Pattern
```python
# Interface
class IJobService(ABC):
    async def create_job(self, data: JobData) -> Job: ...

# Implementation  
class JobService(IJobService):
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create_job(self, data: JobData) -> Job:
        # Implementation here
```

### Repository Pattern
```python
class JobRepository:
    async def save(self, job: Job) -> Job: ...
    async def find_by_id(self, job_id: str) -> Job | None: ...
```

## 🔐 Security Architecture

- **Authentication:** JWT tokens with refresh mechanism
- **Authorization:** Role-based access control
- **Input Validation:** Pydantic models throughout
- **Error Sanitization:** No sensitive data in error responses

## 📈 Monitoring & Observability

- **Health Checks:** Modular system with database, API, cache checks
- **Structured Logging:** JSON logging with correlation IDs
- **Metrics:** Prometheus-compatible metrics export
- **Tracing:** OpenTelemetry integration ready

## 🚀 Deployment Considerations

### Environment Configuration
All configuration via environment variables:
- `DATABASE_URL` → Database connection
- `LOG_LEVEL` → Logging verbosity  
- `JWT_SECRET` → Authentication secret

### Docker Support
```dockerfile
# Multi-stage build with health checks
HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8000/health
```

---

*This architecture supports high scalability, maintainability, and testability while following industry best practices.*