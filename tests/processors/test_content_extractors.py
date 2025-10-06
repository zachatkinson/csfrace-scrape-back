"""Comprehensive tests for src/processors/content_extractors.py.

Test coverage: 143 statements, 0% → 75%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest
from bs4 import BeautifulSoup, Tag

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

    def test_cannot_instantiate_abstract_base_class(self) -> None:
        """Test cannot instantiate ContentExtractorBase directly."""
        # Arrange & Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ContentExtractorBase(name="test")  # type: ignore[abstract]

    def test_subclass_must_implement_extract_method(self) -> None:
        """Test subclass must implement extract() method."""

        # Arrange
        class IncompleteExtractor(ContentExtractorBase):
            """Subclass missing extract() implementation."""

            pass

        # Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteExtractor(name="incomplete")  # type: ignore[abstract]


# =============================================================================
# TEST MainContentExtractor - Main Content Area Detection
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMainContentExtractor:
    """Test MainContentExtractor.extract() method."""

    async def test_extract_finds_main_tag(self) -> None:
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

    async def test_extract_finds_article_tag(self) -> None:
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

    async def test_extract_finds_entry_content_class(self) -> None:
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
        classes = result.get("class")
        assert classes is not None
        assert "entry-content" in classes
        assert "WordPress entry content" in result.get_text()

    async def test_extract_finds_content_with_role_main(self) -> None:
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

    async def test_extract_skips_short_content(self) -> None:
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
        classes = result.get("class")
        assert classes is not None
        assert "entry-content" in classes
        assert "real content" in result.get_text()

    async def test_extract_falls_back_to_body(self) -> None:
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

    async def test_extract_raises_error_when_no_body_found(self) -> None:
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

    async def test_converts_font_weight_bold_to_semantic(self) -> None:
        """Test converts font-weight: 700 to semantic bold."""
        # Arrange
        html = '<div><span style="font-weight: 700;">Bold text</span></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = FontProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        span = result.find("span")
        assert isinstance(span, Tag)
        assert span.get("style") == "font-weight: bold;"

    async def test_converts_font_weight_400_to_normal(self) -> None:
        """Test converts font-weight: 400 to normal."""
        # Arrange
        html = '<div><span style="font-weight: 400;">Normal text</span></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = FontProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        span = result.find("span")
        assert isinstance(span, Tag)
        style = span.get("style", "")
        assert isinstance(style, str)
        assert "font-weight: normal" in style


# =============================================================================
# TEST LayoutProcessor - Layout Style Conversion
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestLayoutProcessor:
    """Test LayoutProcessor.extract() method."""

    async def test_converts_align_attribute_to_text_align_style(self) -> None:
        """Test converts deprecated align attribute to text-align style."""
        # Arrange
        html = '<div><p align="center">Centered text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert isinstance(p, Tag)
        style = p.get("style", "")
        assert isinstance(style, str)
        assert "text-align: center" in style
        assert p.get("align") is None

    async def test_preserves_existing_styles_when_converting_align(self) -> None:
        """Test preserves existing styles when adding text-align."""
        # Arrange
        html = '<div><p style="color: red;" align="right">Red right text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert isinstance(p, Tag)
        style = p.get("style", "")
        assert isinstance(style, str)
        assert "color: red" in style
        assert "text-align: right" in style

    async def test_handles_text_align_left(self) -> None:
        """Test converts align='left' to text-align: left."""
        # Arrange
        html = '<div><p align="left">Left text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert isinstance(p, Tag)
        style = p.get("style", "")
        assert isinstance(style, str)
        assert "text-align: left" in style

    async def test_handles_text_align_justify(self) -> None:
        """Test converts align='justify' to text-align: justify."""
        # Arrange
        html = '<div><p align="justify">Justified text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = LayoutProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        p = result.find("p")
        assert isinstance(p, Tag)
        style = p.get("style", "")
        assert isinstance(style, str)
        assert "text-align: justify" in style


# =============================================================================
# TEST MediaProcessor - Media Content Processing
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMediaProcessor:
    """Test MediaProcessor.extract() method."""

    async def test_adds_responsive_class_to_images(self) -> None:
        """Test adds responsive class to images for responsiveness."""
        # Arrange
        html = '<div><img src="test.jpg" alt="Test"></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        img = result.find("img")
        assert isinstance(img, Tag)
        classes = img.get("class")
        assert classes is not None
        assert "responsive" in classes

    async def test_adds_default_alt_text_when_missing(self) -> None:
        """Test adds default alt text when image has no alt attribute."""
        # Arrange
        html = '<div><img src="test.jpg"></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        img = result.find("img")
        assert isinstance(img, Tag)
        assert img.get("alt") == "Image"

    async def test_preserves_existing_alt_text(self) -> None:
        """Test preserves existing alt text on images."""
        # Arrange
        html = '<div><img src="test.jpg" alt="Original alt"></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        img = result.find("img")
        assert isinstance(img, Tag)
        assert img.get("alt") == "Original alt"

    async def test_adds_gallery_class_to_wordpress_galleries(self) -> None:
        """Test adds gallery class to WordPress gallery elements."""
        # Arrange
        html = '<div><div class="wp-block-gallery"><img src="1.jpg"><img src="2.jpg"></div></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = MediaProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        gallery = result.find("div", class_="wp-block-gallery")
        assert isinstance(gallery, Tag)
        classes = gallery.get("class")
        assert classes is not None
        assert "shopify-gallery" in classes


# =============================================================================
# TEST ComponentProcessor - Interactive Component Processing
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestComponentProcessor:
    """Test ComponentProcessor.extract() method."""

    async def test_adds_button_class_to_button_elements(self) -> None:
        """Test adds btn class to button elements."""
        # Arrange
        html = "<div><button>Click me</button></div>"
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = ComponentProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        button = result.find("button")
        assert isinstance(button, Tag)
        classes = button.get("class")
        assert classes is not None
        assert "btn" in classes

    async def test_converts_button_like_links_to_buttons(self) -> None:
        """Test adds shopify-button class to links with button classes."""
        # Arrange
        html = '<div><a href="#" class="wp-block-button__link">Click</a></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = ComponentProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        link = result.find("a")
        assert isinstance(link, Tag)
        classes = link.get("class")
        assert classes is not None
        assert "shopify-button" in classes
        assert link.get_text() == "Click"


# =============================================================================
# TEST CleanupProcessor - WordPress Artifact Removal
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCleanupProcessor:
    """Test CleanupProcessor.extract() method."""

    async def test_removes_script_tags(self) -> None:
        """Test removes all script tags."""
        # Arrange
        html = '<div><script>alert("test")</script><p>Content</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        assert result.find("script") is None
        assert result.find("p") is not None

    async def test_removes_wordpress_classes(self) -> None:
        """Test removes WordPress-specific classes (wp-*, post-\\d+)."""
        # Arrange
        html = '<div><div class="wp-block-group post-123 custom-class">Content</div></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        inner_div = result.find("div")
        assert isinstance(inner_div, Tag)
        classes = inner_div.get("class")
        assert classes is not None
        assert "wp-block-group" not in classes
        assert "post-123" not in classes
        assert "custom-class" in classes

    async def test_removes_empty_paragraphs(self) -> None:
        """Test removes empty paragraph tags."""
        # Arrange
        html = "<div><p></p><p>   </p><p>Content</p></div>"
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        paragraphs = result.find_all("p")
        assert len(paragraphs) == 1
        assert paragraphs[0].get_text() == "Content"

    async def test_preserves_non_wordpress_classes(self) -> None:
        """Test preserves non-WordPress classes."""
        # Arrange
        html = '<div><div class="custom-class wp-block">Content</div></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.div
        assert isinstance(content, Tag)
        processor = CleanupProcessor()

        # Act
        result = await processor.extract(content)

        # Assert
        inner_div = result.find("div")
        assert isinstance(inner_div, Tag)
        classes = inner_div.get("class")
        assert classes is not None
        assert "custom-class" in classes
        assert "wp-block" not in classes
