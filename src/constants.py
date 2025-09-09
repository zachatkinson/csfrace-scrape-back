"""Centralized constants and configuration for the WordPress to Shopify converter.

This module contains ALL constants used throughout the application.
NO hardcoded values should exist in business logic - everything must be here.
"""

from .core.environment import EnvironmentLoader

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

# Paths - configurable via environment
DEFAULT_OUTPUT_DIR: str = EnvironmentLoader.get_optional("OUTPUT_DIR", "converted_content")
DEFAULT_IMAGES_DIR: str = "images"  # Sub-directory name is a constant (part of app logic)

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

# File Names - centralized file naming (constants, not configurable)
METADATA_FILE: str = "metadata.txt"
HTML_FILE: str = "converted_content.html"
SHOPIFY_FILE: str = "shopify_ready_content.html"

# Cache Configuration - with validation
DEFAULT_TTL: int = EnvironmentLoader.get_int("DEFAULT_TTL", 1800, min_value=60)  # 30 minutes
CACHE_TTL_HTML: int = EnvironmentLoader.get_int(
    "CACHE_TTL_HTML", 1800, min_value=60
)  # 30 minutes for HTML
CACHE_TTL_IMAGES: int = EnvironmentLoader.get_int(
    "CACHE_TTL_IMAGES", 86400, min_value=300
)  # 24 hours for images
CACHE_TTL_METADATA: int = EnvironmentLoader.get_int(
    "CACHE_TTL_METADATA", 3600, min_value=60
)  # 1 hour for metadata
MAX_CACHE_SIZE_MB: int = EnvironmentLoader.get_int(
    "MAX_CACHE_SIZE_MB", 1000, min_value=100
)  # 1GB max cache

# Cache backend configuration
CACHE_BACKEND: str = EnvironmentLoader.get_optional("CACHE_BACKEND", "file")  # file, redis, memory

REDIS_HOST: str = EnvironmentLoader.get_optional("REDIS_HOST", "localhost")
REDIS_PORT: int = EnvironmentLoader.get_int("REDIS_PORT", 6379, min_value=1, max_value=65535)
REDIS_DB: int = EnvironmentLoader.get_int("REDIS_DB", 0, min_value=0, max_value=15)
REDIS_KEY_PREFIX: str = EnvironmentLoader.get_optional("REDIS_KEY_PREFIX", "wp_converter:")

# Redis connection timeouts - configurable for different environments
REDIS_SOCKET_CONNECT_TIMEOUT: float = float(
    EnvironmentLoader.get_optional("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0")
)
REDIS_SOCKET_TIMEOUT: float = float(EnvironmentLoader.get_optional("REDIS_SOCKET_TIMEOUT", "5.0"))

# Robots.txt Configuration
ROBOTS_CACHE_DURATION: int = EnvironmentLoader.get_int(
    "ROBOTS_CACHE_DURATION", 3600, min_value=300
)  # 1 hour
RESPECT_ROBOTS_TXT: bool = EnvironmentLoader.get_bool("RESPECT_ROBOTS_TXT", True)

# Shopify-compatible CSS classes to preserve
SHOPIFY_PRESERVE_CLASSES: frozenset[str] = frozenset(
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
IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

# Default image extension when content type is unknown
DEFAULT_IMAGE_EXTENSION: str = ".jpg"

# Common numerical constants
BYTES_PER_MB: int = 1024 * 1024  # Byte to MB conversion
CACHE_CLEANUP_RATIO: float = 0.8  # Clean to 80% of max size

# Cache and key management
MAX_KEY_LENGTH: int = EnvironmentLoader.get_int(
    "MAX_KEY_LENGTH", 250, min_value=50, max_value=2000
)  # Maximum cache key length
HASH_LENGTH: int = 16  # Standard hash truncation length
KEY_READABLE_OFFSET: int = 20  # Offset for readable part in long keys
SAMPLE_KEY_COUNT: int = 10  # Number of sample keys for statistics
FILE_READ_BUFFER_SIZE: int = 1024  # Buffer size for file reading

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
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:4321"
)

# Timeout configurations
ROBOTS_TIMEOUT: int = EnvironmentLoader.get_int(
    "ROBOTS_TIMEOUT", 10, min_value=1, max_value=60
)  # Robots.txt fetch timeout

