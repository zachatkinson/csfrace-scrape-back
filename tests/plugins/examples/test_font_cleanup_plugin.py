"""Comprehensive tests for FontCleanupPlugin."""

from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from src.plugins.base import PluginConfig, PluginType
from src.plugins.examples.font_cleanup_plugin import FontCleanupPlugin


class TestFontCleanupPluginInitialization:
    """Test FontCleanupPlugin initialization and configuration."""

    def test_plugin_info_property(self):
        """Test plugin info contains expected metadata."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)

        info = plugin.plugin_info

        assert info["name"] == "Font Cleanup"
        assert info["version"] == "1.0.0"
        assert (
            info["description"] == "Removes font tags and font-related CSS styles for cleaner HTML"
        )
        assert info["author"] == "CSFrace Development Team"
        assert info["plugin_type"] == "html_processor"

    @pytest.mark.asyncio
    async def test_initialize_sets_font_properties(self):
        """Test initialize sets font properties correctly."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)

        with patch.object(plugin.logger, "info") as mock_log:
            await plugin.initialize()

        # Check font properties are set
        expected_properties = {
            "font-family",
            "font-size",
            "font-weight",
            "font-style",
            "font-variant",
            "font-stretch",
            "line-height",
            "font",
        }
        assert plugin.font_properties == expected_properties
        mock_log.assert_called_once_with("Font Cleanup Plugin initialized")

    @pytest.mark.asyncio
    async def test_initialize_logging(self):
        """Test initialize logs correctly."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)

        with patch.object(plugin.logger, "info") as mock_log:
            await plugin.initialize()

        mock_log.assert_called_once_with("Font Cleanup Plugin initialized")


class TestProcessHTML:
    """Test HTML processing functionality."""

    @pytest.fixture
    def plugin(self):
        """Create initialized plugin for testing."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)
        # Manually set font_properties to avoid async init in fixture
        plugin.font_properties = {
            "font-family",
            "font-size",
            "font-weight",
            "font-style",
            "font-variant",
            "font-stretch",
            "line-height",
            "font",
        }
        return plugin

    @pytest.mark.asyncio
    async def test_process_html_empty_content(self, plugin):
        """Test processing empty HTML content."""
        result = await plugin.process_html("", {}, {})
        assert result == ""

    @pytest.mark.asyncio
    async def test_process_html_whitespace_only_content(self, plugin):
        """Test processing whitespace-only content."""
        whitespace_content = "   \n\t   "
        result = await plugin.process_html(whitespace_content, {}, {})
        assert result == whitespace_content

    @pytest.mark.asyncio
    async def test_process_html_none_content(self, plugin):
        """Test processing None content."""
        result = await plugin.process_html(None, {}, {})
        assert result is None

    @pytest.mark.asyncio
    async def test_process_html_with_logging(self, plugin):
        """Test process_html logs debug information."""
        html_content = "<p>Test content</p>"

        with patch.object(plugin.logger, "debug") as mock_debug:
            result = await plugin.process_html(html_content, {}, {})

        mock_debug.assert_called_with(
            "Font cleanup completed", original_length=len(html_content), cleaned_length=len(result)
        )

    @pytest.mark.asyncio
    async def test_process_html_calls_cleanup_methods(self, plugin):
        """Test process_html calls all cleanup methods."""
        html_content = "<p>Test</p>"

        with (
            patch.object(plugin, "_remove_font_tags") as mock_font,
            patch.object(plugin, "_clean_font_styles") as mock_styles,
            patch.object(plugin, "_remove_empty_elements") as mock_empty,
        ):
            await plugin.process_html(html_content, {}, {})

            mock_font.assert_called_once()
            mock_styles.assert_called_once()
            mock_empty.assert_called_once()


