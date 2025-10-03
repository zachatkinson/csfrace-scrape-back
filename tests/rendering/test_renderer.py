"""Comprehensive tests for rendering service - MANDATORY TEST_BUILDING.md compliance.

This module tests the adaptive rendering pipeline and service integration:
- RenderingStrategy configuration and validation
- AdaptiveRenderer content analysis and strategy selection
- JavaScript vs static rendering decisions
- Concurrent rendering with multiple URLs
- RenderingService fallback mechanisms
- Factory functions for common configurations

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive rendering pipeline testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest
from pydantic import ValidationError

from src.rendering.browser import BrowserConfig, JavaScriptRenderer, RenderResult
from src.rendering.detector import ContentAnalysis, DynamicContentDetector
from src.rendering.renderer import (
    AdaptiveRenderer,
    RenderingService,
    RenderingStrategy,
    create_adaptive_renderer,
    create_rendering_service,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def default_rendering_strategy() -> RenderingStrategy:
    """Factory for default RenderingStrategy - DRY principle."""
    return RenderingStrategy()


@pytest.fixture
def mock_detector() -> DynamicContentDetector:
    """Factory for mock DynamicContentDetector - DRY principle."""
    detector = MagicMock(spec=DynamicContentDetector)
    detector.analyze_html = MagicMock(
        return_value=ContentAnalysis(
            is_dynamic=False,
            confidence_score=0.3,
            fallback_strategy="standard",
            reasons=["Test analysis"],
        )
    )
    return detector


@pytest.fixture
def mock_js_renderer() -> AsyncMock:
    """Factory for mock JavaScriptRenderer - DRY principle."""
    renderer = AsyncMock(spec=JavaScriptRenderer)
    renderer.initialize = AsyncMock()
    renderer.cleanup = AsyncMock()
    renderer.render_page = AsyncMock(
        return_value=RenderResult(
            html="<html><body>Rendered Content</body></html>",
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            load_time=1.0,
            javascript_executed=True,
        )
    )
    return renderer


@pytest.fixture
def static_html() -> str:
    """Factory for static HTML content - DRY principle."""
    return "<html><body><p>Static content</p></body></html>"


@pytest.fixture
def dynamic_html() -> str:
    """Factory for dynamic HTML content - DRY principle."""
    return """
    <html>
        <head><script src="https://cdn.com/react.min.js"></script></head>
        <body><div id="root"></div></body>
    </html>
    """


# ============================================================================
# RenderingStrategy Tests
# ============================================================================


@pytest.mark.unit
class TestRenderingStrategy:
    """Tests for RenderingStrategy configuration."""

    def test_strategy_initialization_with_defaults(self):
        """Test strategy initializes with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        strategy = RenderingStrategy()

        # Assert - MANDATORY
        assert strategy.force_javascript is False
        assert strategy.force_static is False
        assert strategy.confidence_threshold == 0.5
        assert strategy.enable_screenshots is False
        assert strategy.enable_network_capture is False
        assert strategy.max_concurrent_renders == 3

    def test_strategy_with_custom_values(self):
        """Test strategy accepts custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_values = {
            "force_javascript": True,
            "confidence_threshold": 0.7,
            "enable_screenshots": True,
            "max_concurrent_renders": 10,
        }

        # Act - MANDATORY
        strategy = RenderingStrategy(**custom_values)

        # Assert - MANDATORY
        assert strategy.force_javascript is True
        assert strategy.confidence_threshold == 0.7
        assert strategy.enable_screenshots is True
        assert strategy.max_concurrent_renders == 10

    def test_strategy_rejects_conflicting_force_options(self):
        """Test strategy rejects conflicting force options - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        conflicting_values = {"force_javascript": True, "force_static": True}

        # Act & Assert - MANDATORY
        with pytest.raises(ValidationError) as exc_info:
            RenderingStrategy(**conflicting_values)

        assert "Cannot force both JavaScript and static rendering" in str(exc_info.value)

    def test_strategy_with_browser_config(self):
        """Test strategy with browser config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        browser_config = BrowserConfig(browser_type="firefox", timeout=60.0)

        # Act - MANDATORY
        strategy = RenderingStrategy(browser_config=browser_config)

        # Assert - MANDATORY
        assert strategy.browser_config is not None
        assert strategy.browser_config.browser_type == "firefox"
        assert strategy.browser_config.timeout == 60.0


# ============================================================================
# AdaptiveRenderer Tests
# ============================================================================


@pytest.mark.unit
class TestAdaptiveRendererInitialization:
    """Tests for AdaptiveRenderer initialization."""

    def test_renderer_initialization_with_defaults(self):
        """Test renderer initializes with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        renderer = AdaptiveRenderer()

        # Assert - MANDATORY
        assert renderer.strategy is not None
        assert renderer.detector is not None
        assert renderer._js_renderer is None

    def test_renderer_initialization_with_custom_strategy(
        self, default_rendering_strategy: RenderingStrategy
    ):
        """Test renderer with custom strategy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_strategy = RenderingStrategy(
            force_javascript=False, confidence_threshold=0.8, enable_screenshots=True
        )

        # Act - MANDATORY
        renderer = AdaptiveRenderer(strategy=custom_strategy)

        # Assert - MANDATORY
        assert renderer.strategy.confidence_threshold == 0.8
        assert renderer.strategy.enable_screenshots is True

    def test_renderer_initialization_with_custom_detector(self, mock_detector):
        """Test renderer with custom detector - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (mock_detector from fixture)

        # Act - MANDATORY
        renderer = AdaptiveRenderer(detector=mock_detector)

        # Assert - MANDATORY
        assert renderer.detector == mock_detector


