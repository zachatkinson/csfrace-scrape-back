"""Unit tests for HTML processor."""

import pytest
from bs4 import BeautifulSoup

from src.processors.html_processor import HTMLProcessor


class TestHTMLProcessor:
    """Test cases for HTML processing functionality."""

    @pytest.mark.unit
    async def test_font_formatting_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of <b> and <i> tags to semantic equivalents."""
        html = "<div><b>Bold text</b> and <i>italic text</i></div>"
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div")

        result = await html_processor._convert_font_formatting(content)

        assert result.find("strong") is not None
        assert result.find("em") is not None
        assert result.find("b") is None
        assert result.find("i") is None
        assert result.find("strong").get_text() == "Bold text"
        assert result.find("em").get_text() == "italic text"

    @pytest.mark.unit
    async def test_text_alignment_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of WordPress text alignment classes."""
        html = '<div><p class="has-text-align-center">Centered text</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div")

        result = await html_processor._convert_text_alignment(content)

        p_tag = result.find("p")
        assert "center" in p_tag.get("class", [])
        assert "has-text-align-center" not in p_tag.get("class", [])

    @pytest.mark.unit
    async def test_kadence_layout_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of Kadence row layouts to media-grid."""
        html = """
        <div class="wp-block-kadence-rowlayout">
            <div class="kt-has-2-columns">
                <div class="wp-block-kadence-column">
                    <div class="kt-inside-inner-col">
                        <h3>Column 1</h3>
                        <p>Content 1</p>
                    </div>
                </div>
                <div class="wp-block-kadence-column">
                    <div class="kt-inside-inner-col">
                        <h3>Column 2</h3>
                        <p>Content 2</p>
                    </div>
                </div>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        await html_processor._convert_kadence_layouts(soup)

        # Check that Kadence layout is gone
        assert soup.find("div", class_="wp-block-kadence-rowlayout") is None

        # Check that media-grid-2 was created
        media_grid = soup.find("div", class_="media-grid-2")
        assert media_grid is not None

        # Check that text boxes were created
        text_boxes = media_grid.find_all("div", class_="media-grid-text-box")
        assert len(text_boxes) == 2

        # Verify content was preserved
        assert text_boxes[0].find("h3").get_text() == "Column 1"
        assert text_boxes[1].find("h3").get_text() == "Column 2"

    @pytest.mark.unit
    async def test_simple_image_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of wp-block-image to simple img tags."""
        html = """
        <div class="wp-block-image">
            <img src="/test.jpg" alt="Test image" width="300" height="200">
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        await html_processor._convert_simple_images(soup)

        # Check that wp-block-image is gone
        assert soup.find("div", class_="wp-block-image") is None

        # Check that img tag remains with attributes
        img = soup.find("img")
        assert img is not None
        assert img.get("src") == "/test.jpg"
        assert img.get("alt") == "Test image"
        assert img.get("width") == "300"
        assert img.get("height") == "200"

    @pytest.mark.unit
    async def test_button_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of Kadence buttons to Shopify format."""
        html = """
        <div class="wp-block-kadence-advancedbtn">
            <a class="button" href="https://external.com">Click Me</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        await html_processor._convert_buttons(soup)

        # Check that Kadence button block is gone
        assert soup.find("div", class_="wp-block-kadence-advancedbtn") is None

        # Check new button format
        button = soup.find("a")
        assert button is not None
        assert "button" in button.get("class", [])
        assert "button--full-width" in button.get("class", [])
        assert "button--primary" in button.get("class", [])
        assert button.get("target") == "_blank"
        assert button.get("rel") == "noreferrer noopener"
        assert button.get_text() == "Click Me"

    @pytest.mark.unit
    async def test_blockquote_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of pullquotes to testimonial format."""
        html = """
        <figure class="wp-block-pullquote">
            <blockquote>
                <p>This is a test quote</p>
                <cite>Test Author</cite>
            </blockquote>
        </figure>
        """
        soup = BeautifulSoup(html, "html.parser")

        await html_processor._convert_blockquotes(soup)

        # Check that pullquote is gone
        assert soup.find("figure", class_="wp-block-pullquote") is None

        # Check testimonial structure
        testimonial = soup.find("div", class_="testimonial-quote")
        assert testimonial is not None
        assert "group" in testimonial.get("class", [])

        quote_container = testimonial.find("div", class_="quote-container")
        assert quote_container is not None

        blockquote = quote_container.find("blockquote")
        assert blockquote is not None
        assert blockquote.find("p").get_text() == "This is a test quote"

        cite = quote_container.find("cite")
        assert cite is not None
        assert cite.find("span").get_text() == "Test Author"

    @pytest.mark.unit
    async def test_youtube_embed_conversion(self, html_processor: HTMLProcessor):
        """Test conversion of YouTube embeds to responsive format."""
        html = """
        <figure class="wp-block-embed-youtube">
            <div class="wp-block-embed__wrapper">
                <iframe src="https://www.youtube.com/embed/test123" title="Test Video"></iframe>
            </div>
            <figcaption>Test caption</figcaption>
        </figure>
        """
        soup = BeautifulSoup(html, "html.parser")

        await html_processor._convert_youtube_embeds(soup)

        # Check that YouTube figure is gone
        assert soup.find("figure", class_="wp-block-embed-youtube") is None

        # Check responsive structure
        wrapper = soup.find("div")
        assert wrapper is not None

        # Should have container div and caption
        container = wrapper.find("div", style=lambda x: x and "display: flex" in x)
        assert container is not None

        iframe = container.find("iframe")
        assert iframe is not None
        assert "aspect-ratio: 16/9" in iframe.get("style", "")
        assert iframe.get("src") == "https://www.youtube.com/embed/test123"

        # Check caption
        caption_p = wrapper.find("p")
        assert caption_p is not None
        assert caption_p.find("strong").get_text() == "Test caption"

    @pytest.mark.unit
    async def test_external_links_fix(self, html_processor: HTMLProcessor):
        """Test addition of target and rel attributes to external links."""
        html = """
        <div>
            <a href="https://external.com">External</a>
            <a href="https://csfrace.com/internal">Internal</a>
            <a href="/relative">Relative</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div")

        result = await html_processor._fix_external_links(content)

        links = result.find_all("a")

        # External link should have target and rel
        external_link = links[0]
        assert external_link.get("target") == "_blank"
        assert external_link.get("rel") == "noreferrer noopener"

        # Internal and relative links should not
        internal_link = links[1]
        assert internal_link.get("target") is None

        relative_link = links[2]
        assert relative_link.get("target") is None

    @pytest.mark.unit
    async def test_script_removal(self, html_processor: HTMLProcessor):
        """Test removal of script tags."""
        html = """
        <div>
            <p>Safe content</p>
            <script>alert('malicious');</script>
            <script src="external.js"></script>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div")

        await html_processor._remove_scripts(content)

        # Scripts should be gone
        assert len(content.find_all("script")) == 0
        # Safe content should remain
        assert content.find("p").get_text() == "Safe content"

    @pytest.mark.unit
    async def test_wordpress_artifacts_cleanup(self, html_processor: HTMLProcessor):
        """Test cleanup of WordPress classes and attributes."""
        html = """
        <div class="wp-block-something preserve-this center"
             style="color: red;"
             data-align="center"
             id="wp-123">
            <p>Content</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div")

        result = await html_processor._cleanup_wordpress_artifacts(content)

        # Should only keep preserved classes
        classes = result.get("class", [])
        assert "center" in classes
        assert "wp-block-something" not in classes
        assert "preserve-this" not in classes

        # Style and WordPress attributes should be removed
        assert result.get("style") is None
        assert result.get("data-align") is None
        assert result.get("id") is None

    @pytest.mark.unit
    async def test_full_processing_pipeline(
        self, html_processor: HTMLProcessor, sample_soup: BeautifulSoup
    ):
        """Test the complete HTML processing pipeline."""
        result_html = await html_processor.process(sample_soup)

        # Parse result to check transformations
        result_soup = BeautifulSoup(result_html, "html.parser")

        # Font formatting should be converted
        assert result_soup.find("strong") is not None
        assert result_soup.find("em") is not None
        assert result_soup.find("b") is None
        assert result_soup.find("i") is None

        # Text alignment should be converted
        center_elem = result_soup.find(class_="center")
        assert center_elem is not None

        # Kadence layouts should be converted
        media_grid = result_soup.find(class_="media-grid-2")
        assert media_grid is not None

        # Images should be simplified
        img = result_soup.find("img")
        assert img is not None
        assert img.parent.name != "div" or "wp-block-image" not in img.parent.get("class", [])

        # External links should have target
        external_link = result_soup.find("a", href="https://external-site.com")
        assert external_link.get("target") == "_blank"

        # Scripts should be removed
        assert len(result_soup.find_all("script")) == 0

        # YouTube embed should be responsive
        youtube_iframe = result_soup.find("iframe", src=lambda x: x and "youtube.com" in x)
        assert youtube_iframe is not None
        assert "aspect-ratio: 16/9" in youtube_iframe.get("style", "")

    @pytest.mark.unit
    def test_is_external_link(self, html_processor: HTMLProcessor):
        """Test external link detection."""
        assert html_processor._is_external_link("https://external.com") is True
        assert html_processor._is_external_link("https://csfrace.com/page") is False
        assert html_processor._is_external_link("/relative/path") is False
        assert html_processor._is_external_link("mailto:test@example.com") is False
        assert html_processor._is_external_link("") is False
