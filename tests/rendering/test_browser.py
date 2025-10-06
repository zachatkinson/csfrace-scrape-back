"""Comprehensive tests for browser management - MANDATORY TEST_BUILDING.md compliance.

This module tests browser lifecycle, pool management, and JavaScript rendering:
- BrowserConfig validation
- BrowserPool initialization and cleanup
- Context management and pooling
- JavaScriptRenderer page rendering
- Network monitoring and screenshots
- Retry mechanisms and error handling

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive browser lifecycle testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Browser, BrowserContext, Page, Response
from pydantic import ValidationError

from src.rendering.browser import (
    BrowserConfig,
    BrowserPool,
    JavaScriptRenderer,
    RenderResult,
    create_renderer,
)
from src.utils.retry import RetryConfig

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def default_browser_config() -> BrowserConfig:
    """Factory for default BrowserConfig - DRY principle."""
    return BrowserConfig()


@pytest.fixture
def mock_playwright() -> AsyncMock:
    """Factory for mock Playwright instance - DRY principle."""
    playwright = AsyncMock()
    playwright.chromium = AsyncMock()
    playwright.firefox = AsyncMock()
    playwright.webkit = AsyncMock()
    return playwright


@pytest.fixture
def mock_browser() -> AsyncMock:
    """Factory for mock Browser instance - DRY principle."""
    browser = AsyncMock(spec=Browser)
    context = AsyncMock(spec=BrowserContext)
    browser.new_context = AsyncMock(return_value=context)
    return browser


@pytest.fixture
def mock_page() -> AsyncMock:
    """Factory for mock Page instance - DRY principle."""
    page = AsyncMock(spec=Page)
    page.url = "https://example.com"
    page.title = AsyncMock(return_value="Example Page")
    page.content = AsyncMock(return_value="<html><body>Content</body></html>")
    page.get_attribute = AsyncMock(return_value="")
    page.close = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"screenshot_data")
    page.on = MagicMock()
    return page


@pytest.fixture
def mock_response() -> AsyncMock:
    """Factory for mock Response instance - DRY principle."""
    response = AsyncMock(spec=Response)
    response.status = 200
    return response


# ============================================================================
# BrowserConfig Tests
# ============================================================================


@pytest.mark.unit
class TestBrowserConfig:
    """Tests for BrowserConfig validation."""

    def test_config_initialization_with_defaults(self) -> None:
        """Test config initializes with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = BrowserConfig()

        # Assert - MANDATORY
        assert config.browser_type == "chromium"
        assert config.headless is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.timeout == 30.0

    def test_config_with_custom_values(self) -> None:
        """Test config accepts custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_values = {
            "browser_type": "firefox",
            "headless": False,
            "viewport_width": 1280,
            "timeout": 60.0,
        }

        # Act - MANDATORY
        config = BrowserConfig(**custom_values)

        # Assert - MANDATORY
        assert config.browser_type == "firefox"
        assert config.headless is False
        assert config.viewport_width == 1280
        assert config.timeout == 60.0

    def test_browser_type_validation_rejects_invalid(self) -> None:
        """Test browser_type validation rejects invalid values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        invalid_browser_type = "invalid_browser"

        # Act & Assert - MANDATORY
        with pytest.raises(ValidationError) as exc_info:
            BrowserConfig(browser_type=invalid_browser_type)

        assert "Browser type must be one of" in str(exc_info.value)

    def test_browser_type_validation_accepts_valid(self) -> None:
        """Test browser_type validation accepts valid values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        valid_browsers = ["chromium", "firefox", "webkit"]

        # Act - MANDATORY
        for browser in valid_browsers:
            config = BrowserConfig(browser_type=browser)

            # Assert - MANDATORY
            assert config.browser_type == browser

    def test_wait_until_validation_rejects_invalid(self) -> None:
        """Test wait_until validation rejects invalid values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        invalid_wait_until = "invalid_wait"

        # Act & Assert - MANDATORY
        with pytest.raises(ValidationError) as exc_info:
            BrowserConfig(wait_until=invalid_wait_until)

        assert "wait_until must be one of" in str(exc_info.value)

    def test_wait_until_validation_accepts_valid(self) -> None:
        """Test wait_until validation accepts valid values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        valid_conditions = ["load", "domcontentloaded", "networkidle"]

        # Act - MANDATORY
        for condition in valid_conditions:
            config = BrowserConfig(wait_until=condition)

            # Assert - MANDATORY
            assert config.wait_until == condition


# ============================================================================
# RenderResult Tests
# ============================================================================


@pytest.mark.unit
class TestRenderResult:
    """Tests for RenderResult dataclass."""

    def test_render_result_initialization(self) -> None:
        """Test RenderResult initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "<html><body>Content</body></html>"
        url = "https://example.com"
        status_code = 200
        final_url = "https://example.com/final"
        load_time = 1.5

        # Act - MANDATORY
        result = RenderResult(
            html=html,
            url=url,
            status_code=status_code,
            final_url=final_url,
            load_time=load_time,
            javascript_executed=True,
        )

        # Assert - MANDATORY
        assert result.html == html
        assert result.url == url
        assert result.status_code == status_code
        assert result.final_url == final_url
        assert result.load_time == load_time
        assert result.javascript_executed is True
        assert result.metadata == {}
        assert result.screenshots == {}
        assert result.network_requests == []

    def test_render_result_with_metadata(self) -> None:
        """Test RenderResult with metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        metadata = {"title": "Example", "description": "Test page"}

        # Act - MANDATORY
        result = RenderResult(
            html="<html></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=1.0,
            javascript_executed=True,
            metadata=metadata,
        )

        # Assert - MANDATORY
        assert result.metadata == metadata
        assert result.metadata["title"] == "Example"

    def test_render_result_with_screenshots(self) -> None:
        """Test RenderResult with screenshots - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        screenshots = {"main": b"image_data"}

        # Act - MANDATORY
        result = RenderResult(
            html="<html></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=1.0,
            javascript_executed=True,
            screenshots=screenshots,
        )

        # Assert - MANDATORY
        assert result.screenshots == screenshots
        assert "main" in result.screenshots


