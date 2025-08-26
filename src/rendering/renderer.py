"""High-level rendering service that integrates detection and browser automation."""

import asyncio
from dataclasses import asdict
from typing import Any, Optional, Union

import structlog
from pydantic import BaseModel, Field

from src.rendering.browser import BrowserConfig, JavaScriptRenderer, RenderResult
from src.rendering.detector import (
    ContentAnalysis,
    DynamicContentDetector,
    get_recommended_wait_conditions,
)
from src.utils.retry import RetryConfig

logger = structlog.get_logger(__name__)


class RenderingStrategy(BaseModel):
    """Configuration for rendering strategy."""

    # Detection settings
    force_javascript: bool = Field(default=False, description="Force JavaScript rendering")
    force_static: bool = Field(default=False, description="Force static HTTP rendering")
    confidence_threshold: float = Field(
        default=0.5, description="Confidence threshold for JS rendering"
    )

    # Browser settings
    browser_config: Optional[BrowserConfig] = Field(
        default=None, description="Browser configuration"
    )

    # Retry settings
    retry_config: Optional[RetryConfig] = Field(default=None, description="Retry configuration")

    # Performance settings
    enable_screenshots: bool = Field(default=False, description="Enable screenshot capture")
    enable_network_capture: bool = Field(
        default=False, description="Enable network request capture"
    )
    max_concurrent_renders: int = Field(default=3, description="Maximum concurrent renders")

    def model_post_init(self, __context):
        """Post-initialization validation."""
        if self.force_javascript and self.force_static:
            raise ValueError("Cannot force both JavaScript and static rendering")


