"""Comprehensive tests for src/processors/content_extractors.py.

Test coverage: 143 statements, 0% → 75%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest
from bs4 import BeautifulSoup

from src.processors.content_extractors import (
    CleanupProcessor,
    ComponentProcessor,
    ContentExtractorBase,
    FontProcessor,
    LayoutProcessor,
    MainContentExtractor,
    MediaProcessor,
)

# =============================================================================
# TEST ContentExtractorBase - Abstract Base Class
# =============================================================================


@pytest.mark.unit
class TestContentExtractorBase:
    """Test ContentExtractorBase abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test cannot instantiate ContentExtractorBase directly."""
        # Arrange & Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ContentExtractorBase(name="test")

    def test_subclass_must_implement_extract_method(self):
        """Test subclass must implement extract() method."""

        # Arrange
        class IncompleteExtractor(ContentExtractorBase):
            """Subclass missing extract() implementation."""

            pass

        # Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteExtractor(name="incomplete")


# =============================================================================
# TEST MainContentExtractor - Main Content Area Detection
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMainContentExtractor:
    """Test MainContentExtractor.extract() method."""

    async def test_extract_finds_main_tag(self):
        """Test finds content in <main> tag."""
        # Arrange
        html = """
        <html>
            <body>
                <main>
                    <p>This is the main content area with more than 100 characters to ensure it meets the minimum content length requirement for detection.</p>
                </main>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act
        result = await extractor.extract(soup)

        # Assert
        assert result.name == "main"
        assert "main content area" in result.get_text()

    async def test_extract_finds_article_tag(self):
        """Test finds content in <article> tag."""
        # Arrange
        html = """
        <html>
            <body>
                <article>
                    <p>This is article content with more than 100 characters to ensure it meets the minimum content length requirement for detection as main content.</p>
                </article>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act
        result = await extractor.extract(soup)

        # Assert
        assert result.name == "article"
        assert "article content" in result.get_text()

    async def test_extract_finds_entry_content_class(self):
        """Test finds content with .entry-content class (WordPress)."""
        # Arrange
        html = """
        <html>
            <body>
                <div class="entry-content">
                    <p>WordPress entry content with more than 100 characters to ensure it meets the minimum content length requirement for detection as main content.</p>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act
        result = await extractor.extract(soup)

        # Assert
        assert "entry-content" in result.get("class", [])
        assert "WordPress entry content" in result.get_text()

    async def test_extract_finds_content_with_role_main(self):
        """Test finds content with role='main' attribute."""
        # Arrange
        html = """
        <html>
            <body>
                <div role="main">
                    <p>Content with role=main attribute and more than 100 characters to ensure it meets the minimum content length requirement for detection.</p>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act
        result = await extractor.extract(soup)

        # Assert
        assert result.get("role") == "main"
        assert "role=main" in result.get_text()

    async def test_extract_skips_short_content(self):
        """Test skips content shorter than 100 characters."""
        # Arrange
        html = """
        <html>
            <body>
                <article><p>Short</p></article>
                <div class="entry-content">
                    <p>This is the real content with more than 100 characters to ensure it meets the minimum content length requirement for detection as main content area.</p>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act
        result = await extractor.extract(soup)

        # Assert - Should find .entry-content, not article
        assert "entry-content" in result.get("class", [])
        assert "real content" in result.get_text()

    async def test_extract_falls_back_to_body(self):
        """Test falls back to <body> when no main content found."""
        # Arrange
        html = """
        <html>
            <body>
                <div><p>Some content</p></div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act
        result = await extractor.extract(soup)

        # Assert
        assert result.name == "body"

    async def test_extract_raises_error_when_no_body_found(self):
        """Test raises ProcessingError when no body tag exists."""
        # Arrange
        html = "<html><head></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MainContentExtractor()

        # Act & Assert
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            await extractor.extract(soup)


# =============================================================================
# TEST FontProcessor - Font Style Conversion
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFontProcessor:
    """Test FontProcessor.extract() method."""

    async def test_converts_font_weight_bold_to_semantic(self):
        """Test converts font-weight: 700 to semantic bold."""
        # Arrange
        html = '<div><span style="font-weight: 700;">Bold text</span></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = FontProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        span = result.find("span")
        assert span.get("style") == "font-weight: bold;"

    async def test_converts_font_weight_400_to_normal(self):
        """Test converts font-weight: 400 to normal."""
        # Arrange
        html = '<div><span style="font-weight: 400;">Normal text</span></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = FontProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        span = result.find("span")
        assert "font-weight: normal" in span.get("style", "")


# =============================================================================
# TEST LayoutProcessor - Layout Style Conversion
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestLayoutProcessor:
    """Test LayoutProcessor.extract() method."""

    async def test_converts_align_attribute_to_text_align_style(self):
        """Test converts deprecated align attribute to text-align style."""
        # Arrange
        html = '<div><p align="center">Centered text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert "text-align: center" in p.get("style", "")
        assert p.get("align") is None

    async def test_preserves_existing_styles_when_converting_align(self):
        """Test preserves existing styles when adding text-align."""
        # Arrange
        html = '<div><p style="color: red;" align="right">Red right text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        style = p.get("style", "")
        assert "color: red" in style
        assert "text-align: right" in style

    async def test_handles_text_align_left(self):
        """Test converts align='left' to text-align: left."""
        # Arrange
        html = '<div><p align="left">Left text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert "text-align: left" in p.get("style", "")

    async def test_handles_text_align_justify(self):
        """Test converts align='justify' to text-align: justify."""
        # Arrange
        html = '<div><p align="justify">Justified text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert "text-align: justify" in p.get("style", "")


# =============================================================================
# TEST MediaProcessor - Media Content Processing
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMediaProcessor:
    """Test MediaProcessor.extract() method."""

    async def test_adds_responsive_class_to_images(self):
        """Test adds responsive class to images for responsiveness."""
        # Arrange
        html = '<div><img src="test.jpg" alt="Test"></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        img = result.find("img")
        assert "responsive" in img.get("class", [])

    async def test_adds_default_alt_text_when_missing(self):
        """Test adds default alt text when image has no alt attribute."""
        # Arrange
        html = '<div><img src="test.jpg"></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        img = result.find("img")
        assert img.get("alt") == "Image"

    async def test_preserves_existing_alt_text(self):
        """Test preserves existing alt text on images."""
        # Arrange
        html = '<div><img src="test.jpg" alt="Original alt"></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        img = result.find("img")
        assert img.get("alt") == "Original alt"

    async def test_adds_gallery_class_to_wordpress_galleries(self):
        """Test adds gallery class to WordPress gallery elements."""
        # Arrange
        html = '<div><div class="wp-block-gallery"><img src="1.jpg"><img src="2.jpg"></div></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        gallery = result.find("div", class_="wp-block-gallery")
        assert "shopify-gallery" in gallery.get("class", [])


# =============================================================================
# TEST ComponentProcessor - Interactive Component Processing
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestComponentProcessor:
    """Test ComponentProcessor.extract() method."""

    async def test_adds_button_class_to_button_elements(self):
        """Test adds btn class to button elements."""
        # Arrange
        html = "<div><button>Click me</button></div>"
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = ComponentProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        button = result.find("button")
        assert "btn" in button.get("class", [])

    async def test_converts_button_like_links_to_buttons(self):
        """Test adds shopify-button class to links with button classes."""
        # Arrange
        html = '<div><a href="#" class="wp-block-button__link">Click</a></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = ComponentProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        link = result.find("a")
        assert link is not None
        assert "shopify-button" in link.get("class", [])
        assert link.get_text() == "Click"


# =============================================================================
# TEST CleanupProcessor - WordPress Artifact Removal
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCleanupProcessor:
    """Test CleanupProcessor.extract() method."""

    async def test_removes_script_tags(self):
        """Test removes all script tags."""
        # Arrange
        html = '<div><script>alert("test")</script><p>Content</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        assert result.find("script") is None
        assert result.find("p") is not None

    async def test_removes_wordpress_classes(self):
        """Test removes WordPress-specific classes (wp-*, post-\\d+)."""
        # Arrange
        html = '<div><div class="wp-block-group post-123 custom-class">Content</div></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        inner_div = result.find("div")
        classes = inner_div.get("class", [])
        assert "wp-block-group" not in classes
        assert "post-123" not in classes
        assert "custom-class" in classes

    async def test_removes_empty_paragraphs(self):
        """Test removes empty paragraph tags."""
        # Arrange
        html = "<div><p></p><p>   </p><p>Content</p></div>"
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        paragraphs = result.find_all("p")
        assert len(paragraphs) == 1
        assert paragraphs[0].get_text() == "Content"

    async def test_preserves_non_wordpress_classes(self):
        """Test preserves non-WordPress classes."""
        # Arrange
        html = '<div><div class="custom-class wp-block">Content</div></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        inner_div = result.find("div")
        classes = inner_div.get("class", [])
        assert "custom-class" in classes
        assert "wp-block" not in classes
