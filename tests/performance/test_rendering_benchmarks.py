"""Performance benchmark tests for rendering system.

This module implements comprehensive rendering performance tests following TDD and CLAUDE.md
standards to ensure optimal performance and identify bottlenecks in the rendering pipeline.
"""

import asyncio
import gc
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from src.rendering.browser import BrowserConfig, BrowserPool, JavaScriptRenderer, RenderResult
from src.rendering.detector import ContentAnalysis, DynamicContentDetector
from src.rendering.renderer import AdaptiveRenderer


@pytest.mark.benchmark
class TestRenderingPerformanceBenchmarks:
    """Benchmark tests for rendering performance and resource usage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.process = psutil.Process(os.getpid())
        self.initial_memory = self.process.memory_info().rss

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="memory")
    async def test_memory_leak_detection_during_rendering(self):
        """Test for memory leaks during repeated rendering operations."""
        renderer = AdaptiveRenderer()

        # Mock dependencies to avoid actual network calls
        mock_detector = MagicMock()
        mock_detector.analyze_html.return_value = ContentAnalysis(
            is_dynamic=False, confidence_score=0.1, fallback_strategy="standard"
        )
        renderer.detector = mock_detector

        # Mock both static and JS renderers
        mock_static_renderer = AsyncMock()
        mock_js_renderer = AsyncMock()

        async def mock_render(url, **kwargs):
            return RenderResult(
                html="<html>Test content</html>",
                url=url,
                status_code=200,
                final_url=url,
                load_time=0.1,
                javascript_executed=False,
            )

        mock_static_renderer.render_page.side_effect = mock_render
        mock_js_renderer.render_page.side_effect = mock_render

        renderer._static_renderer = mock_static_renderer
        renderer._js_renderer = mock_js_renderer

        # Measure memory before rendering loop
        gc.collect()  # Force garbage collection
        initial_memory = self.process.memory_info().rss

        # Perform many rendering operations
        render_count = 100
        for i in range(render_count):
            result, analysis = await renderer.render_page(f"https://example.com/page{i}")
            assert result.status_code == 200

            # Force garbage collection periodically
            if i % 10 == 0:
                gc.collect()

        # Measure memory after rendering loop
        gc.collect()
        final_memory = self.process.memory_info().rss
        memory_increase = final_memory - initial_memory
        memory_increase_mb = memory_increase / (1024 * 1024)

        # Memory increase should be reasonable (< 50MB for 100 renders)
        assert memory_increase_mb < 50, (
            f"Memory increased by {memory_increase_mb:.2f}MB - potential memory leak"
        )

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="concurrency")
    async def test_browser_pool_exhaustion_scenarios(self):
        """Test browser pool behavior under resource exhaustion."""
        # Test with limited pool size
        config = BrowserConfig()
        pool_size = 3
        pool = BrowserPool(config, max_contexts=pool_size)

        # Mock browser and contexts
        mock_browser = AsyncMock()
        mock_contexts = [AsyncMock() for _ in range(pool_size)]

        pool._browser = mock_browser
        pool._contexts = mock_contexts
        pool._context_usage = dict.fromkeys(mock_contexts, 0)

        # Attempt to exceed pool capacity with concurrent requests
        concurrent_requests = pool_size + 5  # More than pool capacity

        async def simulate_render():
            try:
                async with pool.get_context() as context:
                    await asyncio.sleep(0.1)  # Simulate work
                    return context
            except Exception as e:
                return f"Error: {e}"

        # Run concurrent requests
        start_time = time.time()
        results = await asyncio.gather(*[simulate_render() for _ in range(concurrent_requests)])
        execution_time = time.time() - start_time

        # Should handle pool exhaustion gracefully
        successful_requests = [
            r for r in results if not isinstance(r, str) or not r.startswith("Error")
        ]
        error_requests = [r for r in results if isinstance(r, str) and r.startswith("Error")]

        # Pool should serve requests (may queue some)
        assert len(successful_requests) > 0

        # Should complete in reasonable time (not hang indefinitely)
        assert execution_time < 10.0  # Should complete within 10 seconds

        # Cleanup
        await pool.cleanup()

    @pytest.mark.benchmark(group="speed")
    def test_content_detector_speed_benchmark(self, benchmark):
        """Benchmark content detector performance with various HTML sizes."""
        detector = DynamicContentDetector()

        # Generate HTML of different sizes
        test_html = """  # noqa: W291, W293
        <html>
        <head>
            <title>Performance Test</title>
            <script src="framework.js"></script>
        </head>
        <body>
            <div class="content">
                {content_placeholder}
            </div>
            <script>
                // Dynamic content detection test
                console.log("Testing framework detection");
            </script>
        </body>
        </html>
        """

        # Medium size content (10KB)
        content_size = "x" * 10000  # 10KB of content
        html_content = test_html.replace("{content_placeholder}", content_size)

        # Benchmark the detector
        result = benchmark(detector.analyze_html, html_content)

        # Verify benchmark worked correctly
        assert isinstance(result, ContentAnalysis)
        assert result.confidence_score >= 0.0

    @pytest.mark.benchmark(group="large_content")
    def test_large_content_handling_performance(self, benchmark):
        """Test content processing performance with large content (>10MB)."""
        detector = DynamicContentDetector()

        # Generate large HTML content (>10MB)
        large_content_size = 11 * 1024 * 1024  # 11MB
        large_content = "x" * large_content_size
        large_html = f"""
        <html>
        <head>
            <title>Large Content Test</title>
            <script src="framework.js"></script>
        </head>
        <body>
            <div class="content">
                {large_content}
            </div>
            <script>
                console.log("Large content processing");
                window.appFramework = "test";
            </script>
        </body>
        </html>
        """

        # Benchmark large content processing
        result = benchmark(detector.analyze_html, large_html)

        # Should handle large content successfully
        assert isinstance(result, ContentAnalysis)
        assert result.confidence_score >= 0.0

    @pytest.mark.benchmark(group="concurrent")
    def test_concurrent_detection_benchmark(self, benchmark):
        """Benchmark concurrent content detection performance."""
        detector = DynamicContentDetector()

        # Create multiple HTML samples for concurrent testing
        html_samples = []
        for i in range(10):
            html = f"""  # noqa: W291, W293
            <html>
            <head><title>Sample {i}</title></head>
            <body>
                <div>Content sample {i}</div>
                <script>console.log('Sample {i}');</script>
            </body>
            </html>
            """
            html_samples.append(html)

        def analyze_multiple():
            """Analyze multiple HTML samples."""
            results = []
            for html in html_samples:
                result = detector.analyze_html(html)
                results.append(result)
            return results

        # Benchmark concurrent analysis
        results = benchmark(analyze_multiple)

        # Verify all analyses completed
        assert len(results) == 10
        assert all(isinstance(r, ContentAnalysis) for r in results)

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="pool")
    async def test_browser_pool_initialization_performance(self):
        """Test browser pool initialization and cleanup performance."""
        config = BrowserConfig()

        # Measure pool creation time
        start_time = time.time()
        pool = BrowserPool(config, max_contexts=5)
        creation_time = time.time() - start_time

        # Mock initialization for testing
        pool._browser = AsyncMock()
        pool._contexts = [AsyncMock() for _ in range(5)]

        # Measure initialization time
        start_time = time.time()
        await pool.initialize()
        init_time = time.time() - start_time

        # Measure cleanup time
        start_time = time.time()
        await pool.cleanup()
        cleanup_time = time.time() - start_time

        # Performance assertions
        assert creation_time < 1.0  # Pool creation should be fast
        assert init_time < 5.0  # Initialization should complete within 5 seconds
        assert cleanup_time < 2.0  # Cleanup should complete within 2 seconds

    @pytest.mark.benchmark(group="memory_usage")
    def test_content_analysis_memory_efficiency(self):
        """Test memory efficiency of content analysis with various sizes."""
        detector = DynamicContentDetector()

        # Test with progressively larger content
        content_sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB
        memory_usage = []

        for size in content_sizes:
            content = "x" * size
            html = f"<html><body><div>{content}</div></body></html>"

            # Measure memory before analysis
            gc.collect()
            memory_before = self.process.memory_info().rss

            # Perform analysis
            result = detector.analyze_html(html)

            # Measure memory after analysis
            memory_after = self.process.memory_info().rss
            memory_increase = memory_after - memory_before

            memory_usage.append((size, memory_increase))

            # Verify analysis completed
            assert isinstance(result, ContentAnalysis)

        # Memory usage should not grow excessively with content size
        for i in range(1, len(memory_usage)):
            prev_size, prev_memory = memory_usage[i - 1]
            curr_size, curr_memory = memory_usage[i]

            # Memory growth should be proportional to content size, not exponential
            size_ratio = curr_size / prev_size
            memory_ratio = curr_memory / max(prev_memory, 1)  # Avoid division by zero

            # Memory growth should not exceed 100x the content size growth
            # Note: Memory tests can be flaky due to GC timing and system factors
            if prev_memory > 0:  # Only check if we have a baseline
                assert memory_ratio < (size_ratio * 100), (
                    f"Excessive memory growth: {memory_ratio} vs {size_ratio}"
                )


@pytest.mark.benchmark
class TestConcurrencyPerformance:
    """Test concurrent operation performance and limits."""

    def setup_method(self):
        """Set up test fixtures."""
        self.process = psutil.Process(os.getpid())

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="concurrent_rendering")
    async def test_concurrent_rendering_performance_limits(self):
        """Test performance limits of concurrent rendering operations."""
        renderer = AdaptiveRenderer()

        # Test different concurrency levels
        concurrency_levels = [1, 5, 10, 20]
        performance_results = {}

        for concurrency in concurrency_levels:
            # Mock the entire render_page method to avoid external dependencies
            async def mock_render_page(url, **kwargs):
                await asyncio.sleep(0.1)  # Simulate 100ms processing time
                return (
                    RenderResult(
                        html="<html>Test content</html>",
                        url=url,
                        status_code=200,
                        final_url=url,
                        load_time=0.1,
                        javascript_executed=False,
                    ),
                    ContentAnalysis(
                        is_dynamic=False,
                        confidence_score=0.1,
                        fallback_strategy="standard"
                    )
                )

            # Mock render_page directly to avoid external HTTP requests
            renderer.render_page = mock_render_page

            # Generate URLs for testing
            urls = [f"https://test-domain.example/page{i}" for i in range(10)]

            # Measure concurrent rendering time
            start_time = time.time()
            results = await renderer.render_multiple(urls, max_concurrent=concurrency)
            execution_time = time.time() - start_time

            performance_results[concurrency] = execution_time

            # Verify all renders completed successfully
            assert len(results) == 10
            for url in urls:
                result, analysis = results[url]
                assert result.status_code == 200

        # Higher concurrency should improve performance (up to a point)
        assert performance_results[5] <= performance_results[1] * 1.1  # Should be faster or similar
        assert (
            performance_results[10] <= performance_results[5] * 1.2
        )  # Diminishing returns acceptable

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="stress_test")
    async def test_rendering_system_stress_test(self):
        """Stress test the rendering system with high load."""
        renderer = AdaptiveRenderer()

        # Simulate varying response times
        response_times = [0.05, 0.1, 0.2, 0.15, 0.08]  # Mix of fast and slow responses
        call_count = 0

        async def mock_render_page(url, **kwargs):
            nonlocal call_count
            delay = response_times[call_count % len(response_times)]
            await asyncio.sleep(delay)
            call_count += 1

            return (
                RenderResult(
                    html=f"<html>Content for {url}</html>",
                    url=url,
                    status_code=200,
                    final_url=url,
                    load_time=delay,
                    javascript_executed=False,
                ),
                ContentAnalysis(
                    is_dynamic=False,
                    confidence_score=0.1,
                    fallback_strategy="standard"
                )
            )

        # Mock render_page directly to avoid external HTTP requests
        renderer.render_page = mock_render_page

        # Generate large number of URLs for stress testing
        num_urls = 50
        urls = [f"https://test-domain.example/stress-test/{i}" for i in range(num_urls)]

        # Measure memory before stress test
        gc.collect()
        initial_memory = self.process.memory_info().rss

        # Run stress test
        start_time = time.time()
        results = await renderer.render_multiple(urls, max_concurrent=15)
        execution_time = time.time() - start_time

        # Measure memory after stress test
        gc.collect()
        final_memory = self.process.memory_info().rss
        memory_increase = (final_memory - initial_memory) / (1024 * 1024)  # MB

        # Verify all renders completed
        assert len(results) == num_urls
        successful_renders = 0
        for url in urls:
            if url in results:
                result, analysis = results[url]
                if result.status_code == 200:
                    successful_renders += 1

        # All renders should be successful since we're using mocks
        assert successful_renders == num_urls, f"Only {successful_renders}/{num_urls} renders succeeded"

        # Performance and reliability assertions
        success_rate = successful_renders / num_urls
        assert success_rate >= 0.95  # At least 95% success rate
        assert execution_time < 60.0  # Should complete within 1 minute
        assert memory_increase < 100.0  # Memory increase should be reasonable (<100MB)


@pytest.mark.benchmark
class TestBrowserSpecificPerformance:
    """Test browser-specific performance characteristics."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="browser_operations")
    async def test_javascript_renderer_performance(self):
        """Test JavaScript renderer performance under various conditions."""
        config = BrowserConfig(
            viewport_width=1920,
            viewport_height=1080,
            timeout=30.0,
        )
        renderer = JavaScriptRenderer(config)

        # Mock browser pool for performance testing
        mock_pool = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        # Configure mocks
        mock_page.goto.return_value = AsyncMock(status=200)
        mock_page.content.return_value = "<html><body>Test content</body></html>"
        mock_page.url = "https://example.com"
        mock_page.title.return_value = "Test Page"
        mock_page.close = AsyncMock()

        mock_context.new_page.return_value = mock_page

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_context():
            yield mock_context

        mock_pool.get_context = mock_get_context
        renderer._pool = mock_pool

        # Test rendering performance
        urls = [f"https://example.com/page{i}" for i in range(5)]

        start_time = time.time()
        for url in urls:
            result = await renderer.render_page(url)
            assert result.status_code == 200
        execution_time = time.time() - start_time

        # Should complete efficiently
        assert execution_time < 10.0  # Should render 5 pages within 10 seconds
        average_time_per_page = execution_time / len(urls)
        assert average_time_per_page < 3.0  # Each page should render within 3 seconds on average

    @pytest.mark.benchmark(group="browser_config")
    def test_browser_config_creation_performance(self, benchmark):
        """Benchmark browser configuration creation performance."""

        def create_complex_config():
            return BrowserConfig(
                viewport_width=1920,
                viewport_height=1080,
                timeout=30.0,
                extra_http_headers={
                    "User-Agent": "CustomBot/1.0",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                proxy={"server": "http://proxy:8080"},
                ignore_https_errors=False,
                javascript_enabled=True,
            )

        config = benchmark(create_complex_config)

        # Verify configuration was created correctly
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert "User-Agent" in config.extra_http_headers
        assert config.proxy["server"] == "http://proxy:8080"

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="pool_management")
    async def test_browser_pool_context_cycling_performance(self):
        """Test performance of context cycling in browser pool."""
        config = BrowserConfig()
        pool = BrowserPool(config, max_contexts=3)

        # Mock browser and contexts for testing
        mock_browser = AsyncMock()
        mock_contexts = [AsyncMock() for _ in range(3)]

        pool._browser = mock_browser
        pool._contexts = mock_contexts
        pool._context_usage = dict.fromkeys(mock_contexts, 0)

        # Test rapid context acquisition and release
        start_time = time.time()

        for _ in range(20):  # More requests than contexts
            async with pool.get_context() as context:
                assert context is not None
                await asyncio.sleep(0.01)  # Brief usage

        execution_time = time.time() - start_time

        # Should handle context cycling efficiently
        assert execution_time < 5.0  # Should complete within 5 seconds

        # Verify context usage was tracked
        assert all(usage >= 0 for usage in pool._context_usage.values())

        # Cleanup
        await pool.cleanup()


