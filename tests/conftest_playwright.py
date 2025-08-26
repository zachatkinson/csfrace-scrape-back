"""Playwright configuration for CI optimization."""

import os
from typing import Any

import pytest


@pytest.fixture(scope="session")
def browser_config() -> dict[str, Any]:
    """Configure browser for CI environment with performance optimizations."""
    config = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            # Performance optimizations
            "--disable-component-extensions-with-background-pages",
            "--disable-default-apps",
            "--disable-client-side-phishing-detection",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--safebrowsing-disable-auto-update",
            "--password-store=basic",
            "--use-mock-keychain",
        ],
        "ignore_default_args": ["--enable-automation"],
    }

    # CI-specific optimizations
    if os.getenv("CI"):
        config["args"].extend(
            [
                "--no-zygote",  # Disable zygote process (CI safety)
                "--single-process",  # Use single process (CI stability)
                "--disable-web-security",  # Disable web security for faster testing
            ]
        )

    return config


@pytest.fixture(scope="session")
def browser_context_config() -> dict[str, Any]:
    """Configure browser context for CI with resource blocking."""
    return {
        "ignore_https_errors": True,
        "user_agent": "Mozilla/5.0 (compatible; TestBot/1.0; CI)",
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture
async def optimized_page(browser_context):
    """Create a page with resource blocking for faster tests."""
    page = await browser_context.new_page()

    # Block unnecessary resources to speed up tests by ~500ms per page load
    await page.route("**/*.{png,jpg,jpeg,gif,svg,webp}", lambda route: route.abort())
    await page.route("**/*.{css,woff,woff2,ttf,eot}", lambda route: route.abort())
    await page.route("**/analytics**", lambda route: route.abort())
    await page.route("**/tracking**", lambda route: route.abort())
    await page.route("**/ads**", lambda route: route.abort())
    await page.route("**/facebook**", lambda route: route.abort())
    await page.route("**/twitter**", lambda route: route.abort())
    await page.route("**/google-analytics**", lambda route: route.abort())
    await page.route("**/googletagmanager**", lambda route: route.abort())

    yield page
    await page.close()

