"""Unit tests for metadata extractor."""

import pytest
from bs4 import BeautifulSoup

from src.processors.metadata_extractor import MetadataExtractor


class TestMetadataExtractor:
    """Test cases for metadata extraction functionality."""

    @pytest.mark.unit
    async def test_basic_metadata_extraction(self, metadata_extractor: MetadataExtractor):
        """Test extraction of basic metadata fields."""
        html = """
        <html>
        <head>
            <title>Test Blog Post Title</title>
            <meta name="description" content="This is a test description">
            <meta property="article:published_time" content="2024-01-15T10:00:00Z">
        </head>
        <body>Content</body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        assert metadata["title"] == "Test Blog Post Title"
        assert metadata["meta_description"] == "This is a test description"
        assert metadata["published_date"] == "2024-01-15T10:00:00Z"
        assert metadata["url"] == "https://test.example.com/blog/test-post"
        assert metadata["url_slug"] == "test-post"

    @pytest.mark.unit
    async def test_missing_title(self, metadata_extractor: MetadataExtractor):
        """Test handling of missing title tag."""
        html = "<html><head></head><body>Content</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        assert metadata["title"] == "No Title Found"

    @pytest.mark.unit
    async def test_meta_description_fallbacks(self, metadata_extractor: MetadataExtractor):
        """Test fallback mechanisms for meta description."""
        # Test Open Graph description fallback
        html_og = """
        <html>
        <head>
            <meta property="og:description" content="Open Graph description">
        </head>
        </html>
        """
        soup_og = BeautifulSoup(html_og, "html.parser")
        metadata_og = await metadata_extractor.extract(soup_og)
        assert metadata_og["meta_description"] == "Open Graph description"

        # Test Twitter description fallback
        html_twitter = """
        <html>
        <head>
            <meta name="twitter:description" content="Twitter description">
        </head>
        </html>
        """
        soup_twitter = BeautifulSoup(html_twitter, "html.parser")
        metadata_twitter = await metadata_extractor.extract(soup_twitter)
        assert metadata_twitter["meta_description"] == "Twitter description"

        # Test no description found
        html_empty = "<html><head></head></html>"
        soup_empty = BeautifulSoup(html_empty, "html.parser")
        metadata_empty = await metadata_extractor.extract(soup_empty)
        assert metadata_empty["meta_description"] == "No description found"

    @pytest.mark.unit
    async def test_published_date_extraction_methods(self, metadata_extractor: MetadataExtractor):
        """Test various methods of extracting published dates."""
        test_cases = [
            # Article published time
            (
                '<meta property="article:published_time" content="2024-01-15T10:00:00Z">',
                "2024-01-15T10:00:00Z",
            ),
            # Time element with datetime
            (
                '<time datetime="2024-02-15T15:30:00Z">February 15, 2024</time>',
                "2024-02-15T15:30:00Z",
            ),
            # Time element with pubdate
            ('<time pubdate datetime="2024-03-15">March 15, 2024</time>', "2024-03-15"),
            # Entry date class
            ('<div class="entry-date">April 15, 2024</div>', "April 15, 2024"),
            # Published class
            ('<span class="published">May 15, 2024</span>', "May 15, 2024"),
            # Schema.org microdata
            (
                '<meta itemprop="datePublished" content="2024-06-15T12:00:00Z">',
                "2024-06-15T12:00:00Z",
            ),
        ]

        for html_snippet, expected_date in test_cases:
            html = f"<html><head></head><body>{html_snippet}</body></html>"
            soup = BeautifulSoup(html, "html.parser")

            metadata = await metadata_extractor.extract(soup)
            assert metadata["published_date"] == expected_date, f"Failed for {html_snippet}"

    @pytest.mark.unit
    async def test_published_date_not_found(self, metadata_extractor: MetadataExtractor):
        """Test handling when no published date is found."""
        html = "<html><head></head><body>Content without date</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        assert metadata["published_date"] == "Date not found"

    @pytest.mark.unit
    async def test_url_slug_extraction(self):
        """Test URL slug extraction from different URL patterns."""
        test_cases = [
            ("https://example.com/blog/my-post", "my-post"),
            ("https://example.com/blog/category/my-post/", "my-post"),
            ("https://example.com/", "homepage"),
            ("https://example.com", "homepage"),
            ("https://example.com/single-page", "single-page"),
        ]

        for url, expected_slug in test_cases:
            extractor = MetadataExtractor(url)
            html = "<html><head></head><body></body></html>"
            soup = BeautifulSoup(html, "html.parser")

            metadata = await extractor.extract(soup)
            assert metadata["url_slug"] == expected_slug, f"Failed for {url}"

    @pytest.mark.unit
    async def test_metadata_with_empty_values(self, metadata_extractor: MetadataExtractor):
        """Test handling of empty metadata values."""
        html = """
        <html>
        <head>
            <title></title>
            <meta name="description" content="">
            <time datetime=""></time>
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        assert metadata["title"] == "No Title Found"
        assert metadata["meta_description"] == "No description found"
        assert metadata["published_date"] == "Date not found"

    @pytest.mark.unit
    async def test_metadata_with_whitespace(self, metadata_extractor: MetadataExtractor):
        """Test trimming of whitespace in metadata values."""
        html = """
        <html>
        <head>
            <title>   Test Title   </title>
            <meta name="description" content="   Test description   ">
        </head>
        <body>
            <div class="entry-date">   January 15, 2024   </div>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        assert metadata["title"] == "Test Title"
        assert metadata["meta_description"] == "Test description"
        assert metadata["published_date"] == "January 15, 2024"

    @pytest.mark.unit
    async def test_priority_order_for_descriptions(self, metadata_extractor: MetadataExtractor):
        """Test that standard meta description takes priority over others."""
        html = """
        <html>
        <head>
            <meta name="description" content="Standard description">
            <meta property="og:description" content="Open Graph description">
            <meta name="twitter:description" content="Twitter description">
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        # Standard meta description should take priority
        assert metadata["meta_description"] == "Standard description"

    @pytest.mark.unit
    async def test_priority_order_for_dates(self, metadata_extractor: MetadataExtractor):
        """Test that article:published_time takes priority over other date sources."""
        html = """
        <html>
        <head>
            <meta property="article:published_time" content="2024-01-15T10:00:00Z">
        </head>
        <body>
            <time datetime="2024-02-15T10:00:00Z">Different date</time>
            <div class="entry-date">Yet another date</div>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        metadata = await metadata_extractor.extract(soup)

        # Article published time should take priority
        assert metadata["published_date"] == "2024-01-15T10:00:00Z"
