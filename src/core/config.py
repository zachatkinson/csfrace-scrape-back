"""Configuration settings for the converter."""

from dataclasses import dataclass, field

from ..constants import CONSTANTS


@dataclass(frozen=True)
class HttpConfig:
    """HTTP-related configuration."""

    timeout: int = CONSTANTS.DEFAULT_TIMEOUT
    max_concurrent: int = CONSTANTS.MAX_CONCURRENT
    rate_limit_delay: float = CONSTANTS.RATE_LIMIT_DELAY
    max_retries: int = CONSTANTS.MAX_RETRIES
    backoff_factor: float = CONSTANTS.BACKOFF_FACTOR
    user_agent: str = CONSTANTS.DEFAULT_USER_AGENT


@dataclass(frozen=True)
class OutputConfig:
    """Output-related configuration."""

    default_dir: str = CONSTANTS.DEFAULT_OUTPUT_DIR
    images_subdir: str = CONSTANTS.DEFAULT_IMAGES_DIR
    metadata_file: str = CONSTANTS.METADATA_FILE
    html_file: str = CONSTANTS.HTML_FILE
    shopify_file: str = CONSTANTS.SHOPIFY_FILE


@dataclass(frozen=True)
class RobotsConfig:
    """Robots.txt configuration."""

    respect_robots_txt: bool = CONSTANTS.RESPECT_ROBOTS_TXT
    cache_duration: int = CONSTANTS.ROBOTS_CACHE_DURATION


@dataclass(frozen=True)
class ShopifyConfig:
    """Shopify-specific configuration."""

    preserve_classes: frozenset[str] = CONSTANTS.SHOPIFY_PRESERVE_CLASSES
    content_type_extensions: dict[str, str] = field(
        default_factory=lambda: CONSTANTS.IMAGE_CONTENT_TYPES
    )


@dataclass(frozen=True)
class ConverterConfig:
    """Configuration for the WordPress to Shopify converter.

    Organized into logical groups to maintain clean separation of concerns.
    """

    http: HttpConfig = field(default_factory=HttpConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    robots: RobotsConfig = field(default_factory=RobotsConfig)
    shopify: ShopifyConfig = field(default_factory=ShopifyConfig)

    # Backward compatibility properties
    @property
    def images_subdir(self) -> str:
        """Backward compatibility for images_subdir access."""
        return self.output.images_subdir

    @property
    def default_timeout(self) -> int:
        """Backward compatibility for default_timeout access."""
        return self.http.timeout

    @property
    def preserve_classes(self) -> frozenset[str]:
        """Backward compatibility for preserve_classes access."""
        return self.shopify.preserve_classes

    @property
    def max_retries(self) -> int:
        """Backward compatibility for max_retries access."""
        return self.http.max_retries

    @property
    def respect_robots_txt(self) -> bool:
        """Backward compatibility for respect_robots_txt access."""
        return self.robots.respect_robots_txt


# Global config instance
config = ConverterConfig()