# HTTP timeouts
CONNECTION_TIMEOUT: float = float(EnvironmentLoader.get_optional("CONNECTION_TIMEOUT", "10.0"))
READ_TIMEOUT: float = float(EnvironmentLoader.get_optional("READ_TIMEOUT", "30.0"))
TOTAL_TIMEOUT: float = float(EnvironmentLoader.get_optional("TOTAL_TIMEOUT", "60.0"))

# Browser timeouts
BROWSER_TIMEOUT: float = float(EnvironmentLoader.get_optional("BROWSER_TIMEOUT", "30.0"))
PAGE_LOAD_TIMEOUT: float = float(EnvironmentLoader.get_optional("PAGE_LOAD_TIMEOUT", "30.0"))
SCRIPT_TIMEOUT: float = float(EnvironmentLoader.get_optional("SCRIPT_TIMEOUT", "10.0"))

# Rendering timeouts
RENDER_TIMEOUT: float = float(EnvironmentLoader.get_optional("RENDER_TIMEOUT", "60.0"))
SCREENSHOT_TIMEOUT: float = float(EnvironmentLoader.get_optional("SCREENSHOT_TIMEOUT", "10.0"))

# Network timeouts
DNS_TIMEOUT: float = float(EnvironmentLoader.get_optional("DNS_TIMEOUT", "5.0"))
KEEPALIVE_TIMEOUT: float = float(EnvironmentLoader.get_optional("KEEPALIVE_TIMEOUT", "30.0"))

# Progress tracking constants
PROGRESS_START: int = 0
PROGRESS_SETUP: int = 10
PROGRESS_FETCH: int = 20
PROGRESS_PROCESS: int = 60
PROGRESS_COMPLETE: int = 100

# SEO and content analysis constants
WORDS_PER_MINUTE_READING: int = 200  # Average reading speed
IFRAME_ASPECT_RATIO: str = "16/9"  # Standard video aspect ratio

# Logging level constants
LOG_LEVEL_INFO: int = 20  # INFO logging level

# Logging Configuration
LOG_LEVEL: str = EnvironmentLoader.get_optional("LOG_LEVEL", "INFO")  # Configurable via env
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Test Constants
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

# CLI Constants
DEFAULT_PROMETHEUS_URL: str = EnvironmentLoader.get_url(
    "DEFAULT_PROMETHEUS_URL", "http://prometheus:9090"
)
DEFAULT_GRAFANA_PORT: int = EnvironmentLoader.get_int(
    "DEFAULT_GRAFANA_PORT", 3000, min_value=1024, max_value=65535
)

# Example URLs for help text
EXAMPLE_CSFRACE_URL: str = "https://csfrace.com/blog/sample-post"
EXAMPLE_SITE_URL: str = "https://site.com"

# Progress display
PROGRESS_SEPARATOR: str = "-" * 50

# Exit codes
EXIT_CODE_KEYBOARD_INTERRUPT: int = 130

# API Validation Constants - All validation limits centralized
# Job validation limits
API_MAX_RETRIES_LIMIT: int = 10  # Maximum allowed retry attempts
API_MIN_TIMEOUT_SECONDS: int = 5  # Minimum timeout value
API_MAX_TIMEOUT_SECONDS: int = 300  # Maximum timeout value (5 minutes)

# Batch validation limits
API_MAX_NAME_LENGTH: int = 255  # Maximum batch name length
API_MAX_URLS_PER_BATCH: int = 1000  # Maximum URLs in a single batch
API_MAX_CONCURRENT_JOBS: int = 20  # Maximum concurrent job processing

# Database and pagination limits
DATABASE_POOL_SIZE: int = EnvironmentLoader.get_int(
    "DATABASE_POOL_SIZE", 20, min_value=5, max_value=100
)
DATABASE_MAX_OVERFLOW: int = EnvironmentLoader.get_int(
    "DATABASE_MAX_OVERFLOW", 30, min_value=10, max_value=200
)
API_DEFAULT_PAGE_SIZE: int = 50  # Default pagination page size
API_MAX_PAGE_SIZE: int = 200  # Maximum allowed page size
API_DEFAULT_LIMIT: int = 100  # Default query limit

