"""Centralized constants and configuration for the WordPress to Shopify converter.

This module contains ALL constants used throughout the application.
NO hardcoded values should exist in business logic - everything must be here.
"""

from os import environ

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
DEFAULT_IMAGES_DIR: str = "images"  # Sub-directory name is a constant (part of app logic)

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
MAX_KEY_LENGTH: int = int(environ.get("MAX_KEY_LENGTH", "250"))  # Maximum cache key length
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
DEFAULT_API_PORT: int = int(environ.get("API_PORT", "8000"))
ALLOWED_ORIGINS_DEFAULT: str = environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:4321"
)

# Timeout configurations
ROBOTS_TIMEOUT: int = int(environ.get("ROBOTS_TIMEOUT", "10"))  # Robots.txt fetch timeout

# HTTP timeouts
CONNECTION_TIMEOUT: float = float(environ.get("CONNECTION_TIMEOUT", "10.0"))
READ_TIMEOUT: float = float(environ.get("READ_TIMEOUT", "30.0"))
TOTAL_TIMEOUT: float = float(environ.get("TOTAL_TIMEOUT", "60.0"))

# Browser timeouts
BROWSER_TIMEOUT: float = float(environ.get("BROWSER_TIMEOUT", "30.0"))
PAGE_LOAD_TIMEOUT: float = float(environ.get("PAGE_LOAD_TIMEOUT", "30.0"))
SCRIPT_TIMEOUT: float = float(environ.get("SCRIPT_TIMEOUT", "10.0"))

# Rendering timeouts
RENDER_TIMEOUT: float = float(environ.get("RENDER_TIMEOUT", "60.0"))
SCREENSHOT_TIMEOUT: float = float(environ.get("SCREENSHOT_TIMEOUT", "10.0"))

# Network timeouts
DNS_TIMEOUT: float = float(environ.get("DNS_TIMEOUT", "5.0"))
KEEPALIVE_TIMEOUT: float = float(environ.get("KEEPALIVE_TIMEOUT", "30.0"))

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
LOG_LEVEL: str = environ.get("LOG_LEVEL", "INFO")  # Configurable via env
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
DEFAULT_PROMETHEUS_URL: str = environ.get("DEFAULT_PROMETHEUS_URL", "http://prometheus:9090")
DEFAULT_GRAFANA_PORT: int = int(environ.get("DEFAULT_GRAFANA_PORT", "3000"))

# Example URLs for help text
EXAMPLE_CSFRACE_URL: str = "https://csfrace.com/blog/sample-post"
EXAMPLE_SITE_URL: str = "https://site.com"

# Progress display
PROGRESS_SEPARATOR: str = "-" * 50

# Exit codes
EXIT_CODE_KEYBOARD_INTERRUPT: int = 130

# OAuth2 Client Credentials - Environment Variable Based Configuration
OAUTH_GOOGLE_CLIENT_ID: str = environ.get("OAUTH_GOOGLE_CLIENT_ID", "")
OAUTH_GOOGLE_CLIENT_SECRET: str = environ.get("OAUTH_GOOGLE_CLIENT_SECRET", "")

OAUTH_GITHUB_CLIENT_ID: str = environ.get("OAUTH_GITHUB_CLIENT_ID", "")
OAUTH_GITHUB_CLIENT_SECRET: str = environ.get("OAUTH_GITHUB_CLIENT_SECRET", "")

OAUTH_MICROSOFT_CLIENT_ID: str = environ.get("OAUTH_MICROSOFT_CLIENT_ID", "")
OAUTH_MICROSOFT_CLIENT_SECRET: str = environ.get("OAUTH_MICROSOFT_CLIENT_SECRET", "")

# OAuth2 Redirect URIs - Centralized Configuration
OAUTH_REDIRECT_URI_BASE: str = environ.get("OAUTH_REDIRECT_URI_BASE", "http://localhost:8000")

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
OAUTH_TIMEOUT: int = int(environ.get("OAUTH_TIMEOUT", "30"))  # OAuth request timeout
OAUTH_MAX_RETRIES: int = int(environ.get("OAUTH_MAX_RETRIES", "3"))  # OAuth retry attempts

# Authentication constants
BEARER_TOKEN_TYPE: str = "bearer"  # noqa: S105
PASSWORD_CONTEXT_DEPRECATED: str = "auto"  # noqa: S105

# WebAuthn/Passkeys configuration constants
WEBAUTHN_RP_ID: str = environ.get("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_RP_NAME: str = environ.get("WEBAUTHN_RP_NAME", "CSFrace Backend")
WEBAUTHN_ORIGIN: str = environ.get("WEBAUTHN_ORIGIN", "http://localhost:8000")

# Challenge Configuration - Security Settings
CHALLENGE_LENGTH_BYTES: int = 32  # 256-bit challenge (FIDO2 standard)
CHALLENGE_TIMEOUT_MS: int = int(environ.get("WEBAUTHN_CHALLENGE_TIMEOUT_MS", "60000"))  # 1 minute
CHALLENGE_MAX_AGE_MINUTES: int = int(environ.get("WEBAUTHN_CHALLENGE_MAX_AGE", "10"))  # 10 minutes

# Credential Configuration
MAX_CREDENTIALS_PER_USER: int = int(environ.get("WEBAUTHN_MAX_CREDENTIALS", "10"))
DEVICE_NAME_MAX_LENGTH: int = 100
CREDENTIAL_ID_LENGTH: int = 64  # Base64URL encoded length

# Authenticator Selection Preferences - FIDO2 Standards
USER_VERIFICATION_REQUIREMENT: str = "preferred"  # preferred, required, discouraged
AUTHENTICATOR_ATTACHMENT: str = "platform"  # platform, cross-platform, or None
REQUIRE_RESIDENT_KEY: bool = False  # For discoverable credentials

# Attestation Configuration
ATTESTATION_CONVEYANCE: str = "none"  # none, indirect, direct, enterprise

# Timeout Configuration
REGISTRATION_TIMEOUT_MS: int = int(environ.get("WEBAUTHN_REG_TIMEOUT_MS", "60000"))
AUTHENTICATION_TIMEOUT_MS: int = int(environ.get("WEBAUTHN_AUTH_TIMEOUT_MS", "60000"))

# Security Settings
ALLOWED_ORIGINS: list[str] = [
    environ.get("WEBAUTHN_ORIGIN", "http://localhost:8000"),
    environ.get("WEBAUTHN_PRODUCTION_ORIGIN", "https://api.csfrace.com"),
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


# Global instances for backward compatibility
AUTH_CONSTANTS = AuthConstants()
PROGRESS_CONSTANTS = ProgressConstants()
OAUTH_CONSTANTS = OAuthConstants()
WEBAUTHN_CONSTANTS = WebAuthnConstants()
CLI_CONSTANTS = CLIConstants()
CONSTANTS = AppConstants()
