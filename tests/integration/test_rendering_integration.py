"""Integration tests for rendering module."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.rendering.browser import BrowserConfig, JavaScriptRenderer, create_renderer
from src.rendering.detector import (
    DynamicContentDetector,
    get_recommended_wait_conditions,
    should_use_javascript_rendering,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestRenderingIntegration:
    """Integration tests for rendering capabilities."""

    @pytest.fixture
    def renderer_config(self):
        """Test renderer configuration."""
        return BrowserConfig(
            browser_type="chromium",
            headless=True,
            timeout=10.0,
            viewport_width=1280,
            viewport_height=720,
        )

    @pytest.fixture
    def sample_static_html(self):
        """Sample static HTML for testing."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Static Test Page</title>
            <meta name="description" content="A test page for static content">
        </head>
        <body>
            <header>
                <h1>Welcome to Test Page</h1>
                <nav>
                    <a href="/home">Home</a>
                    <a href="/about">About</a>
                </nav>
            </header>
            <main>
                <article>
                    <h2>Article Title</h2>
                    <p>This is a paragraph with static content.</p>
                    <p>Another paragraph with more content.</p>
                    <ul>
                        <li>List item 1</li>
                        <li>List item 2</li>
                        <li>List item 3</li>
                    </ul>
                </article>
            </main>
            <footer>
                <p>&copy; 2024 Test Site</p>
            </footer>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_spa_html(self):
        """Sample SPA HTML for testing."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>React App</title>
            <script src="https://unpkg.com/react@17/umd/react.development.js"></script>
            <script src="https://unpkg.com/react-dom@17/umd/react-dom.development.js"></script>
        </head>
        <body>
            <div id="react-root"></div>
            <script>
                const { useState } = React;

                function App() {
                    const [count, setCount] = useState(0);
                    return React.createElement('div', null,
                        React.createElement('h1', null, 'React Counter'),
                        React.createElement('p', null, `Count: ${count}`),
                        React.createElement('button', {
                            onClick: () => setCount(count + 1)
                        }, 'Increment')
                    );
                }

                ReactDOM.render(React.createElement(App), document.getElementById('react-root'));
            </script>
        </body>
        </html>
        """

    async def test_detector_static_content_analysis(self, sample_static_html):
        """Test dynamic content detector on static content."""
        detector = DynamicContentDetector()
        analysis = detector.analyze_html(sample_static_html, "https://example.com/static")

        # Static content should not require JavaScript rendering
        assert analysis.is_dynamic is False
        assert analysis.confidence_score < 0.5
        assert analysis.fallback_strategy == "standard"
        assert len(analysis.frameworks_detected) == 0
        assert "Static" not in analysis.reasons or len(analysis.reasons) == 0

    async def test_detector_spa_content_analysis(self, sample_spa_html):
        """Test dynamic content detector on SPA content."""
        detector = DynamicContentDetector()
        analysis = detector.analyze_html(sample_spa_html, "https://example.com/spa")

        # SPA content should require JavaScript rendering
        assert analysis.is_dynamic is True
        assert analysis.confidence_score > 0.5
        assert analysis.fallback_strategy in ["javascript", "hybrid"]
        assert "react" in analysis.frameworks_detected
        assert "js_frameworks_in_scripts" in analysis.indicators_found
        assert len(analysis.reasons) > 0

    async def test_should_use_javascript_rendering_utility(
        self, sample_static_html, sample_spa_html
    ):
        """Test utility function for determining JavaScript rendering need."""
        # Static content
        should_use_js, static_analysis = should_use_javascript_rendering(
            sample_static_html, "https://example.com/static"
        )
        assert should_use_js is False
        assert static_analysis.is_dynamic is False

        # SPA content
        should_use_js, spa_analysis = should_use_javascript_rendering(
            sample_spa_html, "https://example.com/spa"
        )
        assert should_use_js is True
        assert spa_analysis.is_dynamic is True

    @patch("src.rendering.browser.async_playwright")
    async def test_renderer_initialization_lifecycle(self, mock_playwright, renderer_config):
        """Test complete renderer initialization and cleanup lifecycle."""
        # Setup mocks
        mock_pw_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser = AsyncMock()
        mock_browser_type = AsyncMock()
        mock_browser_type.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.chromium = mock_browser_type

        # Test renderer lifecycle
        renderer = JavaScriptRenderer(config=renderer_config)

        # Initial state
        assert renderer._pool is None

        # Initialize
        await renderer.initialize()
        assert renderer._pool is not None

        # Verify Playwright was started and browser launched
        mock_playwright.return_value.start.assert_called_once()
        mock_browser_type.launch.assert_called_once()

        # Cleanup
        await renderer.cleanup()
        assert renderer._pool is None

    @patch("src.rendering.browser.async_playwright")
    async def test_renderer_context_manager_lifecycle(self, mock_playwright, renderer_config):
        """Test renderer as async context manager."""
        # Setup mocks
        mock_pw_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser = AsyncMock()
        mock_browser_type = AsyncMock()
        mock_browser_type.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.chromium = mock_browser_type

        renderer = JavaScriptRenderer(config=renderer_config)

        # Test context manager
        async with renderer:
            assert renderer._pool is not None

        # Should be cleaned up after context exit
        assert renderer._pool is None

    @patch("src.rendering.browser.async_playwright")
    async def test_full_rendering_workflow(self, mock_playwright, renderer_config, sample_spa_html):
        """Test complete rendering workflow from detection to rendering."""
        # Setup comprehensive mocks
        mock_pw_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser = AsyncMock()
        mock_browser_type = AsyncMock()
        mock_browser_type.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.chromium = mock_browser_type

        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_page = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_page.url = "https://example.com/spa"
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.content = AsyncMock(return_value=sample_spa_html)
        mock_page.title = AsyncMock(return_value="React App")
        mock_page.get_attribute = AsyncMock(return_value="A test page")
        mock_page.close = AsyncMock()

        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Step 1: Detect if JavaScript rendering is needed
        should_use_js, analysis = should_use_javascript_rendering(sample_spa_html)
        assert should_use_js is True
        assert "react" in analysis.frameworks_detected

        # Step 2: Create renderer and render page
        renderer = JavaScriptRenderer(config=renderer_config)

        try:
            await renderer.initialize()

            # Mock the pool context manager
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def mock_get_context():
                yield mock_context

            renderer._pool.get_context = mock_get_context

            # Render the page
            result = await renderer.render_page("https://example.com/spa")

            # Verify the result
            assert result.url == "https://example.com/spa"
            assert result.status_code == 200
            assert result.final_url == "https://example.com/spa"
            assert result.html == sample_spa_html
            assert result.javascript_executed is True
            assert result.load_time > 0
            assert result.metadata["title"] == "React App"

            # Verify calls were made
            mock_page.goto.assert_called_once()
            mock_page.content.assert_called_once()
            mock_page.close.assert_called_once()

        finally:
            await renderer.cleanup()

    async def test_content_type_determination_workflow(self):
        """Test complete workflow for different content types."""
        detector = DynamicContentDetector()

        # Test multiple HTML samples
        test_cases = [
            {
                "name": "WordPress blog",
                "html": """
                <html>
                <body>
                    <div class="wp-content">
                        <article class="post">
                            <h1>Blog Post Title</h1>
                            <p>Content of the blog post.</p>
                        </article>
                    </div>
                </body>
                </html>
                """,
                "expected_dynamic": False,
                "expected_strategy": "standard",
            },
            {
                "name": "Vue.js app",
                "html": """
                <html>
                <head>
                    <script src="vue.min.js"></script>
                </head>
                <body>
                    <div id="app" v-app>
                        <h1>{{ title }}</h1>
                    </div>
                </body>
                </html>
                """,
                "expected_dynamic": True,
                "expected_strategy": ["javascript", "hybrid"],
            },
            {
                "name": "jQuery enhanced page",
                "html": """
                <html>
                <head>
                    <script src="jquery.min.js"></script>
                </head>
                <body>
                    <div class="content">
                        <h1>Enhanced Content</h1>
                        <p>Some content here.</p>
                        <div class="js-accordion">Accordion</div>
                    </div>
                    <script>$('.js-accordion').accordion();</script>
                </body>
                </html>
                """,
                "expected_dynamic": True,
                "expected_strategy": ["hybrid", "javascript"],
            },
            {
                "name": "Lazy loading images",
                "html": """
                <html>
                <body>
                    <h1>Gallery</h1>
                    <img data-src="image1.jpg" class="lazyload" alt="Image 1">
                    <img data-src="image2.jpg" class="lazyload" alt="Image 2">
                    <img data-src="image3.jpg" class="lazyload" alt="Image 3">
                </body>
                </html>
                """,
                "expected_dynamic": True,  # Lazy loading indicates dynamic content
                "expected_strategy": ["standard", "hybrid"],
            },
        ]

        for case in test_cases:
            analysis = detector.analyze_html(case["html"])

            # Check dynamic detection
            assert analysis.is_dynamic == case["expected_dynamic"], (
                f"Failed for {case['name']}: expected dynamic={case['expected_dynamic']}, "
                f"got {analysis.is_dynamic}"
            )

            # Check strategy (allow multiple valid strategies)
            expected_strategies = case["expected_strategy"]
            if isinstance(expected_strategies, str):
                expected_strategies = [expected_strategies]

            assert analysis.fallback_strategy in expected_strategies, (
                f"Failed for {case['name']}: expected strategy in {expected_strategies}, "
                f"got {analysis.fallback_strategy}"
            )

    async def test_renderer_error_handling(self, renderer_config):
        """Test renderer error handling scenarios."""
        renderer = JavaScriptRenderer(config=renderer_config)

        # Test rendering without initialization
        with pytest.raises(Exception):
            # Should auto-initialize, but if it fails, should raise
            with patch.object(renderer, "initialize", side_effect=Exception("Init failed")):
                await renderer.render_page("https://example.com")

    async def test_browser_config_validation_integration(self):
        """Test browser configuration validation in integration context."""
        # Valid configurations should work
        valid_configs = [
            BrowserConfig(browser_type="chromium"),
            BrowserConfig(browser_type="firefox"),
            BrowserConfig(browser_type="webkit"),
            BrowserConfig(wait_until="load"),
            BrowserConfig(wait_until="domcontentloaded"),
            BrowserConfig(wait_until="networkidle"),
        ]

        for config in valid_configs:
            renderer = JavaScriptRenderer(config=config)
            assert renderer.config == config

        # Invalid configurations should fail
        with pytest.raises(ValueError):
            BrowserConfig(browser_type="invalid_browser")

        with pytest.raises(ValueError):
            BrowserConfig(wait_until="invalid_condition")

    async def test_create_renderer_factory_integration(self):
        """Test renderer factory function integration."""
        # Default renderer
        renderer1 = create_renderer()
        assert renderer1.config.browser_type == "chromium"
        assert renderer1.config.headless is True

        # Custom renderer
        renderer2 = create_renderer(browser_type="firefox", headless=False, timeout=60.0)
        assert renderer2.config.browser_type == "firefox"
        assert renderer2.config.headless is False
        assert renderer2.config.timeout == 60.0

        # Both should be different instances
        assert renderer1 is not renderer2
        assert renderer1.config != renderer2.config

    @patch("src.rendering.browser.async_playwright")
    async def test_concurrent_rendering_workflow(self, mock_playwright, renderer_config):
        """Test concurrent rendering operations."""
        # Setup mocks
        mock_pw_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser = AsyncMock()
        mock_browser_type = AsyncMock()
        mock_browser_type.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.chromium = mock_browser_type

        # Create multiple mock contexts
        mock_contexts = [AsyncMock() for _ in range(3)]
        mock_browser.new_context = AsyncMock(side_effect=mock_contexts)

        # Setup pages for each context
        for i, context in enumerate(mock_contexts):
            mock_page = AsyncMock()
            mock_response = AsyncMock(status=200)
            mock_page.url = f"https://example.com/page{i}"
            mock_page.goto = AsyncMock(return_value=mock_response)
            mock_page.content = AsyncMock(return_value=f"<html><body>Page {i}</body></html>")
            mock_page.title = AsyncMock(return_value=f"Page {i}")
            mock_page.get_attribute = AsyncMock(return_value="")
            mock_page.close = AsyncMock()
            context.new_page = AsyncMock(return_value=mock_page)

        renderer = JavaScriptRenderer(config=renderer_config)

        try:
            await renderer.initialize()

            # Mock the pool to return different contexts
            from contextlib import asynccontextmanager

            context_iter = iter(mock_contexts)

            @asynccontextmanager
            async def mock_get_context():
                context = next(context_iter)
                yield context

            renderer._pool.get_context = mock_get_context

            # Render multiple pages concurrently
            urls = [
                "https://example.com/page0",
                "https://example.com/page1",
                "https://example.com/page2",
            ]

            tasks = [renderer.render_page(url) for url in urls]
            results = await asyncio.gather(*tasks)

            # Verify all results
            assert len(results) == 3
            for i, result in enumerate(results):
                assert result.url == f"https://example.com/page{i}"
                assert result.status_code == 200
                assert f"Page {i}" in result.html

        finally:
            await renderer.cleanup()

    async def test_detection_and_rendering_consistency(self, sample_static_html, sample_spa_html):
        """Test consistency between detection and rendering decisions."""
        detector = DynamicContentDetector()

        # Test static content
        static_analysis = detector.analyze_html(sample_static_html)
        static_conditions = get_recommended_wait_conditions(static_analysis)

        # Should recommend standard approach for static content
        assert static_analysis.fallback_strategy == "standard"
        # Conditions should be minimal for static content

        # Test SPA content
        spa_analysis = detector.analyze_html(sample_spa_html)

        # Should recommend JavaScript rendering for SPA
        assert spa_analysis.fallback_strategy in ["javascript", "hybrid"]
        assert spa_analysis.is_dynamic is True
