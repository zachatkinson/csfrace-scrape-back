"""Comprehensive tests for AsyncWordPressConverter to boost coverage from 20.69% to 85%+.

This module follows TDD principles and tests all critical paths, error scenarios,
and edge cases in the converter module.
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from aioresponses import aioresponses

from src.core.config import ConverterConfig
from src.core.converter import AsyncWordPressConverter
from src.core.exceptions import ConversionError, FetchError, ProcessingError, SaveError


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <meta name="description" content="Test page description">
    </head>
    <body>
        <div class="content">
            <h1>Test Content</h1>
            <p>This is a test paragraph.</p>
            <img src="https://example.com/image1.jpg" alt="Test Image">
            <a href="https://example.com/link">Test Link</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_config():
    """Mock converter configuration."""
    return ConverterConfig(
        default_timeout=10,
        max_concurrent_downloads=5,
        images_subdir="images",
        metadata_file="metadata.txt",
        html_file="converted_content.html",
        shopify_file="shopify_ready_content.html",
    )


class TestAsyncWordPressConverterInitialization:
    """Test converter initialization and validation."""

    def test_init_with_valid_url(self, tmp_path, mock_config):
        """Test initialization with valid URL."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=tmp_path, config=mock_config
        )

        assert converter.base_url == "https://example.com"
        assert converter.output_dir == tmp_path
        assert converter.config == mock_config
        assert converter.images_dir == tmp_path / "images"

    def test_init_with_url_no_protocol(self, tmp_path, mock_config):
        """Test initialization with URL missing protocol."""
        converter = AsyncWordPressConverter(
            base_url="example.com", output_dir=tmp_path, config=mock_config
        )

        assert converter.base_url == "https://example.com"

    def test_init_with_http_protocol(self, tmp_path, mock_config):
        """Test initialization with HTTP protocol."""
        converter = AsyncWordPressConverter(
            base_url="http://example.com", output_dir=tmp_path, config=mock_config
        )

        assert converter.base_url == "http://example.com"

    def test_init_with_default_config(self, tmp_path):
        """Test initialization with default config."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        assert converter.config is not None
        assert converter.images_dir == tmp_path / converter.config.images_subdir

    def test_init_creates_processors(self, tmp_path, mock_config):
        """Test that initialization creates required processors."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=tmp_path, config=mock_config
        )

        assert converter.html_processor is not None
        assert converter.metadata_extractor is not None
        assert converter.image_downloader is not None


class TestURLValidation:
    """Test URL validation logic."""

    def test_validate_url_empty(self):
        """Test validation of empty URL."""
        with pytest.raises(ConversionError, match="URL cannot be empty"):
            AsyncWordPressConverter(base_url="", output_dir=Path("/tmp"))

    def test_validate_url_invalid_structure(self):
        """Test validation of URL with invalid structure."""
        with pytest.raises(ConversionError, match="Invalid domain"):
            AsyncWordPressConverter(base_url="not://a-valid-url", output_dir=Path("/tmp"))

    def test_validate_url_no_netloc(self):
        """Test validation of URL with no netloc."""
        with pytest.raises(ConversionError, match="Invalid URL"):
            AsyncWordPressConverter(base_url="https://", output_dir=Path("/tmp"))

    def test_validate_url_invalid_domain(self):
        """Test validation of URL with invalid domain."""
        with pytest.raises(ConversionError, match="Invalid domain"):
            AsyncWordPressConverter(base_url="https://invalid-domain", output_dir=Path("/tmp"))

    def test_validate_url_localhost(self):
        """Test validation accepts localhost."""
        converter = AsyncWordPressConverter(base_url="https://localhost", output_dir=Path("/tmp"))
        assert converter.base_url == "https://localhost"

    def test_validate_url_with_port(self):
        """Test validation of URL with port."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com:8080", output_dir=Path("/tmp")
        )
        assert converter.base_url == "https://example.com:8080"

    def test_validate_url_with_path(self):
        """Test validation of URL with path."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com/blog", output_dir=Path("/tmp")
        )
        assert converter.base_url == "https://example.com/blog"


