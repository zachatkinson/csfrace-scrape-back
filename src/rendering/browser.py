"""Browser management and JavaScript rendering capabilities."""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast

import structlog
from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright
from pydantic import BaseModel, Field, field_validator

from src.utils.retry import RetryConfig, with_retry

logger = structlog.get_logger(__name__)


class BrowserConfig(BaseModel):
    """Configuration for browser instances."""

    browser_type: str = Field(
        default="chromium", description="Browser type (chromium, firefox, webkit)"
    )
    headless: bool = Field(default=True, description="Run browser in headless mode")
    viewport_width: int = Field(default=1920, description="Viewport width")
    viewport_height: int = Field(default=1080, description="Viewport height")
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="Custom user agent string",
    )
    timeout: float = Field(default=30.0, description="Default timeout in seconds")
    wait_until: str = Field(
        default="networkidle",
        description="Wait until condition (load, domcontentloaded, networkidle)",
    )
    extra_http_headers: dict[str, str] = Field(
        default_factory=dict, description="Additional HTTP headers"
    )
    ignore_https_errors: bool = Field(default=True, description="Ignore HTTPS certificate errors")
    javascript_enabled: bool = Field(default=True, description="Enable JavaScript execution")

    @field_validator("browser_type")
    @classmethod
    def validate_browser_type(cls, v):
        allowed_types = ["chromium", "firefox", "webkit"]
        if v not in allowed_types:
            raise ValueError(f"Browser type must be one of {allowed_types}")
        return v

    @field_validator("wait_until")
    @classmethod
    def validate_wait_until(cls, v):
        allowed_conditions = ["load", "domcontentloaded", "networkidle"]
        if v not in allowed_conditions:
            raise ValueError(f"wait_until must be one of {allowed_conditions}")
        return v


@dataclass
class RenderResult:
    """Result of browser rendering operation."""

    html: str
    url: str
    status_code: int
    final_url: str
    load_time: float
    javascript_executed: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    screenshots: dict[str, bytes] = field(default_factory=dict)
    network_requests: list[dict[str, Any]] = field(default_factory=list)