class TestRemoveFontTags:
    """Test font tag removal functionality."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        return FontCleanupPlugin(config)

    def test_remove_font_tags_simple(self, plugin):
        """Test removing simple font tags."""
        html = "<font>Hello World</font>"
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_font_tags(soup)

        result = str(soup)
        assert "<font" not in result
        assert "Hello World" in result

    def test_remove_font_tags_with_attributes(self, plugin):
        """Test removing font tags with attributes."""
        html = '<font color="red" size="3">Styled text</font>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_font_tags(soup)

        result = str(soup)
        assert "<font" not in result
        assert "Styled text" in result

    def test_remove_font_tags_nested_content(self, plugin):
        """Test removing font tags with nested content."""
        html = "<font><strong>Bold</strong> and <em>italic</em></font>"
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_font_tags(soup)

        result = str(soup)
        assert "<font" not in result
        assert "<strong>Bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_remove_font_tags_multiple(self, plugin):
        """Test removing multiple font tags."""
        html = '<font color="red">Red</font> and <font size="4">Large</font>'
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._remove_font_tags(soup)

        result = str(soup)
        assert "<font" not in result
        assert "Red" in result
        assert "Large" in result
        mock_debug.assert_called_with("Removed font tags", count=2)

    def test_remove_font_tags_no_parent(self, plugin):
        """Test removing font tags when no parent exists."""
        html = "<font>Orphaned</font>"
        soup = BeautifulSoup(html, "html.parser")
        font_tag = soup.find("font")
        font_tag.extract()  # Remove from parent

        # This shouldn't crash
        plugin._remove_font_tags(soup)

    def test_remove_font_tags_no_fonts_found(self, plugin):
        """Test behavior when no font tags are found."""
        html = "<p>No font tags here</p>"
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._remove_font_tags(soup)

        # Should not log anything when no fonts removed
        mock_debug.assert_not_called()

    def test_remove_font_tags_logging_count(self, plugin):
        """Test logging of removed font tag count."""
        html = "<font>One</font><font>Two</font><font>Three</font>"
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._remove_font_tags(soup)

        mock_debug.assert_called_once_with("Removed font tags", count=3)


class TestCleanFontStyles:
    """Test font style cleaning functionality."""

    @pytest.fixture
    def plugin(self):
        """Create plugin with font properties for testing."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)
        plugin.font_properties = {
            "font-family",
            "font-size",
            "font-weight",
            "font-style",
            "font-variant",
            "font-stretch",
            "line-height",
            "font",
        }
        return plugin

    def test_clean_font_styles_simple(self, plugin):
        """Test cleaning simple font styles."""
        html = '<p style="font-size: 14px; color: red;">Text</p>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._clean_font_styles(soup)

        p_tag = soup.find("p")
        style = p_tag.get("style", "")
        assert "font-size" not in style
        assert "color: red" in style

    def test_clean_font_styles_multiple_properties(self, plugin):
        """Test cleaning multiple font-related properties."""
        html = '<div style="font-family: Arial; font-weight: bold; margin: 10px; font-size: 16px;">Content</div>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._clean_font_styles(soup)

        div_tag = soup.find("div")
        style = div_tag.get("style", "")
        assert "font-family" not in style
        assert "font-weight" not in style
        assert "font-size" not in style
        assert "margin: 10px" in style

    def test_clean_font_styles_empty_after_cleanup(self, plugin):
        """Test removing style attribute when empty after cleanup."""
        html = '<span style="font-size: 12px; font-weight: normal;">Text</span>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._clean_font_styles(soup)

        span_tag = soup.find("span")
        assert not span_tag.has_attr("style")

    def test_clean_font_styles_no_style_attributes(self, plugin):
        """Test behavior when no style attributes exist."""
        html = "<p>No styles here</p>"
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._clean_font_styles(soup)

        mock_debug.assert_not_called()

    def test_clean_font_styles_empty_style_attribute(self, plugin):
        """Test handling empty style attributes."""
        html = '<p style="">Empty style</p>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._clean_font_styles(soup)

        # Should not crash and style should remain empty or be removed
        p_tag = soup.find("p")
        style = p_tag.get("style", "")
        assert len(style) == 0

    def test_clean_font_styles_malformed_css(self, plugin):
        """Test handling malformed CSS properties."""
        html = '<p style="font-size; color: blue; font-weight">Text</p>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._clean_font_styles(soup)

        p_tag = soup.find("p")
        style = p_tag.get("style", "")
        assert "color: blue" in style

    def test_clean_font_styles_logging_count(self, plugin):
        """Test logging of cleaned properties count."""
        html = '<p style="font-size: 14px; font-weight: bold; color: red;">Text</p>'
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._clean_font_styles(soup)

        mock_debug.assert_called_with("Cleaned font styles", properties_removed=2)

    def test_clean_font_styles_case_insensitive(self, plugin):
        """Test that font property matching is case-insensitive."""
        html = '<p style="FONT-SIZE: 14px; Font-Weight: bold; color: red;">Text</p>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._clean_font_styles(soup)

        p_tag = soup.find("p")
        style = p_tag.get("style", "")
        assert "FONT-SIZE" not in style
        assert "Font-Weight" not in style
        assert "color: red" in style


