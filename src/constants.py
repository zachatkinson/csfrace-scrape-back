"""Centralized constants and configuration for the WordPress to Shopify converter.

This module contains ALL constants used throughout the application.
NO hardcoded values should exist in business logic - everything must be here.
"""

from dataclasses import dataclass, field
from os import environ


@dataclass(frozen=True)
class AppConstants:
    """Application-wide constants with environment variable support."""

    # URLs - NO hardcoding allowed anywhere else
    DEFAULT_BASE_URL: str = environ.get("BASE_URL", "https://example.com")
    TEST_BASE_URL: str = environ.get("TEST_URL", "https://test.example.com")
    # Domain configuration for link processing
    TARGET_DOMAIN: str = environ.get("TARGET_DOMAIN", "csfrace.com")
    # Protocol constants
    HTTP_PROTOCOL: str = "http://"
    HTTPS_PROTOCOL: str = "https://"
    # Special domains
    LOCALHOST_DOMAIN: str = "localhost"

    # Paths - configurable via environment
    DEFAULT_OUTPUT_DIR: str = environ.get("OUTPUT_DIR", "converted_content")
    # Sub-directory name is a constant (part of app logic)
    DEFAULT_IMAGES_DIR: str = "images"

    # HTTP Configuration
    DEFAULT_TIMEOUT: int = int(environ.get("DEFAULT_TIMEOUT", "30"))
    MAX_CONCURRENT: int = int(environ.get("MAX_CONCURRENT", "10"))
    MAX_RETRIES: int = int(environ.get("MAX_RETRIES", "3"))
    BACKOFF_FACTOR: float = float(environ.get("BACKOFF_FACTOR", "2.0"))
    RATE_LIMIT_DELAY: float = float(environ.get("RATE_LIMIT_DELAY", "0.5"))

    # User Agent
    DEFAULT_USER_AGENT: str = environ.get(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    # File Names - centralized file naming (constants, not configurable)
    METADATA_FILE: str = "metadata.txt"
    HTML_FILE: str = "converted_content.html"
    SHOPIFY_FILE: str = "shopify_ready_content.html"

    # Cache Configuration
    DEFAULT_TTL: int = int(environ.get("DEFAULT_TTL", "1800"))  # 30 minutes
    CACHE_TTL_HTML: int = int(environ.get("CACHE_TTL_HTML", "1800"))  # 30 minutes for HTML
    CACHE_TTL_IMAGES: int = int(environ.get("CACHE_TTL_IMAGES", "86400"))  # 24 hours for images
    CACHE_TTL_METADATA: int = int(environ.get("CACHE_TTL_METADATA", "3600"))  # 1 hour for metadata
    MAX_CACHE_SIZE_MB: int = int(environ.get("MAX_CACHE_SIZE_MB", "1000"))  # 1GB max cache
    REDIS_HOST: str = environ.get("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(environ.get("REDIS_PORT", "6379"))
    REDIS_DB: int = int(environ.get("REDIS_DB", "0"))
    REDIS_KEY_PREFIX: str = environ.get("REDIS_KEY_PREFIX", "wp_converter:")
    # Redis connection timeouts - configurable for different environments
    REDIS_SOCKET_CONNECT_TIMEOUT: float = float(environ.get("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0"))
    REDIS_SOCKET_TIMEOUT: float = float(environ.get("REDIS_SOCKET_TIMEOUT", "5.0"))

    # Robots.txt Configuration
    ROBOTS_CACHE_DURATION: int = int(environ.get("ROBOTS_CACHE_DURATION", "3600"))  # 1 hour
    RESPECT_ROBOTS_TXT: bool = environ.get("RESPECT_ROBOTS_TXT", "true").lower() == "true"

    # Shopify-compatible CSS classes to preserve
    SHOPIFY_PRESERVE_CLASSES: frozenset = frozenset(
        [
            "center",
            "media-grid",
            "media-grid-2",
            "media-grid-4",
            "media-grid-5",
            "media-grid-text-box",
            "testimonial-quote",
            "group",
            "quote-container",
            "button",
            "button--full-width",
            "button--primary",
            "press-release-button",
        ]
    )

    # Content type mappings for images - immutable mapping
    IMAGE_CONTENT_TYPES: dict[str, str] = field(
        default_factory=lambda: {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
        }
    )
    # Default image extension when content type is unknown
    DEFAULT_IMAGE_EXTENSION: str = ".jpg"

    # Common numerical constants
    BYTES_PER_MB: int = 1024 * 1024  # Byte to MB conversion
    CACHE_CLEANUP_RATIO: float = 0.8  # Clean to 80% of max size

    # Cache and key management
    MAX_KEY_LENGTH: int = int(environ.get("MAX_KEY_LENGTH", "250"))  # Maximum cache key length
    HASH_LENGTH: int = 16  # Standard hash truncation length
    KEY_READABLE_OFFSET: int = 20  # Offset for readable part in long keys
    SAMPLE_KEY_COUNT: int = 10  # Number of sample keys for statistics
    FILE_READ_BUFFER_SIZE: int = 1024  # Buffer size for file reading

    # HTTP Status codes
    HTTP_STATUS_OK: int = 200
    HTTP_STATUS_NOT_FOUND: int = 404
    HTTP_STATUS_SERVER_ERROR: int = 500

    # Timeout configurations
    ROBOTS_TIMEOUT: int = int(environ.get("ROBOTS_TIMEOUT", "10"))  # Robots.txt fetch timeout

    # SEO and content analysis constants
    WORDS_PER_MINUTE_READING: int = 200  # Average reading speed
    IFRAME_ASPECT_RATIO: str = "16/9"  # Standard video aspect ratio

    # Progress tracking constants
    PROGRESS_START: int = 0
    PROGRESS_SETUP: int = 10
    PROGRESS_FETCH: int = 20
    PROGRESS_PROCESS: int = 60
    PROGRESS_COMPLETE: int = 100

    # Logging level constants
    LOG_LEVEL_INFO: int = 20  # INFO logging level

    # Logging Configuration
    LOG_LEVEL: str = environ.get("LOG_LEVEL", "INFO")  # Configurable via env
    # Log format is a constant (standardized format)
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


# Global constants instance
CONSTANTS = AppConstants()


@dataclass(frozen=True)
class TestConstants:
    """Constants specifically for testing - separate from production."""

    # Test URLs - controlled test environment
    BASE_TEST_URL: str = "https://test.example.com"
    SAMPLE_POST_URL: str = f"{BASE_TEST_URL}/blog/sample-post"
    LARGE_CONTENT_URL: str = f"{BASE_TEST_URL}/large-content"
    NONEXISTENT_URL: str = "https://nonexistent.example.com/blog/post"
    SLOW_URL: str = "https://slow.example.com/blog/post"

    # Test Redis Configuration
    TEST_REDIS_HOST: str = "localhost"
    TEST_REDIS_PORT: int = 6379
    TEST_REDIS_DB: int = 15  # Use highest DB for tests
    TEST_REDIS_KEY_PREFIX: str = "pytest:"

    # Test file patterns
    SAMPLE_IMAGE_URL: str = "/sample-image.jpg"
    TEST_IMAGE_CONTENT: bytes = b"fake image data"

    # Test HTML content patterns
    SAMPLE_HTML_TITLE: str = "Test Blog Post"
    SAMPLE_HTML_DESCRIPTION: str = "A test blog post for unit testing"


# Global test constants instance
TEST_CONSTANTS = TestConstants()