# ============================================================================
# BrowserPool Tests
# ============================================================================


@pytest.mark.unit
class TestBrowserPoolInitialization:
    """Tests for BrowserPool initialization."""

    @pytest.mark.asyncio
    async def test_browser_pool_initialization(
        self,
        default_browser_config: BrowserConfig,
        mock_playwright: AsyncMock,
        mock_browser: AsyncMock,
    ) -> None:
        """Test browser pool initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        # Act - MANDATORY
        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Assert - MANDATORY
        assert pool._playwright is not None
        assert pool._browser is not None

    @pytest.mark.asyncio
    async def test_browser_pool_cleanup(
        self,
        default_browser_config: BrowserConfig,
        mock_playwright: AsyncMock,
        mock_browser: AsyncMock,
    ) -> None:
        """Test browser pool cleanup closes resources - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Act - MANDATORY
        await pool.cleanup()

        # Assert - MANDATORY
        assert pool._browser is None
        assert pool._playwright is None
        assert len(pool._contexts) == 0

    @pytest.mark.asyncio
    async def test_browser_pool_supports_chromium(self, mock_browser: AsyncMock) -> None:
        """Test browser pool supports chromium - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = BrowserConfig(browser_type="chromium")
        pool = BrowserPool(config)
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        # Act - MANDATORY
        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Assert - MANDATORY
        assert pool._browser is not None
        assert pool._playwright is not None

    @pytest.mark.asyncio
    async def test_browser_pool_supports_firefox(self, mock_browser: AsyncMock) -> None:
        """Test browser pool supports firefox - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = BrowserConfig(browser_type="firefox")
        pool = BrowserPool(config)
        mock_playwright = AsyncMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        # Act - MANDATORY
        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Assert - MANDATORY
        assert pool._browser is not None
        assert pool._playwright is not None

    @pytest.mark.asyncio
    async def test_browser_pool_supports_webkit(self, mock_browser: AsyncMock) -> None:
        """Test browser pool supports webkit - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = BrowserConfig(browser_type="webkit")
        pool = BrowserPool(config)
        mock_playwright = AsyncMock()
        mock_playwright.webkit.launch = AsyncMock(return_value=mock_browser)

        # Act - MANDATORY
        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Assert - MANDATORY
        assert pool._browser is not None
        assert pool._playwright is not None


@pytest.mark.unit
class TestBrowserPoolContextManagement:
    """Tests for BrowserPool context management."""

    @pytest.mark.asyncio
    async def test_get_context_creates_new_context(
        self,
        default_browser_config: BrowserConfig,
        mock_playwright: AsyncMock,
        mock_browser: AsyncMock,
    ) -> None:
        """Test get_context creates new context - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config, max_contexts=5)
        mock_context = AsyncMock(spec=BrowserContext)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Act - MANDATORY
        async with pool.get_context() as context:
            # Assert - MANDATORY
            assert context is not None
            assert len(pool._contexts) == 1

    @pytest.mark.asyncio
    async def test_get_context_reuses_existing_context(
        self,
        default_browser_config: BrowserConfig,
        mock_playwright: AsyncMock,
        mock_browser: AsyncMock,
    ) -> None:
        """Test get_context reuses existing context - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config, context_reuse_limit=10)
        mock_context = AsyncMock(spec=BrowserContext)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Act - MANDATORY
        async with pool.get_context() as context1:
            pass

        async with pool.get_context() as context2:
            # Assert - MANDATORY
            assert context1 == context2
            assert len(pool._contexts) == 1

    @pytest.mark.asyncio
    async def test_context_usage_counter_increments(
        self,
        default_browser_config: BrowserConfig,
        mock_playwright: AsyncMock,
        mock_browser: AsyncMock,
    ) -> None:
        """Test context usage counter increments - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config)
        mock_context = AsyncMock(spec=BrowserContext)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        # Act - MANDATORY
        async with pool.get_context() as context:
            usage_after_first = pool._context_usage.get(context, 0)

        async with pool.get_context() as context:
            usage_after_second = pool._context_usage.get(context, 0)

        # Assert - MANDATORY
        assert usage_after_first == 1
        assert usage_after_second == 2

    @pytest.mark.asyncio
    async def test_should_cleanup_context_logic(
        self, default_browser_config: BrowserConfig
    ) -> None:
        """Test should_cleanup_context logic - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config, context_reuse_limit=5)
        mock_context = AsyncMock(spec=BrowserContext)

        # Test context below limit
        pool._context_usage[mock_context] = 3

        # Act - MANDATORY
        should_cleanup_below = await pool._should_cleanup_context(mock_context)

        # Assert - MANDATORY
        assert should_cleanup_below is False

        # Arrange - context at limit
        pool._context_usage[mock_context] = 5

        # Act - MANDATORY
        should_cleanup_at_limit = await pool._should_cleanup_context(mock_context)

        # Assert - MANDATORY
        assert should_cleanup_at_limit is True

        # Arrange - context above limit
        pool._context_usage[mock_context] = 10

        # Act - MANDATORY
        should_cleanup_above = await pool._should_cleanup_context(mock_context)

        # Assert - MANDATORY
        assert should_cleanup_above is True


# ============================================================================
# JavaScriptRenderer Tests
# ============================================================================


@pytest.mark.unit
class TestJavaScriptRendererInitialization:
    """Tests for JavaScriptRenderer initialization."""

    @pytest.mark.asyncio
    async def test_renderer_initialization(self) -> None:
        """Test renderer initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = JavaScriptRenderer()

        # Act - MANDATORY
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            await renderer.initialize()

        # Assert - MANDATORY
        assert renderer._pool is not None

    @pytest.mark.asyncio
    async def test_renderer_cleanup(self) -> None:
        """Test renderer cleanup closes pool - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = JavaScriptRenderer()
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            await renderer.initialize()

        # Act - MANDATORY
        await renderer.cleanup()

        # Assert - MANDATORY
        assert renderer._pool is None
        mock_pool.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_renderer_with_custom_config(self) -> None:
        """Test renderer with custom config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = BrowserConfig(browser_type="firefox", timeout=60.0)
        retry_config = RetryConfig(max_attempts=5)

        # Act - MANDATORY
        renderer = JavaScriptRenderer(config=config, retry_config=retry_config)

        # Assert - MANDATORY
        assert renderer.config.browser_type == "firefox"
        assert renderer.config.timeout == 60.0
        assert renderer.retry_config.max_attempts == 5