class TestRemoveEmptyElements:
    """Test empty element removal functionality."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        return FontCleanupPlugin(config)

    def test_remove_empty_elements_simple(self, plugin):
        """Test removing simple empty elements."""
        html = "<p></p><span></span><div>Content</div>"
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_empty_elements(soup)

        result = str(soup)
        assert "<p>" not in result
        assert "<span>" not in result
        assert "<div>Content</div>" in result

    def test_remove_empty_elements_preserves_void_elements(self, plugin):
        """Test that void elements are preserved even when empty."""
        html = "<br><hr><img><input><meta>"
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_empty_elements(soup)

        result = str(soup)
        assert "<br" in result
        assert "<hr" in result
        assert "<img" in result
        assert "<input" in result
        assert "<meta" in result

    def test_remove_empty_elements_with_meaningful_children(self, plugin):
        """Test preserving elements with meaningful children."""
        html = '<div><img src="test.jpg"></div><span><input type="text"></span>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_empty_elements(soup)

        result = str(soup)
        assert "<div><img" in result
        assert "<span><input" in result

    def test_remove_empty_elements_with_important_attributes(self, plugin):
        """Test preserving elements with important attributes."""
        html = '<div id="important"></div><span class="required"></span><p data-value="test"></p>'
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_empty_elements(soup)

        result = str(soup)
        assert 'id="important"' in result
        assert 'class="required"' in result
        assert 'data-value="test"' in result

    def test_remove_empty_elements_whitespace_only(self, plugin):
        """Test removing elements with only whitespace."""
        html = "<p>   </p><span>\n\t</span><div>Content</div>"
        soup = BeautifulSoup(html, "html.parser")

        plugin._remove_empty_elements(soup)

        result = str(soup)
        assert result.count("<p") == 0
        assert result.count("<span") == 0
        assert "<div>Content</div>" in result

    def test_remove_empty_elements_logging_count(self, plugin):
        """Test logging of removed element count."""
        html = "<p></p><span></span><em></em>"
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._remove_empty_elements(soup)

        mock_debug.assert_called_with("Removed empty elements", count=3)

    def test_remove_empty_elements_no_removals(self, plugin):
        """Test behavior when no elements are removed."""
        html = "<p>Content</p><span>More content</span>"
        soup = BeautifulSoup(html, "html.parser")

        with patch.object(plugin.logger, "debug") as mock_debug:
            plugin._remove_empty_elements(soup)

        mock_debug.assert_not_called()


class TestIsEmptyElement:
    """Test empty element detection functionality."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        return FontCleanupPlugin(config)

    def test_is_empty_element_with_text(self, plugin):
        """Test element with text content is not empty."""
        html = "<p>Text content</p>"
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("p")

        assert not plugin._is_empty_element(element)

    def test_is_empty_element_whitespace_only(self, plugin):
        """Test element with only whitespace is empty."""
        html = "<p>   \n\t   </p>"
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("p")

        assert plugin._is_empty_element(element)

    def test_is_empty_element_with_meaningful_children(self, plugin):
        """Test element with meaningful children is not empty."""
        html = '<div><img src="test.jpg"></div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        assert not plugin._is_empty_element(element)

    def test_is_empty_element_with_important_id(self, plugin):
        """Test element with ID attribute is not empty."""
        html = '<div id="important"></div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        assert not plugin._is_empty_element(element)

    def test_is_empty_element_with_class(self, plugin):
        """Test element with class attribute is not empty."""
        html = '<span class="important"></span>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("span")

        assert not plugin._is_empty_element(element)

    def test_is_empty_element_with_data_attribute(self, plugin):
        """Test element with data attribute is not empty."""
        html = '<p data-value="test"></p>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("p")

        assert not plugin._is_empty_element(element)

    def test_is_empty_element_truly_empty(self, plugin):
        """Test truly empty element is detected as empty."""
        html = "<div></div>"
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        assert plugin._is_empty_element(element)

    def test_is_empty_element_with_non_meaningful_children(self, plugin):
        """Test element with only non-meaningful children is empty."""
        html = "<div><p></p><span></span></div>"
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        assert plugin._is_empty_element(element)


class TestBasePluginIntegration:
    """Test integration with BasePlugin functionality."""

    def test_inherits_from_html_processor_plugin(self):
        """Test that FontCleanupPlugin inherits from HTMLProcessorPlugin."""
        from src.plugins.base import HTMLProcessorPlugin

        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)

        assert isinstance(plugin, HTMLProcessorPlugin)

    @pytest.mark.asyncio
    async def test_process_method_integration(self):
        """Test the base process method works with our plugin."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)
        await plugin.initialize()

        data = {"html": '<font size="3">Test content</font>', "metadata": {"title": "Test"}}
        context = {}

        result = await plugin.process(data, context)

        assert "html" in result
        assert "<font" not in result["html"]
        assert "Test content" in result["html"]
        assert result["metadata"] == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_process_method_invalid_data(self):
        """Test process method with invalid data structure."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)

        with pytest.raises(ValueError, match="HTMLProcessorPlugin expects dict with 'html' key"):
            await plugin.process("invalid data", {})

    def test_plugin_configuration_methods(self):
        """Test plugin configuration methods work correctly."""
        config = PluginConfig(
            name="test_font_cleanup",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=50,
            settings={"custom_setting": "value"},
        )
        plugin = FontCleanupPlugin(config)

        assert plugin.is_enabled() is True
        assert plugin.get_priority() == 50
        assert plugin.get_setting("custom_setting") == "value"
        assert plugin.get_setting("nonexistent", "default") == "default"

        plugin.set_setting("new_setting", "new_value")
        assert plugin.get_setting("new_setting") == "new_value"