class AdaptiveRenderer:
    """Adaptive renderer that automatically chooses the best rendering strategy."""

    def __init__(
        self,
        strategy: Optional[RenderingStrategy] = None,
        detector: Optional[DynamicContentDetector] = None,
    ):
        self.strategy = strategy or RenderingStrategy()
        self.detector = detector or DynamicContentDetector()

        # Initialize browser renderer lazily
        self._js_renderer: Optional[JavaScriptRenderer] = None
        self._render_semaphore = asyncio.Semaphore(self.strategy.max_concurrent_renders)

        logger.info("Adaptive renderer initialized", strategy=self.strategy.model_dump())

    async def _ensure_js_renderer(self) -> JavaScriptRenderer:
        """Ensure JavaScript renderer is initialized."""
        if not self._js_renderer:
            browser_config = self.strategy.browser_config or BrowserConfig()

            self._js_renderer = JavaScriptRenderer(
                config=browser_config, retry_config=self.strategy.retry_config
            )
            await self._js_renderer.initialize()

            logger.debug("JavaScript renderer initialized")

        return self._js_renderer

    async def analyze_content(
        self, html: str, url: Optional[str] = None
    ) -> tuple[bool, ContentAnalysis]:
        """Analyze content to determine rendering strategy."""
        # Check for forced strategies
        if self.strategy.force_javascript:
            logger.debug("JavaScript rendering forced by configuration")
            # Create a mock analysis for forced JS
            analysis = ContentAnalysis(
                is_dynamic=True,
                confidence_score=1.0,
                fallback_strategy="javascript",
                reasons=["Forced JavaScript rendering by configuration"],
            )
            return True, analysis

        if self.strategy.force_static:
            logger.debug("Static rendering forced by configuration")
            # Create a mock analysis for forced static
            analysis = ContentAnalysis(
                is_dynamic=False,
                confidence_score=0.0,
                fallback_strategy="standard",
                reasons=["Forced static rendering by configuration"],
            )
            return False, analysis

        # Perform automatic detection
        analysis = self.detector.analyze_html(html, url)

        # Apply confidence threshold
        should_use_js = (
            analysis.is_dynamic and analysis.confidence_score >= self.strategy.confidence_threshold
        )

        logger.debug(
            "Content analysis completed",
            url=url,
            is_dynamic=analysis.is_dynamic,
            confidence_score=analysis.confidence_score,
            should_use_js=should_use_js,
            strategy=analysis.fallback_strategy,
            indicators=len(analysis.indicators_found),
        )

        return should_use_js, analysis

    async def render_page(
        self, url: str, static_html: Optional[str] = None, **render_options
    ) -> tuple[RenderResult, ContentAnalysis]:
        """Render a page using adaptive strategy selection."""
        async with self._render_semaphore:
            return await self._render_page_internal(url, static_html, **render_options)

    async def _render_page_internal(
        self, url: str, static_html: Optional[str] = None, **render_options
    ) -> tuple[RenderResult, ContentAnalysis]:
        """Internal page rendering implementation."""
        start_time = asyncio.get_event_loop().time()

        # If static HTML is provided, analyze it first
        if static_html:
            should_use_js, analysis = await self.analyze_content(static_html, url)

            # If static content is sufficient, return it as render result
            if not should_use_js:
                logger.info(
                    "Using static HTML content",
                    url=url,
                    strategy=analysis.fallback_strategy,
                    confidence=analysis.confidence_score,
                )

                render_time = asyncio.get_event_loop().time() - start_time

                return RenderResult(
                    html=static_html,
                    url=url,
                    status_code=200,  # Assume success for provided HTML
                    final_url=url,
                    load_time=render_time,
                    javascript_executed=False,
                    metadata={"analysis": asdict(analysis), "source": "static_provided"},
                ), analysis

        # Use JavaScript rendering
        logger.info("Using JavaScript rendering", url=url)

        js_renderer = await self._ensure_js_renderer()

        # Get recommended wait conditions from analysis
        wait_conditions = {}
        if static_html:
            wait_conditions = get_recommended_wait_conditions(analysis)

        # Merge with user-provided options
        render_options.update(
            {
                "take_screenshot": render_options.get(
                    "take_screenshot", self.strategy.enable_screenshots
                ),
                "capture_network": render_options.get(
                    "capture_network", self.strategy.enable_network_capture
                ),
                **wait_conditions,
            }
        )

        # Perform JavaScript rendering
        result = await js_renderer.render_page(url, **render_options)

        # Re-analyze the rendered content for verification
        final_analysis = self.detector.analyze_html(result.html, url)

        # Add analysis metadata to result
        result.metadata.update(
            {
                "initial_analysis": asdict(analysis) if static_html else None,
                "final_analysis": asdict(final_analysis),
                "rendering_strategy": "javascript",
            }
        )

        logger.info(
            "JavaScript rendering completed",
            url=url,
            final_url=result.final_url,
            status_code=result.status_code,
            load_time=result.load_time,
            html_length=len(result.html),
        )

        return result, final_analysis

    async def render_multiple(
        self, urls: list[str], **render_options
    ) -> dict[str, tuple[RenderResult, ContentAnalysis]]:
        """Render multiple pages concurrently."""
        logger.info("Starting concurrent rendering", url_count=len(urls))

        # Create tasks for concurrent rendering
        tasks = []
        for url in urls:
            task = asyncio.create_task(
                self.render_page(url, **render_options), name=f"render_{url}"
            )
            tasks.append(task)

        # Execute all tasks and collect results
        results = {}
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)

        for url, task_result in zip(urls, completed_tasks):
            if isinstance(task_result, Exception):
                logger.error("Rendering failed for URL", url=url, error=str(task_result))
                # Create error result
                error_result = RenderResult(
                    html="",
                    url=url,
                    status_code=500,
                    final_url=url,
                    load_time=0.0,
                    javascript_executed=False,
                    metadata={"error": str(task_result)},
                )
                error_analysis = ContentAnalysis(
                    is_dynamic=False,
                    confidence_score=0.0,
                    fallback_strategy="error",
                    reasons=[f"Rendering failed: {task_result}"],
                )
                results[url] = (error_result, error_analysis)
            else:
                results[url] = task_result

        success_count = sum(1 for r, a in results.values() if r.status_code < 400)
        logger.info(
            "Concurrent rendering completed",
            total_urls=len(urls),
            successful=success_count,
            failed=len(urls) - success_count,
        )

        return results

    async def cleanup(self) -> None:
        """Clean up renderer resources."""
        if self._js_renderer:
            await self._js_renderer.cleanup()
            self._js_renderer = None

        logger.info("Adaptive renderer cleaned up")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


class RenderingService:
    """High-level rendering service for integration with scrapers."""

    def __init__(
        self,
        strategy: Optional[RenderingStrategy] = None,
        detector: Optional[DynamicContentDetector] = None,
    ):
        self.adaptive_renderer = AdaptiveRenderer(strategy, detector)

    async def should_render_with_javascript(
        self, html: str, url: Optional[str] = None
    ) -> tuple[bool, ContentAnalysis]:
        """Determine if JavaScript rendering is needed for given HTML."""
        return await self.adaptive_renderer.analyze_content(html, url)

    async def enhance_static_content(
        self, url: str, static_html: str, **render_options
    ) -> Union[str, tuple[RenderResult, ContentAnalysis]]:
        """Enhance static content with JavaScript rendering if needed."""
        should_use_js, analysis = await self.should_render_with_javascript(static_html, url)

        if not should_use_js:
            logger.debug("Static content is sufficient", url=url)
            return static_html

        logger.info(
            "Enhancing static content with JavaScript rendering",
            url=url,
            confidence=analysis.confidence_score,
            frameworks=analysis.frameworks_detected,
        )

        result, final_analysis = await self.adaptive_renderer.render_page(
            url, static_html, **render_options
        )

        return result, final_analysis

    async def render_page_with_fallback(
        self, url: str, static_html: Optional[str] = None, **render_options
    ) -> tuple[str, dict[str, Any]]:
        """Render page with automatic fallback strategy."""
        try:
            if static_html:
                # Try to enhance static content
                enhanced = await self.enhance_static_content(url, static_html, **render_options)

                if isinstance(enhanced, str):
                    # Static content was sufficient
                    return enhanced, {"strategy": "static", "enhanced": False}
                else:
                    # JavaScript enhancement was performed
                    result, analysis = enhanced
                    return result.html, {
                        "strategy": "javascript",
                        "enhanced": True,
                        "analysis": asdict(analysis),
                        "metadata": result.metadata,
                    }
            else:
                # No static HTML provided, use JavaScript rendering
                result, analysis = await self.adaptive_renderer.render_page(url, **render_options)

                return result.html, {
                    "strategy": "javascript",
                    "analysis": asdict(analysis),
                    "metadata": result.metadata,
                }

        except Exception as e:
            logger.error("Rendering failed, using fallback", url=url, error=str(e))

            # Fallback to static content if available
            if static_html:
                return static_html, {"strategy": "fallback_static", "error": str(e)}

            # No fallback available
            raise

    async def cleanup(self) -> None:
        """Clean up service resources."""
        await self.adaptive_renderer.cleanup()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


# Factory functions
def create_adaptive_renderer(
    browser_type: str = "chromium",
    headless: bool = True,
    timeout: float = 30.0,
    confidence_threshold: float = 0.5,
    **kwargs,
) -> AdaptiveRenderer:
    """Create an adaptive renderer with common configurations."""
    browser_config = BrowserConfig(
        browser_type=browser_type,
        headless=headless,
        timeout=timeout,
        **{k: v for k, v in kwargs.items() if k in BrowserConfig.model_fields},
    )

    strategy = RenderingStrategy(
        browser_config=browser_config,
        confidence_threshold=confidence_threshold,
        **{k: v for k, v in kwargs.items() if k in RenderingStrategy.model_fields},
    )

    return AdaptiveRenderer(strategy=strategy)


def create_rendering_service(
    browser_type: str = "chromium",
    headless: bool = True,
    confidence_threshold: float = 0.5,
    **kwargs,
) -> RenderingService:
    """Create a rendering service with common configurations."""
    adaptive_renderer = create_adaptive_renderer(
        browser_type=browser_type,
        headless=headless,
        confidence_threshold=confidence_threshold,
        **kwargs,
    )

    return RenderingService(
        strategy=adaptive_renderer.strategy, detector=adaptive_renderer.detector
    )
