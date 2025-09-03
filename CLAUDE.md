# Claude Code Best Practices - WordPress to Shopify Converter

## Project Overview
This Python3 application converts WordPress blog content from the CSFrace website to Shopify-compatible HTML format. It handles various WordPress blocks, embeds, and formatting while ensuring the output is optimized for Shopify's content system.

## MANDATORY Code Quality Standards

### 1. IDT, DRY and SOLID Principles (MANDATORY)
**These principles are MANDATORY and must be followed without exception. NO EXCEPTIONS.**

#### IDT (Implementation-Driven Testing) - PRACTICAL APPROACH
**MANDATORY: ALL code must be developed using comprehensive Implementation-Driven Testing practices.**

- **Design interfaces and APIs first for clear contracts**
- **Implement core functionality following SOLID principles**
- **Create comprehensive test coverage immediately after implementation**
- **Refactor based on test feedback and discovered edge cases**
- **Minimum 85% test coverage required (90%+ for core business logic)**

**IDT Workflow (MANDATORY):**
```python
# 1. DESIGN: Plan the interface/API structure first
class DataProcessor:
    def process_data(self, input_data: List[Dict]) -> ProcessedResult:
        """Process input data and return structured results."""
        pass

# 2. IMPLEMENT: Write core functionality following standards
class DataProcessor:
    def process_data(self, input_data: List[Dict]) -> ProcessedResult:
        validated_data = self._validate_input(input_data)
        processed = self._transform_data(validated_data)
        return self._format_results(processed)

# 3. TEST: Create comprehensive test coverage
def test_data_processor_handles_valid_input():
    processor = DataProcessor()
    result = processor.process_data([{"key": "value"}])
    assert result.success is True
    assert len(result.items) == 1

def test_data_processor_handles_edge_cases():
    processor = DataProcessor()
    result = processor.process_data([])  # Empty input
    assert result.success is True
    assert len(result.items) == 0

# 4. REFACTOR: Improve based on test feedback
class DataProcessor:
    def process_data(self, input_data: List[Dict]) -> ProcessedResult:
        # Enhanced implementation with better error handling
        if not input_data:
            return ProcessedResult.empty()
        
        validated_data = self._validate_input(input_data)
        processed = self._transform_data(validated_data)
        return self._format_results(processed)
```

**IDT Requirements:**
- **Design clear interfaces before implementation**
- **Each feature must have comprehensive test coverage**
- **All tests must pass before any code is merged**
- **Test names must clearly describe behavior and edge cases**
- **Tests must be independent and repeatable**
- **Include unit, integration, and performance tests as appropriate**

#### DRY (Don't Repeat Yourself) - ZERO TOLERANCE
- **NEVER duplicate code, values, or logic anywhere**
- **ALL repeated values must be extracted to constants**
- **NO hardcoded URLs, paths, or magic numbers in business logic**
- **Use environment variables with proper defaults**
- **Extract common functionality into reusable utilities**

**Constants Management Pattern (MANDATORY):**
```python
# constants.py - MANDATORY for all projects
from dataclasses import dataclass
from os import environ
from pathlib import Path

@dataclass(frozen=True)
class AppConstants:
    # URLs - NO hardcoding allowed
    DEFAULT_BASE_URL: str = environ.get("BASE_URL", "https://example.com")
    TEST_BASE_URL: str = environ.get("TEST_URL", "https://test.example.com") 
    
    # Paths - NO hardcoding allowed
    DEFAULT_OUTPUT_DIR: Path = Path(environ.get("OUTPUT_DIR", "converted_content"))
    DEFAULT_IMAGES_DIR: str = "images"
    
    # Timeouts and limits
    DEFAULT_TIMEOUT: int = int(environ.get("DEFAULT_TIMEOUT", "30"))
    MAX_CONCURRENT: int = int(environ.get("MAX_CONCURRENT", "10"))
    MAX_RETRIES: int = int(environ.get("MAX_RETRIES", "3"))
    
    # File names - centralized
    METADATA_FILE: str = "metadata.txt" 
    HTML_FILE: str = "converted_content.html"
    SHOPIFY_FILE: str = "shopify_ready_content.html"
```

#### SOLID Principles (MANDATORY)
1. **Single Responsibility**: Each class/function has ONE clear purpose
2. **Open/Closed**: Extend through inheritance/composition, not modification  
3. **Liskov Substitution**: Subclasses must work exactly like base classes
4. **Interface Segregation**: Create focused, specific interfaces
5. **Dependency Inversion**: Depend on abstractions, inject dependencies

**Dependency Injection Pattern (MANDATORY):**
```python
# GOOD - Dependencies injected, testable, flexible
class AsyncWordPressConverter:
    def __init__(self, 
                 base_url: str, 
                 output_dir: Path,
                 config: Optional[ConverterConfig] = None,
                 http_client: Optional[HTTPClient] = None,
                 logger: Optional[Logger] = None):
        self.config = config or default_config
        self.http_client = http_client or default_client
        self.logger = logger or get_logger(__name__)
```

#### Configuration Management (MANDATORY)
- **ALL configuration through environment variables**
- **NO hardcoded values in business logic** 
- **Validation on all configuration inputs**
- **Sensible defaults with explicit documentation**

### 2. Code Style & Formatting (MANDATORY)  
- **PEP 8 Compliance**: Follow PEP 8 style guide for Python code
- **Line Length**: Maximum 100 characters (relaxed from PEP 8's 79 for readability)
- **Indentation**: 4 spaces (no tabs)
- **Naming Conventions**:
  - Classes: `PascalCase` (e.g., `WordPressToShopifyConverter`)
  - Functions/Methods: `snake_case` (e.g., `convert_font_formatting`)  
  - Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_OUTPUT_DIR`)
  - Private methods: Leading underscore (e.g., `_internal_method`)

### 2. Type Hints
Implement type hints for better code clarity and IDE support:
```python
from typing import Dict, List, Optional, Tuple

def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
    """Extract page metadata with type hints."""
    pass

def process_content(self, html_content: str) -> Tuple[Dict[str, str], str]:
    """Process content returning metadata and HTML."""
    pass
```

### 3. Code Quality & Formatting (MANDATORY)
**CRITICAL: All code MUST pass linting and formatting before commits/PRs.**

**Mandatory Tools:**
```bash
# Format code (must pass)
python -m black src/ tests/ --line-length=100 --check

# Lint code (must pass) 
python -m ruff check src/ tests/

# Type checking (strongly recommended)
python -m mypy src/
```

**Pre-commit Requirements:**
- **Install pre-commit hooks**: `pre-commit install`
- **All commits must pass pre-commit hooks**
- **CI will fail if linting/formatting fails**

**Code Style Enforcement:**
- **Line Length**: 100 characters (configured in pyproject.toml)
- **Import Organization**: Ruff handles import sorting automatically
- **Type Hints**: Use modern Python type hints (`list[str]` not `List[str]`)
- **String Quotes**: Prefer double quotes for consistency

**Configuration Files:**
- **pyproject.toml**: Contains all tool configurations (Ruff, Black, MyPy, pytest)
- **Modern Ruff config**: Uses `[tool.ruff.lint]` section (not deprecated top-level)
- **Ignore patterns**: Only acceptable patterns in ignore lists

**Acceptable Ignore Patterns (already configured):**
```toml
[tool.ruff.lint]
ignore = [
    "E501",   # line too long (handled by black)
    "S324",   # insecure hash functions (MD5 ok for URL hashing)
    "B904",   # raise from err (optional)
    "ARG002", # unused args (common in interfaces)
]
```

### 4. Error Handling
- Use specific exception types rather than bare `except:`
- Implement proper logging instead of print statements
- Provide meaningful error messages with context
- Consider creating custom exceptions for domain-specific errors

```python
import logging

logger = logging.getLogger(__name__)

try:
    response = self.session.get(url, timeout=10)
    response.raise_for_status()
except requests.Timeout:
    logger.error(f"Timeout fetching URL: {url}")
    raise
except requests.HTTPError as e:
    logger.error(f"HTTP error {e.response.status_code} for URL: {url}")
    raise
```

### 4. Documentation Standards
- **Docstrings**: Use Google or NumPy style docstrings for all public methods
- **Module docstrings**: Include at the top of each file
- **Inline comments**: Use sparingly, code should be self-documenting
- **Type annotations**: Prefer over docstring type descriptions

```python
def convert_content(self, html: str, options: Dict[str, Any]) -> str:
    """Convert WordPress HTML to Shopify format.
    
    Args:
        html: Raw HTML content from WordPress
        options: Conversion options dictionary
        
    Returns:
        Converted HTML string ready for Shopify
        
    Raises:
        ConversionError: If content cannot be converted
    """
```

### 5. Test Organization Standards (MANDATORY)
**Test Directory Structure MUST Mirror Source Directory Structure:**

```
tests/                          # Mirror src/ structure exactly
├── __init__.py
├── conftest.py                # Shared test fixtures
├── batch/                     # Mirror src/batch/
│   ├── __init__.py
│   └── test_processor.py      # Tests for src/batch/processor.py
├── caching/                   # Mirror src/caching/
│   ├── __init__.py
│   ├── test_base.py          # Tests for src/caching/base.py
│   ├── test_file_cache.py    # Tests for src/caching/file_cache.py
│   └── test_manager.py       # Tests for src/caching/manager.py
├── core/                     # Mirror src/core/
│   ├── __init__.py
│   ├── test_config.py        # Tests for src/core/config.py
│   ├── test_converter.py     # Tests for src/core/converter.py
│   └── test_exceptions.py    # Tests for src/core/exceptions.py
├── rendering/                # Mirror src/rendering/
│   ├── __init__.py
│   ├── test_browser.py       # Tests for src/rendering/browser.py
│   ├── test_detector.py      # Tests for src/rendering/detector.py
│   └── test_renderer.py      # Tests for src/rendering/renderer.py
└── utils/                    # Mirror src/utils/
    ├── __init__.py
    ├── test_html.py          # Tests for src/utils/html.py
    ├── test_http.py          # Tests for src/utils/http.py
    └── test_retry.py         # Tests for src/utils/retry.py
```

**Rules:**
- **MANDATORY**: Test file names MUST correspond directly to source file names
- **Pattern**: `test_<module_name>.py` tests `<module_name>.py`
- **Location**: Tests MUST be in the same relative path as source files
- **Example**: `src/rendering/browser.py` → `tests/rendering/test_browser.py`
- **Benefits**: Easy navigation, clear test-to-code mapping, maintainability

### 6. Comprehensive Testing Standards
Modern testing approaches for reliable scraper development:

**Testing Framework Setup:**
```python
# conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import aiohttp
from aioresponses import aioresponses

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for testing."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    return session

@pytest.fixture
def sample_html():
    """Load sample HTML for testing."""
    with open('tests/fixtures/sample_content.html', 'r') as f:
        return f.read()

@pytest.fixture
def mock_responses():
    """Mock HTTP responses."""
    with aioresponses() as m:
        yield m
```

**Test Categories and Naming:**
- **Unit Tests**: `test_<unit>_<scenario>_<expected_result>`
- **Integration Tests**: `test_integration_<feature>_<scenario>`
- **Performance Tests**: `test_performance_<operation>_<condition>`
- **End-to-End Tests**: `test_e2e_<workflow>_<scenario>`

**Test Structure Example:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_converter.py    # Unit tests for converter logic
│   ├── test_parsers.py      # Parser unit tests
│   ├── test_validators.py   # Validation unit tests
│   └── test_utils.py        # Utility function tests
├── integration/
│   ├── __init__.py
│   ├── test_scraper_integration.py
│   └── test_export_integration.py
├── performance/
│   ├── __init__.py
│   ├── test_concurrent_processing.py
│   └── test_memory_usage.py
├── e2e/
│   ├── __init__.py
│   └── test_full_conversion_workflow.py
├── fixtures/
│   ├── sample_wordpress.html
│   ├── sample_responses.json
│   └── test_configurations.yaml
└── utils/
    ├── __init__.py
    ├── test_helpers.py
    └── mock_servers.py
```

**Advanced Testing Patterns:**

```python
# Property-based testing with hypothesis
from hypothesis import given, strategies as st
import hypothesis.strategies as st

@given(st.text(), st.integers(min_value=1, max_value=100))
def test_url_validation_fuzzing(url_fragment, port):
    """Test URL validation with random inputs."""
    validator = URLValidator()
    # Test should not crash with any input
    result = validator.validate(f"http://example.com:{port}/{url_fragment}")
    assert isinstance(result, bool)

# Async testing
@pytest.mark.asyncio
async def test_concurrent_requests_handling():
    """Test concurrent request processing."""
    scraper = AsyncScraper(max_concurrent=5)
    urls = [f"http://example.com/page{i}" for i in range(10)]
    
    with aioresponses() as mock:
        for url in urls:
            mock.get(url, payload={"status": "ok"})
        
        results = await scraper.fetch_multiple(urls)
        assert len(results) == 10
        assert all(r is not None for r in results)

# Performance testing
@pytest.mark.performance
def test_large_html_processing_performance():
    """Test performance with large HTML documents."""
    large_html = "<div>" * 10000 + "content" + "</div>" * 10000
    
    start_time = time.time()
    processor = HTMLProcessor()
    result = processor.process(large_html)
    execution_time = time.time() - start_time
    
    assert execution_time < 5.0  # Should complete within 5 seconds
    assert result is not None

# Mock external services
@pytest.fixture
def mock_wordpress_server():
    """Mock WordPress server for testing."""
    responses = {
        '/robots.txt': 'User-agent: *\nAllow: /',
        '/sample-post': '<html><body>Sample content</body></html>',
        '/api/posts': '{"posts": [{"id": 1, "title": "Test"}]}'
    }
    
    with aioresponses() as mock:
        for path, content in responses.items():
            mock.get(f"http://mock-wordpress.com{path}", body=content)
        yield mock

# Parameterized testing
@pytest.mark.parametrize("input_format,expected_output", [
    ("wordpress", "shopify"),
    ("drupal", "shopify"),
    ("custom", "shopify"),
])
def test_format_conversion(input_format, expected_output, converter):
    """Test conversion between different formats."""
    result = converter.convert(input_format)
    assert result.format == expected_output
```

**Testing Best Practices:**
- **Test Isolation**: Each test should be independent
- **Descriptive Names**: Test names should explain what they verify
- **Arrange-Act-Assert**: Clear test structure
- **Mock External Dependencies**: Don't test third-party services
- **Test Data Management**: Use fixtures for reusable test data
- **Coverage Goals**: Aim for >85% code coverage
- **Performance Benchmarks**: Set performance expectations
- **Error Condition Testing**: Test failure scenarios

**CI/CD Integration:**
```bash
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --disable-warnings
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=85
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    performance: marks tests as performance tests
    e2e: marks tests as end-to-end tests
```

### 6. Web Scraping Ethics & Legal Compliance
Responsible scraping practices are essential for sustainable automation:

**Legal and Ethical Guidelines:**
- **robots.txt Compliance**: Always check and respect robots.txt files
- **Terms of Service**: Review and comply with website ToS before scraping
- **Rate Limiting**: Implement respectful delays between requests
- **Server Load**: Monitor and avoid overwhelming target servers
- **Contact Information**: Include contact details in User-Agent headers
- **Data Privacy**: Comply with GDPR, CCPA, and other privacy regulations
- **Copyright Respect**: Avoid scraping copyrighted content without permission

```python
import requests
from urllib.robotparser import RobotFileParser

class EthicalScraper:
    def __init__(self, base_url: str, user_agent: str = None):
        self.base_url = base_url
        self.user_agent = user_agent or "MyBot/1.0 (+http://example.com/contact)"
        self.rp = RobotFileParser()
        self.rp.set_url(f"{base_url}/robots.txt")
        self.rp.read()
    
    def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        return self.rp.can_fetch(self.user_agent, url)
    
    def respectful_request(self, url: str, delay: float = 1.0):
        """Make request with proper delay and headers."""
        if not self.can_fetch(url):
            logger.warning(f"robots.txt disallows fetching {url}")
            return None
            
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        time.sleep(delay)  # Respectful delay
        return requests.get(url, headers=headers)
```

**Data Privacy Checklist:**
- [ ] Obtain necessary permissions for data collection
- [ ] Implement data minimization (only collect what's needed)
- [ ] Provide clear data usage disclosure
- [ ] Offer opt-out mechanisms
- [ ] Secure data storage and transmission
- [ ] Regular data cleanup and retention policies

### 7. Enhanced Security & Data Validation
Comprehensive security measures for production scrapers:

**Input Validation with Pydantic:**
```python
from pydantic import BaseModel, validator, AnyHttpUrl
from typing import List
import bleach
from urllib.parse import urlparse

class ScrapingRequest(BaseModel):
    urls: List[AnyHttpUrl]
    output_format: str = 'html'
    max_pages: int = 100
    
    @validator('urls')
    def validate_urls(cls, v):
        allowed_domains = ['wordpress.com', 'csfrace.com']
        for url in v:
            parsed = urlparse(str(url))
            if parsed.netloc not in allowed_domains:
                raise ValueError(f'Domain {parsed.netloc} not allowed')
        return v
    
    @validator('output_format')
    def validate_output_format(cls, v):
        allowed_formats = ['html', 'json', 'markdown']
        if v not in allowed_formats:
            raise ValueError(f'Format {v} not supported')
        return v

# Content sanitization
class ContentSanitizer:
    def __init__(self):
        self.allowed_tags = [
            'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote'
        ]
        self.allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title'],
            'div': ['class']
        }
    
    def sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content to prevent XSS attacks."""
        return bleach.clean(
            html_content,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True
        )
```

**Security Checklist for Scrapers:**
- [ ] Input validation on all user inputs
- [ ] URL validation and domain whitelisting
- [ ] File path traversal prevention
- [ ] SSRF prevention measures
- [ ] Dependency vulnerability scanning with `safety`
- [ ] Secret scanning in code with `detect-secrets`
- [ ] Rate limiting implementation
- [ ] Request size limits
- [ ] Output sanitization with `bleach`
- [ ] HTTPS enforcement
- [ ] Secure headers in responses
- [ ] Authentication and authorization
- [ ] Audit logging for security events

### 7. Async/Concurrent Programming Standards
Modern scrapers should leverage asynchronous programming for optimal performance:

```python
import asyncio
import aiohttp
from typing import List, AsyncGenerator

class AsyncConverter:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> str:
        """Async page fetching with semaphore control."""
        async with self.semaphore:
            async with session.get(url) as response:
                return await response.text()
    
    async def process_urls(self, urls: List[str]) -> List[str]:
        """Process multiple URLs concurrently."""
        connector = aiohttp.TCPConnector(
            limit=100,           # Total connection pool size
            limit_per_host=10,   # Per-host connection limit
            ttl_dns_cache=300,   # DNS cache TTL
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'MyBot/1.0'}
        ) as session:
            tasks = [self.fetch_page(session, url) for url in urls]
            return await asyncio.gather(*tasks, return_exceptions=True)
```

**Async Best Practices:**
- Use `asyncio.Semaphore` to limit concurrent connections
- Implement proper connection pooling with `aiohttp.TCPConnector`
- Set appropriate timeouts for different operations
- Handle exceptions gracefully in async contexts
- Use `async with` for proper resource cleanup
- Prefer `asyncio.gather()` for parallel tasks
- Implement backpressure mechanisms for large datasets

**Error Handling in Async:**
```python
async def safe_fetch(self, session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            else:
                logger.warning(f"HTTP {response.status} for {url}")
                return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"Client error for {url}: {e}")
        return None
```

### 9. Retry & Resilience Patterns
Implement robust retry mechanisms for handling transient failures:

```python
import asyncio
import random
from typing import Any, Callable, Optional
from functools import wraps

class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

async def retry_with_exponential_backoff(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs
) -> Any:
    """Retry function with exponential backoff and jitter."""
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt == config.max_attempts - 1:
                break
                
            delay = min(
                config.base_delay * (config.backoff_factor ** attempt),
                config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(
                f"Attempt {attempt + 1} failed: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)
    
    raise last_exception

class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Reset circuit breaker on success."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

class BulkheadPattern:
    """Isolate resources to prevent cascade failures."""
    def __init__(self, max_concurrent_operations: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent_operations)
    
    async def execute(self, func: Callable, *args, **kwargs):
        """Execute function with resource isolation."""
        async with self.semaphore:
            return await func(*args, **kwargs)
```

**Resilience Best Practices:**
- **Exponential Backoff**: Increase delay between retries exponentially
- **Jitter**: Add randomness to prevent thundering herd problems
- **Circuit Breaker**: Fail fast when service is consistently unavailable
- **Bulkhead Pattern**: Isolate resources to prevent cascade failures
- **Timeout Hierarchies**: Set different timeouts for different operations
- **Graceful Degradation**: Provide fallback functionality when possible

### 10. Monitoring & Observability Standards
Implement comprehensive monitoring for production-ready scrapers:

**Structured Logging:**
```python
import structlog
import sys
from typing import Dict, Any

def configure_logging():
    """Configure structured logging with correlation IDs."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() 
            else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

**Metrics Collection:**
```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
REQUESTS_TOTAL = Counter('scraper_requests_total', 'Total requests', ['status'])
REQUEST_DURATION = Histogram('scraper_request_duration_seconds', 'Request duration')
ACTIVE_REQUESTS = Gauge('scraper_active_requests', 'Active requests')

class MetricsCollector:
    def time_request(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            ACTIVE_REQUESTS.inc()
            try:
                result = await func(*args, **kwargs)
                REQUEST_DURATION.observe(time.time() - start_time)
                REQUESTS_TOTAL.labels(status='success').inc()
                return result
            except Exception as e:
                REQUESTS_TOTAL.labels(status='error').inc()
                raise
            finally:
                ACTIVE_REQUESTS.dec()
        return wrapper
```

**SLI/SLO Definitions:**
- **Availability SLO**: 99.9% uptime (43.8 minutes downtime/month)
- **Latency SLI**: 95% of requests complete within 5 seconds
- **Error Rate SLI**: Less than 1% of requests result in errors
- **Throughput SLI**: Process at least 1000 URLs per hour

### 8. Performance Optimizations
- **Session Reuse**: Use requests.Session() or aiohttp.ClientSession() for connection pooling
- **Lazy Loading**: Load large resources only when needed
- **Batch Processing**: Process multiple items efficiently
- **Caching**: Consider caching frequently accessed data
- **Async Operations**: Use `asyncio` and `aiohttp` for concurrent downloads
- **Memory Management**: Use generators for large datasets
- **Connection Pooling**: Configure appropriate pool sizes

### 12. Enhanced Configuration Management
Robust configuration system with validation and environment support:

```python
# config/models.py
from pydantic import BaseSettings, validator
from typing import List, Optional
import yaml

class ScraperConfig(BaseSettings):
    # Core settings
    concurrent_requests: int = 10
    request_timeout: int = 30
    retry_attempts: int = 3
    backoff_factor: float = 2.0
    
    # Rate limiting
    requests_per_second: int = 10
    burst_size: int = 20
    respect_robots_txt: bool = True
    
    # Output settings
    output_formats: List[str] = ['html', 'json']
    compression_enabled: bool = True
    output_directory: str = 'output'
    
    # Monitoring
    metrics_enabled: bool = True
    log_level: str = 'INFO'
    structured_logging: bool = True
    
    @validator('requests_per_second')
    def validate_rate_limit(cls, v):
        if v <= 0:
            raise ValueError('requests_per_second must be positive')
        return v
    
    class Config:
        env_prefix = 'SCRAPER_'
        case_sensitive = False

# config/loader.py
class ConfigLoader:
    def __init__(self, config_path: str = None, environment: str = 'default'):
        self.config_path = config_path or f'config/{environment}.yaml'
        
    def load_config(self) -> ScraperConfig:
        """Load configuration from YAML file and environment variables."""
        config_data = {}
        
        # Load from YAML file
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
        except FileNotFoundError:
            pass  # Use defaults
            
        return ScraperConfig(**config_data)
```

**Configuration Files:**
```yaml
# config/default.yaml
scraper:
  concurrent_requests: 5
  request_timeout: 30
  retry_attempts: 3
  backoff_factor: 2.0

rate_limiting:
  requests_per_second: 10
  burst_size: 20
  respect_robots_txt: true

output:
  formats: ['html', 'json', 'markdown']
  compression_enabled: true
  output_directory: 'converted_content'

monitoring:
  metrics_enabled: true
  log_level: 'INFO'
  structured_logging: true
  
# config/production.yaml
scraper:
  concurrent_requests: 20
  request_timeout: 45
  
rate_limiting:
  requests_per_second: 50
  
monitoring:
  log_level: 'WARNING'
```

### 9. Logging Best Practices
```python
import logging
from pathlib import Path

def setup_logging(log_level=logging.INFO):
    """Configure logging for the application."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # File handler
    file_handler = logging.FileHandler("converter.log")
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Root logger configuration
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )
```

### 10. CLI Enhancement Suggestions
- Add `--verbose` flag for detailed output
- Implement `--dry-run` mode to preview without downloading
- Support `--config` flag for configuration files
- Add `--batch` mode for processing multiple URLs from a file
- Include `--no-images` flag to skip image downloads
- Provide `--format` option for output formats (HTML, Markdown)

### 11. Scraper-Specific Package Structure
Optimized project structure for modern Python scrapers:

```
csfrace-scrape/
├── src/
│   ├── __init__.py
│   ├── core/                    # Core business logic
│   │   ├── __init__.py
│   │   ├── base_scraper.py      # Abstract base scraper
│   │   ├── session_manager.py   # HTTP session management
│   │   └── rate_limiter.py      # Rate limiting logic
│   ├── scrapers/                # Scraper implementations
│   │   ├── __init__.py
│   │   ├── wordpress_scraper.py
│   │   ├── shopify_scraper.py
│   │   └── generic_scraper.py
│   ├── parsers/                 # HTML/content parsers
│   │   ├── __init__.py
│   │   ├── html_parser.py
│   │   ├── metadata_extractor.py
│   │   └── content_converter.py
│   ├── validators/              # Data validators
│   │   ├── __init__.py
│   │   ├── url_validator.py
│   │   ├── content_validator.py
│   │   └── schema_validator.py
│   ├── exporters/               # Output formatters
│   │   ├── __init__.py
│   │   ├── html_exporter.py
│   │   ├── json_exporter.py
│   │   └── markdown_exporter.py
│   ├── monitoring/              # Observability
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   ├── logging_config.py
│   │   └── health_checks.py
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── async_utils.py
│       ├── text_processing.py
│       └── file_utils.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── performance/
│   ├── e2e/
│   └── fixtures/
├── config/
│   ├── default.yaml
│   ├── development.yaml
│   ├── production.yaml
│   └── test.yaml
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── docs/
│   ├── api/
│   ├── deployment/
│   └── examples/
├── scripts/
│   ├── setup.sh
│   ├── test.sh
│   └── deploy.sh
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── cd.yml
│       └── security-scan.yml
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   ├── prod.txt
│   └── test.txt
├── pyproject.toml           # Modern Python packaging
├── README.md
├── CLAUDE.md
├── .gitignore
└── main.py                  # CLI entry point
```

### 12. Dependencies Management
- Pin exact versions in `requirements.txt` for production
- Use `requirements-dev.txt` for development dependencies
- Consider using `pipenv` or `poetry` for dependency management
- Regular security updates with `pip-audit`

### 13. Git Workflow
- Use meaningful commit messages
- Follow conventional commits format
- Create feature branches for new functionality
- Use `.gitignore` to exclude:
  - `__pycache__/`
  - `*.pyc`
  - `.env`
  - `converted_content/`
  - `*.log`

### 16. Development Environment Setup
Complete development environment configuration:

**Python Environment Management:**
```bash
# Install pyenv for Python version management
curl https://pyenv.run | bash

# Install Python 3.11
pyenv install 3.11.0
pyenv local 3.11.0

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements/dev.txt
```

**Pre-commit Hooks Setup:**
```bash
# Install pre-commit
python -m pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

**Pre-commit Configuration (.pre-commit-config.yaml):**
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100, --max-complexity=10]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]
  
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, src/]
  
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

**Development Commands:**

**IMPORTANT: Use `uv` for all environments (local, CI/CD, Docker) as it's now the recommended standard for modern Python development in 2025. uv provides 40% faster builds, better security, and smaller images:**

```bash
# Install dependencies
uv sync

# Run the converter
uv run python -m src.main <wordpress-url>

# Run with configuration file
uv run python -m src.main --config config/development.yaml

# Run tests
uv run python -m pytest tests/ -v --cov=src --cov-report=html

# Run specific test categories
uv run python -m pytest tests/unit/ -m "not slow"
uv run python -m pytest tests/integration/ --maxfail=1
uv run python -m pytest tests/performance/ --benchmark-only

# Code quality checks
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run bandit -r src/

# Format code
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/

# Build documentation
uv run sphinx-build -b html docs/ docs/_build/

# Build Docker image
docker build -t csfrace-scraper .

# Run with Docker Compose
docker-compose up -d

# Performance profiling
uv run python -m cProfile -o profile.stats src/main.py <url>
uv run python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(10)"
```

**CI/CD Commands (production-ready with uv):**
```bash
# Modern CI/CD with uv (40% faster builds)
uv sync --frozen --no-editable
uv run pytest tests/ -v --cov=src --cov-report=html
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run bandit -r src/
```

**IDE Configuration (.vscode/settings.json):**
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.linting.banditEnabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length=100"],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"]
}
```

**Environment Variables (.env.example):**
```bash
# Application settings
SCRAPER_LOG_LEVEL=INFO
SCRAPER_CONCURRENT_REQUESTS=10
SCRAPER_REQUEST_TIMEOUT=30

# Database settings (if using)
DATABASE_URL=postgresql://user:pass@localhost:5432/scraper

# Redis settings (if using)
REDIS_URL=redis://localhost:6379/0

# Monitoring settings
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
PROMETHEUS_METRICS_PORT=9090

# External API keys (if needed)
WORDPRESS_API_KEY=your-api-key
SHOPIFY_API_KEY=your-api-key
```

### 13. Docker & Deployment Standards
Production-ready containerization and deployment:

**Multi-stage Dockerfile:**
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements/ ./requirements/
RUN pip install --user --no-cache-dir -r requirements/prod.txt

# Production stage
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r scraper && useradd -r -g scraper scraper

# Copy dependencies from builder stage
COPY --from=builder /root/.local /home/scraper/.local

# Set up application
WORKDIR /app
COPY --chown=scraper:scraper . .

# Update PATH
ENV PATH=/home/scraper/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Switch to non-root user
USER scraper

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose for Development:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  scraper:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - SCRAPER_LOG_LEVEL=DEBUG
      - SCRAPER_METRICS_ENABLED=true
    volumes:
      - ./output:/app/output
      - ./logs:/app/logs
    depends_on:
      - redis
      - postgres
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: scraper
      POSTGRES_USER: scraper
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  redis_data:
  postgres_data:
```

### 14. CI/CD Pipeline Requirements
Automated testing and deployment pipeline:

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Cache pip packages
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements/*.txt') }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements/dev.txt
    
    - name: Lint with flake8
      run: |
        flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 src/ tests/ --count --max-complexity=10 --max-line-length=100
    
    - name: Format check with black
      run: black --check src/ tests/
    
    - name: Type check with mypy
      run: mypy src/
    
    - name: Security scan with bandit
      run: bandit -r src/
    
    - name: Dependency check with safety
      run: safety check
    
    - name: Run unit tests
      run: |
        pytest tests/unit/ --cov=src --cov-report=xml --cov-report=term-missing
    
    - name: Run integration tests
      run: pytest tests/integration/
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'
    
    - name: Upload Trivy scan results to GitHub Security tab
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  deploy:
    needs: [test, security]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push Docker image
      env:
        DOCKER_REGISTRY: ${{ secrets.DOCKER_REGISTRY }}
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build -t $DOCKER_REGISTRY/scraper:$IMAGE_TAG .
        docker push $DOCKER_REGISTRY/scraper:$IMAGE_TAG
```

### 15. Performance Benchmarking Standards
Systematic performance monitoring and optimization:

```python
# Performance testing with pytest-benchmark
import pytest
import asyncio
from memory_profiler import profile
import cProfile
import pstats
from typing import List

class PerformanceBenchmark:
    @pytest.mark.benchmark(group="parsing")
    def test_html_parsing_performance(self, benchmark, sample_html):
        """Benchmark HTML parsing performance."""
        parser = HTMLParser()
        result = benchmark(parser.parse, sample_html)
        assert result is not None
    
    @pytest.mark.benchmark(group="conversion")
    def test_content_conversion_performance(self, benchmark, wordpress_content):
        """Benchmark content conversion speed."""
        converter = ContentConverter()
        result = benchmark(converter.convert, wordpress_content)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_scraping_performance(self):
        """Test performance with concurrent requests."""
        scraper = AsyncScraper(max_concurrent=10)
        urls = [f"http://example.com/page{i}" for i in range(100)]
        
        start_time = time.time()
        results = await scraper.scrape_multiple(urls)
        execution_time = time.time() - start_time
        
        # Performance assertions
        assert execution_time < 30.0  # Should complete within 30 seconds
        assert len(results) == 100
        assert sum(1 for r in results if r is not None) >= 95  # 95% success rate
    
    @profile
    def test_memory_usage_large_dataset(self):
        """Profile memory usage with large datasets."""
        large_dataset = ['content'] * 10000
        processor = BatchProcessor()
        results = processor.process_batch(large_dataset)
        return results
    
    def test_cpu_profiling(self):
        """Profile CPU usage of critical functions."""
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Run the code to profile
        scraper = Scraper()
        scraper.process_complex_page(sample_complex_html)
        
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(10)  # Show top 10 functions
```

## Future Enhancements Roadmap
**Priority 1 - Critical for Production:**
1. **Async/Concurrent Processing** - Implement aiohttp + asyncio
2. **Robust Error Recovery** - Exponential backoff, circuit breaker
3. **Comprehensive Testing Suite** - Unit, integration, performance tests
4. **Advanced Rate Limiting** - Token bucket, robots.txt compliance

**Priority 2 - Important for Reliability:**
5. **Session & Cookie Management** - Persistent sessions, auth support
6. **Content Validation** - Schema validation, XSS prevention
7. **Performance Monitoring** - Metrics collection, profiling
8. **Enhanced CLI** - Interactive mode, config file support

**Priority 3 - Nice to Have Features:**
9. **Data Pipeline Architecture** - Queue-based processing
10. **Advanced Parsing** - JavaScript rendering, dynamic content
11. **Multiple Output Formats** - JSON, CSV, Markdown export
12. **Observability** - Structured logging, OpenTelemetry

**Priority 4 - Future Enhancements:**
13. **Machine Learning Features** - Content classification, auto-tagging
14. **Distributed Scraping** - Celery, Kubernetes job scheduling
15. **API & Web Interface** - REST API, admin dashboard

## Quality Checklist
Before committing code, ensure:
- [ ] Code follows PEP 8 style guide
- [ ] All functions have docstrings
- [ ] Type hints are implemented
- [ ] Error handling is comprehensive
- [ ] Tests are written and passing
- [ ] No hardcoded values or credentials
- [ ] Logging is used instead of print statements
- [ ] Code is DRY (Don't Repeat Yourself)
- [ ] Complex logic is well-commented
- [ ] README is updated if functionality changes