@pytest.mark.unit
class TestAdaptiveRendererContentAnalysis:
    """Tests for AdaptiveRenderer content analysis."""

    @pytest.mark.asyncio
    async def test_analyze_content_with_force_javascript(self, static_html: str):
        """Test analyze_content with forced JavaScript - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = RenderingStrategy(force_javascript=True)
        renderer = AdaptiveRenderer(strategy=strategy)

        # Act - MANDATORY
        should_use_js, analysis = await renderer.analyze_content(static_html)

        # Assert - MANDATORY
        assert should_use_js is True
        assert analysis.is_dynamic is True
        assert analysis.confidence_score == 1.0
        assert analysis.fallback_strategy == "javascript"

    @pytest.mark.asyncio
    async def test_analyze_content_with_force_static(self, dynamic_html: str):
        """Test analyze_content with forced static - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = RenderingStrategy(force_static=True)
        renderer = AdaptiveRenderer(strategy=strategy)

        # Act - MANDATORY
        should_use_js, analysis = await renderer.analyze_content(dynamic_html)

        # Assert - MANDATORY
        assert should_use_js is False
        assert analysis.is_dynamic is False
        assert analysis.confidence_score == 0.0
        assert analysis.fallback_strategy == "standard"

    @pytest.mark.asyncio
    async def test_analyze_content_automatic_detection_static(self, static_html: str):
        """Test automatic detection for static content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()

        # Act - MANDATORY
        should_use_js, analysis = await renderer.analyze_content(static_html)

        # Assert - MANDATORY
        assert should_use_js is False
        assert analysis.confidence_score < 0.5

    @pytest.mark.asyncio
    async def test_analyze_content_automatic_detection_dynamic(self, dynamic_html: str):
        """Test automatic detection for dynamic content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()

        # Act - MANDATORY
        should_use_js, analysis = await renderer.analyze_content(dynamic_html)

        # Assert - MANDATORY
        assert should_use_js is True
        assert "react" in analysis.frameworks_detected

    @pytest.mark.asyncio
    async def test_analyze_content_applies_confidence_threshold(self):
        """Test confidence threshold is applied - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Create HTML that results in medium confidence (around 0.4)
        medium_confidence_html = """
        <html>
            <body>
                <div class="js-content"></div>
                <img data-src="lazy.jpg" />
            </body>
        </html>
        """
        strategy = RenderingStrategy(confidence_threshold=0.6)
        renderer = AdaptiveRenderer(strategy=strategy)

        # Act - MANDATORY
        should_use_js, analysis = await renderer.analyze_content(medium_confidence_html)

        # Assert - MANDATORY
        # Should not use JS because confidence < threshold
        assert should_use_js is False


@pytest.mark.unit
class TestAdaptiveRendererPageRendering:
    """Tests for AdaptiveRenderer page rendering."""

    @pytest.mark.asyncio
    async def test_render_page_with_static_html_sufficient(self, static_html: str, mock_detector):
        """Test render_page uses static HTML when sufficient - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer(detector=mock_detector)
        url = "https://example.com"

        # Act - MANDATORY
        result, analysis = await renderer.render_page(url, static_html=static_html)

        # Assert - MANDATORY
        assert result.html == static_html
        assert result.javascript_executed is False
        assert result.metadata["source"] == "static_provided"

    @pytest.mark.asyncio
    async def test_render_page_uses_javascript_for_dynamic(self, dynamic_html: str):
        """Test render_page uses JavaScript for dynamic content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()
        url = "https://example.com"

        # Mock JavaScript renderer
        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()
            mock_js.render_page = AsyncMock(
                return_value=RenderResult(
                    html="<html><body>JS Rendered</body></html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=1.5,
                    javascript_executed=True,
                )
            )
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            result, analysis = await renderer.render_page(url, static_html=dynamic_html)

        # Assert - MANDATORY
        assert result.javascript_executed is True
        assert "rendering_strategy" in result.metadata
        assert result.metadata["rendering_strategy"] == "javascript"

    @pytest.mark.asyncio
    async def test_render_page_without_static_html(self):
        """Test render_page without static HTML - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()
        url = "https://example.com"

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()
            mock_js.render_page = AsyncMock(
                return_value=RenderResult(
                    html="<html><body>Rendered</body></html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=2.0,
                    javascript_executed=True,
                )
            )
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            result, analysis = await renderer.render_page(url)

        # Assert - MANDATORY
        assert result.javascript_executed is True
        mock_js.render_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_page_applies_strategy_options(self):
        """Test render_page applies strategy options - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = RenderingStrategy(enable_screenshots=True, enable_network_capture=True)
        renderer = AdaptiveRenderer(strategy=strategy)
        url = "https://example.com"

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()
            mock_js.render_page = AsyncMock(
                return_value=RenderResult(
                    html="<html></html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=1.0,
                    javascript_executed=True,
                )
            )
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            await renderer.render_page(url)

        # Assert - MANDATORY
        call_kwargs = mock_js.render_page.call_args.kwargs
        assert call_kwargs.get("take_screenshot") is True
        assert call_kwargs.get("capture_network") is True


@pytest.mark.unit
class TestAdaptiveRendererConcurrentRendering:
    """Tests for AdaptiveRenderer concurrent rendering."""

    @pytest.mark.asyncio
    async def test_render_multiple_urls(self):
        """Test render_multiple with multiple URLs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()

            async def mock_render(url, **kwargs):
                return RenderResult(
                    html=f"<html>{url}</html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=0.5,
                    javascript_executed=True,
                )

            mock_js.render_page = AsyncMock(side_effect=mock_render)
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            results = await renderer.render_multiple(urls)

        # Assert - MANDATORY
        assert len(results) == 3
        for url in urls:
            assert url in results
            result, analysis = results[url]
            assert result.url == url

    @pytest.mark.asyncio
    async def test_render_multiple_handles_errors(self):
        """Test render_multiple handles errors gracefully - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()
        urls = ["https://example.com/1", "https://example.com/2"]

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()

            async def mock_render(url, **kwargs):
                if "2" in url:
                    raise RuntimeError("Test error")
                return RenderResult(
                    html=f"<html>{url}</html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=0.5,
                    javascript_executed=True,
                )

            mock_js.render_page = AsyncMock(side_effect=mock_render)
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            results = await renderer.render_multiple(urls)

        # Assert - MANDATORY
        assert len(results) == 2
        # First URL should succeed
        assert results["https://example.com/1"][0].status_code == 200
        # Second URL should have error result
        assert results["https://example.com/2"][0].status_code == 500
        assert "error" in results["https://example.com/2"][0].metadata

    @pytest.mark.asyncio
    async def test_render_multiple_respects_concurrency_limit(self):
        """Test render_multiple respects concurrency limit - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        strategy = RenderingStrategy(max_concurrent_renders=2)
        renderer = AdaptiveRenderer(strategy=strategy)
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

        concurrent_count = 0
        max_concurrent = 0

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()

            async def mock_render(url, **kwargs):
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.1)  # Simulate work
                concurrent_count -= 1
                return RenderResult(
                    html=f"<html>{url}</html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=0.1,
                    javascript_executed=True,
                )

            mock_js.render_page = AsyncMock(side_effect=mock_render)
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            await renderer.render_multiple(urls, max_concurrent=2)

        # Assert - MANDATORY
        assert max_concurrent <= 2


