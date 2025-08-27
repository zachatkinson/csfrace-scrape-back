"""Comprehensive tests for SEOMetadataPlugin."""

import json
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from src.plugins.base import PluginConfig, PluginType
from src.plugins.examples.seo_metadata_plugin import SEOMetadataPlugin


class TestSEOMetadataPluginInitialization:
    """Test SEOMetadataPlugin initialization and configuration."""

    def test_plugin_info_property(self):
        """Test plugin info contains expected metadata."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = SEOMetadataPlugin(config)

        info = plugin.plugin_info

        assert info["name"] == "SEO Metadata Extractor"
        assert info["version"] == "1.0.0"
        assert info["description"] == "Extracts comprehensive SEO metadata from HTML content"
        assert info["author"] == "CSFrace Development Team"
        assert info["plugin_type"] == "metadata_extractor"

    @pytest.mark.asyncio
    async def test_initialize_logging(self):
        """Test initialize logs correctly."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = SEOMetadataPlugin(config)

        with patch.object(plugin.logger, "info") as mock_log:
            await plugin.initialize()

        mock_log.assert_called_once_with("SEO Metadata Plugin initialized")


class TestExtractMetadata:
    """Test main metadata extraction functionality."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    @pytest.mark.asyncio
    async def test_extract_metadata_calls_all_extractors(self, plugin):
        """Test extract_metadata calls all extraction methods."""
        html_content = "<html><head><title>Test</title></head></html>"
        url = "https://example.com/test"
        context = {}

        with (
            patch.object(
                plugin, "_extract_basic_seo", return_value={"title": "Test"}
            ) as mock_basic,
            patch.object(plugin, "_extract_open_graph", return_value={}) as mock_og,
            patch.object(plugin, "_extract_twitter_card", return_value={}) as mock_twitter,
            patch.object(plugin, "_extract_schema_org", return_value={}) as mock_schema,
            patch.object(plugin, "_extract_seo_signals", return_value={}) as mock_signals,
        ):
            result = await plugin.extract_metadata(html_content, url, context)

            mock_basic.assert_called_once()
            mock_og.assert_called_once()
            mock_twitter.assert_called_once()
            mock_schema.assert_called_once()
            mock_signals.assert_called_once()

            assert result == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_extract_metadata_logging(self, plugin):
        """Test extract_metadata logs debug information."""
        html_content = "<html><head><title>Test</title></head></html>"
        url = "https://example.com/test"
        context = {}

        with patch.object(plugin.logger, "debug") as mock_debug:
            await plugin.extract_metadata(html_content, url, context)

        mock_debug.assert_called_once()
        call_args = mock_debug.call_args[1]
        assert "metadata_keys" in call_args

    @pytest.mark.asyncio
    async def test_extract_metadata_empty_html(self, plugin):
        """Test extract_metadata with empty HTML."""
        result = await plugin.extract_metadata("", "https://example.com", {})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_extract_metadata_integration(self, plugin):
        """Test extract_metadata integration with real HTML."""
        html_content = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
            <meta property="og:title" content="OG Title">
        </head>
        <body>
            <h1>Main Heading</h1>
            <p>Content</p>
        </body>
        </html>
        """

        result = await plugin.extract_metadata(html_content, "https://example.com", {})

        assert "title" in result
        assert "description" in result
        assert "open_graph" in result
        assert "headings" in result


