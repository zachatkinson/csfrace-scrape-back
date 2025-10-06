"""Comprehensive tests for src/processors/metadata_extractor.py.

Test coverage: 57 statements, 0% → 80%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest
from bs4 import BeautifulSoup

from src.core.exceptions import ProcessingError
from src.processors.metadata_extractor import MetadataExtractor

# =============================================================================
# TEST MetadataExtractor - Initialization
# =============================================================================


@pytest.mark.unit
class TestMetadataExtractorInitialization:
    """Test MetadataExtractor initialization."""

    def test_initialization_with_base_url(self) -> None:
        """Test initialization with base URL."""
        # Arrange & Act
        extractor = MetadataExtractor(base_url="https://example.com/blog")

        # Assert
        assert extractor.base_url == "https://example.com/blog"


# =============================================================================
# TEST MetadataExtractor - extract Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMetadataExtractorExtract:
    """Test MetadataExtractor.extract() method."""

    async def test_extract_basic_metadata(self) -> None:
        """Test extracts basic metadata from HTML."""
        # Arrange
        html = """
        <html>
            <head>
                <title>Test Page Title</title>
                <meta name="description" content="Test description">
            </head>
            <body></body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com/test-page")

        # Act
        metadata = await extractor.extract(soup)

        # Assert
        assert metadata["title"] == "Test Page Title"
        assert metadata["url"] == "https://example.com/test-page"
        assert metadata["url_slug"] == "test-page"
        assert metadata["meta_description"] == "Test description"

    async def test_extract_with_no_title_tag(self) -> None:
        """Test extracts default title when title tag missing."""
        # Arrange
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        metadata = await extractor.extract(soup)

        # Assert
        assert metadata["title"] == "No Title Found"

    async def test_extract_with_empty_title_tag(self) -> None:
        """Test extracts default title when title tag empty."""
        # Arrange
        html = "<html><head><title>   </title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        metadata = await extractor.extract(soup)

        # Assert
        assert metadata["title"] == "No Title Found"

    async def test_extract_strips_whitespace_from_title(self) -> None:
        """Test strips whitespace from title."""
        # Arrange
        html = "<html><head><title>  Test Title  </title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        metadata = await extractor.extract(soup)

        # Assert
        assert metadata["title"] == "Test Title"

    async def test_extract_url_slug_from_path(self) -> None:
        """Test extracts URL slug from path."""
        # Arrange
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com/blog/my-post")

        # Act
        metadata = await extractor.extract(soup)

        # Assert
        assert metadata["url_slug"] == "my-post"

    async def test_extract_url_slug_for_homepage(self) -> None:
        """Test extracts homepage slug for root URL."""
        # Arrange
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com/")

        # Act
        metadata = await extractor.extract(soup)

        # Assert
        assert metadata["url_slug"] == "homepage"

    async def test_extract_raises_processing_error_on_exception(self) -> None:
        """Test raises ProcessingError when extraction fails."""
        # Arrange
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act & Assert
        with pytest.raises(ProcessingError, match="Failed to extract metadata"):
            await extractor.extract(None)  # type: ignore[arg-type]  # Invalid soup causes exception