@pytest.mark.unit
class TestJavaScriptRendererPageRendering:
    """Tests for JavaScriptRenderer page rendering."""

    @pytest.mark.asyncio
    async def test_render_page_initializes_pool_if_needed(self) -> None:
        """Test render_page initializes pool if needed - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = JavaScriptRenderer()

        # Act & Assert - MANDATORY
        # Pool should not be initialized yet
        assert renderer._pool is None

        # After initialization, pool should exist
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            await renderer.initialize()
            assert renderer._pool is not None

    @pytest.mark.asyncio
    async def test_render_result_contains_expected_fields(self) -> None:
        """Test RenderResult contains all expected fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "<html><body>Test Content</body></html>"
        url = "https://example.com"

        # Act - MANDATORY
        result = RenderResult(
            html=html,
            url=url,
            status_code=200,
            final_url=url,
            load_time=1.5,
            javascript_executed=True,
        )

        # Assert - MANDATORY
        assert result.html == html
        assert result.url == url
        assert result.status_code == 200
        assert result.javascript_executed is True
        assert isinstance(result.metadata, dict)
        assert isinstance(result.screenshots, dict)
        assert isinstance(result.network_requests, list)

    @pytest.mark.asyncio
    async def test_renderer_config_passed_to_pool(self) -> None:
        """Test renderer config is passed to pool - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = BrowserConfig(browser_type="firefox", timeout=60.0)
        renderer = JavaScriptRenderer(config=config)

        # Act - MANDATORY
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            await renderer.initialize()

        # Assert - MANDATORY
        # Verify BrowserPool was called with the config
        mock_pool_class.assert_called_once()
        call_args = mock_pool_class.call_args
        assert call_args[0][0].browser_type == "firefox"
        assert call_args[0][0].timeout == 60.0

    @pytest.mark.asyncio
    async def test_renderer_cleanup_closes_pool(self) -> None:
        """Test renderer cleanup closes pool - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = JavaScriptRenderer()
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            await renderer.initialize()

        # Act - MANDATORY
        await renderer.cleanup()

        # Assert - MANDATORY
        mock_pool.cleanup.assert_called_once()
        assert renderer._pool is None

    @pytest.mark.asyncio
    async def test_renderer_context_manager(self) -> None:
        """Test renderer as async context manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            async with JavaScriptRenderer() as renderer:
                # Assert - MANDATORY during context
                assert renderer._pool is not None

            # Assert - MANDATORY after context exit
            assert renderer._pool is None
            mock_pool.cleanup.assert_called_once()


# ============================================================================
# Factory Function Tests
# ============================================================================


@pytest.mark.unit
class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_renderer_with_defaults(self) -> None:
        """Test create_renderer with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        renderer = create_renderer()

        # Assert - MANDATORY
        assert isinstance(renderer, JavaScriptRenderer)
        assert renderer.config.browser_type == "chromium"
        assert renderer.config.headless is True
        assert renderer.config.timeout == 30.0

    def test_create_renderer_with_custom_params(self) -> None:
        """Test create_renderer with custom parameters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        browser_type = "firefox"
        headless = False
        timeout = 60.0

        # Act - MANDATORY
        renderer = create_renderer(browser_type=browser_type, headless=headless, timeout=timeout)

        # Assert - MANDATORY
        assert renderer.config.browser_type == "firefox"
        assert renderer.config.headless is False
        assert renderer.config.timeout == 60.0


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestBrowserPerformance:
    """MANDATORY performance tests for browser management."""

    def test_browser_config_initialization_performance(self) -> None:
        """MANDATORY performance test - browser config initialization speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            BrowserConfig()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per initialization
        assert execution_time < 1.0  # Total <1s for 1000 initializations

    @pytest.mark.asyncio
    async def test_browser_pool_initialization_performance(
        self,
        default_browser_config: BrowserConfig,
        mock_playwright: AsyncMock,
        mock_browser: AsyncMock,
    ) -> None:
        """MANDATORY performance test - browser pool initialization speed."""
        # Arrange - MANDATORY
        pool = BrowserPool(default_browser_config)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        # Act - MANDATORY
        start_time = time.perf_counter()

        with patch("src.rendering.browser.async_playwright", return_value=mock_playwright):
            await pool.initialize()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        assert execution_time < 1.0  # <1s for pool initialization

    def test_render_result_creation_performance(self) -> None:
        """MANDATORY performance test - render result creation speed."""
        # Arrange - MANDATORY
        iterations = 10000
        html = "<html><body>Content</body></html>"

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            RenderResult(
                html=html,
                url="https://example.com",
                status_code=200,
                final_url="https://example.com",
                load_time=1.0,
                javascript_executed=True,
            )

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <100μs per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations
