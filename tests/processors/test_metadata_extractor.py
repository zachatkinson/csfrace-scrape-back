"""Comprehensive tests for metadata extraction."""

from unittest.mock import patch

import pytest
import pytest_asyncio
from bs4 import BeautifulSoup

from src.core.exceptions import ProcessingError
from src.processors.metadata_extractor import MetadataExtractor


class TestMetadataExtractor:
    """Test metadata extraction functionality."""

    @pytest_asyncio.fixture
    async def extractor(self):
        """Create metadata extractor instance."""
        return MetadataExtractor("https://csfrace.com/test-page")

    @pytest.mark.asyncio
    async def test_extractor_initialization(self):
        """Test metadata extractor initialization."""
        base_url = "https://csfrace.com/blog/post"
        extractor = MetadataExtractor(base_url)

        assert extractor.base_url == base_url

    @pytest.mark.asyncio
    async def test_extract_basic_metadata(self, extractor):
        """Test extraction of basic page metadata."""
        html_content = """
        <html>
        <head>
            <title>Test Blog Post - CSF Race</title>
            <meta name="description" content="This is a test blog post about racing.">
        </head>
        <body>
            <h1>Test Content</h1>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        metadata = await extractor.extract(soup)

        assert metadata["title"] == "Test Blog Post - CSF Race"
        assert metadata["meta_description"] == "This is a test blog post about racing."
        assert metadata["url"] == "https://csfrace.com/test-page"
        assert metadata["url_slug"] == "test-page"

    @pytest.mark.asyncio
    async def test_extract_no_title(self, extractor):
        """Test metadata extraction when no title is present."""
        html_content = "<html><head></head><body><h1>Content</h1></body></html>"

        soup = BeautifulSoup(html_content, "html.parser")
        metadata = await extractor.extract(soup)

        assert metadata["title"] == "No Title Found"

    @pytest.mark.asyncio
    async def test_extract_empty_title(self, extractor):
        """Test metadata extraction with empty title."""
        html_content = "<html><head><title>   </title></head><body></body></html>"

        soup = BeautifulSoup(html_content, "html.parser")
        metadata = await extractor.extract(soup)

        assert metadata["title"] == "No Title Found"

    @pytest.mark.asyncio
    async def test_extract_url_slug_from_path(self):
        """Test URL slug extraction from different URL paths."""
        test_cases = [
            ("https://csfrace.com/blog/racing-tips", "racing-tips"),
            ("https://csfrace.com/news/2023/championship", "championship"),
            ("https://csfrace.com/", "homepage"),
            ("https://csfrace.com", "homepage"),
            ("https://csfrace.com/single-page", "single-page"),
        ]

        for url, expected_slug in test_cases:
            extractor = MetadataExtractor(url)
            html_content = "<html><head><title>Test</title></head></html>"
            soup = BeautifulSoup(html_content, "html.parser")

            metadata = await extractor.extract(soup)
            assert metadata["url_slug"] == expected_slug, f"Failed for URL: {url}"

    @pytest.mark.asyncio
    async def test_extract_meta_description_standard(self, extractor):
        """Test extraction of standard meta description."""
        html_content = """
        <html>
        <head>
            <meta name="description" content="Standard meta description content.">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        with patch(
            "src.utils.html.find_meta_content", return_value="Standard meta description content."
        ):
            meta_desc = await extractor._extract_meta_description(soup)
            assert meta_desc == "Standard meta description content."

    @pytest.mark.asyncio
    async def test_extract_meta_description_og(self, extractor):
        """Test extraction of Open Graph description when standard is missing."""
        html_content = """
        <html>
        <head>
            <meta property="og:description" content="Open Graph description.">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        # Mock find_meta_content to return None for standard, then OG description
        with patch(
            "src.utils.html.find_meta_content", side_effect=[None, "Open Graph description."]
        ):
            meta_desc = await extractor._extract_meta_description(soup)
            assert meta_desc == "Open Graph description."

    @pytest.mark.asyncio
    async def test_extract_meta_description_twitter(self, extractor):
        """Test extraction of Twitter description when others are missing."""
        html_content = """
        <html>
        <head>
            <meta name="twitter:description" content="Twitter card description.">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        # Mock find_meta_content to return None for standard and OG, then Twitter
        with patch(
            "src.utils.html.find_meta_content",
            side_effect=[None, None, "Twitter card description."],
        ):
            meta_desc = await extractor._extract_meta_description(soup)
            assert meta_desc == "Twitter card description."

    @pytest.mark.asyncio
    async def test_extract_meta_description_none_found(self, extractor):
        """Test meta description extraction when none are found."""
        html_content = "<html><head></head></html>"

        soup = BeautifulSoup(html_content, "html.parser")

        with patch("src.utils.html.find_meta_content", return_value=None):
            meta_desc = await extractor._extract_meta_description(soup)
            assert meta_desc == "No description found"

    @pytest.mark.asyncio
    async def test_extract_meta_description_whitespace_handling(self, extractor):
        """Test meta description extraction with whitespace handling."""
        html_content = """
        <html>
        <head>
            <meta name="description" content="  Description with whitespace  ">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        with patch(
            "src.utils.html.find_meta_content", return_value="  Description with whitespace  "
        ):
            meta_desc = await extractor._extract_meta_description(soup)
            assert meta_desc == "Description with whitespace"

    @pytest.mark.asyncio
    async def test_extract_published_date_article_property(self, extractor):
        """Test published date extraction from article:published_time property."""
        html_content = """
        <html>
        <head>
            <meta property="article:published_time" content="2023-08-26T10:30:00Z">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26T10:30:00Z"

    @pytest.mark.asyncio
    async def test_extract_published_date_article_name(self, extractor):
        """Test published date extraction from article:published_time name."""
        html_content = """
        <html>
        <head>
            <meta name="article:published_time" content="2023-08-26">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26"

    @pytest.mark.asyncio
    async def test_extract_published_date_time_datetime(self, extractor):
        """Test published date extraction from time element with datetime attribute."""
        html_content = """
        <html>
        <body>
            <time datetime="2023-08-26T15:45:00">August 26, 2023</time>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26T15:45:00"

    @pytest.mark.asyncio
    async def test_extract_published_date_time_pubdate(self, extractor):
        """Test published date extraction from time element with pubdate attribute."""
        html_content = """
        <html>
        <body>
            <time datetime="2023-08-26T12:00:00" pubdate>Published today</time>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26T12:00:00"

    @pytest.mark.asyncio
    async def test_extract_published_date_wordpress_classes(self, extractor):
        """Test published date extraction from WordPress date classes."""
        html_content = """
        <html>
        <body>
            <span class="entry-date">March 15, 2023</span>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "March 15, 2023"

    @pytest.mark.asyncio
    async def test_extract_published_date_published_class(self, extractor):
        """Test published date extraction from .published class."""
        html_content = """
        <html>
        <body>
            <time class="published">2023-08-26</time>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26"

    @pytest.mark.asyncio
    async def test_extract_published_date_post_date_class(self, extractor):
        """Test published date extraction from .post-date class."""
        html_content = """
        <html>
        <body>
            <div class="post-date">August 26, 2023</div>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "August 26, 2023"

    @pytest.mark.asyncio
    async def test_extract_published_date_microdata_datetime(self, extractor):
        """Test published date extraction from microdata with datetime."""
        html_content = """
        <html>
        <body>
            <time itemprop="datePublished" datetime="2023-08-26T14:30:00">
                Published on Aug 26
            </time>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26T14:30:00"

    @pytest.mark.asyncio
    async def test_extract_published_date_microdata_content(self, extractor):
        """Test published date extraction from microdata with content attribute."""
        html_content = """
        <html>
        <body>
            <meta itemprop="datePublished" content="2023-08-26">
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26"

    @pytest.mark.asyncio
    async def test_extract_published_date_fallback_text(self, extractor):
        """Test published date extraction falls back to element text when no datetime."""
        html_content = """
        <html>
        <body>
            <time itemprop="datePublished">August 26, 2023</time>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "August 26, 2023"

    @pytest.mark.asyncio
    async def test_extract_published_date_none_found(self, extractor):
        """Test published date extraction when no date is found."""
        html_content = "<html><head></head><body><p>No date here</p></body></html>"

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "Date not found"

    @pytest.mark.asyncio
    async def test_extract_published_date_empty_values(self, extractor):
        """Test published date extraction with empty date values."""
        html_content = """
        <html>
        <body>
            <time datetime="">Empty datetime</time>
            <span class="entry-date">   </span>
            <meta itemprop="datePublished" content="">
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "Date not found"

    @pytest.mark.asyncio
    async def test_extract_published_date_priority_order(self, extractor):
        """Test that published date extraction follows correct priority order."""
        html_content = """
        <html>
        <head>
            <meta property="article:published_time" content="2023-08-26T10:00:00Z">
        </head>
        <body>
            <time datetime="2023-08-26T12:00:00">Different time</time>
            <span class="entry-date">August 26, 2023</span>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        # Should prefer the first selector (article:published_time property)
        assert published_date == "2023-08-26T10:00:00Z"

    @pytest.mark.asyncio
    async def test_extract_complete_metadata_integration(self, extractor):
        """Test complete metadata extraction with all fields."""
        html_content = """
        <html>
        <head>
            <title>Racing Championship News - CSF Race</title>
            <meta name="description" content="Latest news from the racing championship.">
            <meta property="article:published_time" content="2023-08-26T10:30:00Z">
        </head>
        <body>
            <article>
                <h1>Championship Results</h1>
                <time class="entry-date">August 26, 2023</time>
                <p>Article content here.</p>
            </article>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        with patch(
            "src.utils.html.find_meta_content",
            return_value="Latest news from the racing championship.",
        ):
            metadata = await extractor.extract(soup)

            assert metadata["title"] == "Racing Championship News - CSF Race"
            assert metadata["meta_description"] == "Latest news from the racing championship."
            assert metadata["url"] == "https://csfrace.com/test-page"
            assert metadata["url_slug"] == "test-page"
            assert metadata["published_date"] == "2023-08-26T10:30:00Z"

    @pytest.mark.asyncio
    async def test_extract_exception_handling(self, extractor):
        """Test exception handling in metadata extraction."""
        # Create a mock that will raise an exception
        with patch.object(
            extractor, "_extract_meta_description", side_effect=Exception("Test error")
        ):
            html_content = "<html><head><title>Test</title></head></html>"
            soup = BeautifulSoup(html_content, "html.parser")

            with pytest.raises(ProcessingError, match="Failed to extract metadata"):
                await extractor.extract(soup)


class TestMetadataExtractorEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_extract_with_malformed_html(self):
        """Test metadata extraction with malformed HTML."""
        extractor = MetadataExtractor("https://csfrace.com/malformed")
        malformed_html = "<title>Test</title><meta name='desc' content='test'><p>Unclosed"

        soup = BeautifulSoup(malformed_html, "html.parser")

        with patch("src.utils.html.find_meta_content", return_value="test"):
            metadata = await extractor.extract(soup)

            # Should handle malformed HTML gracefully
            assert metadata["title"] == "Test"
            assert metadata["meta_description"] == "test"

    @pytest.mark.asyncio
    async def test_extract_with_unicode_content(self):
        """Test metadata extraction with Unicode content."""
        extractor = MetadataExtractor("https://csfrace.com/unicode")
        html_content = """
        <html>
        <head>
            <title>Racing News • CSF Race™</title>
            <meta name="description" content="Latest racing news with émojis 🏁">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        with patch(
            "src.utils.html.find_meta_content", return_value="Latest racing news with émojis 🏁"
        ):
            metadata = await extractor.extract(soup)

            assert "Racing News • CSF Race™" in metadata["title"]
            assert "émojis 🏁" in metadata["meta_description"]

    @pytest.mark.asyncio
    async def test_extract_with_very_long_content(self):
        """Test metadata extraction with very long content."""
        extractor = MetadataExtractor("https://csfrace.com/long")
        long_title = "Very Long Title " * 50
        long_description = "Very long description content " * 100

        html_content = f"""
        <html>
        <head>
            <title>{long_title}</title>
            <meta name="description" content="{long_description}">
        </head>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")

        with patch("src.utils.html.find_meta_content", return_value=long_description):
            metadata = await extractor.extract(soup)

            assert metadata["title"] == long_title.strip()
            assert metadata["meta_description"] == long_description

    @pytest.mark.asyncio
    async def test_url_slug_with_special_characters(self):
        """Test URL slug extraction with special characters in path."""
        test_urls = [
            ("https://csfrace.com/news/2023-08-26_race-results", "2023-08-26_race-results"),
            ("https://csfrace.com/drivers/john-doe%20racing", "john-doe%20racing"),
            ("https://csfrace.com/events/formula-1@silverstone", "formula-1@silverstone"),
        ]

        for url, expected_slug in test_urls:
            extractor = MetadataExtractor(url)
            html_content = "<html><head><title>Test</title></head></html>"
            soup = BeautifulSoup(html_content, "html.parser")

            metadata = await extractor.extract(soup)
            assert metadata["url_slug"] == expected_slug

    @pytest.mark.asyncio
    async def test_date_extraction_selector_failure_recovery(self):
        """Test that date extraction continues if selector fails."""
        extractor = MetadataExtractor("https://csfrace.com/test")

        # HTML with elements that could cause selector issues
        html_content = """
        <html>
        <body>
            <time class="published" datetime="2023-08-26">Valid date</time>
        </body>
        </html>
        """

        soup = BeautifulSoup(html_content, "html.parser")
        published_date = await extractor._extract_published_date(soup)

        assert published_date == "2023-08-26"

    @pytest.mark.asyncio
    async def test_meta_description_with_html_entities(self):
        """Test meta description extraction with HTML entities."""
        extractor = MetadataExtractor("https://csfrace.com/entities")

        with patch(
            "src.utils.html.find_meta_content",
            return_value="Racing news &amp; results - it's great!",
        ):
            html_content = "<html><head></head></html>"
            soup = BeautifulSoup(html_content, "html.parser")

            meta_desc = await extractor._extract_meta_description(soup)
            assert meta_desc == "Racing news &amp; results - it's great!"