class TestExtractBasicSEO:
    """Test basic SEO metadata extraction."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    @patch("src.utils.html.find_meta_content")
    def test_extract_basic_seo_title_only(self, mock_find_meta, plugin):
        """Test extracting title only."""
        html = "<html><head><title>Test Title</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        mock_find_meta.return_value = None

        result = plugin._extract_basic_seo(soup, "https://example.com")

        assert result["title"] == "Test Title"
        assert result["title_length"] == len("Test Title")
        assert "description" not in result

    @patch("src.utils.html.find_meta_content")
    def test_extract_basic_seo_with_description(self, mock_find_meta, plugin):
        """Test extracting title and description."""
        html = "<html><head><title>Test Title</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        mock_find_meta.side_effect = (
            lambda soup, name: "Test description" if name == "description" else None
        )

        result = plugin._extract_basic_seo(soup, "https://example.com")

        assert result["title"] == "Test Title"
        assert result["description"] == "Test description"
        assert result["description_length"] == len("Test description")

    @patch("src.utils.html.find_meta_content")
    def test_extract_basic_seo_with_keywords(self, mock_find_meta, plugin):
        """Test extracting keywords."""
        html = "<html><head><title>Test</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        mock_find_meta.side_effect = (
            lambda soup, name: "keyword1, keyword2, keyword3" if name == "keywords" else None
        )

        result = plugin._extract_basic_seo(soup, "https://example.com")

        assert result["keywords"] == ["keyword1", "keyword2", "keyword3"]

    def test_extract_basic_seo_canonical_url(self, plugin):
        """Test extracting canonical URL."""
        html = '<html><head><link rel="canonical" href="/canonical-page"></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_basic_seo(soup, "https://example.com/test")

        assert result["canonical_url"] == "https://example.com/canonical-page"

    def test_extract_basic_seo_absolute_canonical_url(self, plugin):
        """Test extracting absolute canonical URL."""
        html = (
            '<html><head><link rel="canonical" href="https://example.com/canonical"></head></html>'
        )
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_basic_seo(soup, "https://example.com/test")

        assert result["canonical_url"] == "https://example.com/canonical"

    def test_extract_basic_seo_robots_meta(self, plugin):
        """Test extracting robots meta tag."""
        html = '<html><head><meta name="robots" content="noindex, nofollow"></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_basic_seo(soup, "https://example.com")

        assert result["robots"] == "noindex, nofollow"

    def test_extract_basic_seo_no_title(self, plugin):
        """Test handling missing title tag."""
        html = "<html><head></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        with patch("src.utils.html.find_meta_content", return_value=None):
            result = plugin._extract_basic_seo(soup, "https://example.com")

        assert "title" not in result
        assert "title_length" not in result

    def test_extract_basic_seo_empty_title(self, plugin):
        """Test handling empty title tag."""
        html = "<html><head><title></title></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        with patch("src.utils.html.find_meta_content", return_value=None):
            result = plugin._extract_basic_seo(soup, "https://example.com")

        assert result["title"] == ""
        assert result["title_length"] == 0

    @patch("src.utils.html.find_meta_content")
    def test_extract_basic_seo_keywords_with_empty_items(self, mock_find_meta, plugin):
        """Test keywords extraction filters empty items."""
        html = "<html><head></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        mock_find_meta.side_effect = (
            lambda soup, name: "keyword1, , keyword2,  , keyword3" if name == "keywords" else None
        )

        result = plugin._extract_basic_seo(soup, "https://example.com")

        assert result["keywords"] == ["keyword1", "keyword2", "keyword3"]


class TestExtractOpenGraph:
    """Test Open Graph metadata extraction."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    def test_extract_open_graph_basic(self, plugin):
        """Test extracting basic Open Graph metadata."""
        html = """
        <html><head>
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
            <meta property="og:image" content="https://example.com/image.jpg">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_open_graph(soup, "https://example.com")

        assert "open_graph" in result
        og = result["open_graph"]
        assert og["open_graph_title"] == "OG Title"
        assert og["open_graph_description"] == "OG Description"
        assert og["open_graph_image"] == "https://example.com/image.jpg"

    def test_extract_open_graph_no_og_tags(self, plugin):
        """Test behavior when no OG tags are present."""
        html = "<html><head><title>Regular title</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_open_graph(soup, "https://example.com")

        assert result == {}

    def test_extract_open_graph_empty_content(self, plugin):
        """Test handling OG tags with empty content."""
        html = """
        <html><head>
            <meta property="og:title" content="">
            <meta property="og:description" content="Valid description">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_open_graph(soup, "https://example.com")

        assert "open_graph" in result
        og = result["open_graph"]
        assert "open_graph_title" not in og
        assert og["open_graph_description"] == "Valid description"

    def test_extract_open_graph_missing_property(self, plugin):
        """Test handling OG tags without property attribute."""
        html = """
        <html><head>
            <meta property="og:title" content="Valid title">
            <meta content="Invalid - no property">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_open_graph(soup, "https://example.com")

        assert "open_graph" in result
        og = result["open_graph"]
        assert og["open_graph_title"] == "Valid title"
        assert len(og) == 1

    def test_extract_open_graph_whitespace_handling(self, plugin):
        """Test OG content whitespace is stripped."""
        html = """
        <html><head>
            <meta property="og:title" content="  Padded Title  ">
            <meta property="og:description" content="
            Multiline description
            ">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_open_graph(soup, "https://example.com")

        og = result["open_graph"]
        assert og["open_graph_title"] == "Padded Title"
        assert "Multiline description" in og["open_graph_description"]