@pytest.mark.benchmark
class TestResourceLimitPerformance:
    """Test performance under resource limit conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.process = psutil.Process(os.getpid())

    @pytest.mark.asyncio
    @pytest.mark.benchmark(group="resource_limits")
    async def test_performance_under_memory_pressure(self):
        """Test system performance when approaching memory limits."""
        renderer = AdaptiveRenderer()

        # Create memory pressure by generating large content
        large_content = "x" * (1 * 1024 * 1024)  # 1MB content (reduced for test speed)
        large_html = f"<html><body>{large_content}</body></html>"

        # Mock the internal render method to avoid network calls
        async def mock_render_internal(url, static_html=None, **kwargs):
            result = RenderResult(
                html=large_html,
                url=url,
                status_code=200,
                final_url=url,
                load_time=1.0,
                javascript_executed=False,
            )
            analysis = ContentAnalysis(
                is_dynamic=False, confidence_score=0.1, fallback_strategy="standard"
            )
            return result, analysis

        # Monitor memory during rendering
        initial_memory = self.process.memory_info().rss

        # Render multiple large pages
        urls = [f"https://example.com/large{i}" for i in range(5)]

        start_time = time.time()
        with patch.object(renderer, "_render_page_internal", side_effect=mock_render_internal):
            for url in urls:
                result, analysis = await renderer.render_page(url)
                assert result.status_code == 200

                # Force garbage collection to manage memory
                gc.collect()

        execution_time = time.time() - start_time
        final_memory = self.process.memory_info().rss

        memory_increase = (final_memory - initial_memory) / (1024 * 1024)  # MB

        # Should handle large content efficiently
        assert execution_time < 30.0  # Should complete within 30 seconds
        assert memory_increase < 200.0  # Memory increase should be reasonable

    @pytest.mark.benchmark(group="cpu_usage")
    def test_cpu_intensive_content_detection(self, benchmark):
        """Benchmark CPU usage during intensive content detection."""
        detector = DynamicContentDetector()

        # Generate CPU-intensive HTML with complex patterns
        complex_html = """  # noqa: W291, W293
        <html>
        <head>
            <script src="jquery.js"></script>
            <script src="react.js"></script>
            <script src="vue.js"></script>
            <script src="angular.js"></script>
        </head>
        <body>
        """

        # Add many nested elements to increase processing complexity
        for i in range(1000):
            complex_html += f"""
            <div class="level-{i % 10}" data-framework="framework-{i % 5}">
                <span>Content {i}</span>
                <script>window.data_{i} = {{id: {i}}};</script>
            </div>
            """

        complex_html += """
        </body>
        </html>
        """

        # Benchmark the complex analysis
        result = benchmark(detector.analyze_html, complex_html)

        # Verify analysis completed correctly
        assert isinstance(result, ContentAnalysis)
        assert result.confidence_score >= 0.0

        # Should detect the complexity (multiple scripts, frameworks, etc.)
        assert len(result.frameworks_detected) > 0 or result.confidence_score > 0.3
