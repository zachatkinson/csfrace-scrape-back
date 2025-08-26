"""Unit tests for adaptive renderer module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rendering.browser import BrowserConfig, RenderResult
from src.rendering.detector import ContentAnalysis, DynamicContentDetector
from src.rendering.renderer import (
    AdaptiveRenderer,
    RenderingService,
    RenderingStrategy,
    create_adaptive_renderer,
    create_rendering_service,
)


class TestRenderingStrategy:
    """Test rendering strategy configuration."""

    def test_rendering_strategy_defaults(self):
        """Test default rendering strategy values."""
        strategy = RenderingStrategy()

        assert strategy.force_javascript is False
        assert strategy.force_static is False
        assert strategy.confidence_threshold == 0.5
        assert strategy.browser_config is None
        assert strategy.retry_config is None
        assert strategy.enable_screenshots is False
        assert strategy.enable_network_capture is False
        assert strategy.max_concurrent_renders == 3

    def test_rendering_strategy_custom_values(self):
        """Test custom rendering strategy configuration."""
        browser_config = BrowserConfig(browser_type="firefox")

        strategy = RenderingStrategy(
            force_javascript=True,
            confidence_threshold=0.8,
            browser_config=browser_config,
            enable_screenshots=True,
            max_concurrent_renders=5,
        )

        assert strategy.force_javascript is True
        assert strategy.confidence_threshold == 0.8
        assert strategy.browser_config == browser_config
        assert strategy.enable_screenshots is True
        assert strategy.max_concurrent_renders == 5

    def test_rendering_strategy_validation(self):
        """Test rendering strategy validation."""
        # Should not allow both force flags
        with pytest.raises(ValueError, match="Cannot force both"):
            RenderingStrategy(force_javascript=True, force_static=True)


class TestAdaptiveRenderer:
    """Test adaptive renderer functionality."""

    @pytest.fixture
    def mock_detector(self):
        """Mock dynamic content detector."""
        detector = MagicMock(spec=DynamicContentDetector)
        return detector

    @pytest.fixture
    def sample_analysis(self):
        """Sample content analysis."""
        return ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.7,
            frameworks_detected=["react"],
            indicators_found=["js_frameworks_in_scripts"],
            fallback_strategy="javascript",
            reasons=["React framework detected"],
        )

    @pytest.fixture
    def static_analysis(self):
        """Sample static content analysis."""
        return ContentAnalysis(
            is_dynamic=False,
            confidence_score=0.2,
            frameworks_detected=[],
            indicators_found=[],
            fallback_strategy="standard",
            reasons=[],
        )

    @pytest.mark.asyncio
    async def test_adaptive_renderer_initialization(self):
        """Test adaptive renderer initialization."""
        strategy = RenderingStrategy(confidence_threshold=0.8)
        renderer = AdaptiveRenderer(strategy=strategy)

        assert renderer.strategy == strategy
        assert isinstance(renderer.detector, DynamicContentDetector)
        assert renderer._js_renderer is None
        assert renderer._render_semaphore._value == 3  # Default max concurrent

    @pytest.mark.asyncio
    async def test_adaptive_renderer_custom_detector(self, mock_detector):
        """Test adaptive renderer with custom detector."""
        renderer = AdaptiveRenderer(detector=mock_detector)

        assert renderer.detector == mock_detector

    @pytest.mark.asyncio
    async def test_analyze_content_force_javascript(self, mock_detector):
        """Test content analysis with forced JavaScript."""
        strategy = RenderingStrategy(force_javascript=True)
        renderer = AdaptiveRenderer(strategy=strategy, detector=mock_detector)

        should_use_js, analysis = await renderer.analyze_content(
            "<html></html>", "https://example.com"
        )

        assert should_use_js is True
        assert analysis.is_dynamic is True
        assert analysis.confidence_score == 1.0
        assert analysis.fallback_strategy == "javascript"
        assert "Forced JavaScript rendering" in analysis.reasons[0]

        # Detector should not be called when forcing
        mock_detector.analyze_html.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_content_force_static(self, mock_detector):
        """Test content analysis with forced static."""
        strategy = RenderingStrategy(force_static=True)
        renderer = AdaptiveRenderer(strategy=strategy, detector=mock_detector)

        should_use_js, analysis = await renderer.analyze_content(
            "<html></html>", "https://example.com"
        )

        assert should_use_js is False
        assert analysis.is_dynamic is False
        assert analysis.confidence_score == 0.0
        assert analysis.fallback_strategy == "standard"
        assert "Forced static rendering" in analysis.reasons[0]

        # Detector should not be called when forcing
        mock_detector.analyze_html.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_content_automatic_detection(self, mock_detector, sample_analysis):
        """Test automatic content analysis."""
        mock_detector.analyze_html.return_value = sample_analysis

        strategy = RenderingStrategy(confidence_threshold=0.5)
        renderer = AdaptiveRenderer(strategy=strategy, detector=mock_detector)

        html = "<html><script src='react.js'></script></html>"
        should_use_js, analysis = await renderer.analyze_content(html, "https://example.com")

        assert should_use_js is True  # 0.7 > 0.5 threshold
        assert analysis == sample_analysis
        mock_detector.analyze_html.assert_called_once_with(html, "https://example.com")

    @pytest.mark.asyncio
    async def test_analyze_content_below_threshold(self, mock_detector, static_analysis):
        """Test content analysis below confidence threshold."""
        mock_detector.analyze_html.return_value = static_analysis

        strategy = RenderingStrategy(confidence_threshold=0.5)
        renderer = AdaptiveRenderer(strategy=strategy, detector=mock_detector)

        should_use_js, analysis = await renderer.analyze_content("<html></html>")

        assert should_use_js is False  # 0.2 < 0.5 threshold
        assert analysis == static_analysis

    @patch("src.rendering.renderer.JavaScriptRenderer")
    @pytest.mark.asyncio
    async def test_ensure_js_renderer(self, mock_js_renderer_class, mock_detector):
        """Test JavaScript renderer initialization."""
        mock_js_renderer = AsyncMock()
        mock_js_renderer_class.return_value = mock_js_renderer

        renderer = AdaptiveRenderer(detector=mock_detector)

        # First call should create and initialize renderer
        js_renderer = await renderer._ensure_js_renderer()

        assert js_renderer == mock_js_renderer
        assert renderer._js_renderer == mock_js_renderer
        mock_js_renderer.initialize.assert_called_once()

        # Second call should return existing renderer
        js_renderer2 = await renderer._ensure_js_renderer()

        assert js_renderer2 == mock_js_renderer
        assert mock_js_renderer.initialize.call_count == 1  # Not called again

    @patch("src.rendering.renderer.get_recommended_wait_conditions")
    @pytest.mark.asyncio
    async def test_render_page_with_static_html(
        self, mock_wait_conditions, mock_detector, static_analysis
    ):
        """Test rendering with provided static HTML."""
        mock_detector.analyze_html.return_value = static_analysis
        mock_wait_conditions.return_value = {"wait_until": "load"}

        renderer = AdaptiveRenderer(detector=mock_detector)

        static_html = "<html><body>Static content</body></html>"
        result, analysis = await renderer.render_page(
            "https://example.com", static_html=static_html
        )

        # Should use static HTML directly
        assert result.html == static_html
        assert result.url == "https://example.com"
        assert result.status_code == 200
        assert result.javascript_executed is False
        assert analysis == static_analysis

        # Should analyze the provided HTML
        mock_detector.analyze_html.assert_called_with(static_html, "https://example.com")

    @patch("src.rendering.renderer.get_recommended_wait_conditions")
    @pytest.mark.asyncio
    async def test_render_page_javascript_rendering(
        self, mock_wait_conditions, mock_detector, sample_analysis
    ):
        """Test JavaScript rendering."""
        mock_detector.analyze_html.return_value = sample_analysis
        mock_wait_conditions.return_value = {
            "wait_until": "networkidle",
            "additional_wait_time": 2.0,
        }

        # Mock JavaScript renderer
        mock_js_renderer = AsyncMock()
        mock_render_result = RenderResult(
            html="<html><body>Rendered content</body></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=1.5,
            javascript_executed=True,
            metadata={},
        )
        mock_js_renderer.render_page.return_value = mock_render_result

        with patch.object(AdaptiveRenderer, "_ensure_js_renderer", return_value=mock_js_renderer):
            renderer = AdaptiveRenderer(detector=mock_detector)

            static_html = "<html><script src='react.js'></script></html>"
            result, final_analysis = await renderer.render_page(
                "https://example.com", static_html=static_html
            )

            # Should use JavaScript rendering
            assert result.html == "<html><body>Rendered content</body></html>"
            assert result.javascript_executed is True

            # Should call renderer with wait conditions
            expected_options = {
                "take_screenshot": False,
                "capture_network": False,
                "wait_until": "networkidle",
                "additional_wait_time": 2.0,
            }
            mock_js_renderer.render_page.assert_called_once_with(
                "https://example.com", **expected_options
            )

            # Should re-analyze the rendered content
            assert mock_detector.analyze_html.call_count == 2

    @pytest.mark.asyncio
    async def test_render_multiple_pages(self, mock_detector, static_analysis):
        """Test concurrent rendering of multiple pages."""
        mock_detector.analyze_html.return_value = static_analysis

        renderer = AdaptiveRenderer(detector=mock_detector)

        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

        with patch.object(renderer, "render_page") as mock_render:
            # Mock successful renders
            mock_render.side_effect = [
                (
                    RenderResult(
                        html=f"Content {i}",
                        url=url,
                        status_code=200,
                        final_url=url,
                        load_time=1.0,
                        javascript_executed=False,
                    ),
                    static_analysis,
                )
                for i, url in enumerate(urls, 1)
            ]

            results = await renderer.render_multiple(urls)

            assert len(results) == 3
            for i, url in enumerate(urls, 1):
                result, analysis = results[url]
                assert result.html == f"Content {i}"
                assert result.url == url

    @pytest.mark.asyncio
    async def test_render_multiple_with_errors(self, mock_detector):
        """Test concurrent rendering with some failures."""
        renderer = AdaptiveRenderer(detector=mock_detector)

        urls = ["https://example.com/1", "https://example.com/2"]

        with patch.object(renderer, "render_page") as mock_render:
            # First succeeds, second fails
            mock_render.side_effect = [
                (
                    RenderResult(
                        html="Success",
                        url=urls[0],
                        status_code=200,
                        final_url=urls[0],
                        load_time=1.0,
                        javascript_executed=False,
                    ),
                    ContentAnalysis(is_dynamic=False, confidence_score=0.2),
                ),
                Exception("Render failed"),
            ]

            results = await renderer.render_multiple(urls)

            assert len(results) == 2

            # First should succeed
            result1, analysis1 = results[urls[0]]
            assert result1.html == "Success"
            assert result1.status_code == 200

            # Second should be error result
            result2, analysis2 = results[urls[1]]
            assert result2.status_code == 500
            assert "error" in result2.metadata
            assert analysis2.fallback_strategy == "error"

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test renderer cleanup."""
        renderer = AdaptiveRenderer()

        # Mock JavaScript renderer
        mock_js_renderer = AsyncMock()
        renderer._js_renderer = mock_js_renderer

        await renderer.cleanup()

        mock_js_renderer.cleanup.assert_called_once()
        assert renderer._js_renderer is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test renderer as context manager."""
        renderer = AdaptiveRenderer()

        async with renderer:
            assert renderer is not None

        # Should be cleaned up after context exit
        assert renderer._js_renderer is None


class TestRenderingService:
    """Test high-level rendering service."""

    @pytest.fixture
    def mock_adaptive_renderer(self):
        """Mock adaptive renderer."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_rendering_service_initialization(self):
        """Test rendering service initialization."""
        service = RenderingService()

        assert isinstance(service.adaptive_renderer, AdaptiveRenderer)

    @pytest.mark.asyncio
    async def test_should_render_with_javascript(self, mock_adaptive_renderer):
        """Test JavaScript rendering decision."""
        expected_analysis = ContentAnalysis(is_dynamic=True, confidence_score=0.8)
        mock_adaptive_renderer.analyze_content.return_value = (True, expected_analysis)

        service = RenderingService()
        service.adaptive_renderer = mock_adaptive_renderer

        should_use_js, analysis = await service.should_render_with_javascript(
            "<html></html>", "https://example.com"
        )

        assert should_use_js is True
        assert analysis == expected_analysis
        mock_adaptive_renderer.analyze_content.assert_called_once_with(
            "<html></html>", "https://example.com"
        )

    @pytest.mark.asyncio
    async def test_enhance_static_content_no_enhancement(self, mock_adaptive_renderer):
        """Test static content that doesn't need enhancement."""
        static_analysis = ContentAnalysis(is_dynamic=False, confidence_score=0.2)
        mock_adaptive_renderer.analyze_content.return_value = (False, static_analysis)

        service = RenderingService()
        service.adaptive_renderer = mock_adaptive_renderer

        static_html = "<html><body>Static</body></html>"
        result = await service.enhance_static_content("https://example.com", static_html)

        # Should return original HTML
        assert result == static_html

    @pytest.mark.asyncio
    async def test_enhance_static_content_with_enhancement(self, mock_adaptive_renderer):
        """Test static content that gets enhanced with JavaScript."""
        dynamic_analysis = ContentAnalysis(is_dynamic=True, confidence_score=0.8)
        mock_adaptive_renderer.analyze_content.return_value = (True, dynamic_analysis)

        enhanced_result = RenderResult(
            html="<html><body>Enhanced</body></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=2.0,
            javascript_executed=True,
        )
        final_analysis = ContentAnalysis(is_dynamic=True, confidence_score=0.9)
        mock_adaptive_renderer.render_page.return_value = (enhanced_result, final_analysis)

        service = RenderingService()
        service.adaptive_renderer = mock_adaptive_renderer

        static_html = "<html><script>app.render()</script></html>"
        result, analysis = await service.enhance_static_content("https://example.com", static_html)

        # Should return enhanced result
        assert result == enhanced_result
        assert analysis == final_analysis
        mock_adaptive_renderer.render_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_page_with_fallback_static_sufficient(self, mock_adaptive_renderer):
        """Test rendering with static content being sufficient."""
        service = RenderingService()
        service.adaptive_renderer = mock_adaptive_renderer

        with patch.object(service, "enhance_static_content", return_value="<html>Static</html>"):
            html, metadata = await service.render_page_with_fallback(
                "https://example.com", static_html="<html>Original</html>"
            )

            assert html == "<html>Static</html>"
            assert metadata["strategy"] == "static"
            assert metadata["enhanced"] is False

    @pytest.mark.asyncio
    async def test_render_page_with_fallback_enhancement(self, mock_adaptive_renderer):
        """Test rendering with JavaScript enhancement."""
        service = RenderingService()
        service.adaptive_renderer = mock_adaptive_renderer

        enhanced_result = RenderResult(
            html="<html>Enhanced</html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=1.0,
            javascript_executed=True,
            metadata={"test": "data"},
        )
        analysis = ContentAnalysis(is_dynamic=True, confidence_score=0.8)

        with patch.object(
            service, "enhance_static_content", return_value=(enhanced_result, analysis)
        ):
            html, metadata = await service.render_page_with_fallback(
                "https://example.com", static_html="<html>Original</html>"
            )

            assert html == "<html>Enhanced</html>"
            assert metadata["strategy"] == "javascript"
            assert metadata["enhanced"] is True
            assert "analysis" in metadata
            assert "metadata" in metadata

    @pytest.mark.asyncio
    async def test_render_page_with_fallback_error(self, mock_adaptive_renderer):
        """Test rendering with error fallback."""
        service = RenderingService()
        service.adaptive_renderer = mock_adaptive_renderer

        with patch.object(
            service, "enhance_static_content", side_effect=Exception("Render failed")
        ):
            html, metadata = await service.render_page_with_fallback(
                "https://example.com", static_html="<html>Fallback</html>"
            )

            # Should fallback to static content
            assert html == "<html>Fallback</html>"
            assert metadata["strategy"] == "fallback_static"
            assert "error" in metadata

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test service as context manager."""
        service = RenderingService()

        with patch.object(service, "cleanup") as mock_cleanup:
            async with service:
                pass

            mock_cleanup.assert_called_once()


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_adaptive_renderer(self):
        """Test adaptive renderer factory."""
        renderer = create_adaptive_renderer(
            browser_type="firefox",
            headless=False,
            timeout=60.0,
            confidence_threshold=0.8,
            enable_screenshots=True,
        )

        assert isinstance(renderer, AdaptiveRenderer)
        assert renderer.strategy.browser_config.browser_type == "firefox"
        assert renderer.strategy.browser_config.headless is False
        assert renderer.strategy.browser_config.timeout == 60.0
        assert renderer.strategy.confidence_threshold == 0.8
        assert renderer.strategy.enable_screenshots is True

    def test_create_rendering_service(self):
        """Test rendering service factory."""
        service = create_rendering_service(browser_type="webkit", confidence_threshold=0.7)

        assert isinstance(service, RenderingService)
        assert isinstance(service.adaptive_renderer, AdaptiveRenderer)
        assert service.adaptive_renderer.strategy.browser_config.browser_type == "webkit"
        assert service.adaptive_renderer.strategy.confidence_threshold == 0.7