class BrowserPool:
    """Pool of browser contexts for efficient resource management."""

    def __init__(
        self,
        config: BrowserConfig,
        max_contexts: int = 5,
        context_reuse_limit: int = 50,
        cleanup_interval: float = 300.0,
    ):
        self.config = config
        self.max_contexts = max_contexts
        self.context_reuse_limit = context_reuse_limit
        self.cleanup_interval = cleanup_interval

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: list[BrowserContext] = []
        self._context_usage: dict[BrowserContext, int] = {}
        self._last_cleanup = time.time()
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the browser pool."""
        if self._playwright is None:
            logger.info(
                "Initializing Playwright browser pool", browser_type=self.config.browser_type
            )

            self._playwright = await async_playwright().start()

            # Get browser type
            if self.config.browser_type == "chromium":
                browser_type = self._playwright.chromium
            elif self.config.browser_type == "firefox":
                browser_type = self._playwright.firefox
            elif self.config.browser_type == "webkit":
                browser_type = self._playwright.webkit
            else:
                raise ValueError(f"Unsupported browser type: {self.config.browser_type}")

            # Launch browser with configuration
            launch_options: dict[str, Any] = {
                "headless": self.config.headless,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                ],
            }

            self._browser = await browser_type.launch(**launch_options)

            logger.info("Browser pool initialized successfully")

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            logger.info("Cleaning up browser pool")

            # Close all contexts
            for context in self._contexts:
                try:
                    await context.close()
                except Exception as e:
                    logger.warning("Error closing browser context", error=str(e))

            self._contexts.clear()
            self._context_usage.clear()

            # Close browser
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("Error closing browser", error=str(e))

            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping Playwright", error=str(e))

            self._playwright = None

        logger.info("Browser pool cleanup completed")

    async def _create_context(self) -> BrowserContext:
        """Create a new browser context."""
        if not self._browser:
            await self.initialize()

        context_options: dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "user_agent": self.config.user_agent,
            "ignore_https_errors": self.config.ignore_https_errors,
            "java_script_enabled": self.config.javascript_enabled,
        }

        if self.config.extra_http_headers:
            context_options["extra_http_headers"] = self.config.extra_http_headers

        if not self._browser:
            raise RuntimeError("Browser not initialized")
        context = await self._browser.new_context(**context_options)

        # Set default timeout
        context.set_default_timeout(self.config.timeout * 1000)  # Convert to milliseconds

        return context

    async def _should_cleanup_context(self, context: BrowserContext) -> bool:
        """Check if context should be cleaned up."""
        usage = self._context_usage.get(context, 0)
        return usage >= self.context_reuse_limit

    async def _cleanup_stale_contexts(self) -> None:
        """Clean up stale contexts periodically."""
        current_time = time.time()
        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        contexts_to_remove = []
        for context in self._contexts:
            if await self._should_cleanup_context(context):
                contexts_to_remove.append(context)

        for context in contexts_to_remove:
            try:
                await context.close()
                self._contexts.remove(context)
                self._context_usage.pop(context, None)
                logger.debug("Cleaned up stale browser context")
            except Exception as e:
                logger.warning("Error cleaning up context", error=str(e))

        self._last_cleanup = current_time

    @asynccontextmanager
    async def get_context(self) -> AsyncGenerator[BrowserContext, None]:
        """Get a browser context from the pool."""
        async with self._lock:
            await self._cleanup_stale_contexts()

            # Try to reuse existing context
            context = None
            if self._contexts:
                for ctx in self._contexts:
                    if not await self._should_cleanup_context(ctx):
                        context = ctx
                        break

            # Create new context if needed
            if not context and len(self._contexts) < self.max_contexts:
                context = await self._create_context()
                self._contexts.append(context)
                self._context_usage[context] = 0

            # Use least-used context if pool is full
            if not context and self._contexts:
                context = min(self._contexts, key=lambda c: self._context_usage.get(c, 0))

            if not context:
                raise RuntimeError("Unable to obtain browser context")

            # Increment usage counter
            self._context_usage[context] = self._context_usage.get(context, 0) + 1

        try:
            yield context
        finally:
            # Context cleanup is handled by periodic cleanup
            pass


class JavaScriptRenderer:
    """High-level JavaScript rendering service."""

    def __init__(
        self,
        config: BrowserConfig = None,
        pool_config: Optional[dict[str, Any]] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.config = config or BrowserConfig()
        self.pool_config = pool_config or {}
        self.retry_config = retry_config or RetryConfig(
            max_attempts=3, base_delay=1.0, backoff_factor=2.0, jitter=True
        )

        self._pool: Optional[BrowserPool] = None

    async def initialize(self) -> None:
        """Initialize the renderer."""
        if not self._pool:
            self._pool = BrowserPool(self.config, **self.pool_config)
            await self._pool.initialize()

            logger.info("JavaScript renderer initialized")

    async def cleanup(self) -> None:
        """Clean up renderer resources."""
        if self._pool:
            await self._pool.cleanup()
            self._pool = None

            logger.info("JavaScript renderer cleaned up")

    async def render_page(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_for_function: Optional[str] = None,
        execute_script: Optional[str] = None,
        take_screenshot: bool = False,
        full_page_screenshot: bool = False,
        capture_network: bool = False,
        additional_wait_time: float = 0.0,
    ) -> RenderResult:
        """Render a page with JavaScript execution."""
        if self._pool is None:
            await self.initialize()

        async def _render():
            return await self._render_page_internal(
                url=url,
                wait_for_selector=wait_for_selector,
                wait_for_function=wait_for_function,
                execute_script=execute_script,
                take_screenshot=take_screenshot,
                full_page_screenshot=full_page_screenshot,
                capture_network=capture_network,
                additional_wait_time=additional_wait_time,
            )

        @with_retry(self.retry_config)
        async def render_with_retry():
            return await _render()

        return await render_with_retry()

    async def _render_page_internal(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_for_function: Optional[str] = None,
        execute_script: Optional[str] = None,
        take_screenshot: bool = False,
        full_page_screenshot: bool = False,
        capture_network: bool = False,
        additional_wait_time: float = 0.0,
    ) -> RenderResult:
        """Internal page rendering implementation."""
        start_time = time.time()
        network_requests = []

        if not self._pool:
            raise RuntimeError("Browser pool not initialized")
        async with self._pool.get_context() as context:
            page = await context.new_page()

            try:
                # Set up network monitoring if requested
                if capture_network:

                    async def handle_request(request):
                        network_requests.append(
                            {
                                "url": request.url,
                                "method": request.method,
                                "headers": dict(request.headers),
                                "timestamp": time.time(),
                            }
                        )

                    page.on("request", handle_request)

                # Navigate to page
                logger.debug("Navigating to URL", url=url)
                wait_until_literal = cast(
                    "Literal['commit', 'domcontentloaded', 'load', 'networkidle']",
                    self.config.wait_until,
                )
                response = await page.goto(
                    url, wait_until=wait_until_literal, timeout=self.config.timeout * 1000
                )

                if not response:
                    raise RuntimeError(f"Failed to load page: {url}")

                status_code = response.status
                final_url = page.url

                # Wait for specific selector if provided
                if wait_for_selector:
                    logger.debug("Waiting for selector", selector=wait_for_selector)
                    await page.wait_for_selector(
                        wait_for_selector, timeout=self.config.timeout * 1000
                    )

                # Wait for custom function if provided
                if wait_for_function:
                    logger.debug("Waiting for function", function=wait_for_function)
                    await page.wait_for_function(
                        wait_for_function, timeout=self.config.timeout * 1000
                    )

                # Execute custom JavaScript if provided
                script_result = None
                if execute_script:
                    logger.debug("Executing custom script")
                    try:
                        script_result = await page.evaluate(execute_script)
                    except Exception as e:
                        logger.warning("JavaScript execution failed", error=str(e))
                        script_result = None

                # Additional wait time for dynamic content
                if additional_wait_time > 0:
                    logger.debug("Additional wait time", duration=additional_wait_time)
                    await asyncio.sleep(additional_wait_time)

                # Get page content
                html = await page.content()

                # Take screenshots if requested
                screenshots = {}
                if take_screenshot:
                    logger.debug("Taking screenshot")
                    screenshot_options: dict[str, Any] = {"full_page": full_page_screenshot}
                    screenshots["main"] = await page.screenshot(**screenshot_options)

                # Calculate load time
                load_time = time.time() - start_time

                # Extract metadata
                metadata = {
                    "title": await page.title(),
                    "script_result": script_result,
                }

                # Try to get additional metadata
                try:
                    metadata.update(
                        {
                            "meta_description": await page.get_attribute(
                                'meta[name="description"]', "content"
                            )
                            or "",
                            "meta_keywords": await page.get_attribute(
                                'meta[name="keywords"]', "content"
                            )
                            or "",
                            "og_title": await page.get_attribute(
                                'meta[property="og:title"]', "content"
                            )
                            or "",
                            "og_description": await page.get_attribute(
                                'meta[property="og:description"]', "content"
                            )
                            or "",
                        }
                    )
                except Exception as e:
                    logger.debug("Could not extract additional metadata", error=str(e))

                logger.info(
                    "Page rendered successfully",
                    url=url,
                    final_url=final_url,
                    status_code=status_code,
                    load_time=load_time,
                    html_length=len(html),
                )

                return RenderResult(
                    html=html,
                    url=url,
                    status_code=status_code,
                    final_url=final_url,
                    load_time=load_time,
                    javascript_executed=self.config.javascript_enabled,
                    metadata=metadata,
                    screenshots=screenshots,
                    network_requests=network_requests,
                )

            finally:
                await page.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


# Default renderer instance factory
def create_renderer(
    headless: bool = True, browser_type: str = "chromium", timeout: float = 30.0, **kwargs
) -> JavaScriptRenderer:
    """Create a JavaScript renderer with common configurations."""
    config = BrowserConfig(browser_type=browser_type, headless=headless, timeout=timeout, **kwargs)

    return JavaScriptRenderer(config=config)
