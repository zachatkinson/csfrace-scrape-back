"""Browser-based rendering and JavaScript execution module.

This module provides comprehensive browser automation and JavaScript rendering
capabilities for handling dynamic web content, including:

- Playwright-based browser automation
- Dynamic content detection
- Adaptive rendering strategies
- Pool management for efficient resource usage
- High-level rendering service integration

Key Components:
    - BrowserConfig: Configuration for browser instances
    - JavaScriptRenderer: Low-level browser automation
    - DynamicContentDetector: Content analysis and strategy detection
    - AdaptiveRenderer: Intelligent rendering with fallback strategies
    - RenderingService: High-level service for scraper integration

Example Usage:
    ```python
    from src.rendering import create_rendering_service

    async with create_rendering_service() as service:
        html, metadata = await service.render_page_with_fallback(
            "https://example.com",
            static_html=static_content
        )
    ```
"""

from src.rendering.browser import (
    BrowserConfig,
    BrowserPool,
    JavaScriptRenderer,
    RenderResult,
    create_renderer,
)
from src.rendering.detector import (
    ContentAnalysis,
    DynamicContentDetector,
    DynamicContentIndicators,
    get_recommended_wait_conditions,
    should_use_javascript_rendering,
)
from src.rendering.renderer import (
    AdaptiveRenderer,
    RenderingService,
    RenderingStrategy,
    create_adaptive_renderer,
    create_rendering_service,
)

__all__ = [
    # Browser automation
    "BrowserConfig",
    "BrowserPool",
    "JavaScriptRenderer",
    "RenderResult",
    "create_renderer",
    # Content detection
    "DynamicContentIndicators",
    "ContentAnalysis",
    "DynamicContentDetector",
    "should_use_javascript_rendering",
    "get_recommended_wait_conditions",
    # Adaptive rendering
    "RenderingStrategy",
    "AdaptiveRenderer",
    "RenderingService",
    "create_adaptive_renderer",
    "create_rendering_service",
]
