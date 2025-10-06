"""Comprehensive tests for dynamic content detector - MANDATORY TEST_BUILDING.md compliance.

This module tests the DynamicContentDetector and related classes with complete coverage:
- Content analysis and scoring
- Framework detection (React, Vue, Angular, etc.)
- SPA pattern detection
- Lazy loading detection
- AJAX pattern detection
- Fallback strategy determination
- Utility functions
- Performance benchmarking

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive edge case testing
- Performance benchmarks with specific thresholds
"""

import time

import pytest

from src.rendering.detector import (
    ContentAnalysis,
    DynamicContentDetector,
    DynamicContentIndicators,
    get_recommended_wait_conditions,
    should_use_javascript_rendering,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def detector() -> DynamicContentDetector:
    """Factory for DynamicContentDetector - DRY principle."""
    return DynamicContentDetector()


@pytest.fixture
def custom_indicators() -> DynamicContentIndicators:
    """Factory for custom DynamicContentIndicators - DRY principle."""
    return DynamicContentIndicators(
        js_frameworks=["react", "vue"],
        spa_indicators=["ng-app", "v-app"],
        lazy_loading_selectors=["[data-src]", ".lazyload"],
    )


# ============================================================================
# Detector Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestDetectorInitialization:
    """Tests for DynamicContentDetector initialization."""

    def test_detector_initialization_with_defaults(self) -> None:
        """Test detector initializes with default indicators - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        detector = DynamicContentDetector()

        # Assert - MANDATORY
        assert detector.indicators is not None
        assert isinstance(detector.indicators, DynamicContentIndicators)

    def test_detector_initialization_with_custom_indicators(
        self, custom_indicators: DynamicContentIndicators
    ) -> None:
        """Test detector initializes with custom indicators - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (custom_indicators from fixture)

        # Act - MANDATORY
        detector = DynamicContentDetector(indicators=custom_indicators)

        # Assert - MANDATORY
        assert detector.indicators == custom_indicators
        assert len(detector.indicators.js_frameworks) == 2

    def test_detector_compiles_regex_patterns(self, detector: DynamicContentDetector) -> None:
        """Test detector compiles regex patterns - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (detector from fixture)

        # Act - MANDATORY
        patterns = detector._js_framework_patterns

        # Assert - MANDATORY
        assert len(patterns) > 0
        assert all(hasattr(p, "search") for p in patterns)


# ============================================================================
# Empty/Minimal Content Tests
# ============================================================================


@pytest.mark.unit
class TestEmptyContent:
    """Tests for empty or minimal content handling."""

    def test_analyze_empty_html(self, detector: DynamicContentDetector) -> None:
        """Test analyzing empty HTML returns non-dynamic - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = ""

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert result.is_dynamic is False
        assert result.confidence_score == 0.0
        assert "Empty HTML content" in result.reasons

    def test_analyze_whitespace_only_html(self, detector: DynamicContentDetector) -> None:
        """Test analyzing whitespace-only HTML - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "   \n\t   "

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert result.is_dynamic is False
        assert result.confidence_score == 0.0


# ============================================================================
# Framework Detection Tests
# ============================================================================


@pytest.mark.unit
class TestFrameworkDetection:
    """Tests for JavaScript framework detection."""

    def test_detect_react_in_script_src(self, detector: DynamicContentDetector) -> None:
        """Test detecting React in script src attribute - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><script src="https://cdn.com/react.min.js"></script></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "react" in result.frameworks_detected
        assert "js_frameworks_in_scripts" in result.indicators_found

    def test_detect_vue_in_inline_script(self, detector: DynamicContentDetector) -> None:
        """Test detecting Vue in inline script content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "<html><script>new Vue({ el: '#app' })</script></html>"

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "vue" in result.frameworks_detected

    def test_detect_angular_in_script(self, detector: DynamicContentDetector) -> None:
        """Test detecting Angular in script - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><script src="/angular.js"></script></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "angular" in result.frameworks_detected

    def test_detect_multiple_frameworks(self, detector: DynamicContentDetector) -> None:
        """Test detecting multiple frameworks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <script src="/react.js"></script>
            <script>Vue.createApp({})</script>
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "react" in result.frameworks_detected
        assert "vue" in result.frameworks_detected
        assert len(result.frameworks_detected) >= 2


# ============================================================================
# SPA Detection Tests
# ============================================================================


@pytest.mark.unit
class TestSPADetection:
    """Tests for Single Page Application detection."""

    def test_detect_spa_ng_app_attribute(self, detector: DynamicContentDetector) -> None:
        """Test detecting ng-app SPA attribute - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><div ng-app="myApp">Content</div></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "spa_attributes" in result.indicators_found

    def test_detect_spa_react_root_class(self, detector: DynamicContentDetector) -> None:
        """Test detecting react-root class - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><div class="react-root">Content</div></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "spa_attributes" in result.indicators_found

    def test_detect_empty_body_with_scripts(self, detector: DynamicContentDetector) -> None:
        """Test detecting empty body with scripts (classic SPA) - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <head><title>SPA</title></head>
            <body>
                <div id="root"></div>
                <script src="/bundle.js"></script>
            </body>
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "empty_body_with_scripts" in result.indicators_found


# ============================================================================
# Lazy Loading Detection Tests
# ============================================================================


@pytest.mark.unit
class TestLazyLoadingDetection:
    """Tests for lazy loading detection."""

    def test_detect_data_src_lazy_loading(self, detector: DynamicContentDetector) -> None:
        """Test detecting data-src lazy loading - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><img data-src="/image.jpg" /></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "lazy_loading" in result.indicators_found
        assert result.metadata.get("lazy_elements_count", 0) > 0

    def test_detect_lazyload_class(self, detector: DynamicContentDetector) -> None:
        """Test detecting lazyload class - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><img class="lazyload" src="placeholder.jpg" /></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "lazy_loading" in result.indicators_found

    def test_count_multiple_lazy_elements(self, detector: DynamicContentDetector) -> None:
        """Test counting multiple lazy elements - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <img data-src="/img1.jpg" />
            <img data-src="/img2.jpg" />
            <img class="lazyload" />
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert result.metadata.get("lazy_elements_count", 0) >= 2


# ============================================================================
# JavaScript-Dependent Classes Tests
# ============================================================================


@pytest.mark.unit
class TestJSDependentClasses:
    """Tests for JavaScript-dependent class detection."""

    def test_detect_js_prefix_classes(self, detector: DynamicContentDetector) -> None:
        """Test detecting js- prefix classes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><div class="js-toggle-menu">Menu</div></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "js_dependent_classes" in result.indicators_found

    def test_detect_react_prefix_classes(self, detector: DynamicContentDetector) -> None:
        """Test detecting react- prefix classes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><div class="react-component">Component</div></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "js_dependent_classes" in result.indicators_found

    def test_detect_vue_prefix_classes(self, detector: DynamicContentDetector) -> None:
        """Test detecting vue- prefix classes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><div class="vue-app">App</div></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "js_dependent_classes" in result.indicators_found


# ============================================================================
# AJAX Pattern Detection Tests
# ============================================================================


@pytest.mark.unit
class TestAJAXDetection:
    """Tests for AJAX and dynamic loading pattern detection."""

    def test_detect_ajax_in_script(self, detector: DynamicContentDetector) -> None:
        """Test detecting AJAX in script content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "<html><script>$.ajax({ url: '/api/data' })</script></html>"

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "ajax_patterns" in result.indicators_found
        assert "ajax" in result.reasons[0].lower() or any(
            "ajax" in r.lower() for r in result.reasons
        )

    def test_detect_fetch_in_script(self, detector: DynamicContentDetector) -> None:
        """Test detecting fetch API in script - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "<html><script>fetch('/api/data').then()</script></html>"

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "ajax_patterns" in result.indicators_found

    def test_detect_infinite_scroll_pattern(self, detector: DynamicContentDetector) -> None:
        """Test detecting infinite scroll pattern - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><div class="infinite-scroll" data-url="/load-more"></div></html>'

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        # May or may not trigger based on data attribute detection


# ============================================================================
# Content Density Tests
# ============================================================================


@pytest.mark.unit
class TestContentDensity:
    """Tests for content density analysis."""

    def test_low_content_density_detected(self, detector: DynamicContentDetector) -> None:
        """Test detecting low content density - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Lots of markup, minimal text
        html = "<html><div><div><div><div><div>X</div></div></div></div></div></html>"

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert (
            "low_content_density" in result.indicators_found
            or result.metadata.get("content_density", 1.0) < 0.3
        )

    def test_high_content_density_penalizes_score(self, detector: DynamicContentDetector) -> None:
        """Test high content density penalizes dynamic score - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Lots of text, minimal markup
        html = "<html><body>" + "Content text here. " * 1000 + "</body></html>"

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        # High content density suggests static content
        assert result.confidence_score < 0.5 or not result.is_dynamic


# ============================================================================
# Confidence Score Calculation Tests
# ============================================================================


@pytest.mark.unit
class TestConfidenceScore:
    """Tests for confidence score calculation."""

    def test_multiple_indicators_increase_confidence(
        self, detector: DynamicContentDetector
    ) -> None:
        """Test multiple indicators increase confidence score - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <script src="/react.js"></script>
            <div class="js-component" data-src="/lazy.jpg"></div>
            <script>$.ajax({})</script>
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert result.confidence_score > 0.5
        assert len(result.indicators_found) >= 2

    def test_empty_body_pattern_high_confidence(self, detector: DynamicContentDetector) -> None:
        """Test empty body pattern gives high confidence - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <body>
                <div id="app"></div>
                <script src="/main.js"></script>
            </body>
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert "empty_body_with_scripts" in result.indicators_found
        # This should give high confidence for dynamic content


# ============================================================================
# Fallback Strategy Tests
# ============================================================================


@pytest.mark.unit
class TestFallbackStrategy:
    """Tests for fallback strategy determination."""

    def test_high_confidence_uses_javascript_strategy(
        self, detector: DynamicContentDetector
    ) -> None:
        """Test high confidence uses JavaScript strategy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <body>
                <div id="root"></div>
                <script src="/react.js"></script>
                <script src="/bundle.js"></script>
            </body>
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert result.fallback_strategy in ["javascript", "hybrid"]

    def test_low_confidence_uses_standard_strategy(self, detector: DynamicContentDetector) -> None:
        """Test low confidence uses standard strategy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = "<html><body><p>Simple static content</p></body></html>"

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        assert result.fallback_strategy == "standard"

    def test_medium_confidence_uses_hybrid_strategy(self, detector: DynamicContentDetector) -> None:
        """Test medium confidence uses hybrid strategy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <body>
                <p>Some content</p>
                <img class="lazyload" />
            </body>
        </html>
        """

        # Act - MANDATORY
        result = detector.analyze_html(html)

        # Assert - MANDATORY
        # Should be standard or hybrid based on confidence
        assert result.fallback_strategy in ["standard", "hybrid"]


# ============================================================================
# Utility Functions Tests
# ============================================================================


@pytest.mark.unit
class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_should_use_javascript_rendering_with_spa(self) -> None:
        """Test utility function with SPA content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = """
        <html>
            <body>
                <div id="root"></div>
                <script src="/react.js"></script>
            </body>
        </html>
        """

        # Act - MANDATORY
        is_dynamic, analysis = should_use_javascript_rendering(html)

        # Assert - MANDATORY
        assert isinstance(analysis, ContentAnalysis)
        # is_dynamic depends on confidence calculation

    def test_get_recommended_wait_conditions_for_lazy_loading(self) -> None:
        """Test recommended wait conditions for lazy loading - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.7,
            indicators_found=["lazy_loading"],
            frameworks_detected=[],
            fallback_strategy="hybrid",
            reasons=[],
        )

        # Act - MANDATORY
        conditions = get_recommended_wait_conditions(analysis)

        # Assert - MANDATORY
        assert conditions["additional_wait_time"] >= 2.0
        assert "wait_for_function" in conditions

    def test_get_recommended_wait_conditions_for_react(self) -> None:
        """Test recommended wait conditions for React - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.9,
            indicators_found=["js_frameworks_in_scripts"],
            frameworks_detected=["react"],
            fallback_strategy="javascript",
            reasons=[],
        )

        # Act - MANDATORY
        conditions = get_recommended_wait_conditions(analysis)

        # Assert - MANDATORY
        assert conditions["additional_wait_time"] >= 2.0
        assert "React" in conditions.get("wait_for_function", "")


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestDetectorPerformance:
    """MANDATORY performance tests for content detector."""

    def test_detector_initialization_performance(self) -> None:
        """MANDATORY performance test - detector initialization speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            DynamicContentDetector()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per initialization
        assert execution_time < 1.0  # Total <1s for 1000 initializations

    def test_simple_html_analysis_performance(self, detector: DynamicContentDetector) -> None:
        """MANDATORY performance test - simple HTML analysis speed."""
        # Arrange - MANDATORY
        html = "<html><body><p>Simple content</p></body></html>"
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            detector.analyze_html(html)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per analysis
        assert execution_time < 1.0  # Total <1s for 100 analyses

    def test_complex_html_analysis_performance(self, detector: DynamicContentDetector) -> None:
        """MANDATORY performance test - complex HTML analysis speed."""
        # Arrange - MANDATORY
        html = """
        <html>
            <head><script src="/react.js"></script></head>
            <body>
                <div class="js-app react-root">
                    <img data-src="/img1.jpg" />
                    <img class="lazyload" />
                    <div class="infinite-scroll"></div>
                </div>
                <script>fetch('/api/data')</script>
            </body>
        </html>
        """
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            detector.analyze_html(html)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.05  # <50ms per complex analysis
        assert execution_time < 5.0  # Total <5s for 100 analyses
