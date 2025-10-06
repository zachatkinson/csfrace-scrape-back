"""Converter and scraping configuration settings.

This module provides configuration for HTTP settings, output settings,
and other converter options following modern Pydantic patterns.
"""

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from src.core.logging_hierarchy import get_core_logger

from ..constants import (
    BACKOFF_FACTOR,
    DEFAULT_IMAGES_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    HTML_FILE,
    IMAGE_CONTENT_TYPES,
    MAX_CONCURRENT,
    MAX_RETRIES,
    METADATA_FILE,
    RATE_LIMIT_DELAY,
    RESPECT_ROBOTS_TXT,
    ROBOTS_CACHE_DURATION,
    SHOPIFY_FILE,
    SHOPIFY_PRESERVE_CLASSES,
)
from .base import BaseConfig, NetworkMixin

logger = get_core_logger()


class HttpConfig(BaseConfig, NetworkMixin):
    """HTTP-related configuration."""

    timeout: int = Field(DEFAULT_TIMEOUT, ge=1, le=300, description="HTTP timeout in seconds")
    max_concurrent: int = Field(MAX_CONCURRENT, ge=1, le=100, description="Max concurrent requests")
    rate_limit_delay: float = Field(
        RATE_LIMIT_DELAY, ge=0.0, le=10.0, description="Rate limit delay"
    )
    max_retries: int = Field(MAX_RETRIES, ge=0, le=10, description="Max retry attempts")
    backoff_factor: float = Field(
        BACKOFF_FACTOR, ge=1.0, le=10.0, description="Retry backoff factor"
    )
    user_agent: str = Field(DEFAULT_USER_AGENT, description="HTTP User-Agent header")

    # Connection pool settings
    pool_size: int = Field(20, ge=1, le=100, description="Connection pool size")
    pool_timeout: int = Field(30, ge=1, le=300, description="Pool timeout in seconds")

    @field_validator("user_agent", mode="before")
    @classmethod
    def validate_user_agent(cls, v: str) -> str:
        """Validate User-Agent header."""
        if not v or len(v.strip()) < 10:
            raise ValueError("User-Agent must be at least 10 characters long")
        return v.strip()


class OutputConfig(BaseConfig):
    """Output-related configuration."""

    default_dir: str = Field(DEFAULT_OUTPUT_DIR, description="Default output directory")
    images_subdir: str = Field(DEFAULT_IMAGES_DIR, description="Images subdirectory name")
    metadata_file: str = Field(METADATA_FILE, description="Metadata filename")
    html_file: str = Field(HTML_FILE, description="HTML output filename")
    shopify_file: str = Field(SHOPIFY_FILE, description="Shopify output filename")

    # File permissions and safety
    create_directories: bool = Field(True, description="Auto-create output directories")
    overwrite_existing: bool = Field(False, description="Overwrite existing files")
    max_file_size_mb: int = Field(100, ge=1, le=1000, description="Max file size in MB")

    @field_validator("default_dir", "images_subdir", mode="before")
    @classmethod
    def validate_directory_names(cls, v: str) -> str:
        """Validate directory names are safe."""
        if not v or v.strip() == "":
            raise ValueError("Directory name cannot be empty")

        # Basic path safety checks
        safe_v = v.strip()
        if ".." in safe_v or safe_v.startswith("/"):
            raise ValueError("Directory cannot contain '..' or start with '/'")

        return safe_v

    @property
    def output_path(self) -> Path:
        """Get output directory as Path object."""
        return Path(self.default_dir)

    @property
    def images_path(self) -> Path:
        """Get images directory as Path object."""
        return self.output_path / self.images_subdir


class RobotsConfig(BaseConfig):
    """Robots.txt configuration."""

    respect_robots_txt: bool = Field(RESPECT_ROBOTS_TXT, description="Respect robots.txt")
    cache_duration: int = Field(
        ROBOTS_CACHE_DURATION, ge=300, le=86400, description="Cache duration in seconds"
    )
    crawl_delay: float = Field(1.0, ge=0.1, le=10.0, description="Crawl delay in seconds")
    user_agent_for_robots: str = Field("*", description="User-agent for robots.txt matching")


class ShopifyConfig(BaseConfig):
    """Shopify-specific configuration."""

    preserve_classes: set[str] = Field(
        default_factory=lambda: set(SHOPIFY_PRESERVE_CLASSES),
        description="CSS classes to preserve",
    )
    content_type_extensions: dict[str, str] = Field(
        default_factory=lambda: dict(IMAGE_CONTENT_TYPES),
        description="Content type to extension mapping",
    )

    # Content processing options
    minify_html: bool = Field(False, description="Minify HTML output")
    preserve_comments: bool = Field(False, description="Preserve HTML comments")
    convert_relative_urls: bool = Field(True, description="Convert relative URLs to absolute")

    @field_validator("preserve_classes", mode="before")
    @classmethod
    def validate_preserve_classes(cls, v: Any) -> set[str]:
        """Convert preserve_classes to set."""
        if isinstance(v, str):
            return {cls.strip() for cls in v.split(",") if cls.strip()}
        elif isinstance(v, (list, tuple, frozenset)):
            return set(v)
        elif isinstance(v, set):
            return v
        else:
            raise ValueError("preserve_classes must be a string, list, or set")


class ConverterConfig(BaseConfig):
    """Unified configuration for the WordPress to Shopify converter.

    Organized into logical groups to maintain clean separation of concerns
    while providing a single configuration interface.
    """

    # Sub-configurations
    http: HttpConfig = Field(default_factory=HttpConfig, description="HTTP configuration")
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output configuration",
    )
    robots: RobotsConfig = Field(
        default_factory=RobotsConfig,
        description="Robots.txt configuration",
    )
    shopify: ShopifyConfig = Field(
        default_factory=ShopifyConfig,
        description="Shopify configuration",
    )

    # Global converter settings
    debug_mode: bool = Field(False, description="Enable debug mode")
    log_level: str = Field("INFO", description="Logging level")
    enable_metrics: bool = Field(True, description="Enable metrics collection")

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    def get_http_headers(self) -> dict[str, str]:
        """Get HTTP headers for requests."""
        return {
            "User-Agent": self.http.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def validate_output_directory(self) -> None:
        """Validate and create output directory if needed."""
        output_path = self.output.output_path

        if self.output.create_directories:
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                (output_path / self.output.images_subdir).mkdir(exist_ok=True)
                logger.info(f"Created output directories at {output_path}")
            except OSError as e:
                raise ValueError(f"Cannot create output directory {output_path}: {e}") from e
        elif not output_path.exists():
            raise ValueError(f"Output directory {output_path} does not exist")