# OAuth2 Client Credentials - SECURE Environment Variable Configuration
# These should be set in production - no insecure defaults!
OAUTH_GOOGLE_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_GOOGLE_CLIENT_ID", "")
OAUTH_GOOGLE_CLIENT_SECRET: str = EnvironmentLoader.get_optional("OAUTH_GOOGLE_CLIENT_SECRET", "")

OAUTH_GITHUB_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_GITHUB_CLIENT_ID", "")
OAUTH_GITHUB_CLIENT_SECRET: str = EnvironmentLoader.get_optional("OAUTH_GITHUB_CLIENT_SECRET", "")

OAUTH_MICROSOFT_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_MICROSOFT_CLIENT_ID", "")
OAUTH_MICROSOFT_CLIENT_SECRET: str = EnvironmentLoader.get_optional(
    "OAUTH_MICROSOFT_CLIENT_SECRET", ""
)

# OAuth2 Redirect URIs - Centralized Configuration
OAUTH_REDIRECT_URI_BASE: str = EnvironmentLoader.get_url(
    "OAUTH_REDIRECT_URI_BASE", "http://localhost:8000"
)

# Google OAuth2 Configuration
GOOGLE_AUTHORIZATION_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_USER_INFO_URL: str = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES: list[str] = ["openid", "email", "profile"]

# GitHub OAuth2 Configuration
GITHUB_AUTHORIZATION_URL: str = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL: str = "https://github.com/login/oauth/access_token"  # noqa: S105
GITHUB_USER_INFO_URL: str = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL: str = "https://api.github.com/user/emails"
GITHUB_SCOPES: list[str] = ["user:email"]

# Microsoft OAuth2 Configuration
MICROSOFT_AUTHORIZATION_URL: str = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL: str = (
    "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: S105
)
MICROSOFT_USER_INFO_URL: str = "https://graph.microsoft.com/v1.0/me"
MICROSOFT_SCOPES: list[str] = ["openid", "profile", "email", "User.Read"]

# OAuth2 Security Settings
STATE_TOKEN_LENGTH: int = 32  # Length for OAuth2 state parameter
OAUTH_TIMEOUT: int = EnvironmentLoader.get_int(
    "OAUTH_TIMEOUT", 30, min_value=5, max_value=120
)  # OAuth request timeout
OAUTH_MAX_RETRIES: int = EnvironmentLoader.get_int(
    "OAUTH_MAX_RETRIES", 3, min_value=0, max_value=10
)  # OAuth retry attempts

# Authentication constants
BEARER_TOKEN_TYPE: str = "bearer"  # noqa: S105
PASSWORD_CONTEXT_DEPRECATED: str = "auto"  # noqa: S105