class TestExtractTwitterCard:
    """Test Twitter Card metadata extraction."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    def test_extract_twitter_card_basic(self, plugin):
        """Test extracting basic Twitter Card metadata."""
        html = """
        <html><head>
            <meta name="twitter:card" content="summary">
            <meta name="twitter:title" content="Twitter Title">
            <meta name="twitter:description" content="Twitter Description">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_twitter_card(soup)

        assert "twitter" in result
        twitter = result["twitter"]
        assert twitter["twitter_card"] == "summary"
        assert twitter["twitter_title"] == "Twitter Title"
        assert twitter["twitter_description"] == "Twitter Description"

    def test_extract_twitter_card_no_tags(self, plugin):
        """Test behavior when no Twitter tags are present."""
        html = "<html><head><title>Regular title</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_twitter_card(soup)

        assert result == {}

    def test_extract_twitter_card_empty_content(self, plugin):
        """Test handling Twitter tags with empty content."""
        html = """
        <html><head>
            <meta name="twitter:card" content="">
            <meta name="twitter:title" content="Valid title">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_twitter_card(soup)

        assert "twitter" in result
        twitter = result["twitter"]
        assert "twitter_card" not in twitter
        assert twitter["twitter_title"] == "Valid title"

    def test_extract_twitter_card_site_creator(self, plugin):
        """Test extracting site and creator Twitter metadata."""
        html = """
        <html><head>
            <meta name="twitter:site" content="@example">
            <meta name="twitter:creator" content="@author">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_twitter_card(soup)

        twitter = result["twitter"]
        assert twitter["twitter_site"] == "@example"
        assert twitter["twitter_creator"] == "@author"


class TestExtractSchemaOrg:
    """Test Schema.org structured data extraction."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    def test_extract_schema_org_json_ld(self, plugin):
        """Test extracting JSON-LD structured data."""
        schema_data = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Test Article",
            "author": "Test Author",
        }
        html = f"""
        <html><head>
            <script type="application/ld+json">
            {json.dumps(schema_data)}
            </script>
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_schema_org(soup)

        assert "schema_org" in result
        schema_list = result["schema_org"]
        assert len(schema_list) == 1
        assert schema_list[0] == schema_data

    def test_extract_schema_org_multiple_json_ld(self, plugin):
        """Test extracting multiple JSON-LD blocks."""
        schema1 = {"@type": "Article", "headline": "Article 1"}
        schema2 = {"@type": "Person", "name": "John Doe"}

        html = f"""
        <html><head>
            <script type="application/ld+json">{json.dumps(schema1)}</script>
            <script type="application/ld+json">{json.dumps(schema2)}</script>
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_schema_org(soup)

        schema_list = result["schema_org"]
        assert len(schema_list) == 2
        assert schema1 in schema_list
        assert schema2 in schema_list

    def test_extract_schema_org_invalid_json(self, plugin):
        """Test handling invalid JSON in schema scripts."""
        html = """
        <html><head>
            <script type="application/ld+json">
            { invalid json }
            </script>
            <script type="application/ld+json">
            {"@type": "Article", "valid": "data"}
            </script>
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_schema_org(soup)

        # Should only include the valid JSON
        schema_list = result["schema_org"]
        assert len(schema_list) == 1
        assert schema_list[0]["@type"] == "Article"

    def test_extract_schema_org_microdata(self, plugin):
        """Test extracting microdata structured data."""
        html = """
        <html><body>
            <div itemscope itemtype="https://schema.org/Article">
                <h1 itemprop="headline">Article Title</h1>
                <span itemprop="author">Article Author</span>
                <time itemprop="datePublished" datetime="2023-01-01">January 1, 2023</time>
            </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_schema_org(soup)

        schema_list = result["schema_org"]
        assert len(schema_list) == 1
        microdata = schema_list[0]
        assert microdata["@type"] == "Article"
        assert microdata["headline"] == "Article Title"
        assert microdata["author"] == "Article Author"
        assert microdata["datePublished"] == "2023-01-01"

    def test_extract_schema_org_microdata_no_properties(self, plugin):
        """Test microdata with no properties is not included."""
        html = """
        <html><body>
            <div itemscope itemtype="https://schema.org/Article">
                <!-- No itemprop elements -->
            </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_schema_org(soup)

        assert result == {}

    def test_extract_schema_org_no_structured_data(self, plugin):
        """Test behavior when no structured data is present."""
        html = "<html><head><title>Regular page</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_schema_org(soup)

        assert result == {}


