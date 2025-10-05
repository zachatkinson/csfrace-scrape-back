# CSFrace Scraper Backend

[![CI/CD Pipeline](https://github.com/zachatkinson/csfrace-scrape-back/actions/workflows/ci.yml/badge.svg)](https://github.com/zachatkinson/csfrace-scrape-back/actions)
[![Semantic Release](https://img.shields.io/github/v/release/zachatkinson/csfrace-scrape-back?label=release&logo=semantic-release)](https://github.com/zachatkinson/csfrace-scrape-back/releases)
[![Code Coverage](https://codecov.io/gh/zachatkinson/csfrace-scrape-back/branch/master/graph/badge.svg)](https://codecov.io/gh/zachatkinson/csfrace-scrape-back)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Enterprise-grade FastAPI backend for WordPress to Shopify content conversion with OAuth2 SSO, WebAuthn passwordless authentication, GDPR-compliant data management, and comprehensive observability.

## ✨ Highlights

- 🔐 **Modern Authentication** - OAuth2 (Google, GitHub, Microsoft, Facebook, Apple) + WebAuthn/FIDO2 passkeys
- 🛡️ **GDPR Compliant** - Complete "right to be forgotten" implementation with CASCADE deletion
- ⚡ **High Performance** - Async/await patterns, Redis caching, connection pooling
- 📊 **Full Observability** - Hierarchical logging, Prometheus metrics, OpenTelemetry tracing
- 🐳 **Production Ready** - Docker containers, health checks, graceful shutdowns, zero-downtime deploys

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Authentication](#-authentication)
- [API Documentation](#-api-documentation)
- [Configuration](#️-configuration)
- [Development](#️-development)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Monitoring](#-monitoring)
- [Architecture](#️-architecture)
- [Contributing](#-contributing)

## 🚀 Features

### 🔐 Authentication & Security

- **Multi-Provider OAuth2** - Google, GitHub, Microsoft, Facebook, Apple SSO
- **WebAuthn/FIDO2** - Passwordless authentication with hardware security keys and biometrics
- **HttpOnly Cookies** - Secure session management with CSRF protection (SameSite=Lax)
- **Account Protection** - Automatic lockout after failed login attempts with exponential backoff
- **GDPR Compliance** - Complete user deletion with CASCADE foreign key constraints
- **JWT Tokens** - Refresh token rotation with secure storage
- **Rate Limiting** - Token bucket algorithm for API protection

### ⚡ Content Processing

- **Async WordPress Scraping** - Modern async/await patterns with aiohttp
- **Batch Processing** - Concurrent URL processing with intelligent rate limiting
- **Image Optimization** - Automatic downloading, resizing, and metadata extraction
- **Content Sanitization** - XSS protection and HTML sanitization for secure output
- **Real-time Progress** - Server-Sent Events (SSE) for live job monitoring

### 📊 Observability & Monitoring

- **Hierarchical Logging** - Structured logs with component-based organization (auth, API, database, scraping)
- **Prometheus Metrics** - Request counts, latency percentiles, active connections
- **OpenTelemetry** - Distributed tracing with Jaeger integration
- **Health Checks** - Kubernetes-ready liveness and readiness probes
- **Grafana Dashboards** - Pre-built dashboards for system monitoring

### 🗄️ Database & Caching

- **PostgreSQL 17** - SQLAlchemy 2.0 with async support and connection pooling
- **Alembic Migrations** - Version-controlled schema changes with automatic rollback
- **Redis Caching** - Multi-tier caching with intelligent invalidation
- **CASCADE Deletion** - GDPR-compliant foreign key constraints for data integrity

### 🛠️ Developer Experience

- **Auto-generated Docs** - OpenAPI/Swagger with interactive testing
- **Type Safety** - Full MyPy type checking and Pydantic validation
- **Modern Tooling** - UV package manager (40% faster than pip), Ruff linting
- **Comprehensive Tests** - 85%+ coverage with unit, integration, and E2E tests
- **Pre-commit Hooks** - Automatic code formatting and linting

## ⚡ Quick Start

### Prerequisites

- **Python 3.13+** (recommended via [pyenv](https://github.com/pyenv/pyenv))
- **PostgreSQL 17+** (or via Docker)
- **Redis 7+** (optional, for caching)

### 1-Minute Setup

```bash
# Clone repository
git clone https://github.com/zachatkinson/csfrace-scrape-back.git
cd csfrace-scrape-back

# Install UV package manager (40% faster than pip)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Start database services
docker compose -f docker-compose.dev.yml up -d postgres redis

# Initialize database
uv run alembic upgrade head

# Start API server
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

🎉 **Done!** Visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API documentation.

## 💾 Installation

### Option 1: UV Package Manager (Recommended)

```bash
# Install UV (modern, fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies
uv sync

# Development dependencies
uv sync --group dev

# Testing dependencies
uv sync --group test
```

### Option 2: Traditional pip

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/base.txt

# Development setup
pip install -r requirements/dev.txt
```

### Database Setup

```bash
# Using Docker (recommended for development)
docker compose -f docker-compose.dev.yml up -d postgres redis

# Or install PostgreSQL locally
# macOS: brew install postgresql@17
# Ubuntu: apt-get install postgresql-17

# Run migrations
uv run alembic upgrade head

# Verify database connection
uv run python -c "from src.database.models import create_database_engine; create_database_engine().connect()"
```

## 🔐 Authentication

### OAuth2 Providers

We support 5 OAuth2 providers for Single Sign-On (SSO):

| Provider | Setup Guide | Callback URL |
|----------|-------------|--------------|
| Google | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) | `http://localhost:8000/auth/oauth/google/callback` |
| GitHub | [GitHub OAuth Apps](https://github.com/settings/developers) | `http://localhost:8000/auth/oauth/github/callback` |
| Microsoft | [Azure AD Portal](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps) | `http://localhost:8000/auth/oauth/microsoft/callback` |
| Facebook | [Facebook Developers](https://developers.facebook.com/apps/) | `http://localhost:8000/auth/oauth/facebook/callback` |
| Apple | [Apple Developer Portal](https://developer.apple.com/account/resources/identifiers/list/serviceId) | `http://localhost:8000/auth/oauth/apple/callback` |

### Environment Variables for OAuth

```bash
# Google OAuth
OAUTH_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
OAUTH_GOOGLE_CLIENT_SECRET=your-client-secret

# GitHub OAuth
OAUTH_GITHUB_CLIENT_ID=your-github-client-id
OAUTH_GITHUB_CLIENT_SECRET=your-github-client-secret

# Microsoft OAuth
OAUTH_MICROSOFT_CLIENT_ID=your-microsoft-client-id
OAUTH_MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Facebook OAuth
OAUTH_FACEBOOK_CLIENT_ID=your-facebook-app-id
OAUTH_FACEBOOK_CLIENT_SECRET=your-facebook-app-secret

# Apple OAuth
OAUTH_APPLE_CLIENT_ID=your-apple-service-id
OAUTH_APPLE_CLIENT_SECRET=your-apple-client-secret

# OAuth Configuration
OAUTH_REDIRECT_URI_BASE=http://localhost:8000
FORCE_SECURE_COOKIES=false  # Set to true for HTTPS in development
```

### WebAuthn/FIDO2 Passwordless Authentication

```bash
# WebAuthn Configuration
WEBAUTHN_RP_ID=localhost  # Your domain (e.g., csfrace.com)
WEBAUTHN_RP_NAME=CSFrace Backend
WEBAUTHN_ORIGIN=http://localhost:8000  # Must match your app URL
```

### Authentication Flow Examples

```bash
# Traditional username/password
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=secure_password"

# OAuth2 flow (redirects to provider)
# Visit: http://localhost:8000/auth/oauth/google
# User approves → Redirects to callback → Sets httpOnly cookies

# WebAuthn registration (requires frontend integration)
POST /auth/webauthn/register/begin
POST /auth/webauthn/register/complete

# WebAuthn login
POST /auth/webauthn/login/begin
POST /auth/webauthn/login/complete
```

### GDPR Compliance Features

- **Account Deletion** - Complete user data removal with CASCADE constraints
- **Data Export** - Download all user data in JSON format
- **Audit Logging** - Comprehensive logs for all data operations
- **Cookie Consent** - HttpOnly cookies with SameSite=Lax protection

```bash
# Delete user account (removes ALL associated data)
DELETE /auth/account
# Deletes from 7 tables: users, user_settings, linked_accounts,
# webauthn_credentials, account_lockouts, revoked_tokens, jobs
```

## 📚 API Documentation

### Interactive Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) - Interactive API testing
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc) - Clean documentation
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) - Machine-readable spec

### Core Endpoints

#### 🔐 Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user with email/password |
| `/auth/token` | POST | Login with username/password (returns JWT) |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/logout` | POST | Logout and clear cookies |
| `/auth/account` | DELETE | Delete user account (GDPR) |
| `/auth/oauth/{provider}` | GET | Initiate OAuth2 flow |
| `/auth/oauth/{provider}/callback` | GET | OAuth2 callback handler |
| `/auth/webauthn/register/begin` | POST | Start WebAuthn registration |
| `/auth/webauthn/register/complete` | POST | Complete WebAuthn registration |
| `/auth/webauthn/login/begin` | POST | Start WebAuthn login |
| `/auth/webauthn/login/complete` | POST | Complete WebAuthn login |

#### 📄 Jobs & Content

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs` | POST | Create new scraping job |
| `/jobs/{job_id}` | GET | Get job status and details |
| `/jobs/{job_id}/start` | POST | Start a pending job |
| `/jobs/{job_id}/cancel` | POST | Cancel a running job |
| `/jobs/stream` | GET | Real-time SSE job progress |
| `/jobs/batch` | POST | Create multiple jobs |

#### 👤 User Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/user/me` | GET | Get current user profile |
| `/user/settings` | GET/PUT | User preferences and settings |
| `/user/connections` | GET | List OAuth2 connections |
| `/user/passkeys` | GET | List WebAuthn credentials |

#### 🏥 Health & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/ready` | GET | Kubernetes readiness probe |
| `/health/live` | GET | Kubernetes liveness probe |
| `/health/db` | GET | Database connectivity check |
| `/metrics` | GET | Prometheus metrics |

### Example API Usage

```python
import httpx

async with httpx.AsyncClient() as client:
    # Register new user
    register_response = await client.post(
        "http://localhost:8000/auth/register",
        json={
            "username": "john_doe",
            "email": "john@example.com",
            "password": "SecureP@ssw0rd123",
            "full_name": "John Doe"
        }
    )

    # Login to get JWT token
    login_response = await client.post(
        "http://localhost:8000/auth/token",
        data={
            "username": "john@example.com",
            "password": "SecureP@ssw0rd123"
        }
    )

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create scraping job (authenticated)
    job_response = await client.post(
        "http://localhost:8000/jobs",
        headers=headers,
        json={
            "url": "https://csfrace.com/article-slug",
            "output_directory": "/tmp/output",
            "options": {
                "download_images": True,
                "sanitize_html": True
            }
        }
    )

    job_id = job_response.json()["id"]

    # Monitor job progress via SSE
    async with client.stream(
        "GET",
        f"http://localhost:8000/jobs/stream?job_id={job_id}",
        headers=headers
    ) as stream:
        async for line in stream.aiter_lines():
            if line.startswith("data: "):
                print(line[6:])  # Print job progress updates
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# ==================
# Core Application
# ==================
ENVIRONMENT=development  # development|staging|production
LOG_LEVEL=INFO          # DEBUG|INFO|WARNING|ERROR
API_HOST=0.0.0.0
API_PORT=8000

# ==================
# Database
# ==================
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/csfrace_dev
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_ECHO=false  # Set true for SQL query logging

# ==================
# Redis (Optional)
# ==================
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20
CACHE_ENABLED=true
CACHE_TTL=3600

# ==================
# Security
# ==================
SECRET_KEY=your-super-secret-key-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720  # 12 hours
REFRESH_TOKEN_EXPIRE_DAYS=7

# Cookie Security
FORCE_SECURE_COOKIES=false  # true for HTTPS
COOKIE_SAMESITE=lax         # lax|strict|none

# ==================
# CORS
# ==================
ENABLE_CORS=true
CORS_ORIGINS=["http://localhost:3000","http://localhost:4321"]

# ==================
# OAuth2 Providers
# ==================
# See Authentication section above for provider-specific variables

# ==================
# WebAuthn
# ==================
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=CSFrace Backend
WEBAUTHN_ORIGIN=http://localhost:8000

# ==================
# Scraping
# ==================
SCRAPER_CONCURRENT_REQUESTS=10
SCRAPER_REQUEST_TIMEOUT=30
SCRAPER_MAX_RETRIES=3
SCRAPER_USER_AGENT=CSFrace-Scraper/2.0

# ==================
# Rate Limiting
# ==================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10

# ==================
# Monitoring
# ==================
PROMETHEUS_METRICS_ENABLED=true
SENTRY_DSN=  # Optional: Sentry error tracking
OPENTELEMETRY_ENABLED=false
OPENTELEMETRY_SERVICE_NAME=csfrace-backend
```

### Configuration Profiles

```bash
# Development
cp .env.example .env.development
uv run uvicorn src.api.main:app --reload --env-file .env.development

# Staging
cp .env.example .env.staging
uv run uvicorn src.api.main:app --env-file .env.staging

# Production
cp .env.example .env.production
uv run gunicorn src.api.main:app --env-file .env.production
```

## 🛠️ Development

### Development Workflow

```bash
# 1. Clone and setup
git clone https://github.com/zachatkinson/csfrace-scrape-back.git
cd csfrace-scrape-back

# 2. Install dependencies
uv sync --group dev

# 3. Setup pre-commit hooks
uv run pre-commit install

# 4. Start development services
docker compose -f docker-compose.dev.yml up -d

# 5. Run migrations
uv run alembic upgrade head

# 6. Start development server with hot reload
uv run uvicorn src.api.main:app --reload --log-level debug
```

### Code Quality

```bash
# Format code (black-compatible)
uv run ruff format src/ tests/

# Lint code (auto-fix safe issues)
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/

# Security scanning
uv run bandit -r src/

# Check all quality gates (runs on pre-commit)
uv run pre-commit run --all-files
```

### Database Operations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Add new feature"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history

# Check current revision
uv run alembic current

# Generate SQL without applying (dry-run)
uv run alembic upgrade head --sql > migration.sql
```

### Project Structure

```
csfrace-scrape-back/
├── src/
│   ├── api/                  # FastAPI routes and middleware
│   │   ├── routes/          # API endpoints
│   │   └── middleware/      # Request/response middleware
│   ├── auth/                # Authentication system
│   │   ├── router.py        # Auth endpoints
│   │   ├── service.py       # Auth business logic
│   │   ├── dependencies.py  # Auth dependencies
│   │   └── security.py      # Password hashing, JWT
│   ├── core/                # Core business logic
│   │   ├── converter.py     # Content conversion
│   │   └── logging_hierarchy.py  # Structured logging
│   ├── database/            # Database layer
│   │   ├── models/          # SQLAlchemy models
│   │   ├── service.py       # Database operations
│   │   └── services/        # Specialized services
│   ├── monitoring/          # Observability
│   │   ├── metrics.py       # Prometheus metrics
│   │   └── health.py        # Health checks
│   └── utils/               # Shared utilities
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/               # End-to-end tests
├── alembic/               # Database migrations
│   └── versions/          # Migration files
├── docker/                # Docker configurations
├── docs/                  # Documentation
├── pyproject.toml        # Modern Python config
├── Dockerfile            # Production container
└── docker-compose.dev.yml # Development stack
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests with coverage
uv run pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test categories
uv run pytest tests/unit/              # Unit tests only
uv run pytest tests/integration/       # Integration tests
uv run pytest tests/e2e/              # End-to-end tests
uv run pytest -m "not slow"           # Skip slow tests

# Run tests in parallel (faster)
uv run pytest -n auto

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/unit/test_auth.py

# Run specific test
uv run pytest tests/unit/test_auth.py::test_user_registration
```

### Test Coverage

```bash
# Generate HTML coverage report
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html

# Check coverage meets threshold (85%)
uv run pytest --cov=src --cov-fail-under=85
```

### Writing Tests

```python
# tests/unit/test_auth.py
import pytest
from src.auth.service import AuthService

@pytest.mark.asyncio
async def test_user_registration():
    """Test user registration creates user correctly."""
    auth_service = AuthService(db_session)

    user = await auth_service.create_user(
        username="testuser",
        email="test@example.com",
        password="SecurePass123"
    )

    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True

# tests/integration/test_api.py
@pytest.mark.asyncio
async def test_oauth_login_flow(client: AsyncClient):
    """Test complete OAuth2 login flow."""
    # Initiate OAuth flow
    response = await client.get("/auth/oauth/google")
    assert response.status_code == 302

    # Simulate callback
    callback_response = await client.get(
        "/auth/oauth/google/callback",
        params={"code": "test_code"}
    )
    assert callback_response.status_code == 200
    assert "auth_token" in callback_response.cookies
```

## 🚢 Deployment

### Docker Production

```bash
# Build production image
docker build -t csfrace-backend:latest .

# Run production container
docker run -d \
  --name csfrace-backend \
  -p 8000:8000 \
  --env-file .env.production \
  -e DATABASE_URL=postgresql://... \
  csfrace-backend:latest

# Check logs
docker logs -f csfrace-backend

# Health check
curl http://localhost:8000/health
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  backend:
    image: csfrace-backend:latest
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  postgres:
    image: postgres:17-alpine
    environment:
      - POSTGRES_DB=csfrace
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csfrace-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: csfrace-backend
  template:
    metadata:
      labels:
        app: csfrace-backend
    spec:
      containers:
      - name: backend
        image: csfrace-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: csfrace-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Production Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] SSL/TLS certificates installed
- [ ] OAuth2 providers configured with production URLs
- [ ] WebAuthn RP_ID set to production domain
- [ ] Health checks configured (liveness + readiness)
- [ ] Monitoring and alerting setup (Prometheus + Grafana)
- [ ] Backup strategy implemented (PostgreSQL backups)
- [ ] Security headers configured (CORS, CSP, HSTS)
- [ ] Rate limiting enabled
- [ ] Log aggregation configured (ELK, Datadog, etc.)
- [ ] Secrets management (AWS Secrets Manager, Vault)
- [ ] Auto-scaling configured (horizontal pod autoscaler)
- [ ] CDN configured for static assets
- [ ] Database connection pooling optimized

## 📊 Monitoring

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health
# Response: {"status": "healthy", "version": "1.0.0"}

# Detailed health status (includes database, redis)
curl http://localhost:8000/health/detailed
# Response: {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "uptime_seconds": 3600
# }

# Kubernetes liveness probe
curl http://localhost:8000/health/live

# Kubernetes readiness probe
curl http://localhost:8000/health/ready
```

### Prometheus Metrics

```bash
# View all metrics
curl http://localhost:8000/metrics

# Key metrics available:
# - http_requests_total{method,endpoint,status}
# - http_request_duration_seconds{method,endpoint}
# - active_jobs_gauge
# - database_connections_active
# - database_connections_idle
# - redis_cache_hits_total
# - redis_cache_misses_total
# - auth_login_attempts_total{provider,success}
```

### Grafana Dashboards

```bash
# Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Access Grafana
open http://localhost:3000  # Default: admin/admin

# Pre-built dashboards located in:
# monitoring/grafana/dashboards/
# - API Performance Dashboard
# - Database Metrics Dashboard
# - Authentication Dashboard
# - Job Processing Dashboard
```

### Logging

Hierarchical logging with structured output:

```python
from src.core.logging_hierarchy import (
    get_api_logger,
    get_auth_logger,
    get_database_logger,
    get_scraping_logger,
)

# Component-specific loggers
api_logger = get_api_logger()
auth_logger = get_auth_logger()
db_logger = get_database_logger()
scraper_logger = get_scraping_logger()

# Structured logging
auth_logger.info(
    "User login successful",
    user_id=user.id,
    provider="google",
    ip_address=request.client.host
)

# Error logging with context
db_logger.error(
    "Database connection failed",
    error=str(e),
    retry_attempt=3,
    exc_info=True
)
```

## 🏗️ Architecture

### System Overview

```
┌─────────────────────┐
│   Frontend (Astro)  │
│  Port: 3000/4321    │
└──────────┬──────────┘
           │ HTTPS
           ▼
┌─────────────────────┐     ┌──────────────────┐
│   Nginx Reverse     │────▶│   FastAPI API    │
│   Proxy (SSL)       │     │   Port: 8000     │
└─────────────────────┘     └────────┬─────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
           ┌────────────────┐ ┌─────────────┐ ┌─────────────┐
           │  PostgreSQL 17 │ │  Redis 7    │ │ OAuth2      │
           │  (Primary DB)  │ │  (Cache)    │ │ Providers   │
           └────────────────┘ └─────────────┘ └─────────────┘
                    │
                    ▼
           ┌────────────────────────────┐
           │   Monitoring Stack         │
           │  - Prometheus (Metrics)    │
           │  - Grafana (Dashboards)    │
           │  - Jaeger (Tracing)        │
           └────────────────────────────┘
```

### Authentication Flow

```
┌────────┐                                    ┌────────────┐
│ Client │                                    │   Backend  │
└───┬────┘                                    └─────┬──────┘
    │                                               │
    │  1. GET /auth/oauth/google                   │
    ├──────────────────────────────────────────────▶
    │                                               │
    │  2. Redirect to Google                        │
    ◀──────────────────────────────────────────────┤
    │                                               │
    │  3. User approves                             │
    │  4. Google redirects to callback              │
    ├──────────────────────────────────────────────▶
    │                                               │
    │  5. Backend validates code                    │
    │  6. Creates/updates user                      │
    │  7. Sets httpOnly cookies                     │
    │                                               │
    │  8. Redirect to app with cookies              │
    ◀──────────────────────────────────────────────┤
    │                                               │
    │  9. Subsequent requests include cookies       │
    ├──────────────────────────────────────────────▶
    │                                               │
```

### Database Schema

```sql
-- Users and Authentication
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),  -- NULL for OAuth users
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    failed_login_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- OAuth2 Linked Accounts
CREATE TABLE linked_accounts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,  -- google, github, etc.
    provider_user_id VARCHAR(255) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

-- WebAuthn Credentials (Passkeys)
CREATE TABLE webauthn_credentials (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    public_key TEXT NOT NULL,
    sign_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Account Lockouts
CREATE TABLE account_lockouts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    failed_attempts INTEGER NOT NULL,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User Settings
CREATE TABLE user_settings (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    dark_mode BOOLEAN DEFAULT false,
    notifications_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Scraping Jobs
CREATE TABLE jobs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    url VARCHAR NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    domain VARCHAR(253),  -- For analytics
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install dependencies: `uv sync --group dev`
4. Make changes and add tests
5. Run quality checks: `uv run pre-commit run --all-files`
6. Ensure tests pass: `uv run pytest --cov=src`
7. Commit with semantic message: `git commit -m "feat: add amazing feature"`
8. Push and create PR: `git push origin feature/amazing-feature`

### Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting)
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `test:` Test additions or changes
- `chore:` Build process or tooling changes

### Code Standards

- Follow [CLAUDE.md](./CLAUDE.md) coding standards
- Maintain 85%+ test coverage
- Use type hints for all functions
- Write comprehensive docstrings
- Keep functions focused and small (SRP)
- Use dependency injection for testability

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- **[CSFrace Scraper Frontend](https://github.com/zachatkinson/csfrace-scrape-front)** - Astro/React frontend with Nano stores
- **[CSFrace Scraper Orchestration](https://github.com/zachatkinson/csfrace-scrape)** - Docker Compose orchestration

## 📞 Support

- 📖 [Documentation](https://github.com/zachatkinson/csfrace-scrape-back/wiki)
- 🐛 [Bug Reports](https://github.com/zachatkinson/csfrace-scrape-back/issues)
- 💬 [Discussions](https://github.com/zachatkinson/csfrace-scrape-back/discussions)
- 📧 [Email Support](mailto:support@csfrace.com)

## 🙏 Acknowledgments

- **FastAPI** - Modern, high-performance web framework
- **SQLAlchemy 2.0** - Async ORM with excellent PostgreSQL support
- **Pydantic** - Data validation using Python type hints
- **UV** - Fast, reliable Python package installer
- **Ruff** - Extremely fast Python linter and formatter

---

<div align="center">

**CSFrace Scraper Backend** - Enterprise-grade WordPress to Shopify content conversion

Built with ❤️ using FastAPI, Python 3.13, PostgreSQL 17, and modern security patterns

[🚀 Get Started](#-quick-start) • [📚 Documentation](#-api-documentation) • [🤝 Contributing](#-contributing)

</div>