# WebAuthn/Passkeys configuration constants
WEBAUTHN_RP_ID: str = EnvironmentLoader.get_optional("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_RP_NAME: str = EnvironmentLoader.get_optional("WEBAUTHN_RP_NAME", "CSFrace Backend")
WEBAUTHN_ORIGIN: str = EnvironmentLoader.get_url("WEBAUTHN_ORIGIN", "http://localhost:8000")

# Challenge Configuration - Security Settings
CHALLENGE_LENGTH_BYTES: int = 32  # 256-bit challenge (FIDO2 standard)
CHALLENGE_TIMEOUT_MS: int = EnvironmentLoader.get_int(
    "WEBAUTHN_CHALLENGE_TIMEOUT_MS", 60000, min_value=30000, max_value=300000
)  # 1 minute
CHALLENGE_MAX_AGE_MINUTES: int = EnvironmentLoader.get_int(
    "WEBAUTHN_CHALLENGE_MAX_AGE", 10, min_value=1, max_value=60
)  # 10 minutes

# Credential Configuration
MAX_CREDENTIALS_PER_USER: int = EnvironmentLoader.get_int(
    "WEBAUTHN_MAX_CREDENTIALS", 10, min_value=1, max_value=50
)
DEVICE_NAME_MAX_LENGTH: int = 100
CREDENTIAL_ID_LENGTH: int = 64  # Base64URL encoded length

# Authenticator Selection Preferences - FIDO2 Standards
USER_VERIFICATION_REQUIREMENT: str = "preferred"  # preferred, required, discouraged
AUTHENTICATOR_ATTACHMENT: str = "platform"  # platform, cross-platform, or None
REQUIRE_RESIDENT_KEY: bool = False  # For discoverable credentials

# Attestation Configuration
ATTESTATION_CONVEYANCE: str = "none"  # none, indirect, direct, enterprise

# Timeout Configuration
REGISTRATION_TIMEOUT_MS: int = EnvironmentLoader.get_int(
    "WEBAUTHN_REG_TIMEOUT_MS", 60000, min_value=30000, max_value=300000
)
AUTHENTICATION_TIMEOUT_MS: int = EnvironmentLoader.get_int(
    "WEBAUTHN_AUTH_TIMEOUT_MS", 60000, min_value=30000, max_value=300000
)

# Security Settings
ALLOWED_ORIGINS: list[str] = [
    EnvironmentLoader.get_url("WEBAUTHN_ORIGIN", "http://localhost:8000"),
    EnvironmentLoader.get_url("WEBAUTHN_PRODUCTION_ORIGIN", "https://api.csfrace.com"),
]

# Database Configuration
PASSKEY_TABLE_NAME: str = "webauthn_credentials"
CHALLENGE_CACHE_PREFIX: str = "webauthn_challenge:"

# Error Messages - DRY Principle
ERROR_INVALID_CHALLENGE: str = "Invalid or expired challenge"
ERROR_VERIFICATION_FAILED: str = "WebAuthn verification failed"
ERROR_CREDENTIAL_NOT_FOUND: str = "Credential not found or inactive"
ERROR_USER_NOT_FOUND: str = "User not found or inactive"
ERROR_CHALLENGE_TYPE_MISMATCH: str = "Challenge type mismatch"
ERROR_MAX_CREDENTIALS_EXCEEDED: str = "Maximum number of credentials exceeded"

# Success Messages
SUCCESS_CREDENTIAL_REGISTERED: str = "Passkey registered successfully"
SUCCESS_AUTHENTICATION: str = "Authentication successful"
SUCCESS_CREDENTIAL_REVOKED: str = "Passkey revoked successfully"


# Create constant class instances for backward compatibility
class AuthConstants:  # pylint: disable=too-few-public-methods
    """Authentication constants container."""

    BEARER_TOKEN_TYPE = BEARER_TOKEN_TYPE
    PASSWORD_CONTEXT_DEPRECATED = PASSWORD_CONTEXT_DEPRECATED


class ProgressConstants:  # pylint: disable=too-few-public-methods
    """Progress constants container."""

    START = PROGRESS_START
    SETUP = PROGRESS_SETUP
    FETCH = PROGRESS_FETCH
    PROCESS = PROGRESS_PROCESS
    COMPLETE = PROGRESS_COMPLETE


class OAuthConstants:  # pylint: disable=too-few-public-methods
    """OAuth constants container."""

    OAUTH_GOOGLE_CLIENT_ID = OAUTH_GOOGLE_CLIENT_ID
    OAUTH_GOOGLE_CLIENT_SECRET = OAUTH_GOOGLE_CLIENT_SECRET
    OAUTH_GITHUB_CLIENT_ID = OAUTH_GITHUB_CLIENT_ID
    OAUTH_GITHUB_CLIENT_SECRET = OAUTH_GITHUB_CLIENT_SECRET
    OAUTH_MICROSOFT_CLIENT_ID = OAUTH_MICROSOFT_CLIENT_ID
    OAUTH_MICROSOFT_CLIENT_SECRET = OAUTH_MICROSOFT_CLIENT_SECRET
    OAUTH_REDIRECT_URI_BASE = OAUTH_REDIRECT_URI_BASE

    # Google OAuth2 Configuration
    GOOGLE_AUTHORIZATION_URL = GOOGLE_AUTHORIZATION_URL
    GOOGLE_TOKEN_URL = GOOGLE_TOKEN_URL
    GOOGLE_USER_INFO_URL = GOOGLE_USER_INFO_URL
    GOOGLE_SCOPES = GOOGLE_SCOPES

    # GitHub OAuth2 Configuration
    GITHUB_AUTHORIZATION_URL = GITHUB_AUTHORIZATION_URL
    GITHUB_TOKEN_URL = GITHUB_TOKEN_URL
    GITHUB_USER_INFO_URL = GITHUB_USER_INFO_URL
    GITHUB_USER_EMAILS_URL = GITHUB_USER_EMAILS_URL
    GITHUB_SCOPES = GITHUB_SCOPES

    # Microsoft OAuth2 Configuration
    MICROSOFT_AUTHORIZATION_URL = MICROSOFT_AUTHORIZATION_URL
    MICROSOFT_TOKEN_URL = MICROSOFT_TOKEN_URL
    MICROSOFT_USER_INFO_URL = MICROSOFT_USER_INFO_URL
    MICROSOFT_SCOPES = MICROSOFT_SCOPES

    # OAuth2 Security Settings
    STATE_TOKEN_LENGTH = STATE_TOKEN_LENGTH


class WebAuthnConstants:  # pylint: disable=too-few-public-methods
    """WebAuthn constants container."""

    WEBAUTHN_RP_ID = WEBAUTHN_RP_ID
    WEBAUTHN_RP_NAME = WEBAUTHN_RP_NAME
    WEBAUTHN_ORIGIN = WEBAUTHN_ORIGIN
    CHALLENGE_TIMEOUT_MS = CHALLENGE_TIMEOUT_MS
    CHALLENGE_LENGTH_BYTES = CHALLENGE_LENGTH_BYTES


class CLIConstants:  # pylint: disable=too-few-public-methods
    """CLI constants container."""

    DEFAULT_PROMETHEUS_URL = DEFAULT_PROMETHEUS_URL
    DEFAULT_GRAFANA_PORT = DEFAULT_GRAFANA_PORT
    EXAMPLE_CSFRACE_URL = EXAMPLE_CSFRACE_URL
    EXAMPLE_SITE_URL = EXAMPLE_SITE_URL
    PROGRESS_SEPARATOR = PROGRESS_SEPARATOR
    EXIT_CODE_KEYBOARD_INTERRUPT = EXIT_CODE_KEYBOARD_INTERRUPT


# Legacy constants class for backward compatibility (deprecated - use module level constants)
class AppConstants:  # pylint: disable=too-few-public-methods
    """Deprecated - use module level constants instead."""

    def __getattr__(self, name: str):
        """Redirect to module level constants."""
        import sys  # pylint: disable=import-outside-toplevel

        return getattr(sys.modules[__name__], name)

    def __setattr__(self, name: str, value) -> None:
        """Prevent modification to maintain immutability like frozen dataclass."""
        raise AttributeError(f"Cannot set attribute '{name}' on frozen constants")


class TestConstants:  # pylint: disable=too-few-public-methods
    """Test constants container."""

    BASE_TEST_URL = BASE_TEST_URL
    SAMPLE_POST_URL = SAMPLE_POST_URL
    LARGE_CONTENT_URL = LARGE_CONTENT_URL
    NONEXISTENT_URL = NONEXISTENT_URL
    SLOW_URL = SLOW_URL
    TEST_REDIS_HOST = TEST_REDIS_HOST
    TEST_REDIS_PORT = TEST_REDIS_PORT
    TEST_REDIS_DB = TEST_REDIS_DB
    TEST_REDIS_KEY_PREFIX = TEST_REDIS_KEY_PREFIX
    SAMPLE_IMAGE_URL = SAMPLE_IMAGE_URL
    TEST_IMAGE_CONTENT = TEST_IMAGE_CONTENT
    SAMPLE_HTML_TITLE = SAMPLE_HTML_TITLE
    SAMPLE_HTML_DESCRIPTION = SAMPLE_HTML_DESCRIPTION


# Global instances for backward compatibility
AUTH_CONSTANTS = AuthConstants()
PROGRESS_CONSTANTS = ProgressConstants()
OAUTH_CONSTANTS = OAuthConstants()
WEBAUTHN_CONSTANTS = WebAuthnConstants()
CLI_CONSTANTS = CLIConstants()
TEST_CONSTANTS = TestConstants()
CONSTANTS = AppConstants()
