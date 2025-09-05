# WordPress to Shopify Content Converter

[![CI/CD Pipeline](https://github.com/zachatkinson/csfrace-scrape-back/actions/workflows/ci.yml/badge.svg)](https://github.com/zachatkinson/csfrace-scrape-back/actions)
[![Semantic Release](https://img.shields.io/github/v/release/zachatkinson/csfrace-scrape-back?label=release&logo=semantic-release)](https://github.com/zachatkinson/csfrace-scrape-back/releases)
[![Code Coverage](https://codecov.io/gh/zachatkinson/csfrace-scrape-back/branch/master/graph/badge.svg)](https://codecov.io/gh/zachatkinson/csfrace-scrape-back)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A high-performance, async Python application that converts WordPress blog content to Shopify-compatible HTML format. Built with modern async/await patterns, comprehensive monitoring, and a web-based frontend for easy content migration.

## ✨ Features

### Core Functionality
- 🚀 **Async Processing**: High-performance concurrent content processing with aiohttp
- 🔄 **Batch Operations**: Process multiple URLs simultaneously with progress tracking
- 🖼️ **Image Handling**: Automatic image download and optimization
- 🎨 **Style Cleanup**: WordPress-specific CSS cleanup and Shopify optimization
- 📊 **Rich Monitoring**: Comprehensive metrics, logging, and observability

### Web Interface
- 🌐 **Modern Frontend**: [Separate Astro frontend](https://github.com/zachatkinson/csfrace-scrape-front) with React 19 & Tailwind CSS
- 🔐 **User Authentication**: Secure login system with job history
- 📋 **Job Management**: Real-time status updates and artifact downloads
- 📈 **Analytics Dashboard**: Usage statistics and performance metrics
- 🗂️ **File Management**: Organized output with downloadable archives

### Developer Experience  
- 🐳 **Docker Support**: Complete containerization with Docker Compose
- 📈 **Monitoring Stack**: Grafana + Prometheus integration
- 🧪 **Comprehensive Testing**: 90%+ test coverage with performance benchmarks
- 🔧 **CLI Interface**: Full command-line interface for automation
- 📚 **API Documentation**: FastAPI with auto-generated OpenAPI docs

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL (via Docker or local install)
- Redis (optional, for advanced caching)

### Installation

```bash
# Clone the repository
git clone https://github.com/zachatkinson/csfrace-scrape-back.git
cd csfrace-scrape-back

# Install with uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or install with pip
python -m pip install -r requirements.txt

# Set up database
docker compose up -d postgres redis

# Run database migrations
uv run alembic upgrade head
```

### Basic Usage

#### CLI Interface
```bash
# Convert a single URL
uv run python -m src.main https://wordpress-site.com/blog/post

# Batch conversion with custom settings
uv run python -m src.main \
  --urls-file urls.txt \
  --output-dir converted_content \
  --batch-size 10 \
  --format html

# Interactive mode
uv run python -m src.main
```

#### API Server
```bash
# Start the FastAPI server
uv run uvicorn src.api.main:app --reload

# Visit http://localhost:8000/docs for API documentation
```

#### Web Interface
```bash
# Set up the frontend (covered in Frontend Setup section)
cd frontend
npm install
npm run dev

# Visit http://localhost:4321 for the web interface
```

## 📖 Detailed Usage

### Configuration

The application supports multiple configuration methods:

#### Environment Variables
```bash
export BASE_URL="https://your-wordpress-site.com"
export OUTPUT_DIR="/path/to/output"
export DEFAULT_TIMEOUT=30
export MAX_CONCURRENT=10
export POSTGRES_URL="postgresql://user:pass@localhost:5432/csfrace"
```

#### Configuration File
```yaml
# config.yaml
scraper:
  base_url: "https://wordpress-site.com"
  timeout: 30
  max_concurrent: 5

database:
  url: "postgresql://user:pass@localhost:5432/csfrace"
  
output:
  directory: "./converted_content"
  format: "html"
  preserve_images: true
```

### API Usage

#### Create a Conversion Job
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/v1/jobs",
        json={
            "url": "https://wordpress-site.com/blog/post",
            "options": {
                "download_images": True,
                "clean_styles": True,
                "output_format": "html"
            }
        }
    )
    job = response.json()
    print(f"Job created: {job['id']}")
```

#### Monitor Job Status
```python
# Poll for job completion
job_id = "job-uuid-here"
response = await client.get(f"http://localhost:8000/api/v1/jobs/{job_id}")
job_status = response.json()

if job_status["status"] == "completed":
    # Download converted content
    download_response = await client.get(
        f"http://localhost:8000/api/v1/jobs/{job_id}/artifacts"
    )
    with open("converted_content.zip", "wb") as f:
        f.write(download_response.content)
```

### Batch Processing

#### From File
```bash
# Create urls.txt with one URL per line
echo "https://site.com/post1" >> urls.txt
echo "https://site.com/post2" >> urls.txt

# Process batch
uv run python -m src.main --urls-file urls.txt --batch-size 5
```

#### Programmatically
```python
from src.batch.processor import BatchProcessor, BatchConfig

config = BatchConfig(
    max_concurrent=10,
    timeout_seconds=60,
    output_dir="batch_output"
)

processor = BatchProcessor(config)
results = await processor.process_urls([
    "https://site.com/post1",
    "https://site.com/post2",
    "https://site.com/post3"
])

print(f"Processed: {len(results.successful)}/{results.total}")
```

## 🏗️ Architecture

### System Overview
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Frontend  │────│   FastAPI Backend │────│   PostgreSQL    │
│   (Astro/React) │    │   (Python 3.13)  │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │              ┌──────────────────┐              │
         └──────────────│   Redis Cache    │──────────────┘
                        │   (Optional)     │
                        └──────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │  Monitoring Stack       │
                    │  (Grafana + Prometheus) │
                    └─────────────────────────┘
```

### Core Components

- **`src/core/`**: Main conversion engine and configuration
- **`src/api/`**: FastAPI REST API with async endpoints  
- **`src/batch/`**: Concurrent batch processing system
- **`src/processors/`**: HTML processing, image downloading, metadata extraction
- **`src/caching/`**: Multi-tier caching (file + Redis)
- **`src/monitoring/`**: Comprehensive observability stack
- **`src/database/`**: SQLAlchemy models and database operations

### Design Principles

Following [CLAUDE.md](./CLAUDE.md) standards:
- **DRY**: All constants centralized, no hardcoded values
- **SOLID**: Dependency injection, single responsibility
- **IDT**: Implementation-driven testing with 90%+ coverage
- **Async-first**: Built on asyncio and aiohttp
- **Type Safety**: Comprehensive type hints with mypy

## 🌐 Frontend Setup

The web interface is built with Astro and provides a complete user experience:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### Frontend Features
- **Authentication**: User accounts with job history
- **Dashboard**: Overview of recent conversions and usage
- **Batch Upload**: CSV/text file upload for bulk processing
- **Real-time Updates**: WebSocket job status updates
- **Download Manager**: Organized artifact downloads

### Deployment (Netlify)
```bash
# Deploy to Netlify
netlify deploy --prod --dir=dist

# Configure environment variables in Netlify dashboard
ASTRO_API_URL=https://your-api-domain.com
ASTRO_AUTH_SECRET=your-secret-key
```

## 🐳 Docker Deployment

### Development
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Scale workers
docker compose up -d --scale worker=3
```

### Production
```bash
# Build production images
docker compose -f docker compose.prod.yml build

# Deploy with monitoring
docker compose -f docker compose.prod.yml up -d

# Access Grafana at http://localhost:3000
# Access API docs at http://localhost:8000/docs
```

### Services
- **PostgreSQL**: Primary database
- **Redis**: Caching layer
- **API Server**: FastAPI application
- **Worker**: Background job processor
- **Grafana**: Monitoring dashboard
- **Prometheus**: Metrics collection

## 📊 Monitoring & Observability

### Grafana Dashboards
```bash
# Provision Grafana dashboards
uv run python -m src.cli.grafana_cli provision

# Access dashboards at http://localhost:3000
# Default credentials: admin/admin (change immediately)
```

### Available Dashboards
- **System Overview**: CPU, memory, disk usage (USE methodology)
- **Application Metrics**: Request rate, errors, duration (RED methodology)  
- **Database Performance**: Connection pools, query performance
- **Business Metrics**: Conversion rates, user activity

### Metrics Collection
The application exposes metrics at `/metrics` endpoint:
- Request/response metrics
- Database connection stats
- Job processing metrics
- Cache hit rates
- Error rates and types

### Logging
Structured logging with correlation IDs:
```python
import structlog
logger = structlog.get_logger(__name__)

# Logs automatically include correlation IDs and context
logger.info("Processing job", job_id=job.id, url=job.url)
```

## 🧪 Development

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test categories  
uv run pytest tests/unit -v
uv run pytest tests/integration -k test_api
uv run pytest tests/performance --benchmark-only

# Run tests in parallel
uv run pytest -n auto
```

### Code Quality
```bash
# Linting and formatting
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Security scanning
uv run bandit -r src/
uv run safety check
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## 📈 Performance

### Benchmarks
- **Single URL**: ~2-5 seconds average conversion time
- **Batch Processing**: 50+ URLs/minute with proper concurrency
- **Memory Usage**: <100MB base, scales with concurrent jobs
- **Database**: Optimized for 1000+ jobs with proper indexing

### Optimization Tips
- Adjust `MAX_CONCURRENT` based on target site rate limits
- Use Redis caching for frequently accessed content
- Enable compression for large HTML files
- Monitor memory usage with large image downloads

### Scalability
- Horizontal scaling via multiple worker processes
- Database connection pooling for high concurrency
- Redis clustering for cache scaling
- Load balancing with nginx/CloudFlare

## 🔧 Configuration Reference

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | - | WordPress site base URL |
| `OUTPUT_DIR` | `converted_content` | Output directory path |
| `MAX_CONCURRENT` | `10` | Max concurrent requests |
| `DEFAULT_TIMEOUT` | `30` | Request timeout (seconds) |
| `POSTGRES_URL` | - | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `LOG_LEVEL` | `INFO` | Logging level |

### Advanced Configuration
See [CLAUDE.md](./CLAUDE.md) for detailed configuration patterns and constants management.

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: `uv sync --group dev`
4. Make changes following [CLAUDE.md](./CLAUDE.md) standards
5. Add tests with 90%+ coverage
6. Run quality checks: `pre-commit run --all-files`
7. Create a pull request

### Code Style
- Follow CLAUDE.md standards (DRY, SOLID, IDT)
- Use type hints for all functions
- Write comprehensive docstrings
- Add tests for all new functionality
- Keep functions small and focused

### Commit Messages
```
feat(api): add job cancellation endpoint
fix(batch): resolve concurrent processing race condition
docs(readme): update installation instructions
test(core): add edge case tests for URL validation
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Repositories

- **[csfrace-scrape-front](https://github.com/zachatkinson/csfrace-scrape-front)** - Modern Astro/React frontend with Tailwind CSS
- **[csfrace-scrape-back](https://github.com/zachatkinson/csfrace-scrape-back)** - Backend API and scraping engine (this repository)

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) and [asyncio](https://docs.python.org/3/library/asyncio.html)
- Frontend powered by [Astro](https://astro.build/) and [React](https://react.dev/)
- Monitoring with [Grafana](https://grafana.com/) and [Prometheus](https://prometheus.io/)
- Code quality with [Ruff](https://github.com/astral-sh/ruff) and [uv](https://github.com/astral-sh/uv)

## 📞 Support

- 📖 [Documentation](https://github.com/zachatkinson/csfrace-scrape-back/wiki)
- 🐛 [Bug Reports](https://github.com/zachatkinson/csfrace-scrape-back/issues)
- 💬 [Discussions](https://github.com/zachatkinson/csfrace-scrape-back/discussions)
- 📧 [Email](mailto:dev@csfrace.com)

---

**WordPress to Shopify Content Converter** - Making content migration effortless.


## 🚀 Automation Status
✅ Submodule automation system fully implemented and tested
