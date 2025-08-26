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
        return MetadataExtractor("https://example.com")

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

    @pytest.mark.benchmark(group="html_processing")
    def test_html_processor_performance_complex_content(
        self, html_processor, complex_html_content, benchmark
    ):
        """Test HTML processor performance with complex WordPress content."""
        soup = BeautifulSoup(complex_html_content, "html.parser")

        def benchmark_complex_processing():
            import asyncio

            return asyncio.run(html_processor.process(soup))

        result = benchmark(benchmark_complex_processing)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.benchmark(group="html_processing")
    def test_metadata_extraction_performance(
        self, metadata_extractor, large_html_content, benchmark
    ):
        """Test metadata extraction performance."""
        soup = BeautifulSoup(large_html_content, "html.parser")

        def benchmark_metadata_extraction():
            import asyncio

            return asyncio.run(metadata_extractor.extract(soup))

        metadata = benchmark(benchmark_metadata_extraction)
        assert isinstance(metadata, dict)

    @pytest.mark.benchmark(group="html_processing")
    def test_concurrent_processing_performance(self, html_processor, benchmark):
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

        async def concurrent_processing():
            tasks = [process_document(soup) for soup in html_documents]
            return await asyncio.gather(*tasks)

        def benchmark_concurrent_processing():
            return asyncio.run(concurrent_processing())

        results = benchmark(benchmark_concurrent_processing)
        assert len(results) == 10
        assert all(isinstance(result, str) for result in results)

    @pytest.mark.benchmark(group="html_processing")
    def test_memory_efficiency_large_content(self, html_processor, large_html_content, benchmark):
        """Test memory efficiency with large content."""
        try:
            import os

            import psutil
        except ImportError:
            pytest.skip("psutil not available for memory testing")

        soup = BeautifulSoup(large_html_content, "html.parser")

        def benchmark_memory_processing():
            import asyncio

            return asyncio.run(html_processor.process(soup))

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        result = benchmark(benchmark_memory_processing)

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

    @pytest.mark.benchmark(group="html_processing")
    def test_processing_scalability(self, html_processor, benchmark):
        """Test processing scalability with increasing content sizes."""
        element_counts = [100, 500, 1000]

        def benchmark_scalability():
            import asyncio

            processing_times = []

            for count in element_counts:
                large_content = PerformanceTestHelper.create_large_html_content(element_count=count)
                soup = BeautifulSoup(large_content, "html.parser")

                start_time = time.time()
                asyncio.run(html_processor.process(soup))
                processing_time = time.time() - start_time
                processing_times.append(processing_time)

            # Processing should scale reasonably (not exponentially)
            # Each increase in content should take less than 3x the time
            for i in range(1, len(processing_times)):
                ratio = processing_times[i] / processing_times[i - 1]
                size_ratio = element_counts[i] / element_counts[i - 1]

                # Time ratio should be less than 3x the size ratio
                if ratio >= (size_ratio * 3):
                    raise AssertionError(
                        f"Processing time increased by {ratio:.2f}x for {size_ratio}x more content"
                    )
            return processing_times

        result = benchmark(benchmark_scalability)
        assert len(result) == len(element_counts)