@pytest.mark.unit
class TestAdaptiveRendererCleanup:
    """Tests for AdaptiveRenderer cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_js_renderer(self):
        """Test cleanup closes JavaScript renderer - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()
            mock_js.cleanup = AsyncMock()
            mock_js_class.return_value = mock_js

            # Initialize renderer
            await renderer._ensure_js_renderer()

            # Act - MANDATORY
            await renderer.cleanup()

        # Assert - MANDATORY
        mock_js.cleanup.assert_called_once()
        assert renderer._js_renderer is None

    @pytest.mark.asyncio
    async def test_renderer_context_manager(self):
        """Test renderer as async context manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        async with AdaptiveRenderer() as renderer:
            # Assert - MANDATORY during context
            assert renderer is not None

        # Cleanup is called automatically on exit


# ============================================================================
# RenderingService Tests
# ============================================================================


@pytest.mark.unit
class TestRenderingService:
    """Tests for RenderingService."""

    def test_service_initialization(self):
        """Test service initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        service = RenderingService()

        # Assert - MANDATORY
        assert service.adaptive_renderer is not None

    @pytest.mark.asyncio
    async def test_should_render_with_javascript(self, static_html: str):
        """Test should_render_with_javascript - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = RenderingService()

        # Act - MANDATORY
        should_use_js, analysis = await service.should_render_with_javascript(static_html)

        # Assert - MANDATORY
        assert isinstance(should_use_js, bool)
        assert isinstance(analysis, ContentAnalysis)

    @pytest.mark.asyncio
    async def test_enhance_static_content_returns_static(self, static_html: str):
        """Test enhance_static_content returns static when sufficient - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = RenderingService()
        url = "https://example.com"

        # Act - MANDATORY
        result = await service.enhance_static_content(url, static_html)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert result == static_html

    @pytest.mark.asyncio
    async def test_enhance_static_content_uses_javascript(self, dynamic_html: str):
        """Test enhance_static_content uses JS for dynamic - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = RenderingService()
        url = "https://example.com"

        with patch("src.rendering.renderer.JavaScriptRenderer") as mock_js_class:
            mock_js = AsyncMock(spec=JavaScriptRenderer)
            mock_js.initialize = AsyncMock()
            mock_js.render_page = AsyncMock(
                return_value=RenderResult(
                    html="<html><body>Enhanced</body></html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=1.0,
                    javascript_executed=True,
                )
            )
            mock_js_class.return_value = mock_js

            # Act - MANDATORY
            result = await service.enhance_static_content(url, dynamic_html)

        # Assert - MANDATORY
        assert isinstance(result, tuple)
        render_result, analysis = result
        assert render_result.javascript_executed is True

    @pytest.mark.asyncio
    async def test_render_page_with_fallback_static_sufficient(self, static_html: str):
        """Test render_page_with_fallback with static - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = RenderingService()
        url = "https://example.com"

        # Act - MANDATORY
        html, metadata = await service.render_page_with_fallback(url, static_html)

        # Assert - MANDATORY
        assert html == static_html
        assert metadata["strategy"] == "static"
        assert metadata["enhanced"] is False

    @pytest.mark.asyncio
    async def test_render_page_with_fallback_error_handling(self):
        """Test render_page_with_fallback handles errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = RenderingService()
        url = "https://example.com"
        # Use dynamic HTML to force JavaScript rendering attempt which will fail
        fallback_html = '<html><head><script src="react.js"></script></head><body><div id="root"></div></body></html>'

        # Mock enhance_static_content to raise an error
        with patch.object(
            service, "enhance_static_content", side_effect=RuntimeError("Test error")
        ):
            # Act - MANDATORY
            html, metadata = await service.render_page_with_fallback(url, fallback_html)

        # Assert - MANDATORY
        assert html == fallback_html
        assert metadata["strategy"] == "fallback_static"
        assert "error" in metadata

    @pytest.mark.asyncio
    async def test_service_context_manager(self):
        """Test service as async context manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        async with RenderingService() as service:
            # Assert - MANDATORY during context
            assert service is not None


