"""Configuration settings for the converter.

This module provides configuration dataclasses for HTTP settings,
output settings, and other converter options.
"""

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

    def __init__(self, **kwargs):
        """Initialize converter configuration with backward compatibility.

        Args:
            **kwargs: Configuration parameters including:
                - default_timeout: Default timeout for HTTP requests
                - max_concurrent_downloads: Maximum concurrent downloads
                - max_concurrent: Alias for max_concurrent_downloads
                - rate_limit_delay: Rate limiting delay between requests
                - images_subdir: Images subdirectory name
                - preserve_classes: Classes to preserve in HTML
        """
        # Handle backward compatibility for max_concurrent vs max_concurrent_downloads
        max_concurrent_downloads = kwargs.get("max_concurrent_downloads")
        max_concurrent = kwargs.get("max_concurrent")
        max_concurrent_final = (
            max_concurrent_downloads or max_concurrent or CONSTANTS.MAX_CONCURRENT
        )

        # Initialize nested configurations with provided values or defaults
        object.__setattr__(
            self,
            "http",
            HttpConfig(
                timeout=kwargs.get("default_timeout", CONSTANTS.DEFAULT_TIMEOUT),
                max_concurrent=max_concurrent_final,
                rate_limit_delay=kwargs.get("rate_limit_delay", CONSTANTS.RATE_LIMIT_DELAY),
            ),
        )

        object.__setattr__(
            self,
            "output",
            OutputConfig(
                images_subdir=kwargs.get("images_subdir", CONSTANTS.DEFAULT_IMAGES_DIR),
            ),
        )

        object.__setattr__(self, "robots", RobotsConfig())

        preserve_classes = kwargs.get("preserve_classes")
        if preserve_classes:
            object.__setattr__(
                self, "shopify", ShopifyConfig(preserve_classes=frozenset(preserve_classes))
            )
        else:
            object.__setattr__(self, "shopify", ShopifyConfig())

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

    @property
    def max_concurrent_downloads(self) -> int:
        """Backward compatibility for max_concurrent_downloads access."""
        return self.http.max_concurrent

    @property
    def rate_limit_delay(self) -> float:
        """Backward compatibility for rate_limit_delay access."""
        return self.http.rate_limit_delay


# Global config instance
config = ConverterConfig()
