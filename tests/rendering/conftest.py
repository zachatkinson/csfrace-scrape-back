"""
Optimized Playwright fixtures for rendering tests.

This module provides reusable browser contexts and smart test markers
for maximum CI/CD performance.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from src.rendering.browser_config import OptimizedBrowserConfig


# Custom markers for smart test selection
def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line(
        "markers", "no_browser: mark test as not requiring a real browser"
    )
    config.addinivalue_line(
        "markers", "lightweight: mark test as suitable for webkit (lighter browser)"
    )
    config.addinivalue_line(
        "markers", "heavy_browser: mark test as requiring full chromium features"
    )
    config.addinivalue_line(
        "markers", "browser_pool: mark test to use pre-warmed browser pool"
    )


# Browser Pool for pre-warming
class BrowserPool:
    """Pre-warmed browser pool for faster test execution."""

    def __init__(self, size: int = 3):
        self.size = size
        self.browsers: list[Browser] = []
        self.available: list[Browser] = []
        self.lock = asyncio.Lock()

    async def initialize(self, playwright: Playwright, config: OptimizedBrowserConfig):
        """Pre-warm browser instances."""
        for _ in range(self.size):
            browser = await playwright.chromium.launch(
                headless=True,
                args=config.chromium_args,
            )
            self.browsers.append(browser)
            self.available.append(browser)

    async def acquire(self) -> Browser:
        """Get a browser from the pool."""
        async with self.lock:
            while not self.available:
                await asyncio.sleep(0.1)
            return self.available.pop()

    async def release(self, browser: Browser):
        """Return a browser to the pool."""
        async with self.lock:
            if browser not in self.available:
                self.available.append(browser)

    async def cleanup(self):
        """Close all browsers in the pool."""
        for browser in self.browsers:
            await browser.close()


# Global browser pool instance
_browser_pool: BrowserPool | None = None


# Session-scoped fixtures for browser reuse
@pytest_asyncio.fixture(scope="session")
async def playwright_instance() -> AsyncIterator[Playwright]:
    """Session-scoped Playwright instance."""
    async with async_playwright() as playwright:
        yield playwright


@pytest_asyncio.fixture(scope="session")
async def browser_config() -> OptimizedBrowserConfig:
    """Get optimized browser configuration."""
    return OptimizedBrowserConfig.for_ci()


@pytest_asyncio.fixture(scope="session")
async def chromium_browser(
    playwright_instance: Playwright, browser_config: OptimizedBrowserConfig
) -> AsyncIterator[Browser]:
    """Session-scoped Chromium browser for heavy tests."""
    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=browser_config.chromium_args,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture(scope="session")
async def webkit_browser(
    playwright_instance: Playwright, browser_config: OptimizedBrowserConfig
) -> AsyncIterator[Browser]:
    """Session-scoped WebKit browser for lightweight tests."""
    browser = await playwright_instance.webkit.launch(
        headless=True,
        args=browser_config.webkit_args,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture(scope="session")
async def browser_pool(
    playwright_instance: Playwright, browser_config: OptimizedBrowserConfig
) -> AsyncIterator[BrowserPool]:
    """Pre-warmed browser pool for parallel tests."""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(size=3)
        await _browser_pool.initialize(playwright_instance, browser_config)
    yield _browser_pool
    # Don't cleanup here - let session cleanup handle it


# Function-scoped fixtures for test isolation
@pytest_asyncio.fixture
async def browser_context(
    request, chromium_browser: Browser, webkit_browser: Browser, browser_config: OptimizedBrowserConfig
) -> AsyncIterator[BrowserContext]:
    """Get browser context based on test markers."""
    # Choose browser based on test markers
    if "lightweight" in request.keywords:
        browser = webkit_browser
    else:
        browser = chromium_browser

    # Create isolated context for this test
    context = await browser.new_context(**browser_config.context_options)
    yield context
    await context.close()


@pytest_asyncio.fixture
async def page(browser_context: BrowserContext):
    """Get a new page in the browser context."""
    page = await browser_context.new_page()
    yield page
    await page.close()


@pytest_asyncio.fixture
async def pooled_browser(browser_pool: BrowserPool) -> AsyncIterator[Browser]:
    """Get a browser from the pre-warmed pool."""
    browser = await browser_pool.acquire()
    yield browser
    await browser_pool.release(browser)


@pytest_asyncio.fixture
async def pooled_context(
    pooled_browser: Browser, browser_config: OptimizedBrowserConfig
) -> AsyncIterator[BrowserContext]:
    """Get a context from a pooled browser."""
    context = await pooled_browser.new_context(**browser_config.context_options)
    yield context
    await context.close()


# Performance monitoring fixtures
@pytest.fixture
def measure_browser_time():
    """Measure browser operation time for optimization."""
    import time

    times = {}

    def _measure(operation: str):
        start = time.perf_counter()

        def _stop():
            times[operation] = time.perf_counter() - start
            return times[operation]

        return _stop

    yield _measure

    # Report slowest operations
    if times:
        slowest = sorted(times.items(), key=lambda x: x[1], reverse=True)[:3]
        for op, duration in slowest:
            if duration > 1.0:  # Only report slow operations
                print(f"SLOW BROWSER OP: {op} took {duration:.2f}s")


# Utility functions for test optimization
async def quick_page_load(page, url: str, config: OptimizedBrowserConfig):
    """Load a page with optimized settings for speed."""
    # Block unnecessary resources for faster loads
    await page.route(
        "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf}",
        lambda route: route.abort(),
    )
    await page.route(
        "**/*.css",
        lambda route: route.abort() if "critical" not in route.request.url else route.continue_(),
    )

    # Navigate with optimized options
    await page.goto(url, **config.navigation_options)


async def wait_for_idle(page, timeout: int = 1000):
    """Wait for page to be idle (no network activity)."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except:
        # Don't fail tests if network doesn't go idle
        pass