class TestExtractSEOSignals:
    """Test SEO signals extraction."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    def test_extract_seo_signals_headings(self, plugin):
        """Test extracting heading structure."""
        html = """
        <html><body>
            <h1>Main Title</h1>
            <h2>Subtitle 1</h2>
            <h2>Subtitle 2</h2>
            <h3>Sub-subtitle</h3>
            <p>Regular content</p>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "headings" in result
        headings = result["headings"]
        assert headings["h1"] == ["Main Title"]
        assert headings["h1_count"] == 1
        assert headings["h2"] == ["Subtitle 1", "Subtitle 2"]
        assert headings["h2_count"] == 2
        assert headings["h3"] == ["Sub-subtitle"]
        assert headings["h3_count"] == 1
        assert "h4" not in headings

    def test_extract_seo_signals_images(self, plugin):
        """Test extracting image optimization data."""
        html = """
        <html><body>
            <img src="image1.jpg" alt="Image 1">
            <img src="image2.jpg" alt="Image 2">
            <img src="image3.jpg">  <!-- Missing alt -->
            <img src="image4.jpg" alt="">  <!-- Empty alt -->
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "images" in result
        images = result["images"]
        assert images["total_count"] == 4
        assert images["missing_alt_count"] == 2  # Missing and empty alt
        assert images["alt_optimization_score"] == 50.0  # 2/4 * 100

    def test_extract_seo_signals_links(self, plugin):
        """Test extracting link analysis."""
        html = """
        <html><body>
            <a href="https://csfrace.com/internal">Internal CSFrace link</a>
            <a href="https://external.com">External link</a>
            <a href="/relative-internal">Relative internal</a>
            <a href="./relative-internal2">Dot relative</a>
            <a href="https://example.com">Another external</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "links" in result
        links = result["links"]
        assert links["total_count"] == 5
        assert links["internal_count"] == 3  # CSFrace + 2 relative
        assert links["external_count"] == 2

    def test_extract_seo_signals_content_analysis(self, plugin):
        """Test extracting content analysis metrics."""
        # Create content with known word count
        words = ["word"] * 400  # 400 words
        content = " ".join(words)
        html = f"<html><body><p>{content}</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "content_analysis" in result
        analysis = result["content_analysis"]
        assert analysis["word_count"] == 400
        assert analysis["reading_time_minutes"] == 2  # 400/200 WPM

    def test_extract_seo_signals_no_images(self, plugin):
        """Test behavior when no images are present."""
        html = "<html><body><p>No images here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "images" not in result

    def test_extract_seo_signals_no_links(self, plugin):
        """Test behavior when no links are present."""
        html = "<html><body><p>No links here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "links" not in result

    def test_extract_seo_signals_no_headings(self, plugin):
        """Test behavior when no headings are present."""
        html = "<html><body><p>No headings here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        assert "headings" not in result

    def test_extract_seo_signals_reading_time_minimum(self, plugin):
        """Test reading time has minimum of 1 minute."""
        html = "<html><body><p>Short content</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = plugin._extract_seo_signals(soup)

        analysis = result["content_analysis"]
        assert analysis["reading_time_minutes"] == 1


