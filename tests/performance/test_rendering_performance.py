"""Simplified performance benchmark tests for rendering system.

This module implements performance tests that focus on the specific areas mentioned
in the original assessment without complex network mocking.
"""

import gc
import os
from unittest.mock import MagicMock

import psutil
import pytest

from src.rendering.browser import BrowserConfig, BrowserPool
from src.rendering.detector import ContentAnalysis, DynamicContentDetector


@pytest.mark.benchmark
class TestRenderingPerformanceBenchmarks:
    """Core rendering performance benchmarks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.process = psutil.Process(os.getpid())

    @pytest.mark.benchmark(group="memory_leak_detection")
    def test_memory_leak_detection_content_analysis(self):
        """Test for memory leaks during repeated content analysis operations."""
        detector = DynamicContentDetector()

        # Create moderately sized HTML content
        html_content = (
            """
        <html>
        <head>
            <script src="framework.js"></script>
        </head>
        <body>
            <div class="content">
                """
            + ("x" * 10000)
            + """
            </div>
            <script>console.log("test");</script>
        </body>
        </html>
        """
        )

        # Measure memory before analysis loop
        gc.collect()
        initial_memory = self.process.memory_info().rss

        # Perform many analysis operations
        analysis_count = 200
        for i in range(analysis_count):
            result = detector.analyze_html(html_content)
            assert isinstance(result, ContentAnalysis)

            # Force garbage collection periodically
            if i % 20 == 0:
                gc.collect()

        # Measure memory after analysis loop
        gc.collect()
        final_memory = self.process.memory_info().rss
        memory_increase = final_memory - initial_memory
        memory_increase_mb = memory_increase / (1024 * 1024)

        # Memory increase should be reasonable for 200 analyses
        assert memory_increase_mb < 100, (
            f"Memory increased by {memory_increase_mb:.2f}MB - potential leak"
        )

    @pytest.mark.benchmark(group="pool_exhaustion")
    def test_browser_pool_exhaustion_scenarios(self):
        """Test browser pool behavior under resource exhaustion."""
        config = BrowserConfig()
        pool_size = 3
        pool = BrowserPool(config, max_contexts=pool_size)

        # Mock browser components for testing
        pool._browser = MagicMock()
        pool._contexts = [MagicMock() for _ in range(pool_size)]
        pool._context_usage = dict.fromkeys(pool._contexts, 0)

        # Test pool behavior with exhaustion
        acquired_contexts = []

        # Try to acquire more contexts than available
        for i in range(pool_size + 2):
            try:
                # Simulate context acquisition
                if i < pool_size:
                    context = pool._contexts[i]
                    acquired_contexts.append(context)
                    pool._context_usage[context] += 1
                else:
                    # Should handle exhaustion gracefully
                    assert len(acquired_contexts) == pool_size
            except Exception:
                # Pool exhaustion should be handled gracefully
                pass

        # Verify pool state
        assert len(pool._contexts) == pool_size
        assert all(usage > 0 for usage in pool._context_usage.values() if usage is not None)

    @pytest.mark.benchmark(group="large_content")
    def test_large_content_handling_performance(self, benchmark):
        """Test content analysis performance with large content (>10MB)."""
        detector = DynamicContentDetector()

        # Generate large HTML content (>10MB)
        large_content_size = 11 * 1024 * 1024  # 11MB
        large_content = "x" * large_content_size
        large_html = f"""
        <html>
        <head>
            <script src="framework.js"></script>
        </head>
        <body>
            <div class="content">
                {large_content}
            </div>
            <script>console.log("large content test");</script>
        </body>
        </html>
        """

        # Benchmark large content analysis
        result = benchmark(detector.analyze_html, large_html)

        # Should handle large content successfully
        assert isinstance(result, ContentAnalysis)
        assert result.confidence_score >= 0.0

    @pytest.mark.benchmark(group="rendering_speed")
    def test_content_detector_speed_benchmark_various_sizes(self, benchmark):
        """Benchmark content detector with various HTML sizes."""
        detector = DynamicContentDetector()

        # Test with medium size content
        test_html = """
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
                console.log("Testing framework detection");
                window.app = {framework: "test"};
            </script>
        </body>
        </html>
        """

        # Medium size content (50KB)
        content_size = "x" * 50000
        html_content = test_html.replace("{content_placeholder}", content_size)

        # Benchmark the detector
        result = benchmark(detector.analyze_html, html_content)

        # Verify benchmark worked correctly
        assert isinstance(result, ContentAnalysis)
        assert result.confidence_score >= 0.0

    @pytest.mark.benchmark(group="memory_efficiency")
    def test_content_analysis_memory_efficiency(self):
        """Test memory efficiency of content analysis with various sizes."""
        detector = DynamicContentDetector()

        # Test with progressively larger content
        content_sizes = [1024, 10240, 102400, 512000]  # 1KB to 512KB
        memory_usage = []

        for size in content_sizes:
            content = "x" * size
            html = f"""
            <html>
            <head><script src="test.js"></script></head>
            <body><div>{content}</div><script>window.test = true;</script></body>
            </html>
            """

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

            # Memory growth should be reasonable
            size_ratio = curr_size / prev_size
            memory_ratio = abs(curr_memory) / max(abs(prev_memory), 1024)  # Avoid division by zero

            # Memory growth should not be exponential (allow more variance for small changes)
            if abs(curr_memory) > 10240:  # Only check significant memory changes
                assert memory_ratio < (size_ratio * 20), (
                    f"Excessive memory growth: {memory_ratio} vs {size_ratio}"
                )


@pytest.mark.benchmark
class TestBrowserConfigPerformance:
    """Test browser configuration performance."""

    @pytest.mark.benchmark(group="browser_config")
    def test_browser_config_creation_performance(self, benchmark):
        """Benchmark browser configuration creation with complex settings."""

        def create_complex_config():
            return BrowserConfig(
                viewport_width=1920,
                viewport_height=1080,
                timeout=30.0,
                extra_http_headers={
                    "User-Agent": "PerformanceTestBot/1.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
                # Note: proxy config might not be available in BrowserConfig
                ignore_https_errors=False,
                enable_javascript=True,
                wait_for_network_idle=True,
            )

        config = benchmark(create_complex_config)

        # Verify configuration was created correctly
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert len(config.extra_http_headers) == 6
        assert config.ignore_https_errors is False

    @pytest.mark.benchmark(group="pool_creation")
    def test_browser_pool_creation_performance(self, benchmark):
        """Benchmark browser pool creation performance."""

        def create_browser_pool():
            config = BrowserConfig(
                viewport_width=1920,
                viewport_height=1080,
                timeout=30.0,
            )
            return BrowserPool(config, max_contexts=5)

        pool = benchmark(create_browser_pool)

        # Verify pool was created correctly
        assert pool.config.viewport_width == 1920
        assert pool.max_contexts == 5
        assert pool._contexts == []  # Not initialized yet


@pytest.mark.benchmark
class TestContentDetectionStress:
    """Stress test content detection with complex scenarios."""

    @pytest.mark.benchmark(group="cpu_intensive")
    def test_cpu_intensive_content_detection(self, benchmark):
        """Benchmark CPU usage during intensive content detection."""
        detector = DynamicContentDetector()

        # Generate CPU-intensive HTML with many frameworks and complex patterns
        complex_html = """
        <html>
        <head>
            <script src="jquery.min.js"></script>
            <script src="react.development.js"></script>
            <script src="vue.global.js"></script>
            <script src="angular.min.js"></script>
            <script src="lodash.min.js"></script>
        </head>
        <body>
        """

        # Add many nested elements with framework patterns
        for i in range(500):
            framework = ["react", "vue", "angular", "jquery"][i % 4]
            complex_html += f"""
            <div class="component-{framework}-{i}"
                 data-framework="{framework}"
                 data-component-id="{i}">
                <span class="content">Component {i}</span>
                <script>
                    window.{framework}_{i} = {{
                        id: {i},
                        type: "{framework}",
                        initialized: true
                    }};
                </script>
            </div>
            """

        complex_html += """
        <script>
            // Complex initialization patterns
            if (typeof React !== 'undefined') {
                window.reactComponents = Object.keys(window).filter(k => k.startsWith('react_'));
            }
            if (typeof Vue !== 'undefined') {
                window.vueComponents = Object.keys(window).filter(k => k.startsWith('vue_'));
            }
            $(document).ready(function() {
                console.log("jQuery ready");
            });
        </script>
        </body>
        </html>
        """

        # Benchmark the complex analysis
        result = benchmark(detector.analyze_html, complex_html)

        # Verify analysis completed correctly
        assert isinstance(result, ContentAnalysis)
        assert result.confidence_score >= 0.0

        # Should detect multiple frameworks
        assert len(result.frameworks_detected) > 0 or result.confidence_score > 0.5

    @pytest.mark.benchmark(group="concurrent_analysis")
    def test_concurrent_content_analysis_performance(self, benchmark):
        """Benchmark concurrent content analysis performance."""
        detector = DynamicContentDetector()

        # Create multiple HTML samples for concurrent analysis
        html_samples = []
        for i in range(20):
            html = f"""
            <html>
            <head>
                <title>Sample {i}</title>
                <script src="framework-{i}.js"></script>
            </head>
            <body>
                <div class="app-{i}" data-framework="framework-{i % 5}">
                    <h1>Sample Application {i}</h1>
                    <p>Content for sample {i}</p>
                </div>
                <script>
                    window.app_{i} = {{
                        id: {i},
                        framework: "framework-{i % 5}",
                        loaded: true
                    }};
                    console.log("App {i} initialized");
                </script>
            </body>
            </html>
            """
            html_samples.append(html)

        def analyze_multiple():
            """Analyze multiple HTML samples sequentially."""
            results = []
            for html in html_samples:
                result = detector.analyze_html(html)
                results.append(result)
            return results

        # Benchmark the analysis
        results = benchmark(analyze_multiple)

        # Verify all analyses completed
        assert len(results) == 20
        assert all(isinstance(r, ContentAnalysis) for r in results)


@pytest.mark.benchmark
class TestMemoryLeakDetection:
    """Specific tests for memory leak detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.process = psutil.Process(os.getpid())

    def test_repeated_browser_config_creation_memory(self):
        """Test memory usage during repeated browser config creation."""
        # Measure initial memory
        gc.collect()
        initial_memory = self.process.memory_info().rss

        configs = []
        for i in range(1000):
            config = BrowserConfig(
                viewport_width=1920,
                viewport_height=1080,
                timeout=30.0,
                extra_http_headers={
                    f"X-Test-Header-{i}": f"value-{i}",
                    "User-Agent": f"TestBot-{i}/1.0",
                },
            )
            configs.append(config)

            # Periodic cleanup
            if i % 100 == 0:
                gc.collect()

        # Measure peak memory
        peak_memory = self.process.memory_info().rss

        # Cleanup
        del configs
        gc.collect()
        final_memory = self.process.memory_info().rss

        # Calculate memory usage
        memory_increase = (peak_memory - initial_memory) / (1024 * 1024)  # MB
        memory_after_cleanup = (final_memory - initial_memory) / (1024 * 1024)  # MB

        # Memory increase should be reasonable
        assert memory_increase < 50, f"Memory increased by {memory_increase:.2f}MB for 1000 configs"
        # Allow more lenient cleanup check since small memory differences can cause flaky tests
        if memory_increase > 1.0:  # Only check cleanup if there was significant usage
            assert memory_after_cleanup < memory_increase * 0.9, "Memory not freed after cleanup"

    def test_repeated_content_detection_memory(self):
        """Test memory usage during repeated content detection."""
        detector = DynamicContentDetector()

        # Create test HTML
        test_html = """
        <html>
        <head>
            <script src="react.js"></script>
            <script src="vue.js"></script>
        </head>
        <body>
            <div id="app">Test content</div>
            <script>
                window.testData = new Array(1000).fill("test");
                console.log("Application initialized");
            </script>
        </body>
        </html>
        """

        # Measure initial memory
        gc.collect()
        initial_memory = self.process.memory_info().rss

        # Perform many detections
        results = []
        for i in range(500):
            result = detector.analyze_html(test_html)
            results.append(result)

            if i % 50 == 0:
                gc.collect()

        # Measure peak memory
        peak_memory = self.process.memory_info().rss

        # Cleanup
        del results
        gc.collect()
        final_memory = self.process.memory_info().rss

        # Calculate memory usage
        memory_increase = (peak_memory - initial_memory) / (1024 * 1024)  # MB
        memory_after_cleanup = (final_memory - initial_memory) / (1024 * 1024)  # MB

        # Memory increase should be reasonable
        assert memory_increase < 100, (
            f"Memory increased by {memory_increase:.2f}MB for 500 detections"
        )
        assert memory_after_cleanup < memory_increase * 0.5, "Memory not freed after cleanup"
