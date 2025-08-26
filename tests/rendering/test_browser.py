"""Unit tests for browser rendering module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rendering.browser import (
    BrowserConfig,
    BrowserPool,
    JavaScriptRenderer,
    RenderResult,
    create_renderer,
)


class TestBrowserConfig:
    """Test browser configuration validation."""

    def test_browser_config_defaults(self):
        """Test default browser configuration values."""
        config = BrowserConfig()

        assert config.browser_type == "chromium"
        assert config.headless is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.timeout == 30.0
        assert config.wait_until == "networkidle"
        assert config.javascript_enabled is True
        assert config.ignore_https_errors is True

    def test_browser_config_custom_values(self):
        """Test custom browser configuration."""
        config = BrowserConfig(
            browser_type="firefox",
            headless=False,
            viewport_width=1366,
            viewport_height=768,
            timeout=60.0,
            wait_until="load",
        )

        assert config.browser_type == "firefox"
        assert config.headless is False
        assert config.viewport_width == 1366
        assert config.viewport_height == 768
        assert config.timeout == 60.0
        assert config.wait_until == "load"

    def test_browser_config_validation_browser_type(self):
        """Test browser type validation."""
        # Valid browser types
        for browser_type in ["chromium", "firefox", "webkit"]:
            config = BrowserConfig(browser_type=browser_type)
            assert config.browser_type == browser_type

        # Invalid browser type
        with pytest.raises(ValueError, match="Browser type must be one of"):
            BrowserConfig(browser_type="invalid")

    def test_browser_config_validation_wait_until(self):
        """Test wait_until validation."""
        # Valid wait conditions
        for condition in ["load", "domcontentloaded", "networkidle"]:
            config = BrowserConfig(wait_until=condition)
            assert config.wait_until == condition

        # Invalid wait condition
        with pytest.raises(ValueError, match="wait_until must be one of"):
            BrowserConfig(wait_until="invalid")


class TestRenderResult:
    """Test render result data structure."""

    def test_render_result_creation(self):
        """Test creating render result."""
        result = RenderResult(
            html="<html></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com/",
            load_time=1.5,
            javascript_executed=True,
        )

        assert result.html == "<html></html>"
        assert result.url == "https://example.com"
        assert result.status_code == 200
        assert result.final_url == "https://example.com/"
        assert result.load_time == 1.5
        assert result.javascript_executed is True
        assert result.metadata == {}
        assert result.screenshots == {}
        assert result.network_requests == []

    def test_render_result_with_metadata(self):
        """Test render result with additional data."""
        metadata = {"title": "Test Page"}
        screenshots = {"main": b"screenshot_data"}
        network_requests = [{"url": "https://api.example.com", "method": "GET"}]

        result = RenderResult(
            html="<html></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=1.0,
            javascript_executed=True,
            metadata=metadata,
            screenshots=screenshots,
            network_requests=network_requests,
        )

        assert result.metadata == metadata
        assert result.screenshots == screenshots
        assert result.network_requests == network_requests


@pytest.mark.asyncio
class TestBrowserPool:
    """Test browser pool management."""

    @pytest.fixture
    def browser_config(self):
        """Create test browser configuration."""
        return BrowserConfig(browser_type="chromium", headless=True)

    @pytest.fixture
    def browser_pool(self, browser_config):
        """Create test browser pool."""
        return BrowserPool(
            config=browser_config, max_contexts=3, context_reuse_limit=5, cleanup_interval=60.0
        )

    async def test_browser_pool_initialization(self, browser_pool):
        """Test browser pool initialization."""
        assert browser_pool._playwright is None
        assert browser_pool._browser is None
        assert browser_pool._contexts == []
        assert browser_pool.max_contexts == 3
        assert browser_pool.context_reuse_limit == 5

    @patch("src.rendering.browser.async_playwright")
    async def test_browser_pool_initialize(self, mock_playwright, browser_pool):
        """Test browser pool initialization process."""
        # Mock Playwright components
        mock_pw_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser_type = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser_type.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.chromium = mock_browser_type

        # Initialize pool
        await browser_pool.initialize()

        # Verify initialization
        assert browser_pool._playwright == mock_pw_instance
        assert browser_pool._browser == mock_browser
        mock_playwright.return_value.start.assert_called_once()
        mock_browser_type.launch.assert_called_once()

    @patch("src.rendering.browser.async_playwright")
    async def test_browser_pool_cleanup(self, mock_playwright, browser_pool):
        """Test browser pool cleanup."""
        # Setup mocks
        mock_pw_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        browser_pool._playwright = mock_pw_instance
        browser_pool._browser = mock_browser
        browser_pool._contexts = [mock_context]
        browser_pool._context_usage = {mock_context: 1}

        # Test cleanup
        await browser_pool.cleanup()

        # Verify cleanup
        assert browser_pool._playwright is None
        assert browser_pool._browser is None
        assert browser_pool._contexts == []
        assert browser_pool._context_usage == {}

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_pw_instance.stop.assert_called_once()

    @patch("src.rendering.browser.async_playwright")
    async def test_browser_pool_context_creation(self, mock_playwright, browser_pool):
        """Test browser context creation."""
        # Setup mocks
        mock_pw_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_pool._playwright = mock_pw_instance
        browser_pool._browser = mock_browser

        # Test context creation
        context = await browser_pool._create_context()

        assert context == mock_context
        mock_browser.new_context.assert_called_once()
        mock_context.set_default_timeout.assert_called_once_with(30000)  # 30 seconds in ms

    @patch("src.rendering.browser.async_playwright")
    async def test_browser_pool_get_context(self, mock_playwright, browser_pool):
        """Test getting context from pool."""
        # Setup mocks
        mock_pw_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_pool._playwright = mock_pw_instance
        browser_pool._browser = mock_browser

        # Test getting context
        async with browser_pool.get_context() as context:
            assert context == mock_context
            assert context in browser_pool._contexts
            assert browser_pool._context_usage[context] == 1

        # Context should still be in pool for reuse
        assert context in browser_pool._contexts

    async def test_browser_pool_context_reuse_limit(self, browser_pool):
        """Test context reuse limit logic."""
        mock_context = AsyncMock()
        browser_pool._context_usage = {mock_context: 5}  # At limit

        should_cleanup = await browser_pool._should_cleanup_context(mock_context)
        assert should_cleanup is True

        browser_pool._context_usage[mock_context] = 4  # Below limit
        should_cleanup = await browser_pool._should_cleanup_context(mock_context)
        assert should_cleanup is False


@pytest.mark.asyncio
class TestJavaScriptRenderer:
    """Test JavaScript renderer functionality."""

    @pytest.fixture
    def renderer_config(self):
        """Create test renderer configuration."""
        return BrowserConfig(browser_type="chromium", headless=True, timeout=10.0)

    @pytest.fixture
    def mock_pool(self):
        """Create mock browser pool."""
        pool = AsyncMock()
        return pool

    @pytest.fixture
    def renderer(self, renderer_config):
        """Create JavaScript renderer."""
        return JavaScriptRenderer(config=renderer_config)

    async def test_renderer_initialization(self, renderer):
        """Test renderer initialization."""
        assert renderer._pool is None

        # Test actual initialization with mocked pool class
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool.initialize = AsyncMock()
            mock_pool_class.return_value = mock_pool

            await renderer.initialize()

            # Verify pool was created and initialized
            mock_pool_class.assert_called_once_with(renderer.config)
            mock_pool.initialize.assert_called_once()
            assert renderer._pool == mock_pool

    async def test_renderer_cleanup(self, renderer):
        """Test renderer cleanup."""
        mock_pool = AsyncMock()
        renderer._pool = mock_pool

        await renderer.cleanup()

        mock_pool.cleanup.assert_called_once()
        assert renderer._pool is None

    @patch("src.rendering.browser.BrowserPool")
    async def test_renderer_render_page(self, mock_pool_class, renderer):
        """Test page rendering functionality."""
        # Setup mocks
        mock_pool = AsyncMock()
        mock_pool_class.return_value = mock_pool

        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_response = AsyncMock()

        mock_response.status = 200
        mock_page.url = "https://example.com/"
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.get_attribute = AsyncMock(return_value="Test Description")
        mock_page.close = AsyncMock()

        mock_context.new_page = AsyncMock(return_value=mock_page)
        # Mock the async context manager properly
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_context():
            yield mock_context

        mock_pool.get_context = mock_get_context

        # Set pool and mock initialize to avoid creating new pool
        renderer._pool = mock_pool
        with patch.object(renderer, "initialize", new_callable=AsyncMock) as mock_init:
            # Test rendering
            result = await renderer.render_page("https://example.com")

            # Verify result
            assert isinstance(result, RenderResult)
            assert result.url == "https://example.com"
            assert result.status_code == 200
            assert result.final_url == "https://example.com/"
            assert result.html == "<html><body>Test</body></html>"
            assert result.javascript_executed is True
            assert result.load_time > 0

            # Verify calls
            mock_page.goto.assert_called_once()
            mock_page.content.assert_called_once()
            mock_page.close.assert_called_once()

    @patch("src.rendering.browser.BrowserPool")
    async def test_renderer_with_custom_options(self, mock_pool_class, renderer):
        """Test rendering with custom options."""
        # Setup mocks similar to previous test
        mock_pool = AsyncMock()
        mock_pool_class.return_value = mock_pool

        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_response = AsyncMock()

        mock_response.status = 200
        mock_page.url = "https://example.com/"
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.content = AsyncMock(return_value="<html></html>")
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.get_attribute = AsyncMock(return_value="")
        mock_page.wait_for_selector = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="script result")
        mock_page.screenshot = AsyncMock(return_value=b"screenshot")
        mock_page.close = AsyncMock()
        mock_page.on = MagicMock()  # For event listeners

        mock_context.new_page = AsyncMock(return_value=mock_page)
        # Mock the async context manager properly
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_context():
            yield mock_context

        mock_pool.get_context = mock_get_context

        # Set pool and mock initialize to avoid creating new pool
        renderer._pool = mock_pool

        with patch.object(renderer, "initialize", new_callable=AsyncMock) as mock_init:
            # Test with custom options
            result = await renderer.render_page(
                url="https://example.com",
                wait_for_selector="div.content",
                execute_script="return document.title;",
                take_screenshot=True,
                capture_network=True,
                additional_wait_time=1.0,
            )

            # Verify custom options were used
            mock_page.wait_for_selector.assert_called_once_with("div.content", timeout=10000)
            mock_page.evaluate.assert_called_once_with("return document.title;")
            mock_page.screenshot.assert_called_once()
            mock_page.on.assert_called()  # Network capture

            assert result.screenshots["main"] == b"screenshot"
            assert result.metadata["script_result"] == "script result"

    async def test_renderer_context_manager(self, renderer):
        """Test renderer as async context manager."""
        with patch.object(renderer, "initialize", new_callable=AsyncMock) as mock_init:
            with patch.object(renderer, "cleanup", new_callable=AsyncMock) as mock_cleanup:
                async with renderer:
                    mock_init.assert_called_once()

                mock_cleanup.assert_called_once()


class TestRendererFactory:
    """Test renderer factory function."""

    def test_create_renderer_defaults(self):
        """Test creating renderer with defaults."""
        renderer = create_renderer()

        assert isinstance(renderer, JavaScriptRenderer)
        assert renderer.config.browser_type == "chromium"
        assert renderer.config.headless is True
        assert renderer.config.timeout == 30.0

    def test_create_renderer_custom(self):
        """Test creating renderer with custom config."""
        renderer = create_renderer(
            browser_type="firefox", headless=False, timeout=60.0, viewport_width=1366
        )

        assert renderer.config.browser_type == "firefox"
        assert renderer.config.headless is False
        assert renderer.config.timeout == 60.0
        assert renderer.config.viewport_width == 1366


# Integration-style tests that don't require actual browser
@pytest.mark.asyncio
class TestRendererIntegration:
    """Integration tests for renderer components."""

    async def test_full_initialization_cleanup_cycle(self):
        """Test complete initialization and cleanup cycle."""
        renderer = create_renderer()

        # Test that we can create and destroy renderer without errors
        assert renderer._pool is None

        # Mock the pool creation
        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            # Test initialization
            await renderer.initialize()
            mock_pool_class.assert_called_once_with(renderer.config)
            mock_pool.initialize.assert_called_once()
            assert renderer._pool == mock_pool

            # Test cleanup
            await renderer.cleanup()
            mock_pool.cleanup.assert_called_once()
            assert renderer._pool is None

    async def test_multiple_renders_reuse_pool(self):
        """Test that multiple renders reuse the same pool."""
        renderer = create_renderer()

        with patch("src.rendering.browser.BrowserPool") as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            # Mock successful renders
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_response = AsyncMock(status=200)
            mock_page.url = "https://example.com"
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html></html>"
            mock_page.title.return_value = "Test"
            mock_page.get_attribute.return_value = ""

            mock_context.new_page.return_value = mock_page
            # Mock the async context manager properly
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def mock_get_context():
                yield mock_context

            mock_pool.get_context = mock_get_context

            # First render should create pool - pool is None initially
            assert renderer._pool is None
            await renderer.render_page("https://example.com/1")
            assert mock_pool_class.call_count == 1
            mock_pool.initialize.assert_called_once()
            assert renderer._pool == mock_pool

            # Second render should reuse pool - pool already exists
            await renderer.render_page("https://example.com/2")
            assert mock_pool_class.call_count == 1  # No additional pool creation
            assert mock_pool.initialize.call_count == 1  # No additional initialization
