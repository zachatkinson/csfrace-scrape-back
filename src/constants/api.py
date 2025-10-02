"""API-related constants for PERFECT SRP compliance.

ZERO TOLERANCE for mixing domains - only API constants here.
Single source of truth for ALL API-related configuration.
"""

from src.core.environment import EnvironmentLoader

# HTTP Configuration - with validation
DEFAULT_TIMEOUT: int = EnvironmentLoader.get_int("DEFAULT_TIMEOUT", 30, min_value=1, max_value=300)
MAX_CONCURRENT: int = EnvironmentLoader.get_int("MAX_CONCURRENT", 10, min_value=1, max_value=100)
MAX_RETRIES: int = EnvironmentLoader.get_int("MAX_RETRIES", 3, min_value=0, max_value=10)
BACKOFF_FACTOR: float = float(EnvironmentLoader.get_optional("BACKOFF_FACTOR", "2.0"))
RATE_LIMIT_DELAY: float = float(EnvironmentLoader.get_optional("RATE_LIMIT_DELAY", "0.5"))

# User Agent
DEFAULT_USER_AGENT: str = EnvironmentLoader.get_optional(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

# Timeout configurations
CONNECTION_TIMEOUT: float = float(EnvironmentLoader.get_optional("CONNECTION_TIMEOUT", "10.0"))
READ_TIMEOUT: float = float(EnvironmentLoader.get_optional("READ_TIMEOUT", "30.0"))
TOTAL_TIMEOUT: float = float(EnvironmentLoader.get_optional("TOTAL_TIMEOUT", "60.0"))
ROBOTS_TIMEOUT: int = EnvironmentLoader.get_int("ROBOTS_TIMEOUT", 10, min_value=1, max_value=60)

# HTTP Status codes
HTTP_STATUS_OK: int = 200
HTTP_STATUS_NOT_FOUND: int = 404
HTTP_STATUS_SERVER_ERROR: int = 500

# API Error Messages
ERROR_INTERNAL_SERVER: str = "Internal server error"
ERROR_TYPE_INTERNAL: str = "internal_error"

# Development server configuration
LOCALHOST_IP: str = "127.0.0.1"
DEFAULT_API_PORT: int = EnvironmentLoader.get_int("API_PORT", 8000, min_value=1024, max_value=65535)
ALLOWED_ORIGINS_DEFAULT: str = EnvironmentLoader.get_optional(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:3010"
)

# API Validation Constants - All validation limits centralized
API_MAX_RETRIES_LIMIT: int = 10  # Maximum allowed retry attempts
API_MIN_TIMEOUT_SECONDS: int = 5  # Minimum timeout value
API_MAX_TIMEOUT_SECONDS: int = 300  # Maximum timeout value (5 minutes)

# Batch validation limits
API_MAX_NAME_LENGTH: int = 255  # Maximum batch name length
API_MAX_URLS_PER_BATCH: int = 1000  # Maximum URLs in a single batch
API_MAX_CONCURRENT_JOBS: int = 20  # Maximum concurrent job processing

# Database and pagination limits
API_DEFAULT_PAGE_SIZE: int = 50  # Default pagination page size
API_MAX_PAGE_SIZE: int = 200  # Maximum allowed page size
API_DEFAULT_LIMIT: int = 100  # Default query limit

# URLs - NO hardcoding allowed anywhere else
DEFAULT_BASE_URL: str = EnvironmentLoader.get_url("BASE_URL", "https://example.com")
TEST_BASE_URL: str = EnvironmentLoader.get_url("TEST_URL", "https://test.example.com")

# Domain configuration for link processing
TARGET_DOMAIN: str = EnvironmentLoader.get_optional("TARGET_DOMAIN", "csfrace.com")

# Protocol constants
HTTP_PROTOCOL: str = "http://"
HTTPS_PROTOCOL: str = "https://"

# Special domains
LOCALHOST_DOMAIN: str = "localhost"

# Example URLs for help text
EXAMPLE_CSFRACE_URL: str = "https://csfrace.com/blog/sample-post"
EXAMPLE_SITE_URL: str = "https://site.com"

# CLI Constants
DEFAULT_PROMETHEUS_URL: str = EnvironmentLoader.get_url(
    "DEFAULT_PROMETHEUS_URL", "http://prometheus:9090"
)
DEFAULT_GRAFANA_PORT: int = EnvironmentLoader.get_int(
    "DEFAULT_GRAFANA_PORT", 3000, min_value=1024, max_value=65535
)

# Test Constants
BASE_TEST_URL: str = "https://test.example.com"
SAMPLE_POST_URL: str = f"{BASE_TEST_URL}/blog/sample-post"
LARGE_CONTENT_URL: str = f"{BASE_TEST_URL}/large-content"
NONEXISTENT_URL: str = "https://nonexistent.example.com/blog/post"
SLOW_URL: str = "https://slow.example.com/blog/post"

# Test file patterns
SAMPLE_IMAGE_URL: str = "/sample-image.jpg"
SAMPLE_HTML_TITLE: str = "Test Blog Post"
SAMPLE_HTML_DESCRIPTION: str = "A test blog post for unit testing"
