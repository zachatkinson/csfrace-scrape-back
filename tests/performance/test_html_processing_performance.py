"""Performance tests for HTML processing components."""

import time

import pytest
from bs4 import BeautifulSoup

from src.processors.html_processor import HTMLProcessor
from src.processors.metadata_extractor import MetadataExtractor
from tests.utils.test_helpers import PerformanceTestHelper


@pytest.mark.performance
class TestHTMLProcessingPerformance:
    """Test HTML processing performance under various conditions."""

    @pytest.fixture
    def html_processor(self):
        """Create HTML processor instance."""
        return HTMLProcessor()

    @pytest.fixture
    def metadata_extractor(self):
        """Create metadata extractor instance."""
        return MetadataExtractor()

    @pytest.fixture
    def large_html_content(self):
        """Generate large HTML content for performance testing."""
        return PerformanceTestHelper.create_large_html_content(element_count=1000)

    @pytest.fixture
    def complex_html_content(self):
        """Generate complex HTML with various WordPress blocks."""
        from tests.utils.test_helpers import TestDataGenerator

        return f"""
        <html>
            <body>
                {TestDataGenerator.create_complex_content()}
                {TestDataGenerator.create_wordpress_blocks()}
                {TestDataGenerator.create_kadence_layout()}
                {TestDataGenerator.create_image_gallery()}
                {TestDataGenerator.create_embed_content()}
            </body>
        </html>
        """

    def test_html_processor_performance_large_content(
        self, html_processor, large_html_content, benchmark
    ):
        """Test HTML processor performance with large content."""
        soup = BeautifulSoup(large_html_content, "html.parser")

        # Use pytest-benchmark to measure performance
        def process_large_content():
            # Since benchmark doesn't handle async, we use asyncio.run
            import asyncio
            return asyncio.run(html_processor.process(soup))

        result = benchmark(process_large_content)
        
        # Verify result
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_html_processor_performance_complex_content(
        self, html_processor, complex_html_content
    ):
        """Test HTML processor performance with complex WordPress content."""
        soup = BeautifulSoup(complex_html_content, "html.parser")

        start_time = time.time()
        result = await html_processor.process(soup)
        processing_time = time.time() - start_time

        # Should handle complex content quickly
        assert processing_time < 2.0, (
            f"Complex processing took {processing_time:.2f}s, expected < 2s"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_metadata_extraction_performance(self, metadata_extractor, large_html_content):
        """Test metadata extraction performance."""
        soup = BeautifulSoup(large_html_content, "html.parser")
        url = "https://example.com/test"

        start_time = time.time()
        metadata = await metadata_extractor.extract(soup, url)
        extraction_time = time.time() - start_time

        # Metadata extraction should be very fast
        assert extraction_time < 1.0, (
            f"Metadata extraction took {extraction_time:.2f}s, expected < 1s"
        )
        assert isinstance(metadata, dict)

    @pytest.mark.asyncio
    async def test_concurrent_processing_performance(self, html_processor):
        """Test performance under concurrent processing load."""
        import asyncio

        # Create multiple HTML documents to process concurrently
        html_documents = []
        for i in range(10):
            content = (
                f"<html><body><h1>Document {i}</h1><p>Content for document {i}</p></body></html>"
            )
            html_documents.append(BeautifulSoup(content, "html.parser"))

        async def process_document(soup):
            return await html_processor.process(soup)

        start_time = time.time()
        tasks = [process_document(soup) for soup in html_documents]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # 10 small documents should process very quickly even concurrently
        assert total_time < 3.0, f"Concurrent processing took {total_time:.2f}s, expected < 3s"
        assert len(results) == 10
        assert all(isinstance(result, str) for result in results)

    @pytest.mark.asyncio
    async def test_memory_efficiency_large_content(self, html_processor, large_html_content):
        """Test memory efficiency with large content."""
        try:
            import os

            import psutil
        except ImportError:
            pytest.skip("psutil not available for memory testing")

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        soup = BeautifulSoup(large_html_content, "html.parser")
        result = await html_processor.process(soup)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024, (
            f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB"
        )
        assert isinstance(result, str)

    def test_soup_parsing_performance(self, benchmark, large_html_content):
        """Test BeautifulSoup parsing performance."""
        
        def parse_html():
            return BeautifulSoup(large_html_content, "html.parser")

        soup = benchmark(parse_html)
        assert soup is not None

    @pytest.mark.asyncio
    async def test_processing_scalability(self, html_processor):
        """Test processing scalability with increasing content sizes."""
        element_counts = [100, 500, 1000, 2000]
        processing_times = []

        for count in element_counts:
            large_content = PerformanceTestHelper.create_large_html_content(element_count=count)
            soup = BeautifulSoup(large_content, "html.parser")

            start_time = time.time()
            await html_processor.process(soup)
            processing_time = time.time() - start_time
            processing_times.append(processing_time)

        # Processing should scale reasonably (not exponentially)
        # Each doubling of content should take less than 3x the time
        for i in range(1, len(processing_times)):
            ratio = processing_times[i] / processing_times[i - 1]
            size_ratio = element_counts[i] / element_counts[i - 1]

            # Time ratio should be less than 3x the size ratio
            assert ratio < (size_ratio * 3), (
                f"Processing time increased by {ratio:.2f}x for {size_ratio}x more content"
            )