class TestBasePluginIntegration:
    """Test integration with BasePlugin functionality."""

    def test_inherits_from_metadata_extractor_plugin(self):
        """Test that SEOMetadataPlugin inherits from MetadataExtractorPlugin."""
        from src.plugins.base import MetadataExtractorPlugin

        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = SEOMetadataPlugin(config)

        assert isinstance(plugin, MetadataExtractorPlugin)

    @pytest.mark.asyncio
    async def test_process_method_integration(self):
        """Test the base process method works with our plugin."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = SEOMetadataPlugin(config)
        await plugin.initialize()

        html_content = """
        <html><head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head></html>
        """

        data = {
            "html": html_content,
            "url": "https://example.com",
            "metadata": {"existing": "data"},
        }
        context = {}

        result = await plugin.process(data, context)

        assert "html" in result
        assert "metadata" in result
        assert result["metadata"]["existing"] == "data"  # Existing preserved
        assert result["metadata"]["title"] == "Test Page"  # New added
        assert result["metadata"]["description"] == "Test description"

    @pytest.mark.asyncio
    async def test_process_method_invalid_data(self):
        """Test process method with invalid data structure."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = SEOMetadataPlugin(config)

        with pytest.raises(
            ValueError, match="MetadataExtractorPlugin expects dict with 'html' key"
        ):
            await plugin.process("invalid data", {})

    def test_plugin_configuration_methods(self):
        """Test plugin configuration methods work correctly."""
        config = PluginConfig(
            name="test_seo_metadata",
            version="1.0.0",
            plugin_type=PluginType.METADATA_EXTRACTOR,
            enabled=True,
            priority=75,
            settings={"extract_images": True},
        )
        plugin = SEOMetadataPlugin(config)

        assert plugin.is_enabled() is True
        assert plugin.get_priority() == 75
        assert plugin.get_setting("extract_images") is True
        assert plugin.get_setting("nonexistent", False) is False

        plugin.set_setting("new_setting", "test_value")
        assert plugin.get_setting("new_setting") == "test_value"


