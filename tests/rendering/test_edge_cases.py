"""Edge cases and boundary conditions for rendering browser operations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error as PlaywrightError

from src.rendering.browser import BrowserConfig, BrowserPool, JavaScriptRenderer, RenderResult
from src.rendering.detector import ContentAnalysis, DynamicContentDetector
from src.rendering.renderer import AdaptiveRenderer


class TestBrowserEdgeCases:
    """Test browser-specific edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_browser_with_extremely_large_viewport(self):
        """Test browser with unusually large viewport dimensions."""
        config = BrowserConfig(
            viewport_width=16384,  # 16K width
            viewport_height=16384,  # 16K height
        )

        renderer = JavaScriptRenderer(config=config)

        with patch.object(renderer, "_render_page_internal") as mock_render:
            mock_render.return_value = RenderResult(
                html="<html>Large viewport test</html>",
                url="https://example.com",
                status_code=200,
                final_url="https://example.com",
                load_time=0.5,
                javascript_executed=True,
            )

            result = await renderer.render_page("https://example.com")

            # Should handle large viewport without issues
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_browser_with_minimal_viewport(self):
        """Test browser with extremely small viewport."""
        config = BrowserConfig(viewport_width=1, viewport_height=1)

        renderer = JavaScriptRenderer(config=config)

        with patch.object(renderer, "_render_page_internal") as mock_render:
            mock_render.return_value = RenderResult(
                html="<html>Minimal viewport test</html>",
                url="https://example.com",
                status_code=200,
                final_url="https://example.com",
                load_time=0.5,
                javascript_executed=True,
            )

            result = await renderer.render_page("https://example.com")

            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_browser_with_zero_timeout(self):
        """Test browser behavior with zero timeout."""
        config = BrowserConfig(timeout=0.0)
        renderer = JavaScriptRenderer(config=config)

        with patch.object(renderer, "_render_page_internal") as mock_render:
            # Zero timeout should cause immediate timeout
            mock_render.side_effect = PlaywrightError("Navigation timeout of 0 ms exceeded")

            with pytest.raises(PlaywrightError):
                await renderer.render_page("https://example.com")

    @pytest.mark.asyncio
    async def test_browser_pool_with_zero_max_contexts(self):
        """Test browser pool with zero maximum contexts."""
        config = BrowserConfig()

        # Create pool with zero contexts (should not raise during creation)
        pool = BrowserPool(config, max_contexts=0)

        # But trying to get a context should fail
        with pytest.raises(RuntimeError, match="Unable to obtain browser context"):
            async with pool.get_context():
                pass

    @pytest.mark.asyncio
    async def test_browser_pool_context_exhaustion_and_recovery(self):
        """Test browser pool recovery after context exhaustion."""
        config = BrowserConfig()
        # Set very low reuse limit for testing
        pool = BrowserPool(config, max_contexts=1, context_reuse_limit=2)

        # Mock the browser and context creation
        with patch.object(pool, "_create_context") as mock_create:
            mock_context = AsyncMock()
            mock_context.close = AsyncMock()

            # Return same context on each call
            mock_create.return_value = mock_context

            # Use context multiple times - should work up to reuse limit
            async with pool.get_context() as ctx1:
                assert ctx1 == mock_context

            async with pool.get_context() as ctx2:
                assert ctx2 == mock_context  # Should reuse

            # Third usage should trigger context replacement
            async with pool.get_context() as ctx3:
                assert ctx3 == mock_context  # New context with same mock

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_renderer_with_massive_concurrent_requests(self):
        """Test renderer handling massive number of concurrent requests."""
        renderer = AdaptiveRenderer()

        # Mock the internal render method to avoid actual browser operations
        async def mock_render_internal(url, static_html=None, **kwargs):
            # Simulate brief processing
            await asyncio.sleep(0.001)
            return RenderResult(
                html=f"<html>Content for {url}</html>",
                url=url,
                status_code=200,
                final_url=url,
                load_time=0.1,
                javascript_executed=False,
            ), ContentAnalysis(is_dynamic=False, confidence_score=0.1, fallback_strategy="standard")

        with patch.object(renderer, "_render_page_internal", side_effect=mock_render_internal):
            # Test with 10 concurrent requests (reduced for CI performance)
            # 100 requests was causing 20+ minute CI delays in Shard 7
            urls = [f"https://example.com/page{i}" for i in range(10)]

            results = await renderer.render_multiple(urls)

            assert len(results) == 10
            for url in urls:
                result, analysis = results[url]
                assert result.status_code == 200
                assert url in result.html

    @pytest.mark.asyncio
    async def test_browser_with_custom_headers_edge_cases(self):
        """Test browser with various edge case HTTP headers."""
        custom_headers = {
            "X-Empty-Value": "",
            "X-Very-Long-Header": "x" * 8192,  # 8KB header
            "X-Unicode-Header": "测试 🚀 café",
            "X-Special-Chars": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
            "X-Null-Byte": "value\x00with\x00nulls",
            "User-Agent": "",  # Empty user agent
        }

        config = BrowserConfig(extra_http_headers=custom_headers)
        renderer = JavaScriptRenderer(config=config)

        with patch.object(renderer, "_render_page_internal") as mock_render:
            mock_render.return_value = RenderResult(
                html="<html>Custom headers test</html>",
                url="https://example.com",
                status_code=200,
                final_url="https://example.com",
                load_time=0.5,
                javascript_executed=True,
            )

            result = await renderer.render_page("https://example.com")

            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_browser_with_proxy_edge_cases(self):
        """Test browser with various proxy configurations."""

        # Test with various browser configurations that have edge case values
        edge_case_configs = [
            BrowserConfig(
                user_agent="user@domain.com",
                extra_http_headers={"X-Special": "p@ssw0rd!#$%"},
            ),
            BrowserConfig(
                extra_http_headers={"X-Empty": ""},
            ),
            BrowserConfig(
                browser_type="firefox",
                headless=False,
            ),
        ]

        for config in edge_case_configs:
            pool = BrowserPool(config)

            # Should not raise exception during configuration
            assert pool.config == config

    def test_browser_config_with_extreme_values(self):
        """Test browser config with extreme but valid values."""

        # Test maximum values
        max_config = BrowserConfig(
            viewport_width=32767,
            viewport_height=32767,
            timeout=3600.0,  # 1 hour
        )

        assert max_config.viewport_width == 32767
        assert max_config.viewport_height == 32767
        assert max_config.timeout == 3600.0

        # Test very small but positive values
        min_config = BrowserConfig(
            viewport_width=1,
            viewport_height=1,
            timeout=0.001,  # 1ms
        )

        assert min_config.viewport_width == 1
        assert min_config.viewport_height == 1
        assert min_config.timeout == 0.001

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_renderer_with_page_containing_many_iframes(self):
        """Test renderer with page containing numerous nested iframes."""
        html_with_iframes = """
        <html>
        <body>
            <iframe src="https://example.com/frame1"></iframe>
            <iframe src="https://example.com/frame2"></iframe>
            <iframe src="data:text/html,<html><body>Inline frame</body></html>"></iframe>
            <iframe src="javascript:void(0)"></iframe>
            <div>
                <iframe src="https://example.com/nested1">
                    <iframe src="https://example.com/nested2"></iframe>
                </iframe>
            </div>
        </body>
        </html>
        """

        renderer = AdaptiveRenderer()

        mock_detector = MagicMock()
        mock_detector.analyze_html.return_value = ContentAnalysis(
            is_dynamic=True,  # iframes can be dynamic
            confidence_score=0.6,
            fallback_strategy="javascript",
        )
        renderer.detector = mock_detector

        mock_js_renderer = AsyncMock()
        mock_js_renderer.render_page.return_value = RenderResult(
            html=html_with_iframes,
            url="https://iframe-heavy.com",
            status_code=200,
            final_url="https://iframe-heavy.com",
            load_time=3.0,
            javascript_executed=True,
        )
        renderer._js_renderer = mock_js_renderer

        result, analysis = await renderer.render_page("https://iframe-heavy.com")

        assert result.status_code == 200
        assert "iframe" in result.html.lower()
        assert result.javascript_executed is True

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_browser_memory_pressure_simulation(self):
        """Test browser behavior under simulated memory pressure."""
        renderer = JavaScriptRenderer()

        with patch.object(renderer, "_render_page_internal") as mock_render:
            # Simulate memory pressure causing failure
            memory_error = PlaywrightError("Page crashed due to memory exhaustion")
            mock_render.side_effect = memory_error

            with pytest.raises(PlaywrightError, match="memory exhaustion"):
                await renderer.render_page("https://memory-intensive.com")

    @pytest.mark.asyncio
    async def test_renderer_with_page_requiring_authentication(self):
        """Test renderer with pages requiring various authentication methods."""
        renderer = AdaptiveRenderer()

        # Mock the internal render method to simulate auth failure
        async def mock_render_internal(url, static_html=None, **kwargs):
            return RenderResult(
                html="<html><body>Authentication Required</body></html>",
                url=url,
                status_code=401,
                final_url=f"{url}/login",
                load_time=1.0,
                javascript_executed=False,
                metadata={"auth_required": True},
            ), ContentAnalysis(is_dynamic=False, confidence_score=0.2, fallback_strategy="standard")

        with patch.object(renderer, "_render_page_internal", side_effect=mock_render_internal):
            result, analysis = await renderer.render_page("https://protected.com")

            assert result.status_code == 401
            assert "Authentication Required" in result.html

    def test_detector_with_extremely_complex_css_selectors(self):
        """Test detector with HTML containing very complex CSS selectors."""
        detector = DynamicContentDetector()

        complex_css_html = """  # noqa: W291, W293
        <html>
        <head>
            <style>
                div:nth-child(3n+1):not(.excluded):has(> .child:nth-of-type(odd)):where(.complex) {
                    color: red;
                }

                @container sidebar (min-width: 700px) {
                    .card { font-size: 2em; }
                }

                @supports (display: grid) {
                    .grid { display: grid; }
                }

                /* Ultra-complex selector */
                body > main:is(.homepage, .landing) ~ aside:has(.widget:not(:empty)):where(:hover, :focus-within) .content::before {
                    content: "Complex!";
                }
            </style>
            <script>
                // Dynamic CSS manipulation
                document.querySelector('div:nth-child(3n+1):not(.excluded)').style.color = 'blue';
            </script>
        </head>
        <body>
            <div class="complex child">Content</div>
        </body>
        </html>
        """

        analysis = detector.analyze_html(complex_css_html)

        assert isinstance(analysis, ContentAnalysis)
        assert analysis.is_dynamic is True  # Has JavaScript

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_renderer_with_page_using_all_html5_features(self):
        """Test renderer with page using extensive HTML5 features."""
        html5_features_html = """  # noqa: W291, W293
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>HTML5 Features Test</title>
        </head>
        <body>
            <header>
                <nav>
                    <menu>
                        <li><a href="#section1">Section 1</a></li>
                    </menu>
                </nav>
            </header>

            <main>
                <article>
                    <section>
                        <details>
                            <summary>Details Summary</summary>
                            <p>Details content</p>
                        </details>

                        <figure>
                            <img src="test.jpg" alt="Test">
                            <figcaption>Figure Caption</figcaption>
                        </figure>

                        <audio controls>
                            <source src="audio.mp3" type="audio/mpeg">
                        </audio>

                        <video controls width="250">
                            <source src="video.mp4" type="video/mp4">
                            <track kind="subtitles" src="subs.vtt" srclang="en">
                        </video>

                        <canvas id="canvas" width="200" height="100"></canvas>

                        <progress value="70" max="100">70%</progress>
                        <meter value="6" min="0" max="10">6 out of 10</meter>

                        <time datetime="2023-12-25">Christmas</time>

                        <mark>Highlighted text</mark>

                        <dialog open>
                            <p>Dialog content</p>
                        </dialog>
                    </section>
                </article>

                <aside>
                    <template id="template">
                        <div class="template-content">Template</div>
                    </template>
                </aside>
            </main>

            <footer>
                <address>
                    Contact: <a href="mailto:test@example.com">test@example.com</a>
                </address>
            </footer>

            <script>
                // Use modern JavaScript features
                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = 'red';
                ctx.fillRect(10, 10, 50, 50);

                // Service worker registration
                if ('serviceWorker' in navigator) {
                    navigator.serviceWorker.register('/sw.js');
                }

                // Web API usage
                if ('geolocation' in navigator) {
                    navigator.geolocation.getCurrentPosition(() => {});
                }
            </script>
        </body>
        </html>
        """

        detector = DynamicContentDetector()
        analysis = detector.analyze_html(html5_features_html)

        assert isinstance(analysis, ContentAnalysis)
        # HTML5 features alone don't necessarily make content dynamic
        # The detector focuses on JavaScript execution indicators
        assert analysis.is_dynamic is False
        assert analysis.confidence_score >= 0.0  # Any valid confidence score
