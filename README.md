# WordPress to Shopify Content Converter

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/zachatkinson/csfrace-scrape/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/zachatkinson/csfrace-scrape/actions)
[![codecov](https://codecov.io/gh/zachatkinson/csfrace-scrape/branch/master/graph/badge.svg)](https://codecov.io/gh/zachatkinson/csfrace-scrape)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Docker](https://img.shields.io/badge/docker-supported-blue?logo=docker)](https://github.com/zachatkinson/csfrace-scrape/blob/master/Dockerfile)
[![Async](https://img.shields.io/badge/async-aiohttp-blue.svg)](https://docs.aiohttp.org/)

A high-performance, async Python tool for converting WordPress content to Shopify-compatible HTML. Built for enterprise-scale content migrations with advanced batch processing, intelligent caching, and extensible plugin architecture.

## ✨ Key Features

- 🚀 **High-Performance Async Processing** - Concurrent downloads with configurable limits
- 📦 **Intelligent Batch Processing** - Process hundreds of URLs with smart directory organization  
- ⚡ **Advanced Caching System** - File-based and Redis caching with automatic expiration
- 🔧 **Extensible Plugin Architecture** - Custom processing pipelines for specialized content
- ⚙️ **Flexible Configuration** - YAML/JSON config files with CLI overrides
- 📊 **Rich Progress Tracking** - Beautiful console output with statistics and progress bars
- 🗂️ **Archive Management** - Automatic ZIP creation with optional cleanup
- 🌐 **Robots.txt Compliance** - Respectful crawling with rate limiting
- 🔄 **Robust Error Recovery** - Exponential backoff and retry mechanisms
- 🎯 **WordPress Content Expertise** - Specialized handling of Kadence blocks, embeds, and formatting

## Installation

### Prerequisites
- Python 3.9+ (Python 3.11+ recommended)
- Git (for development setup)

### Quick Install
```bash
git clone https://github.com/zachatkinson/csfrace-scrape.git
cd csfrace-scrape
python -m pip install -r requirements/base.txt
```

### Development Install
```bash
python -m pip install -e .[dev,test]
```

### Optional Dependencies
```bash
# For Redis caching (recommended for high-volume processing)
python -m pip install "redis>=5.0.0"

# For advanced plugins (image processing, NLP, etc.)
python -m pip install -r requirements/optional.txt
```

## Quick Start

### Single URL
```bash
python -m src.main https://example.com/blog/post
```

### Batch Processing
```bash
# Multiple URLs
python -m src.main "https://site.com/post1,https://site.com/post2" --batch-size 5

# From file
python -m src.main --urls-file urls.txt --batch-size 10 -o batch_output
```

### With Configuration
```bash
# Generate config template
python -m src.main --generate-config yaml

# Use configuration
python -m src.main --config config.yaml --urls-file urls.txt
```

## Usage Guide

### Command Line Interface

| Option | Description | Example |
|--------|-------------|---------|
| `url` | WordPress URL(s) to convert | `https://example.com/post` |
| `-o, --output` | Output directory | `-o my_output` |
| `-c, --config` | Configuration file | `-c config.yaml` |
| `--urls-file` | File with URLs to process | `--urls-file urls.txt` |
| `--batch-size` | Concurrent processing limit | `--batch-size 5` |
| `--generate-config` | Create example config | `--generate-config yaml` |
| `-v, --verbose` | Enable verbose logging | `-v` |

### Batch Processing Modes

#### 1. Comma-Separated URLs
```bash
python -m src.main "https://site.com/post1,https://site.com/post2,https://site.com/post3"
```

#### 2. Text File Input
Create `urls.txt`:
```
https://example.com/blog/post-1
https://example.com/blog/post-2  
https://example.com/blog/post-3
# Comments are supported
```

Run batch:
```bash
python -m src.main --urls-file urls.txt --batch-size 3
```

#### 3. CSV Input with Custom Settings
Create `jobs.csv`:
```csv
url,slug,output_dir,priority
https://example.com/post-1,custom-slug-1,custom/dir1,1
https://example.com/post-2,custom-slug-2,,2
https://example.com/post-3,,,3
```

Process CSV:
```bash
python -m src.main --urls-file jobs.csv
```

### Configuration Management

#### Generate Configuration Template
```bash
python -m src.main --generate-config yaml  # Creates wp-shopify-config.yaml
python -m src.main --generate-config json  # Creates wp-shopify-config.json
```

#### Example Configuration (`config.yaml`)
```yaml
converter:
  default_timeout: 30
  max_concurrent_downloads: 10
  rate_limit_delay: 0.5
  max_retries: 3
  respect_robots_txt: true
  preserve_classes:
    - center
    - media-grid
    - button--primary

batch:
  max_concurrent: 5
  create_archives: true
  output_base_dir: "batch_output"
  cleanup_after_archive: false
  timeout_per_job: 300
```

#### Use Configuration
```bash
# With configuration file
python -m src.main --config config.yaml https://example.com/post

# Override config settings via CLI
python -m src.main --config config.yaml --batch-size 10 --urls-file urls.txt
```

### Caching System

#### File-Based Caching (Default)
- Automatic local file caching
- Configurable TTL per content type
- Intelligent size management
- Cross-platform compatibility

#### Redis Caching (Recommended for High Volume)
1. Install Redis:
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu/Debian
   sudo apt install redis-server
   sudo systemctl start redis
   ```

2. Install Python Redis client:
   ```bash
   python -m pip install "redis>=5.0.0"
   ```

3. Configure caching in `config.yaml`:
   ```yaml
   cache:
     backend: redis
     redis_host: localhost
     redis_port: 6379
     ttl_html: 1800
     ttl_images: 86400
   ```

## Output Structure

### Single URL Output
```
converted_content/
├── metadata.txt                 # Extracted metadata
├── converted_content.html       # Clean HTML content
├── shopify_ready_content.html   # Complete file for Shopify
└── images/                      # Downloaded images
    ├── image1.jpg
    └── image2.png
```

### Batch Processing Output
```
batch_output/
├── example-com_post-1/          # Organized by domain and slug
│   ├── metadata.txt
│   ├── converted_content.html
│   ├── shopify_ready_content.html
│   └── images/
├── example-com_post-2/
│   └── ...
├── archives/                    # ZIP archives (if enabled)
│   ├── example-com_post-1.zip
│   └── example-com_post-2.zip
└── batch_summary.json          # Processing statistics
```

## Content Conversion Features

### WordPress Block Support
- **Kadence Blocks**: Row layouts → Media grid layouts
- **Advanced Galleries**: Converted to responsive media grids
- **Advanced Buttons**: Shopify-compatible button styles
- **Pullquotes**: Testimonial-style quote formatting
- **Embeds**: YouTube, Instagram with responsive containers

### HTML Transformations
- Font tags: `<b>` → `<strong>`, `<i>` → `<em>`
- Text alignment: WordPress classes → Shopify-compatible
- Image optimization: Clean `<img>` tags with proper alt text
- External links: Auto-add `target="_blank"` and security attributes
- Script removal: Security-focused content sanitization

### Metadata Extraction
- Page title and description
- URL slug generation
- Publication dates
- SEO-relevant meta tags
- Custom WordPress fields

## Plugin Architecture

### Built-in Plugins
- **SEO Metadata Extractor**: Comprehensive SEO data extraction
- **Font Cleanup Plugin**: Removes font-related styling
- **Content Filter**: Customizable content filtering rules

### Creating Custom Plugins
1. Inherit from appropriate base class:
   ```python
   from src.plugins.base import HTMLProcessorPlugin
   
   class MyCustomPlugin(HTMLProcessorPlugin):
       @property
       def plugin_info(self):
           return {
               'name': 'My Custom Plugin',
               'version': '1.0.0',
               'description': 'Custom content processing',
               'author': 'Your Name',
               'plugin_type': 'html_processor'
           }
       
       async def process_html(self, html_content, metadata, context):
           # Custom processing logic
           return processed_html
   ```

2. Register and use:
   ```python
   from src.plugins.registry import plugin_registry
   plugin_registry.register_plugin(MyCustomPlugin)
   ```

## Advanced Features

### Performance Monitoring
```bash
# View processing statistics
python -m src.main --urls-file large-batch.txt -v
```

### Error Recovery
- Automatic retry with exponential backoff
- Graceful handling of failed URLs
- Detailed error reporting and logging
- Continue-on-error batch processing

### Archive Management
```yaml
batch:
  create_archives: true
  archive_format: zip
  cleanup_after_archive: false  # Keep original directories
```

### Robots.txt Compliance
- Automatic robots.txt checking
- Respectful crawl delays
- Rate limiting configuration
- User-agent identification

## Development

### Testing
```bash
# Run all tests
python -m pytest tests/ --cov=src

# Run specific test categories  
python -m pytest tests/unit/test_batch_processor.py
python -m pytest tests/integration/test_priority2_integration.py

# Test with Redis (requires Redis server)
python -m pytest tests/integration/test_redis_cache.py
```

### Code Quality
```bash
# Format code
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

### Semantic Versioning
```bash
# Create version bump and update changelog
cz bump

# View version history
cz changelog
```

## Troubleshooting

### Common Issues

**"No Redis connection"**
- Ensure Redis server is running: `redis-cli ping`
- Check Redis configuration in config file
- Falls back to file caching automatically

**"Batch processing timeout"**
- Reduce `batch_size` in configuration
- Increase `timeout_per_job` setting
- Check network connectivity

**"Permission denied" errors**
- Ensure write permissions in output directory
- Check available disk space
- Verify file system supports long paths (Windows)

### Debug Mode
```bash
python -m src.main --urls-file urls.txt -v  # Verbose logging
```

### Performance Tuning
```yaml
# High-performance configuration
batch:
  max_concurrent: 10
  timeout_per_job: 120
converter:
  max_concurrent_downloads: 20
  rate_limit_delay: 0.1
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes with tests
4. Run the test suite: `pytest tests/`
5. Commit using conventional format: `cz commit`
6. Push and create a Pull Request

See [CLAUDE.md](CLAUDE.md) for development guidelines and coding standards.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- 📋 [Create an Issue](https://github.com/zachatkinson/csfrace-scrape/issues) for bug reports
- 💡 [Request Features](https://github.com/zachatkinson/csfrace-scrape/discussions) for enhancements  
- 📖 [Documentation](https://github.com/zachatkinson/csfrace-scrape/wiki) for detailed guides

## Acknowledgments

Built for CSFrace's WordPress to Shopify migration, featuring specialized handling of Kadence blocks, custom themes, and enterprise-scale content processing requirements.

---

⭐ **Star this repo** if it helped with your WordPress to Shopify migration!