class TestDirectorySetup:
    """Test directory setup functionality."""

    @pytest.mark.asyncio
    async def test_setup_directories_success(self, tmp_path, mock_config):
        """Test successful directory setup."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=tmp_path / "output", config=mock_config
        )

        await converter._setup_directories()

        assert converter.output_dir.exists()
        assert converter.images_dir.exists()

    @pytest.mark.asyncio
    async def test_setup_directories_creates_parents(self, tmp_path, mock_config):
        """Test directory setup creates parent directories."""
        nested_path = tmp_path / "level1" / "level2" / "output"
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=nested_path, config=mock_config
        )

        await converter._setup_directories()

        assert nested_path.exists()
        assert (nested_path / "images").exists()

    @pytest.mark.asyncio
    async def test_setup_directories_permission_error(self, mock_config):
        """Test directory setup with permission error."""
        restricted_path = Path("/root/restricted")
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=restricted_path, config=mock_config
        )

        with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(ConversionError, match="Failed to create directories"):
                await converter._setup_directories()


class TestContentFetching:
    """Test content fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_content_success(self, tmp_path, sample_html):
        """Test successful content fetching."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", body=sample_html, status=200)
            # Mock robots.txt
            mock.get("https://example.com/robots.txt", status=404)

            async with aiohttp.ClientSession() as session:
                content = await converter._fetch_content(session)

                assert content == sample_html

    @pytest.mark.asyncio
    async def test_fetch_content_404_error(self, tmp_path):
        """Test content fetching with 404 error."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com/nonexistent", output_dir=tmp_path
        )

        with aioresponses() as mock:
            mock.get("https://example.com/nonexistent", status=404)
            mock.get("https://example.com/robots.txt", status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(FetchError):
                    await converter._fetch_content(session)

    @pytest.mark.asyncio
    async def test_fetch_content_network_error(self, tmp_path):
        """Test content fetching with network error."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", exception=aiohttp.ClientError())
            mock.get("https://example.com/robots.txt", status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(FetchError):
                    await converter._fetch_content(session)

    @pytest.mark.asyncio
    async def test_fetch_content_timeout(self, tmp_path):
        """Test content fetching with timeout."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", exception=TimeoutError())
            mock.get("https://example.com/robots.txt", status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(FetchError):
                    await converter._fetch_content(session)


class TestContentProcessing:
    """Test content processing functionality."""

    @pytest.mark.asyncio
    async def test_process_content_success(self, tmp_path, sample_html):
        """Test successful content processing."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        mock_metadata = {"title": "Test Page", "description": "Test description"}

        with patch.object(converter.metadata_extractor, "extract", return_value=mock_metadata):
            with patch.object(converter.html_processor, "process", return_value=sample_html):
                metadata, processed_html, image_urls = await converter._process_content(sample_html)

                assert metadata == mock_metadata
                assert processed_html == sample_html
                assert isinstance(image_urls, list)

    @pytest.mark.asyncio
    async def test_process_content_with_images(self, tmp_path, sample_html):
        """Test content processing extracts image URLs."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with patch.object(converter.metadata_extractor, "extract", return_value={}):
            with patch.object(converter.html_processor, "process", return_value=sample_html):
                metadata, processed_html, image_urls = await converter._process_content(sample_html)

                assert len(image_urls) > 0
                assert "https://example.com/image1.jpg" in image_urls

    def test_extract_image_urls_basic(self, tmp_path, sample_html):
        """Test basic image URL extraction."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        image_urls = converter._extract_image_urls(sample_html)

        assert len(image_urls) > 0
        assert "https://example.com/image1.jpg" in image_urls

    def test_extract_image_urls_relative_paths(self, tmp_path):
        """Test image URL extraction with relative paths."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        html_with_relative = '<img src="/images/test.jpg" alt="Test"><img src="./local.png">'
        image_urls = converter._extract_image_urls(html_with_relative)

        assert "https://example.com/images/test.jpg" in image_urls
        assert "https://example.com/local.png" in image_urls

    def test_extract_image_urls_deduplicates(self, tmp_path):
        """Test image URL extraction removes duplicates."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        html_with_dupes = '<img src="/test.jpg"><img src="/test.jpg"><img src="/other.jpg">'
        image_urls = converter._extract_image_urls(html_with_dupes)

        assert len(image_urls) == 2
        assert image_urls.count("https://example.com/test.jpg") == 1


class TestFileSaving:
    """Test file saving functionality."""

    @pytest.mark.asyncio
    async def test_save_content_creates_files(self, tmp_path, mock_config):
        """Test that save_content creates all required files."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=tmp_path, config=mock_config
        )

        metadata = {"title": "Test Page", "description": "Test description"}
        html_content = "<h1>Test Content</h1>"

        await converter._save_content(metadata, html_content)

        # Check all files were created
        assert (tmp_path / "metadata.txt").exists()
        assert (tmp_path / "converted_content.html").exists()
        assert (tmp_path / "shopify_ready_content.html").exists()

    @pytest.mark.asyncio
    async def test_write_metadata_file(self, tmp_path):
        """Test metadata file writing."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        metadata = {"title": "Test Page", "author": "Test Author"}
        metadata_path = tmp_path / "test_metadata.txt"

        await converter._write_metadata_file(metadata_path, metadata)

        assert metadata_path.exists()
        content = metadata_path.read_text()
        assert "EXTRACTED METADATA" in content
        assert "Title: Test Page" in content
        assert "Author: Test Author" in content

    @pytest.mark.asyncio
    async def test_write_shopify_file(self, tmp_path):
        """Test Shopify-ready file writing."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        metadata = {"title": "Test Page", "description": "Test description"}
        html_content = "<h1>Test Content</h1>"
        shopify_path = tmp_path / "test_shopify.html"

        await converter._write_shopify_file(shopify_path, metadata, html_content)

        assert shopify_path.exists()
        content = shopify_path.read_text()
        assert "<!-- METADATA -->" in content
        assert "<!-- Title: Test Page -->" in content
        assert "<h1>Test Content</h1>" in content

    @pytest.mark.asyncio
    async def test_write_text_file_basic(self, tmp_path):
        """Test basic text file writing."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        test_path = tmp_path / "test.txt"
        test_content = "Test content"

        await converter._write_text_file(test_path, test_content)

        assert test_path.exists()
        assert test_path.read_text() == test_content

    @pytest.mark.asyncio
    async def test_save_content_write_error(self, tmp_path, mock_config):
        """Test save_content with write error."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=tmp_path, config=mock_config
        )

        with patch("pathlib.Path.write_text", side_effect=OSError("Write failed")):
            with pytest.raises(SaveError, match="Failed to save content"):
                await converter._save_content({"title": "Test"}, "<h1>Test</h1>")