class TestEndToEndIntegration:
    """Test complete end-to-end SEO metadata extraction scenarios."""

    @pytest.fixture
    def plugin(self):
        """Create plugin for testing."""
        config = PluginConfig(
            name="test_seo_metadata", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        return SEOMetadataPlugin(config)

    @pytest.mark.asyncio
    async def test_complete_seo_extraction_scenario(self, plugin):
        """Test complete SEO extraction with comprehensive content."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Complete SEO Test Page | CSFrace Blog</title>
            <meta name="description" content="This is a comprehensive test page for SEO metadata extraction with all the important elements.">
            <meta name="keywords" content="seo, metadata, testing, extraction">
            <meta name="robots" content="index, follow">
            <link rel="canonical" href="https://csfrace.com/seo-test">

            <!-- Open Graph -->
            <meta property="og:title" content="Complete SEO Test Page">
            <meta property="og:description" content="OG description for social sharing">
            <meta property="og:image" content="https://csfrace.com/og-image.jpg">
            <meta property="og:type" content="article">

            <!-- Twitter Card -->
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:title" content="Twitter optimized title">
            <meta name="twitter:description" content="Twitter description">
            <meta name="twitter:site" content="@csfrace">

            <!-- Schema.org JSON-LD -->
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": "Complete SEO Test Article",
                "author": {
                    "@type": "Person",
                    "name": "SEO Expert"
                },
                "datePublished": "2023-08-27"
            }
            </script>
        </head>
        <body>
            <article itemscope itemtype="https://schema.org/BlogPosting">
                <h1 itemprop="headline">Main Article Title</h1>
                <h2>First Section</h2>
                <p>This is a comprehensive test article with multiple sections and rich content for SEO analysis.</p>

                <h2>Images and Media</h2>
                <img src="image1.jpg" alt="Properly tagged image">
                <img src="image2.jpg" alt="Another image with alt text">
                <img src="image3.jpg">  <!-- Missing alt for testing -->

                <h3>Subsection</h3>
                <p>More detailed content with various elements.</p>

                <h2>Links Section</h2>
                <p>Here are some links:</p>
                <ul>
                    <li><a href="https://csfrace.com/internal-page">Internal CSFrace link</a></li>
                    <li><a href="/relative-internal">Relative internal link</a></li>
                    <li><a href="https://external-site.com">External site link</a></li>
                    <li><a href="./another-relative">Another relative link</a></li>
                </ul>

                <div itemprop="author" itemscope itemtype="https://schema.org/Person">
                    <span itemprop="name">Test Author</span>
                </div>

                <time itemprop="datePublished" datetime="2023-08-27">August 27, 2023</time>
            </article>
        </body>
        </html>
        """

        with patch("src.utils.html.find_meta_content") as mock_find:
            mock_find.side_effect = lambda soup, name: {
                "description": "This is a comprehensive test page for SEO metadata extraction with all the important elements.",
                "keywords": "seo, metadata, testing, extraction",
            }.get(name)

            result = await plugin.extract_metadata(
                html_content, "https://csfrace.com/test-page", {}
            )

        # Verify basic SEO metadata
        assert result["title"] == "Complete SEO Test Page | CSFrace Blog"
        assert result["title_length"] == len(result["title"])
        assert (
            result["description"]
            == "This is a comprehensive test page for SEO metadata extraction with all the important elements."
        )
        assert result["keywords"] == ["seo", "metadata", "testing", "extraction"]
        assert result["canonical_url"] == "https://csfrace.com/seo-test"
        assert result["robots"] == "index, follow"

        # Verify Open Graph metadata
        assert "open_graph" in result
        og = result["open_graph"]
        assert og["open_graph_title"] == "Complete SEO Test Page"
        assert og["open_graph_description"] == "OG description for social sharing"
        assert og["open_graph_image"] == "https://csfrace.com/og-image.jpg"
        assert og["open_graph_type"] == "article"

        # Verify Twitter metadata
        assert "twitter" in result
        twitter = result["twitter"]
        assert twitter["twitter_card"] == "summary_large_image"
        assert twitter["twitter_title"] == "Twitter optimized title"
        assert twitter["twitter_site"] == "@csfrace"

        # Verify Schema.org data
        assert "schema_org" in result
        schema_list = result["schema_org"]
        assert len(schema_list) >= 1

        # Find the JSON-LD article
        json_ld_article = next((s for s in schema_list if s.get("@type") == "Article"), None)
        assert json_ld_article is not None
        assert json_ld_article["headline"] == "Complete SEO Test Article"

        # Verify SEO signals
        assert "headings" in result
        headings = result["headings"]
        assert "h1" in headings
        assert "h2" in headings
        assert "h3" in headings
        assert headings["h1_count"] == 1
        assert headings["h2_count"] == 3

        assert "images" in result
        images = result["images"]
        assert images["total_count"] == 3
        assert images["missing_alt_count"] == 1
        assert images["alt_optimization_score"] == (2 / 3) * 100

        assert "links" in result
        links = result["links"]
        assert links["total_count"] == 4
        assert links["internal_count"] == 3  # CSFrace + 2 relative
        assert links["external_count"] == 1

        assert "content_analysis" in result
        content = result["content_analysis"]
        assert content["word_count"] > 0
        assert content["character_count"] > 0
        assert content["reading_time_minutes"] >= 1

    @pytest.mark.asyncio
    async def test_minimal_html_scenario(self, plugin):
        """Test extraction from minimal HTML content."""
        html_content = "<html><head><title>Minimal Page</title></head><body><p>Simple content</p></body></html>"

        with patch("src.utils.html.find_meta_content", return_value=None):
            result = await plugin.extract_metadata(html_content, "https://example.com", {})

        # Should still extract basic information
        assert result["title"] == "Minimal Page"
        assert "content_analysis" in result
        assert result["content_analysis"]["word_count"] > 0

        # Should not have metadata that doesn't exist
        assert "open_graph" not in result
        assert "twitter" not in result
        assert "schema_org" not in result
        assert "headings" not in result
        assert "images" not in result
        assert "links" not in result

    @pytest.mark.asyncio
    async def test_malformed_html_scenario(self, plugin):
        """Test extraction from malformed HTML."""
        html_content = """
        <html>
        <head><title>Test</title>
        <meta property="og:title" content="OG Title"
        <script type="application/ld+json">{ invalid json }</script>
        <body>
        <h1>Heading without closing tag
        <p>Paragraph content
        <img src="image.jpg" alt="Alt text"
        """

        with patch("src.utils.html.find_meta_content", return_value=None):
            result = await plugin.extract_metadata(html_content, "https://example.com", {})

        # Should handle gracefully and extract what it can
        assert "title" in result
        assert "content_analysis" in result

        # Should not crash on malformed content
        assert isinstance(result, dict)
