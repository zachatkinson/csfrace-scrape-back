"""Configuration settings for the converter.

This module has been refactored to use the unified configuration system.
Import the unified configuration from the config package for backward compatibility.
"""

from dataclasses import dataclass, field

# Import from unified config system
from ..config import get_settings
from ..constants import CONSTANTS


# Maintain backward compatibility with the old dataclass-based approach
@dataclass(frozen=True)
class HttpConfig:
    """HTTP-related configuration - backward compatibility wrapper."""

    timeout: int = CONSTANTS.DEFAULT_TIMEOUT
    max_concurrent: int = CONSTANTS.MAX_CONCURRENT
    rate_limit_delay: float = CONSTANTS.RATE_LIMIT_DELAY
    max_retries: int = CONSTANTS.MAX_RETRIES
    backoff_factor: float = CONSTANTS.BACKOFF_FACTOR
    user_agent: str = CONSTANTS.DEFAULT_USER_AGENT


@dataclass(frozen=True)
class OutputConfig:
    """Output-related configuration - backward compatibility wrapper."""

    default_dir: str = CONSTANTS.DEFAULT_OUTPUT_DIR
    images_subdir: str = CONSTANTS.DEFAULT_IMAGES_DIR
    metadata_file: str = CONSTANTS.METADATA_FILE
    html_file: str = CONSTANTS.HTML_FILE
    shopify_file: str = CONSTANTS.SHOPIFY_FILE


@dataclass(frozen=True)
class RobotsConfig:
    """Robots.txt configuration - backward compatibility wrapper."""

    respect_robots_txt: bool = CONSTANTS.RESPECT_ROBOTS_TXT
    cache_duration: int = CONSTANTS.ROBOTS_CACHE_DURATION


@dataclass(frozen=True)
class ShopifyConfig:
    """Shopify-specific configuration - backward compatibility wrapper."""

    preserve_classes: frozenset[str] = CONSTANTS.SHOPIFY_PRESERVE_CLASSES
    content_type_extensions: dict[str, str] = field(
        default_factory=lambda: CONSTANTS.IMAGE_CONTENT_TYPES
    )


@dataclass(frozen=True)
class ConverterConfig:
    """Configuration for the WordPress to Shopify converter.

    Maintains backward compatibility while delegating to the new unified system.
    """

    http: HttpConfig = field(default_factory=HttpConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    robots: RobotsConfig = field(default_factory=RobotsConfig)
    shopify: ShopifyConfig = field(default_factory=ShopifyConfig)

    def __init__(self, **kwargs):
        """Initialize converter configuration with backward compatibility."""
        # Delegate to the new system while maintaining the old interface
        try:
            settings = get_settings()
            new_config = settings.converter

            # Map new config to old dataclass structure
            object.__setattr__(
                self,
                "http",
                HttpConfig(
                    timeout=new_config.http.timeout,
                    max_concurrent=new_config.http.max_concurrent,
                    rate_limit_delay=new_config.http.rate_limit_delay,
                    max_retries=new_config.http.max_retries,
                    backoff_factor=new_config.http.backoff_factor,
                    user_agent=new_config.http.user_agent,
                ),
            )

            object.__setattr__(
                self,
                "output",
                OutputConfig(
                    default_dir=new_config.output.default_dir,
                    images_subdir=new_config.output.images_subdir,
                    metadata_file=new_config.output.metadata_file,
                    html_file=new_config.output.html_file,
                    shopify_file=new_config.output.shopify_file,
                ),
            )

            object.__setattr__(
                self,
                "robots",
                RobotsConfig(
                    respect_robots_txt=new_config.robots.respect_robots_txt,
                    cache_duration=new_config.robots.cache_duration,
                ),
            )

            object.__setattr__(
                self,
                "shopify",
                ShopifyConfig(
                    preserve_classes=frozenset(new_config.shopify.preserve_classes),
                    content_type_extensions=dict(new_config.shopify.content_type_extensions),
                ),
            )

        except Exception:
            # Fallback to original logic if new system fails
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


# Global config instance - tries to use new system, falls back to old
try:
    settings = get_settings()
    config = ConverterConfig()
except Exception:
    # Fallback if new system is not available
    config = ConverterConfig()