# =============================================================================
# TEST MetadataExtractor - _extract_meta_description Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMetadataExtractorExtractMetaDescription:
    """Test MetadataExtractor._extract_meta_description() method."""

    async def test_extract_meta_description_from_standard_meta_tag(self) -> None:
        """Test extracts description from standard meta tag."""
        # Arrange
        html = '<html><head><meta name="description" content="Standard description"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        description = await extractor._extract_meta_description(soup)

        # Assert
        assert description == "Standard description"

    async def test_extract_meta_description_from_opengraph(self) -> None:
        """Test extracts description from OpenGraph meta tag."""
        # Arrange
        html = '<html><head><meta property="og:description" content="OG description"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        description = await extractor._extract_meta_description(soup)

        # Assert
        assert description == "OG description"

    async def test_extract_meta_description_from_twitter(self) -> None:
        """Test extracts description from Twitter meta tag."""
        # Arrange
        html = '<html><head><meta name="twitter:description" content="Twitter description"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        description = await extractor._extract_meta_description(soup)

        # Assert
        assert description == "Twitter description"

    async def test_extract_meta_description_priority_order(self) -> None:
        """Test standard meta description takes priority over OpenGraph."""
        # Arrange
        html = """
        <html><head>
            <meta name="description" content="Standard description">
            <meta property="og:description" content="OG description">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        description = await extractor._extract_meta_description(soup)

        # Assert - Standard meta takes priority
        assert description == "Standard description"

    async def test_extract_meta_description_strips_whitespace(self) -> None:
        """Test strips whitespace from description."""
        # Arrange
        html = (
            '<html><head><meta name="description" content="  Spaced description  "></head></html>'
        )
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        description = await extractor._extract_meta_description(soup)

        # Assert
        assert description == "Spaced description"

    async def test_extract_meta_description_returns_default_when_not_found(self) -> None:
        """Test returns default message when no description found."""
        # Arrange
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        description = await extractor._extract_meta_description(soup)

        # Assert
        assert description == "No description found"


# =============================================================================
# TEST MetadataExtractor - _extract_published_date Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMetadataExtractorExtractPublishedDate:
    """Test MetadataExtractor._extract_published_date() method."""

    async def test_extract_published_date_from_article_published_time(self) -> None:
        """Test extracts date from article:published_time meta tag."""
        # Arrange
        html = '<html><head><meta property="article:published_time" content="2024-01-15"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        date = await extractor._extract_published_date(soup)

        # Assert
        assert date == "2024-01-15"

    async def test_extract_published_date_from_time_datetime(self) -> None:
        """Test extracts date from time element with datetime attribute."""
        # Arrange
        html = (
            '<html><body><time datetime="2024-01-15T10:30:00">January 15, 2024</time></body></html>'
        )
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        date = await extractor._extract_published_date(soup)

        # Assert
        assert date == "2024-01-15T10:30:00"

    async def test_extract_published_date_from_wordpress_class(self) -> None:
        """Test extracts date from WordPress entry-date class."""
        # Arrange
        html = '<html><body><span class="entry-date">January 15, 2024</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        date = await extractor._extract_published_date(soup)

        # Assert
        assert date == "January 15, 2024"

    async def test_extract_published_date_from_schema_org_microdata(self) -> None:
        """Test extracts date from schema.org datePublished microdata."""
        # Arrange
        html = (
            '<html><body><span itemprop="datePublished" datetime="2024-01-15"></span></body></html>'
        )
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        date = await extractor._extract_published_date(soup)

        # Assert
        assert date == "2024-01-15"

    async def test_extract_published_date_strips_whitespace(self) -> None:
        """Test strips whitespace from date."""
        # Arrange
        html = '<html><body><span class="entry-date">  2024-01-15  </span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        date = await extractor._extract_published_date(soup)

        # Assert
        assert date == "2024-01-15"

    async def test_extract_published_date_returns_default_when_not_found(self) -> None:
        """Test returns default message when no date found."""
        # Arrange
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        extractor = MetadataExtractor(base_url="https://example.com")

        # Act
        date = await extractor._extract_published_date(soup)

        # Assert
        assert date == "Date not found"


# =============================================================================
# TEST MetadataExtractor - supports_url Method
# =============================================================================


@pytest.mark.unit
class TestMetadataExtractorSupportsUrl:
    """Test MetadataExtractor.supports_url() method."""

    def test_supports_url_returns_true_for_same_domain(self) -> None:
        """Test returns True for URL with same domain."""
        # Arrange
        extractor = MetadataExtractor(base_url="https://example.com/blog")

        # Act
        result = extractor.supports_url("https://example.com/about")

        # Assert
        assert result is True

    def test_supports_url_returns_false_for_different_domain(self) -> None:
        """Test returns False for URL with different domain."""
        # Arrange
        extractor = MetadataExtractor(base_url="https://example.com/blog")

        # Act
        result = extractor.supports_url("https://other.com/page")

        # Assert
        assert result is False

    def test_supports_url_handles_subdomain_differences(self) -> None:
        """Test handles subdomain differences correctly."""
        # Arrange
        extractor = MetadataExtractor(base_url="https://blog.example.com")

        # Act
        result = extractor.supports_url("https://www.example.com")

        # Assert
        assert result is False

    def test_supports_url_ignores_path_differences(self) -> None:
        """Test ignores path differences when checking domain."""
        # Arrange
        extractor = MetadataExtractor(base_url="https://example.com/blog/post1")

        # Act
        result = extractor.supports_url("https://example.com/about/us")

        # Assert
        assert result is True
