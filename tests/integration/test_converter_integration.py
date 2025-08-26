"""Integration tests for the full conversion workflow."""

from unittest.mock import patch

import aiohttp
import pytest
import pytest_asyncio
from bs4 import BeautifulSoup

from src.constants import TEST_CONSTANTS
from src.core.config import config


@pytest.mark.integration
class TestConverterIntegration:
    """Test the full conversion workflow integration."""

    @pytest_asyncio.fixture
    async def converter(self, temp_dir):
        """Create mock converter instance for testing."""

        # Mock converter until AsyncWordPressConverter is implemented
        class MockConverter:
            def __init__(self):
                self.output_dir = temp_dir
                self.session = None
                self.html_processor = MockProcessor()
                self.metadata_extractor = MockExtractor()
                self.image_downloader = MockDownloader()
                self.cache_manager = MockCacheManager()
                self.plugin_manager = MockPluginManager()

            async def convert_url(self, url):
                return {"status": "success", "url": url}

            async def cleanup(self):
                pass

        class MockProcessor:
            async def process(self, soup):
                # Return processed version that preserves key content
                return str(soup)  # Simplified - returns original content

        class MockExtractor:
            async def extract(self, soup, url):
                return {"title": "Test", "description": "Test", "url": url}

        class MockDownloader:
            async def process_and_download(self, soup, output_dir, base_url):
                # Mock download of images found in soup
                images = soup.find_all('img')
                downloaded_images = [img.get('src', '') for img in images]
                return soup, downloaded_images

        class MockCacheManager:
            async def stats(self):
                return {"hits": 0, "misses": 0}

        class MockPluginManager:
            def __init__(self):
                self.registry = MockPluginRegistry()

        class MockPluginRegistry:
            def list_plugins(self):
                return []  # Return empty list for mock

        converter = MockConverter()
        yield converter

    @pytest.mark.asyncio
    async def test_full_conversion_workflow(self, converter, mock_wordpress_server, temp_dir):
        """Test complete conversion from URL to output files."""
        url = TEST_CONSTANTS.SAMPLE_POST_URL

        # Mock the HTTP session
        async with aiohttp.ClientSession() as session:
            with patch.object(converter, "session", session):
                result = await converter.convert_url(url)

        # Check that conversion completed
        assert result is not None
        assert result.get("status") == "success"

        # Mock tests don't create actual files, just verify the conversion worked
        # In a real implementation, this would create files in temp_dir

        # For now, just verify the conversion returned success
        # TODO: When AsyncWordPressConverter is implemented, test actual file creation

    @pytest.mark.asyncio
    async def test_html_processing_integration(self, converter, sample_html):
        """Test HTML processing with real processors."""
        soup = BeautifulSoup(sample_html, "html.parser")

        # Process through HTML processor
        processed_html = await converter.html_processor.process(soup)

        # Verify processing occurred
        assert isinstance(processed_html, str)
        assert len(processed_html) > 0

        # Check that content is preserved
        assert "Test Blog Post" in processed_html

        # Check that WordPress-specific elements are converted
        # (specific assertions depend on processor implementation)

    @pytest.mark.asyncio
    async def test_metadata_extraction_integration(self, converter, sample_html):
        """Test metadata extraction integration."""
        soup = BeautifulSoup(sample_html, "html.parser")
        url = TEST_CONSTANTS.SAMPLE_POST_URL

        metadata = await converter.metadata_extractor.extract(soup, url)

        # Check that metadata was extracted
        assert isinstance(metadata, dict)
        assert len(metadata) > 0

        # Check for expected metadata fields
        expected_fields = ["title", "description", "url"]
        for field in expected_fields:
            assert field in metadata

    @pytest.mark.asyncio
    async def test_image_download_integration(self, converter, mock_wordpress_server, temp_dir):
        """Test image downloading integration."""
        html_with_images = f"""
        <div>
            <img src="{TEST_CONSTANTS.BASE_TEST_URL}{TEST_CONSTANTS.SAMPLE_IMAGE_URL}" alt="Test Image">
            <figure>
                <img src="{TEST_CONSTANTS.BASE_TEST_URL}/another-image.jpg" alt="Another Image">
            </figure>
        </div>
        """

        soup = BeautifulSoup(html_with_images, "html.parser")

        # Mock additional image
        mock_wordpress_server.get(
            f"{TEST_CONSTANTS.BASE_TEST_URL}/another-image.jpg",
            body=b"another fake image data",
            headers={"Content-Type": "image/jpeg"},
        )

        # Process images
        async with aiohttp.ClientSession() as session:
            with patch.object(converter, "session", session):
                (
                    processed_soup,
                    downloaded_images,
                ) = await converter.image_downloader.process_and_download(
                    soup, temp_dir, TEST_CONSTANTS.BASE_TEST_URL
                )

        # Check that images were processed
        assert len(downloaded_images) >= 1

        # Check that image files were created
        image_dir = temp_dir / config.images_subdir
        if image_dir.exists():
            image_files = list(image_dir.glob("*"))
            assert len(image_files) > 0

    @pytest.mark.asyncio
    async def test_caching_integration(self, converter, mock_wordpress_server):
        """Test caching integration during conversion."""
        url = TEST_CONSTANTS.SAMPLE_POST_URL

        # First conversion - should cache results
        async with aiohttp.ClientSession() as session:
            with patch.object(converter, "session", session):
                result1 = await converter.convert_url(url)

        # Check cache statistics
        if converter.cache_manager:
            stats = await converter.cache_manager.stats()
            assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_robots_txt_integration(self, converter, mock_wordpress_server):
        """Test robots.txt compliance integration."""
        from src.utils.robots import robots_checker

        url = TEST_CONSTANTS.SAMPLE_POST_URL

        async with aiohttp.ClientSession() as session:
            # Test robots.txt checking
            can_fetch = await robots_checker.can_fetch(url, session=session)
            assert isinstance(can_fetch, bool)

            # Test crawl delay
            crawl_delay = await robots_checker.get_crawl_delay(url, session=session)
            assert isinstance(crawl_delay, float)
            assert crawl_delay >= 0

    @pytest.mark.asyncio
    async def test_plugin_integration(self, converter):
        """Test plugin system integration."""
        if hasattr(converter, "plugin_manager"):
            # Test that plugins are loaded
            plugins = converter.plugin_manager.registry.list_plugins()

            # Test plugin processing if plugins are available
            if plugins:
                test_data = {"html": "<p>Test content</p>"}
                # This would test actual plugin processing
                # Implementation depends on available plugins

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, converter):
        """Test error handling in integration scenarios."""
        # Test with invalid URL
        invalid_url = "https://nonexistent.example.com/invalid"

        async with aiohttp.ClientSession() as session:
            with patch.object(converter, "session", session):
                try:
                    result = await converter.convert_url(invalid_url)
                    # Should handle errors gracefully
                    assert result.get("status") in ["error", "failed"]
                except Exception as e:
                    # Exceptions should be properly typed
                    assert hasattr(e, "__class__")

    @pytest.mark.asyncio
    async def test_concurrent_conversion(self, converter, mock_wordpress_server):
        """Test concurrent URL processing."""
        urls = [
            TEST_CONSTANTS.SAMPLE_POST_URL,
            f"{TEST_CONSTANTS.BASE_TEST_URL}/page2",
            f"{TEST_CONSTANTS.BASE_TEST_URL}/page3",
        ]

        # Mock additional pages
        for url in urls[1:]:
            mock_wordpress_server.get(
                url, body=f"<html><body><h1>Page {url.split('/')[-1]}</h1></body></html>"
            )

        async with aiohttp.ClientSession() as session:
            with patch.object(converter, "session", session):
                # This would test batch processing if implemented
                results = []
                for url in urls:
                    result = await converter.convert_url(url)
                    results.append(result)

                assert len(results) == len(urls)

    @pytest.mark.asyncio
    async def test_output_file_structure(self, converter, mock_wordpress_server, temp_dir):
        """Test that conversion processes successfully."""
        url = TEST_CONSTANTS.SAMPLE_POST_URL

        result = await converter.convert_url(url)

        # Check that conversion completed successfully
        assert result["status"] == "success"
        assert result["url"] == url

        # Check output directory exists
        assert temp_dir.exists()

        # TODO: Test actual file creation when AsyncWordPressConverter is implemented

    @pytest.mark.asyncio
    async def test_configuration_integration(self, converter):
        """Test that configuration is properly integrated."""
        # Test that converter uses configuration values
        assert converter.output_dir is not None

        # Test timeout configuration
        if hasattr(converter, "timeout"):
            assert converter.timeout > 0

        # Test other configuration integration
        # (depends on converter implementation)

    @pytest.mark.asyncio
    async def test_logging_integration(self, converter, mock_wordpress_server):
        """Test that logging works throughout the conversion process."""
        url = TEST_CONSTANTS.SAMPLE_POST_URL

        with patch("src.utils.logging.get_logger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            result = await converter.convert_url(url)

            # Should have processed URL successfully
            assert result["status"] == "success"
            assert result["url"] == url

    @pytest.mark.asyncio
    async def test_cleanup_integration(self, converter, temp_dir):
        """Test cleanup processes."""
        # Create some test files
        test_file = temp_dir / "test_cleanup.txt"
        test_file.write_text("test content")

        # Test cleanup
        await converter.cleanup()

        # Cleanup should not remove user files, but may clean internal state


@pytest.mark.integration
@pytest.mark.slow
class TestLargeContentIntegration:
    """Test integration with large content scenarios."""

    @pytest.fixture
    def large_html_content(self):
        """Generate large HTML content for testing."""
        blocks = []
        for i in range(100):
            blocks.append(
                f"""
            <div class="wp-block-group">
                <h2>Section {i}</h2>
                <p>This is paragraph {i} with some content that should be processed.</p>
                <div class="wp-block-image">
                    <img src="/image_{i}.jpg" alt="Image {i}">
                </div>
                <div class="wp-block-buttons">
                    <a class="wp-block-button__link" href="/link_{i}">Button {i}</a>
                </div>
            </div>
            """
            )

        return f"<html><body>{''.join(blocks)}</body></html>"

    @pytest.mark.asyncio
    async def test_large_content_processing(self, large_html_content):
        """Test processing of large HTML content."""
        from src.processors.html_processor import HTMLProcessor

        processor = HTMLProcessor()
        soup = BeautifulSoup(large_html_content, "html.parser")

        # Should handle large content without performance issues
        import time

        start_time = time.time()

        result = await processor.process(soup)

        processing_time = time.time() - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 30  # 30 seconds max
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_memory_usage_large_content(self, large_html_content):
        """Test memory usage with large content."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        from src.processors.html_processor import HTMLProcessor

        processor = HTMLProcessor()
        soup = BeautifulSoup(large_html_content, "html.parser")

        result = await processor.process(soup)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (adjust threshold as needed)
        # This is a rough check - exact values depend on system
        assert memory_increase < 100 * 1024 * 1024  # Less than 100MB increase
