"""Configuration settings for the converter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConverterConfig:
    """Configuration for the WordPress to Shopify converter."""

    # HTTP Settings
    default_timeout: int = 30
    max_concurrent_downloads: int = 10
    rate_limit_delay: float = 0.5
    max_retries: int = 3
    backoff_factor: float = 2.0

    # User Agent
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Output Settings
    default_output_dir: str = "converted_content"
    images_subdir: str = "images"

    # Shopify-compatible CSS classes to preserve
    preserve_classes: frozenset[str] = frozenset(
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

    # File names
    metadata_file: str = "metadata.txt"
    html_file: str = "converted_content.html"
    shopify_file: str = "shopify_ready_content.html"

    # Robots.txt settings
    respect_robots_txt: bool = True
    robots_cache_duration: int = 3600  # 1 hour

    # Content type mappings for images
    content_type_extensions: dict = None

    def __post_init__(self):
        if self.content_type_extensions is None:
            object.__setattr__(
                self,
                "content_type_extensions",
                {
                    "image/jpeg": ".jpg",
                    "image/jpg": ".jpg",
                    "image/png": ".png",
                    "image/gif": ".gif",
                    "image/webp": ".webp",
                    "image/svg+xml": ".svg",
                },
            )


# Global config instance
config = ConverterConfig()