# ============================================================================
# Factory Function Tests
# ============================================================================


@pytest.mark.unit
class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_adaptive_renderer_with_defaults(self):
        """Test create_adaptive_renderer with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        renderer = create_adaptive_renderer()

        # Assert - MANDATORY
        assert isinstance(renderer, AdaptiveRenderer)
        assert renderer.strategy.browser_config is not None
        assert renderer.strategy.browser_config.browser_type == "chromium"

    def test_create_adaptive_renderer_with_custom_params(self):
        """Test create_adaptive_renderer with custom params - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        browser_type = "firefox"
        confidence_threshold = 0.7

        # Act - MANDATORY
        renderer = create_adaptive_renderer(
            browser_type=browser_type, confidence_threshold=confidence_threshold
        )

        # Assert - MANDATORY
        assert renderer.strategy.browser_config.browser_type == "firefox"
        assert renderer.strategy.confidence_threshold == 0.7

    def test_create_rendering_service_with_defaults(self):
        """Test create_rendering_service with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        service = create_rendering_service()

        # Assert - MANDATORY
        assert isinstance(service, RenderingService)
        assert service.adaptive_renderer is not None

    def test_create_rendering_service_with_custom_params(self):
        """Test create_rendering_service with custom params - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        browser_type = "webkit"
        confidence_threshold = 0.8

        # Act - MANDATORY
        service = create_rendering_service(
            browser_type=browser_type, confidence_threshold=confidence_threshold
        )

        # Assert - MANDATORY
        assert service.adaptive_renderer.strategy.browser_config.browser_type == "webkit"
        assert service.adaptive_renderer.strategy.confidence_threshold == 0.8


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestRendererPerformance:
    """MANDATORY performance tests for renderer."""

    def test_rendering_strategy_initialization_performance(self):
        """MANDATORY performance test - rendering strategy initialization speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            RenderingStrategy()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per initialization
        assert execution_time < 1.0  # Total <1s for 1000 initializations

    def test_adaptive_renderer_initialization_performance(self):
        """MANDATORY performance test - adaptive renderer initialization speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            AdaptiveRenderer()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per initialization
        assert execution_time < 1.0  # Total <1s for 100 initializations

    @pytest.mark.asyncio
    async def test_analyze_content_performance(self, static_html: str):
        """MANDATORY performance test - content analysis speed."""
        # Arrange - MANDATORY
        renderer = AdaptiveRenderer()
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await renderer.analyze_content(static_html)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.02  # <20ms per analysis
        assert execution_time < 2.0  # Total <2s for 100 analyses