class TestMainConversionFlow:
    """Test the main convert() method integration."""

    @pytest.mark.asyncio
    async def test_convert_success_full_flow(self, tmp_path, sample_html, mock_config):
        """Test successful complete conversion flow."""
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=tmp_path, config=mock_config
        )

        mock_metadata = {"title": "Test Page", "description": "Test description"}

        with aioresponses() as mock:
            mock.get("https://example.com", body=sample_html, status=200)
            mock.get("https://example.com/robots.txt", status=404)

            with patch.object(converter.metadata_extractor, "extract", return_value=mock_metadata):
                with patch.object(converter.html_processor, "process", return_value=sample_html):
                    with patch.object(converter.image_downloader, "download_all"):
                        await converter.convert()

        # Check files were created
        assert (tmp_path / "metadata.txt").exists()
        assert (tmp_path / "converted_content.html").exists()
        assert (tmp_path / "shopify_ready_content.html").exists()

    @pytest.mark.asyncio
    async def test_convert_with_progress_callback(self, tmp_path, sample_html):
        """Test conversion with progress callback."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        progress_calls = []

        def progress_callback(progress: int):
            progress_calls.append(progress)

        with aioresponses() as mock:
            mock.get("https://example.com", body=sample_html, status=200)
            mock.get("https://example.com/robots.txt", status=404)

            with patch.object(converter.metadata_extractor, "extract", return_value={}):
                with patch.object(converter.html_processor, "process", return_value=sample_html):
                    with patch.object(converter.image_downloader, "download_all"):
                        await converter.convert(progress_callback=progress_callback)

        # Verify progress callbacks were made
        assert len(progress_calls) > 0
        assert all(isinstance(call, int) for call in progress_calls)

    @pytest.mark.asyncio
    async def test_convert_fetch_failure(self, tmp_path):
        """Test conversion with fetch failure."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", status=404)
            mock.get("https://example.com/robots.txt", status=404)

            with pytest.raises(ConversionError):
                await converter.convert()

    @pytest.mark.asyncio
    async def test_convert_processing_failure(self, tmp_path, sample_html):
        """Test conversion with processing failure."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", body=sample_html, status=200)
            mock.get("https://example.com/robots.txt", status=404)

            with patch.object(
                converter.html_processor,
                "process",
                side_effect=ProcessingError("Processing failed"),
            ):
                with pytest.raises(ConversionError):
                    await converter.convert()

    @pytest.mark.asyncio
    async def test_convert_unexpected_error(self, tmp_path, sample_html):
        """Test conversion with unexpected error."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", body=sample_html, status=200)
            mock.get("https://example.com/robots.txt", status=404)

            # Mock _setup_directories to throw an unexpected error
            with patch.object(
                converter, "_setup_directories", side_effect=ValueError("Unexpected error")
            ):
                with pytest.raises(ConversionError, match="Conversion failed"):
                    await converter.convert()


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and comprehensive error handling."""

    @pytest.mark.asyncio
    async def test_convert_with_empty_html(self, tmp_path):
        """Test conversion with empty HTML response."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            mock.get("https://example.com", body="", status=200)
            mock.get("https://example.com/robots.txt", status=404)

            with patch.object(converter.metadata_extractor, "extract", return_value={}):
                with patch.object(converter.html_processor, "process", return_value=""):
                    with patch.object(converter.image_downloader, "download_all"):
                        # Should complete without error
                        await converter.convert()

    @pytest.mark.asyncio
    async def test_convert_with_malformed_html(self, tmp_path):
        """Test conversion with malformed HTML."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        malformed_html = "<html><body><div><p>Unclosed tags"

        with aioresponses() as mock:
            mock.get("https://example.com", body=malformed_html, status=200)
            mock.get("https://example.com/robots.txt", status=404)

            with patch.object(converter.metadata_extractor, "extract", return_value={}):
                with patch.object(converter.html_processor, "process", return_value=malformed_html):
                    with patch.object(converter.image_downloader, "download_all"):
                        # Should handle malformed HTML without crashing
                        await converter.convert()

    def test_url_normalization_edge_cases(self, tmp_path):
        """Test URL normalization with various edge cases."""
        # Test trailing slash
        converter1 = AsyncWordPressConverter(base_url="https://example.com/", output_dir=tmp_path)
        assert converter1.base_url == "https://example.com/"

        # Test subdirectory
        converter2 = AsyncWordPressConverter(
            base_url="https://example.com/blog/", output_dir=tmp_path
        )
        assert converter2.base_url == "https://example.com/blog/"

        # Test with query parameters
        converter3 = AsyncWordPressConverter(
            base_url="https://example.com/?page=1", output_dir=tmp_path
        )
        assert converter3.base_url == "https://example.com/?page=1"

    @pytest.mark.asyncio
    async def test_concurrent_conversion_safety(self, tmp_path, sample_html):
        """Test that converter handles concurrent operations safely."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        with aioresponses() as mock:
            # Add multiple mock responses
            for _ in range(3):
                mock.get("https://example.com", body=sample_html, status=200)
                mock.get("https://example.com/robots.txt", status=404)

            # Mock all dependencies
            with patch.object(converter.metadata_extractor, "extract", return_value={}):
                with patch.object(converter.html_processor, "process", return_value=sample_html):
                    with patch.object(converter.image_downloader, "download_all"):
                        # Run multiple conversions concurrently
                        tasks = [converter.convert() for _ in range(3)]
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        # All should complete without exceptions
                        for result in results:
                            assert not isinstance(result, Exception)

    def test_memory_efficiency_with_large_content(self, tmp_path):
        """Test memory efficiency with large content."""
        converter = AsyncWordPressConverter(base_url="https://example.com", output_dir=tmp_path)

        # Create large HTML content
        large_content = "<div>" + "x" * 100000 + "</div>"

        # Should extract image URLs without memory issues
        image_urls = converter._extract_image_urls(large_content)
        assert isinstance(image_urls, list)
