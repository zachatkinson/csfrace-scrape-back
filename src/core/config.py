"""Configuration settings for the converter."""

from dataclasses import dataclass, field

from ..constants import CONSTANTS


@dataclass(frozen=True)
class ConverterConfig:
    """Configuration for the WordPress to Shopify converter.

    All values use centralized constants to eliminate DRY violations.
    """

    # HTTP Settings - using centralized constants
    default_timeout: int = CONSTANTS.DEFAULT_TIMEOUT
    max_concurrent_downloads: int = CONSTANTS.MAX_CONCURRENT
    rate_limit_delay: float = CONSTANTS.RATE_LIMIT_DELAY
    max_retries: int = CONSTANTS.MAX_RETRIES
    backoff_factor: float = CONSTANTS.BACKOFF_FACTOR

    # User Agent - using centralized constant
    user_agent: str = CONSTANTS.DEFAULT_USER_AGENT

    # Output Settings - using centralized constants
    default_output_dir: str = CONSTANTS.DEFAULT_OUTPUT_DIR
    images_subdir: str = CONSTANTS.DEFAULT_IMAGES_DIR

    # Shopify-compatible CSS classes - using centralized constant
    preserve_classes: frozenset[str] = CONSTANTS.SHOPIFY_PRESERVE_CLASSES

    # File names - using centralized constants
    metadata_file: str = CONSTANTS.METADATA_FILE
    html_file: str = CONSTANTS.HTML_FILE
    shopify_file: str = CONSTANTS.SHOPIFY_FILE

    # Robots.txt settings - using centralized constants
    respect_robots_txt: bool = CONSTANTS.RESPECT_ROBOTS_TXT
    robots_cache_duration: int = CONSTANTS.ROBOTS_CACHE_DURATION

    # Content type mappings - using centralized constant
    content_type_extensions: dict[str, str] = field(
        default_factory=lambda: CONSTANTS.IMAGE_CONTENT_TYPES
    )


# Global config instance
config = ConverterConfig()
