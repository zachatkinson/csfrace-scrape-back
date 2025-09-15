"""
Optimized browser configuration for Playwright tests.

This module provides optimized browser settings for CI/CD performance.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OptimizedBrowserConfig:
    """Optimized browser configuration for performance."""

    # Browser launch arguments for CI optimization
    chromium_args: list[str] = field(
        default_factory=lambda: [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",  # Overcome limited resource problems
            "--disable-gpu",  # No GPU in CI
            "--no-sandbox",  # Faster in containers
            "--disable-web-security",  # If testing doesn't need CORS
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--single-process",  # Reduces overhead for simple tests
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-translate",
            "--disable-sync",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--no-first-run",
            "--safebrowsing-disable-auto-update",
            "--mute-audio",
            "--autoplay-policy=no-user-gesture-required",
        ]
    )

    # Lightweight browser args for simple tests
    webkit_args: list[str] = field(
        default_factory=lambda: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]
    )

    # Context options for faster execution
    context_options: dict[str, Any] = field(
        default_factory=lambda: {
            "viewport": {"width": 1280, "height": 720},
            "ignore_https_errors": True,
            "reduced_motion": "reduce",  # Disable animations
            "force_colors": "none",  # Disable color schemes
            "bypass_csp": True,  # Bypass content security policy for tests
            "java_script_enabled": True,
            "accept_downloads": False,
            "has_touch": False,
            "is_mobile": False,
            "locale": "en-US",
            "timezone_id": "UTC",
            "permissions": [],  # No special permissions needed
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
    )

    # Navigation options for faster page loads
    navigation_options: dict[str, Any] = field(
        default_factory=lambda: {
            "wait_until": "domcontentloaded",  # Don't wait for all resources
            "timeout": 10000,  # 10 second timeout
        }
    )

    @classmethod
    def for_ci(cls) -> "OptimizedBrowserConfig":
        """Get optimized configuration for CI environment."""
        return cls()

    @classmethod
    def for_performance_tests(cls) -> "OptimizedBrowserConfig":
        """Get configuration optimized for performance benchmarks."""
        config = cls()
        # Performance tests need more realistic settings
        config.navigation_options["wait_until"] = "networkidle"
        config.context_options["viewport"] = {"width": 1920, "height": 1080}
        return config

    @classmethod
    def for_simple_tests(cls) -> "OptimizedBrowserConfig":
        """Get lightweight configuration for simple DOM tests."""
        config = cls()
        # Simple tests can be more aggressive with optimizations
        config.context_options["java_script_enabled"] = False
        config.navigation_options["timeout"] = 5000
        return config
