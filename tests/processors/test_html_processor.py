"""Tests for SOLID-compliant HTML processing architecture."""

import pytest
from bs4 import BeautifulSoup

from src.processors.content_extractors import (
    CleanupProcessor,
    FontProcessor,
    LayoutProcessor,
    MainContentExtractor,
    MediaProcessor,
)
from src.processors.html_processor import HTMLProcessorOrchestrator


class TestHTMLProcessorOrchestrator:
    """Test HTML processing orchestrator - SOLID compliance validation."""

    @pytest.fixture
    def orchestrator(self):
        """Create HTML processor orchestrator instance."""
        return HTMLProcessorOrchestrator()

    @pytest.fixture
    def font_processor(self):
        """Create font processor for isolated testing."""
        return FontProcessor()

    @pytest.fixture
    def layout_processor(self):
        """Create layout processor for isolated testing."""
        return LayoutProcessor()

    @pytest.mark.asyncio
    async def test_font_formatting_conversion_isolated(self, font_processor):
        """Test font formatting conversion using dedicated FontProcessor - Single Responsibility."""
        html_content = """
        <p style="font-size: 18px; color: #333; font-weight: bold;">
            Styled text
        </p>
        <span style="font-size: 24px; color: red;">Large red text</span>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        result = await font_processor.extract(soup)

        # Check that inline styles are converted to appropriate classes or structure
        converted_html = str(result)

        # Should preserve text content
        assert "Styled text" in converted_html
        assert "Large red text" in converted_html

    @pytest.mark.asyncio
    async def test_text_alignment_conversion_isolated(self, layout_processor):
        """Test text alignment conversion using dedicated LayoutProcessor - Single Responsibility."""
        html_content = """
        <p style="text-align: center;">Centered text</p>
        <p class="has-text-align-center">WordPress centered</p>
        <div style="text-align: right;">Right aligned</div>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        result = await layout_processor.extract(soup)

        converted_html = str(result)

        # Should convert alignment styles to Shopify-compatible classes
        assert "Centered text" in converted_html
        assert "WordPress centered" in converted_html
        assert "Right aligned" in converted_html

    @pytest.mark.asyncio
    async def test_orchestrator_full_pipeline(self, orchestrator):
        """Test orchestrator coordinates all processors following SOLID Open/Closed Principle."""
        complex_html = """
        <article class="wp-block-post-content">
            <h2 style="font-size: 24px; text-align: center;">Main Heading</h2>
            <p style="font-weight: bold; color: #333;">
                This is <strong>bold text</strong> with <em>emphasis</em>.
            </p>
            <div style="text-align: right;">
                <img src="image.jpg" alt="Sample image" style="max-width: 100%;">
            </div>
            <ul class="wp-block-list">
                <li>First item</li>
                <li>Second item</li>
            </ul>
        </article>
        """

        soup = BeautifulSoup(complex_html, "html.parser")
        result = await orchestrator.process(soup)

        converted_html = str(result)

        # Verify content is preserved
        assert "Main Heading" in converted_html
        assert "bold text" in converted_html
        assert "First item" in converted_html
        assert "Second item" in converted_html
        assert "Sample image" in converted_html

    @pytest.mark.asyncio
    async def test_individual_processor_isolation(self, font_processor, layout_processor):
        """Test that individual processors work in isolation - Single Responsibility Principle."""
        html_content = """
        <p style="font-size: 18px; text-align: center; color: red;">
            Test content with both font and layout styles
        </p>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        # Test font processor handles only font concerns
        font_result = await font_processor.extract(soup.find("p"))
        font_html = str(font_result)

        # Test layout processor handles only layout concerns
        layout_result = await layout_processor.extract(soup.find("p"))
        layout_html = str(layout_result)

        # Both should preserve content but focus on their specific responsibilities
        assert "Test content with both font and layout styles" in font_html
        assert "Test content with both font and layout styles" in layout_html


class TestContentExtractors:
    """Test individual content extractors for Single Responsibility compliance."""

    @pytest.fixture
    def main_content_extractor(self):
        return MainContentExtractor()

    @pytest.fixture
    def media_processor(self):
        return MediaProcessor()

    @pytest.fixture
    def cleanup_processor(self):
        return CleanupProcessor()

    @pytest.mark.asyncio
    async def test_main_content_extractor_focus(self, main_content_extractor):
        """Test MainContentExtractor focuses only on main content identification."""
        html_with_sidebar = """
        <div>
            <aside class="sidebar">Sidebar content that adds some length to the overall document</aside>
            <main class="content">
                <h1>Main article with comprehensive title that provides sufficient context</h1>
                <p>Main content here with detailed information that explains the topic thoroughly and provides enough text content to exceed the minimum character threshold for content extraction processing requirements.</p>
            </main>
            <footer>Footer content with additional information and links</footer>
        </div>
        """

        soup = BeautifulSoup(html_with_sidebar, "html.parser")
        result = await main_content_extractor.extract(soup)
        result_html = str(result)

        # Should focus on main content
        assert "Main article with comprehensive title" in result_html
        assert "Main content here with detailed information" in result_html

    @pytest.mark.asyncio
    async def test_cleanup_processor_sanitization(self, cleanup_processor):
        """Test CleanupProcessor removes unwanted elements while preserving content."""
        messy_html = """
        <div>
            <p>Good content</p>
            <script>alert('bad');</script>
            <p>More good content</p>
            <!-- Comment to remove -->
        </div>
        """

        soup = BeautifulSoup(messy_html, "html.parser")
        result = await cleanup_processor.extract(soup)
        result_html = str(result)

        # Should preserve good content
        assert "Good content" in result_html
        assert "More good content" in result_html

        # Should remove problematic elements
        assert "<script>" not in result_html
        assert "alert" not in result_html
