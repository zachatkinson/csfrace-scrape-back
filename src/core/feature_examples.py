"""
Examples of how to use feature flags in the codebase.

This module demonstrates various patterns for implementing feature flags
in your WordPress to Shopify converter application.
"""

import logging
from typing import Any

from src.core.feature_flags import feature_enabled, with_feature_flag

logger = logging.getLogger(__name__)


class ContentParser:
    """Example parser with feature flag integration."""

    def parse_wordpress_content(self, content: str, user_id: str | None = None) -> dict[str, Any]:
        """Parse WordPress content with optional new parser."""

        # Pattern 1: Simple conditional logic
        if feature_enabled("new_wordpress_parser", user_id):
            logger.info("Using new WordPress parser (feature flag enabled)")
            return self._parse_with_new_parser(content)
        else:
            logger.info("Using legacy WordPress parser")
            return self._parse_with_legacy_parser(content)

    def _parse_with_new_parser(self, content: str) -> dict[str, Any]:
        """New parser with enhanced features."""
        return {
            "parser_version": "2.0",
            "content": content,
            "features": ["gallery_support", "block_parsing", "metadata_extraction"],
            "performance_optimized": True,
        }

    def _parse_with_legacy_parser(self, content: str) -> dict[str, Any]:
        """Legacy parser for backward compatibility."""
        return {
            "parser_version": "1.0",
            "content": content,
            "features": ["basic_parsing"],
            "performance_optimized": False,
        }


class ImageProcessor:
    """Example image processor with feature flags."""

    def process_images(self, images: list[str], user_id: str | None = None) -> list[dict[str, Any]]:
        """Process images with optional enhanced processing."""
        processed_images = []

        for image_url in images:
            if feature_enabled("enhanced_image_processing", user_id):
                # Use enhanced processing
                processed_images.append(self._enhanced_image_processing(image_url))
            else:
                # Use basic processing
                processed_images.append(self._basic_image_processing(image_url))

        return processed_images

    def _enhanced_image_processing(self, image_url: str) -> dict[str, Any]:
        """Enhanced image processing with WebP conversion and optimization."""
        return {
            "original_url": image_url,
            "optimized_url": image_url.replace(".jpg", "_optimized.webp"),
            "formats": ["webp", "jpg", "avif"],
            "compression": "high",
            "processing_method": "enhanced",
        }

    def _basic_image_processing(self, image_url: str) -> dict[str, Any]:
        """Basic image processing."""
        return {
            "original_url": image_url,
            "optimized_url": image_url,
            "formats": ["jpg"],
            "compression": "standard",
            "processing_method": "basic",
        }


class CacheManager:
    """Example cache manager with feature-flagged caching strategies."""

    def __init__(self):
        self.file_cache = {}  # Simple dict for demo
        self.redis_cache = None  # Would be Redis client

    def get_cached_content(self, key: str, user_id: str | None = None) -> Any | None:
        """Get content from cache with advanced caching if enabled."""

        # Check if advanced caching is enabled
        if feature_enabled("advanced_caching", user_id):
            return self._get_from_advanced_cache(key)
        else:
            return self._get_from_simple_cache(key)

    def set_cached_content(self, key: str, content: Any, user_id: str | None = None) -> bool:
        """Set content in cache with appropriate strategy."""

        if feature_enabled("advanced_caching", user_id):
            return self._set_in_advanced_cache(key, content)
        else:
            return self._set_in_simple_cache(key, content)

    def _get_from_advanced_cache(self, key: str) -> Any | None:
        """Multi-layer cache lookup (Redis + file fallback)."""
        # Try Redis first
        if self.redis_cache:
            result = self.redis_cache.get(key)
            if result:
                logger.debug(f"Cache hit (Redis): {key}")
                return result

        # Fallback to file cache
        result = self.file_cache.get(key)
        if result:
            logger.debug(f"Cache hit (file): {key}")
            return result

        logger.debug(f"Cache miss: {key}")
        return None

    def _get_from_simple_cache(self, key: str) -> Any | None:
        """Simple file-based cache lookup."""
        result = self.file_cache.get(key)
        if result:
            logger.debug(f"Simple cache hit: {key}")
        else:
            logger.debug(f"Simple cache miss: {key}")
        return result

    def _set_in_advanced_cache(self, key: str, content: Any) -> bool:
        """Set in multi-layer cache."""
        try:
            # Set in Redis if available
            if self.redis_cache:
                self.redis_cache.set(key, content, ex=3600)  # 1 hour TTL

            # Also set in file cache as backup
            self.file_cache[key] = content
            logger.debug(f"Advanced cache set: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to set advanced cache: {e}")
            return False

    def _set_in_simple_cache(self, key: str, content: Any) -> bool:
        """Set in simple file cache."""
        try:
            self.file_cache[key] = content
            logger.debug(f"Simple cache set: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to set simple cache: {e}")
            return False


class BatchProcessor:
    """Example batch processor with async feature flag."""

    @with_feature_flag("async_batch_processing")
    def process_batch_async(self, items: list[str]) -> dict[str, Any] | None:
        """Process batch asynchronously if feature is enabled."""
        logger.info(f"Processing {len(items)} items asynchronously")
        return {
            "processed_count": len(items),
            "processing_method": "async",
            "performance_boost": "50%",
        }

    def process_batch(self, items: list[str], user_id: str | None = None) -> dict[str, Any]:
        """Process batch with optional async processing."""

        # Try async processing first
        if feature_enabled("async_batch_processing", user_id):
            result = self.process_batch_async(items)
            if result:
                return result

        # Fallback to synchronous processing
        logger.info(f"Processing {len(items)} items synchronously")
        return {
            "processed_count": len(items),
            "processing_method": "sync",
            "performance_boost": "0%",
        }


class MetricsCollector:
    """Example metrics collector with feature-flagged Prometheus integration."""

    def collect_conversion_metrics(
        self, conversion_data: dict[str, Any], user_id: str | None = None
    ) -> None:
        """Collect metrics with optional Prometheus integration."""

        # Basic metrics (always collected)
        self._collect_basic_metrics(conversion_data)

        # Enhanced Prometheus metrics if enabled
        if feature_enabled("prometheus_metrics", user_id):
            self._collect_prometheus_metrics(conversion_data)

    def _collect_basic_metrics(self, data: dict[str, Any]) -> None:
        """Collect basic metrics to local storage."""
        logger.debug("Collecting basic metrics")
        # Simple counter increment, etc.

    def _collect_prometheus_metrics(self, data: dict[str, Any]) -> None:
        """Collect detailed Prometheus metrics."""
        logger.debug("Collecting enhanced Prometheus metrics")
        # Prometheus histogram, gauge, counter updates
        # More detailed performance metrics
        # Custom business metrics


# Usage example in your main application
def example_usage():
    """Example of how to use feature flags in your application."""

    # Initialize feature flags (usually done at app startup)
    from src.core.feature_flags import initialize_feature_flags

    initialize_feature_flags(environment="development", user_id_provider=lambda: "test-user-123")

    # Use feature-flagged components
    parser = ContentParser()
    result = parser.parse_wordpress_content("<html>Example content</html>")

    print(f"Parser result: {result}")

    # Check multiple flags
    image_processor = ImageProcessor()
    cache_manager = CacheManager()

    images = ["image1.jpg", "image2.png"]
    processed = image_processor.process_images(images)
    print(f"Processed images: {processed}")

    # Cache some data
    cache_manager.set_cached_content("test-key", {"data": "test"})
    cached = cache_manager.get_cached_content("test-key")
    print(f"Cached data: {cached}")


if __name__ == "__main__":
    example_usage()