class TestEndToEndIntegration:
    """Test complete end-to-end font cleanup scenarios."""

    @pytest.fixture
    def plugin(self):
        """Create fully initialized plugin."""
        config = PluginConfig(
            name="test_font_cleanup", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = FontCleanupPlugin(config)
        plugin.font_properties = {
            "font-family",
            "font-size",
            "font-weight",
            "font-style",
            "font-variant",
            "font-stretch",
            "line-height",
            "font",
        }
        return plugin

    @pytest.mark.asyncio
    async def test_complete_font_cleanup_scenario(self, plugin):
        """Test complete font cleanup with multiple issues."""
        html_content = """
        <div>
            <font color="red" size="4">Old font tag content</font>
            <p style="font-family: Arial; font-size: 14px; color: blue; margin: 10px;">
                Styled paragraph
            </p>
            <span style="font-weight: bold; font-style: italic;">Font styles only</span>
            <div style="background: yellow;">Normal content</div>
            <font><strong>Nested content</strong></font>
        </div>
        """

        result = await plugin.process_html(html_content, {}, {})

        # Verify font tags are removed but content preserved
        assert "<font" not in result
        assert "Old font tag content" in result
        assert "<strong>Nested content</strong>" in result

        # Verify font styles are cleaned but other styles preserved
        assert "font-family" not in result
        assert "font-size" not in result
        assert "font-weight" not in result
        assert "font-style" not in result
        assert "color: blue" in result
        assert "margin: 10px" in result
        assert "background: yellow" in result

        # Verify content integrity
        assert "Styled paragraph" in result
        assert "Normal content" in result

    @pytest.mark.asyncio
    async def test_complex_nested_scenario(self, plugin):
        """Test complex nested font cleanup scenario."""
        html_content = """
        <article>
            <font size="5">
                <h2 style="font-family: Georgia; color: #333;">Article Title</h2>
                <p style="font-size: 16px; line-height: 1.5; margin: 20px;">
                    Article content with <font color="red">highlighted</font> text.
                </p>
            </font>
            <div style="font-weight: normal; padding: 10px;">
                <span></span>
                <img src="image.jpg" alt="Test image">
            </div>
        </article>
        """

        result = await plugin.process_html(html_content, {}, {})

        # Verify all font tags removed
        assert "<font" not in result

        # Verify font-related CSS removed
        assert "font-family" not in result
        assert "font-size" not in result
        assert "line-height" not in result
        assert "font-weight" not in result

        # Verify non-font CSS preserved
        assert "color: #333" in result
        assert "margin: 20px" in result
        assert "padding: 10px" in result

        # Verify content structure preserved
        assert "<h2" in result
        assert "Article Title" in result
        assert "Article content" in result
        assert "highlighted" in result
        assert 'src="image.jpg"' in result and 'alt="Test image"' in result

        # Verify empty span is removed but meaningful elements preserved
        assert "<span></span>" not in result
        assert "<img" in result

    @pytest.mark.asyncio
    async def test_edge_cases_scenario(self, plugin):
        """Test edge cases and boundary conditions."""
        html_content = """
        <div>
            <font></font>
            <p style="">Empty style</p>
            <span style="font-size: ; color: red;">Malformed CSS</span>
            <div style="FONT-WEIGHT: BOLD; Font-Family: Arial;">Mixed case</div>
            <empty id="keep-me"></empty>
            <meaningless class="also-keep"></meaningless>
        </div>
        """

        result = await plugin.process_html(html_content, {}, {})

        # Verify empty font tags removed
        assert "<font></font>" not in result

        # Verify malformed CSS handled gracefully
        assert "color: red" in result

        # Verify case-insensitive font property removal
        assert "FONT-WEIGHT" not in result
        assert "Font-Family" not in result

        # Verify elements with attributes preserved
        assert 'id="keep-me"' in result
        assert 'class="also-keep"' in result
