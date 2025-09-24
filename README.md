# CSFrace Scraper Backend

[![CI/CD Pipeline](https://github.com/zachatkinson/csfrace-scrape-back/actions/workflows/ci.yml/badge.svg)](https://github.com/zachatkinson/csfrace-scrape-back/actions)
[![Semantic Release](https://img.shields.io/github/v/release/zachatkinson/csfrace-scrape-back?label=release&logo=semantic-release)](https://github.com/zachatkinson/csfrace-scrape-back/releases)
[![Code Coverage](https://codecov.io/gh/zachatkinson/csfrace-scrape-back/branch/master/graph/badge.svg)](https://codecov.io/gh/zachatkinson/csfrace-scrape-back)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> A high-performance, enterprise-grade backend API for converting WordPress content to Shopify-compatible formats with real-time processing, authentication, and comprehensive monitoring.

## 🚀 Features

### Core Functionality
- **🔄 Async Content Conversion** - WordPress to Shopify HTML conversion with modern async/await patterns
- **⚡ Batch Processing** - Handle multiple URLs concurrently with intelligent rate limiting
- **🖼️ Image Processing** - Automatic image downloading, optimization, and metadata extraction
- **🛡️ Content Sanitization** - XSS protection and HTML sanitization for secure output
- **📊 Real-time Monitoring** - Job progress tracking via Server-Sent Events (SSE)

### Enterprise Features
- **🔐 Multi-factor Authentication** - JWT, OAuth2, and WebAuthn/FIDO2 support
- **📈 Observability** - Prometheus metrics, OpenTelemetry tracing, and Grafana dashboards
- **🗄️ Robust Database Layer** - PostgreSQL with SQLAlchemy 2.0 and async operations
- **⚡ Redis Caching** - Multi-tier caching with intelligent invalidation
- **🐳 Production Ready** - Docker containers, health checks, and graceful shutdowns

### Developer Experience
- **📚 Auto-generated API Docs** - FastAPI with OpenAPI/Swagger documentation
- **🧪 Comprehensive Testing** - 80%+ coverage with unit, integration, and performance tests
- **🔧 Modern Tooling** - UV package manager, Ruff linting, MyPy type checking
- **🚦 CI/CD Pipeline** - Automated testing, security scanning, and semantic releases

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Configuration](#-configuration)
- [Development](#-development)
- [Docker Deployment](#-docker-deployment)
- [Testing](#-testing)
- [Monitoring](#-monitoring)
- [Contributing](#-contributing)

## ⚡ Quick Start

### Prerequisites
- **Python 3.13+** (recommended via [pyenv](https://github.com/pyenv/pyenv))
- **PostgreSQL 17.6+** (or via Docker)
- **Redis 7+** (optional, for enhanced performance)

### 1-Minute Setup
```bash
# Clone and setup
git clone https://github.com/zachatkinson/csfrace-scrape-back.git
cd csfrace-scrape-back

# Install dependencies (using modern UV package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Start database services
docker compose -f docker-compose.dev.yml up -d postgres redis

# Initialize database
uv run alembic upgrade head

# Start the API server
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API documentation.

## 💾 Installation

### Option 1: UV Package Manager (Recommended)
```bash
# Install UV (40% faster than pip)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras

# Development dependencies
uv sync --group dev
```

### Option 2: Traditional pip
```bash
python -m pip install -r requirements/base.txt

# Development setup
python -m pip install -r requirements/dev.txt
```

### Database Setup
```bash
# Using Docker (recommended)
docker compose -f docker-compose.dev.yml up -d postgres redis

# Or install PostgreSQL locally
# macOS: brew install postgresql@17
# Ubuntu: apt-get install postgresql-17

# Run migrations
uv run alembic upgrade head
```

## 🎯 Usage

### CLI Interface
```bash
# Convert single WordPress URL
uv run python -m src.main https://csfrace.com/article-slug

# Batch processing from file
echo "https://csfrace.com/post1\nhttps://csfrace.com/post2" > urls.txt
uv run python -m src.main --urls-file urls.txt --batch-size 5

# Interactive mode with configuration
uv run python -m src.main --config config/production.yaml --interactive
```

### API Server
```bash
# Development server with hot reload
uv run uvicorn src.api.main:app --reload --port 8000

# Production server with Gunicorn
uv run gunicorn src.api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Basic API Usage
```python
import httpx

async with httpx.AsyncClient() as client:
    # Create conversion job
    response = await client.post(
        "http://localhost:8000/jobs",
        json={
            "url": "https://csfrace.com/article-slug",
            "options": {
                "format": "shopify",
                "download_images": True,
                "sanitize_html": True
            }
        }
    )
    job = response.json()

    # Monitor job progress
    job_id = job["id"]
    status = await client.get(f"http://localhost:8000/jobs/{job_id}")

    # Check job completion
    if status.json()["status"] == "completed":
        print("Job completed successfully!")
        # Results are available in the job response data
```

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs` | POST | Create new conversion job |
| `/jobs/{job_id}` | GET | Get job status and details |
| `/jobs/{job_id}/start` | POST | Start a pending job |
| `/jobs/{job_id}/cancel` | POST | Cancel a running job |
| `/jobs/stream` | GET | Real-time job progress via SSE |
| `/auth/token` | POST | User authentication (login) |
| `/auth/register` | POST | User registration |
| `/auth/refresh` | POST | Refresh JWT token |
| `/user/settings` | GET/PUT | User settings management |
| `/health` | GET | Health check and system status |
| `/health/ready` | GET | Readiness check |
| `/health/live` | GET | Liveness check |
| `/metrics` | GET | Prometheus metrics |

### Authentication
```bash
# Register new user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure_password"}'

# Login and get JWT token
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=user@example.com&password=secure_password'

# Use token for authenticated requests
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://localhost:8000/jobs"
```

## ⚙️ Configuration

### Environment Variables
```bash
# Core application settings
ENVIRONMENT=development|staging|production
LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
API_HOST=0.0.0.0
API_PORT=8000

# Database configuration
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/csfrace_dev
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis configuration (optional)
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20

# Security settings
JWT_SECRET_KEY=your-super-secure-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=["http://localhost:3000","http://localhost:4321"]

# Scraping settings
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Monitoring settings
PROMETHEUS_METRICS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
OPENTELEMETRY_SERVICE_NAME=csfrace-scraper-backend
```

### Configuration Files
```yaml
# config/development.yaml
api:
  host: "0.0.0.0"
  port: 8000
  debug: true

database:
  url: "postgresql+asyncpg://postgres:postgres@localhost:5432/csfrace_dev"
  echo_sql: true

scraper:
  max_concurrent: 5
  timeout: 30
  user_agent: "CSFrace-Scraper-Dev/1.0"

monitoring:
  prometheus_enabled: true
  log_level: "DEBUG"
```

## 🛠️ Development

### Development Setup
```bash
# Clone repository
git clone https://github.com/zachatkinson/csfrace-scrape-back.git
cd csfrace-scrape-back

# Install development dependencies
uv sync --group dev

# Setup pre-commit hooks
pre-commit install

# Start development services
docker compose -f docker-compose.dev.yml up -d

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn src.api.main:app --reload
```

### Code Quality Tools
```bash
# Format code with Ruff
uv run ruff format src/ tests/

# Lint code
uv run ruff check src/ tests/ --fix

# Type checking with MyPy
uv run mypy src/

# Security scanning
uv run bandit -r src/

# Dependency vulnerability check
uv run safety check
```

### Database Operations
```bash
# Create new migration
uv run alembic revision --autogenerate -m "Add new feature"

# Apply migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

## 🐳 Docker Deployment

### Development Environment
```bash
# Start all services including database
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose logs -f backend

# Run commands in container
docker compose exec backend uv run alembic upgrade head
```

### Production Deployment
```bash
# Build production image
docker build -t csfrace-scraper-backend:latest .

# Run with production settings
docker run -d \
  --name csfrace-backend \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DATABASE_URL=postgresql://... \
  csfrace-scraper-backend:latest
```

### Docker Compose Production
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=html --cov-report=term

# Run specific test categories
uv run pytest tests/unit/     # Unit tests only
uv run pytest tests/integration/  # Integration tests
uv run pytest -m "not slow"  # Skip slow tests

# Run tests in parallel
uv run pytest -n auto
```

### Test Structure
```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # API endpoint and database tests
├── performance/    # Load and performance tests
├── fixtures/       # Test data and factories
└── conftest.py     # Shared test configuration
```

### Writing Tests
```python
# Example unit test
@pytest.mark.asyncio
async def test_wordpress_converter():
    converter = WordPressConverter()
    result = await converter.convert("https://example.com/post")
    assert result.status == "success"
    assert "converted_html" in result.data

# Example integration test
@pytest.mark.asyncio
async def test_create_job_endpoint(client: AsyncClient):
    response = await client.post("/jobs", json={
        "url": "https://test.com/post",
        "options": {"format": "shopify"}
    })
    assert response.status_code == 201
    assert "id" in response.json()
```

## 📊 Monitoring

### Health Checks
```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health status
curl http://localhost:8000/health/detailed

# Database connectivity check
curl http://localhost:8000/health/db
```

### Prometheus Metrics
```bash
# View all metrics
curl http://localhost:8000/metrics

# Key metrics include:
# - http_requests_total
# - http_request_duration_seconds
# - active_jobs_gauge
# - database_connections_active
# - redis_cache_hits_total
```

### Grafana Dashboards
1. Start monitoring stack: `docker compose -f docker-compose.monitoring.yml up -d`
2. Access Grafana: [http://localhost:3000](http://localhost:3000) (admin/admin)
3. Import dashboards from `monitoring/dashboards/`

### Logging
```python
# Structured logging example
import structlog

logger = structlog.get_logger(__name__)

# Logs with context
logger.info("Processing job",
           job_id=job.id,
           url=job.url,
           user_id=user.id)

# Error logging with traceback
try:
    await process_content(url)
except Exception as e:
    logger.error("Content processing failed",
                url=url,
                error=str(e),
                exc_info=True)
```

## 🏗️ Architecture

### System Overview
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │────│   FastAPI API    │────│   PostgreSQL    │
│   (External)    │    │   (This Repo)    │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                       ┌──────────────────┐              │
                       │   Redis Cache    │──────────────┘
                       │   (Optional)     │
                       └──────────────────┘
                                │
                   ┌─────────────────────────┐
                   │  Monitoring Stack       │
                   │  (Grafana + Prometheus) │
                   └─────────────────────────┘
```

### Core Components
- **`src/api/`** - FastAPI application with routes and middleware
- **`src/core/`** - Business logic and content conversion engine
- **`src/auth/`** - Authentication and authorization system
- **`src/database/`** - SQLAlchemy models and database operations
- **`src/processors/`** - Content processing and image handling
- **`src/monitoring/`** - Metrics collection and health checks
- **`src/caching/`** - Multi-tier caching implementation
- **`src/utils/`** - Shared utilities and helpers

### Database Schema
```sql
-- Core job tracking
CREATE TABLE scraping_jobs (
    id UUID PRIMARY KEY,
    url VARCHAR NOT NULL,
    status job_status DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    user_id UUID REFERENCES users(id),
    options JSONB,
    metadata JSONB
);

-- Processed content storage
CREATE TABLE content_results (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES scraping_jobs(id),
    original_html TEXT,
    converted_html TEXT,
    extracted_images JSONB,
    metadata JSONB
);

-- User management
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🚢 Deployment

### Production Checklist
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] SSL/TLS certificates installed
- [ ] Health checks configured
- [ ] Monitoring and alerting setup
- [ ] Backup strategy implemented
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] Log aggregation configured

### Performance Optimization
- **Database**: Connection pooling, query optimization, proper indexing
- **Caching**: Redis for session data and frequently accessed content
- **HTTP**: Connection reuse, compression, CDN for static assets
- **Async**: Non-blocking I/O for all database and HTTP operations
- **Monitoring**: Real-time metrics and alerts for performance issues

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Workflow
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: `uv sync --group dev`
4. Make your changes and add tests
5. Run quality checks: `pre-commit run --all-files`
6. Ensure all tests pass: `uv run pytest --cov=src`
7. Submit a pull request

### Code Standards
- Follow [CLAUDE.md](./CLAUDE.md) coding standards
- Maintain 80%+ test coverage
- Use type hints for all functions
- Write comprehensive docstrings
- Follow semantic commit messages

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- **[CSFrace Scraper Frontend](https://github.com/zachatkinson/csfrace-scrape-front)** - Modern Astro/React frontend interface
- **[CSFrace Scraper](https://github.com/zachatkinson/csfrace-scrape)** - Main orchestration repository with Docker Compose

## 📞 Support

- 📖 [Documentation](https://github.com/zachatkinson/csfrace-scrape-back/wiki)
- 🐛 [Bug Reports](https://github.com/zachatkinson/csfrace-scrape-back/issues)
- 💬 [Discussions](https://github.com/zachatkinson/csfrace-scrape-back/discussions)
- 📧 [Email Support](mailto:support@csfrace.com)

---

<div align="center">

**CSFrace Scraper Backend** - Enterprise-grade WordPress to Shopify content conversion

Made with ❤️ using FastAPI, Python 3.13, and modern async patterns

</div>