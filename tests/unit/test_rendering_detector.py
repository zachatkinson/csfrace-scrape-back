"""Unit tests for dynamic content detection."""

import pytest

from src.rendering.detector import (
    ContentAnalysis,
    DynamicContentDetector,
    DynamicContentIndicators,
    get_recommended_wait_conditions,
    should_use_javascript_rendering,
)


class TestDynamicContentIndicators:
    """Test dynamic content indicators configuration."""

    def test_default_indicators(self):
        """Test default indicator configuration."""
        indicators = DynamicContentIndicators()

        # Verify JS frameworks
        expected_frameworks = [
            "react",
            "vue",
            "angular",
            "svelte",
            "ember",
            "backbone",
            "knockout",
            "jquery",
        ]
        for framework in expected_frameworks:
            assert framework in indicators.js_frameworks

        # Verify SPA indicators
        spa_indicators = ["ng-app", "ng-controller", "v-app", "react-root"]
        for indicator in spa_indicators:
            assert indicator in indicators.spa_indicators

        # Verify lazy loading selectors
        assert "[data-src]" in indicators.lazy_loading_selectors
        assert ".lazyload" in indicators.lazy_loading_selectors

        # Verify JS dependent classes
        assert "js-" in indicators.js_dependent_classes
        assert "react-" in indicators.js_dependent_classes

    def test_custom_indicators(self):
        """Test custom indicator configuration."""
        custom_indicators = DynamicContentIndicators(
            js_frameworks=["custom-framework"],
            spa_indicators=["custom-spa"],
            lazy_loading_selectors=[".custom-lazy"],
            js_dependent_classes=["custom-js-"],
            ajax_indicators=["custom-ajax"],
        )

        assert custom_indicators.js_frameworks == ["custom-framework"]
        assert custom_indicators.spa_indicators == ["custom-spa"]
        assert custom_indicators.lazy_loading_selectors == [".custom-lazy"]
        assert custom_indicators.js_dependent_classes == ["custom-js-"]
        assert custom_indicators.ajax_indicators == ["custom-ajax"]


class TestContentAnalysis:
    """Test content analysis data structure."""

    def test_content_analysis_creation(self):
        """Test creating content analysis result."""
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.8,
            indicators_found=["js_frameworks_in_scripts"],
            frameworks_detected=["react"],
            fallback_strategy="javascript",
            reasons=["React framework detected"],
            metadata={"content_density": 0.5},
        )

        assert analysis.is_dynamic is True
        assert analysis.confidence_score == 0.8
        assert analysis.indicators_found == ["js_frameworks_in_scripts"]
        assert analysis.frameworks_detected == ["react"]
        assert analysis.fallback_strategy == "javascript"
        assert analysis.reasons == ["React framework detected"]
        assert analysis.metadata == {"content_density": 0.5}

    def test_content_analysis_defaults(self):
        """Test content analysis with defaults."""
        analysis = ContentAnalysis(is_dynamic=False, confidence_score=0.2)

        assert analysis.is_dynamic is False
        assert analysis.confidence_score == 0.2
        assert analysis.indicators_found == []
        assert analysis.frameworks_detected == []
        assert analysis.fallback_strategy == "standard"
        assert analysis.reasons == []
        assert analysis.metadata == {}


class TestDynamicContentDetector:
    """Test dynamic content detector functionality."""

    @pytest.fixture
    def detector(self):
        """Create detector instance."""
        return DynamicContentDetector()

    def test_detector_initialization(self, detector):
        """Test detector initialization."""
        assert isinstance(detector.indicators, DynamicContentIndicators)
        assert len(detector._js_framework_patterns) > 0
        assert len(detector._spa_patterns) > 0

    def test_detect_react_framework(self, detector):
        """Test detection of React framework."""
        html = """
        <html>
        <head>
            <script src="https://cdn.react.com/react.min.js"></script>
        </head>
        <body>
            <div id="react-root"></div>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html, "https://example.com")

        assert analysis.is_dynamic is True
        assert "react" in analysis.frameworks_detected
        assert "js_frameworks_in_scripts" in analysis.indicators_found
        assert analysis.confidence_score > 0.5
        assert analysis.fallback_strategy in ["javascript", "hybrid"]

    def test_detect_vue_framework(self, detector):
        """Test detection of Vue.js framework."""
        html = """
        <html>
        <head>
            <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
        </head>
        <body>
            <div id="app" v-app>
                <h1>{{ message }}</h1>
            </div>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert analysis.is_dynamic is True
        assert "vue" in analysis.frameworks_detected
        assert "js_frameworks_in_scripts" in analysis.indicators_found
        assert "spa_attributes" in analysis.indicators_found
        assert analysis.confidence_score > 0.5

    def test_detect_angular_framework(self, detector):
        """Test detection of Angular framework."""
        html = """
        <html>
        <head>
            <script src="https://angular.io/js/angular.min.js"></script>
        </head>
        <body ng-app="myApp">
            <div ng-controller="MyController">
                <p>{{ message }}</p>
            </div>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert analysis.is_dynamic is True
        assert "angular" in analysis.frameworks_detected
        assert "js_frameworks_in_scripts" in analysis.indicators_found
        assert "spa_attributes" in analysis.indicators_found

    def test_detect_lazy_loading(self, detector):
        """Test detection of lazy loading elements."""
        html = """
        <html>
        <body>
            <img data-src="image1.jpg" class="lazyload" alt="Image 1">
            <img src="image2.jpg" loading="lazy" alt="Image 2">
            <div class="lazy-image" data-src="bg.jpg"></div>
            <div class="skeleton"></div>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert "lazy_loading" in analysis.indicators_found
        assert analysis.metadata.get("lazy_elements_count", 0) >= 3
        assert "lazy-loaded elements" in " ".join(analysis.reasons)

    def test_detect_js_dependent_classes(self, detector):
        """Test detection of JavaScript-dependent CSS classes."""
        html = """
        <html>
        <body>
            <div class="js-toggle">Toggle</div>
            <div class="react-component">React Component</div>
            <div class="vue-widget">Vue Widget</div>
            <div class="ng-container">Angular Container</div>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert "js_dependent_classes" in analysis.indicators_found
        expected_classes = ["js-toggle", "react-component", "vue-widget", "ng-container"]
        assert any(cls in " ".join(analysis.reasons) for cls in expected_classes)

    def test_detect_ajax_patterns(self, detector):
        """Test detection of AJAX patterns."""
        html = """
        <html>
        <body>
            <div data-ajax-url="/api/data">Content</div>
            <div data-infinite-scroll="true">Infinite scroll</div>
            <button class="load-more" data-endpoint="/more">Load More</button>
            <script>
                fetch('/api/data').then(response => response.json());
                $.ajax({ url: '/data', method: 'GET' });
            </script>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert "ajax_patterns" in analysis.indicators_found
        # Should detect patterns like "ajax", "fetch", etc.
        assert len([r for r in analysis.reasons if "AJAX" in r or "patterns" in r]) > 0

    def test_detect_low_content_density(self, detector):
        """Test detection of low content density (SPA pattern)."""
        # Very minimal HTML with mostly markup (typical SPA)
        html = """
        <html>
        <head>
            <script src="app.js"></script>
            <link rel="stylesheet" href="styles.css">
        </head>
        <body>
            <div id="app"></div>
            <script>app.render();</script>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert "low_content_density" in analysis.indicators_found
        assert analysis.metadata.get("content_density", 1.0) < 0.3
        assert "Low content density" in " ".join(analysis.reasons)

    def test_detect_spa_meta_tags(self, detector):
        """Test detection of SPA-related meta tags."""
        html = """
        <html>
        <head>
            <meta name="application-type" content="spa">
            <meta property="og:type" content="application/javascript">
            <script type="module" src="app.js"></script>
        </head>
        <body></body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert "spa_meta_tags" in analysis.indicators_found
        assert "Meta tags suggest single-page application" in analysis.reasons

    def test_detect_empty_body_pattern(self, detector):
        """Test detection of empty body with scripts (classic SPA)."""
        html = """
        <html>
        <head>
            <title>SPA App</title>
        </head>
        <body>
            <div id="root"></div>
            <script src="bundle.js"></script>
            <script>
                ReactDOM.render(App, document.getElementById('root'));
            </script>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert "empty_body_with_scripts" in analysis.indicators_found
        assert "Empty body with scripts detected" in " ".join(analysis.reasons)

    def test_static_content_detection(self, detector):
        """Test detection of static content."""
        html = """
        <html>
        <head>
            <title>Static Blog Post</title>
            <meta name="description" content="A regular blog post">
        </head>
        <body>
            <header>
                <h1>My Blog</h1>
                <nav>
                    <a href="/home">Home</a>
                    <a href="/about">About</a>
                </nav>
            </header>
            <main>
                <article>
                    <h2>Blog Post Title</h2>
                    <p>This is a regular blog post with lots of static content.</p>
                    <p>It contains multiple paragraphs of text content.</p>
                    <p>The content is rendered server-side and doesn't require JavaScript.</p>
                </article>
            </main>
            <footer>
                <p>Copyright 2024</p>
            </footer>
        </body>
        </html>
        """

        analysis = detector.analyze_html(html)

        assert analysis.is_dynamic is False
        assert analysis.confidence_score < 0.5
        assert analysis.fallback_strategy == "standard"
        assert len(analysis.indicators_found) <= 1  # Minimal indicators
        assert len(analysis.frameworks_detected) == 0

    def test_confidence_score_calculation(self, detector):
        """Test confidence score calculation logic."""
        # High confidence case - multiple strong indicators
        high_confidence_html = """
        <html>
        <head><script src="react.js"></script></head>
        <body>
            <div id="react-root" class="js-app"></div>
            <script>ReactDOM.render();</script>
        </body>
        </html>
        """

        high_analysis = detector.analyze_html(high_confidence_html)
        assert high_analysis.confidence_score > 0.7

        # Medium confidence case - some indicators
        medium_confidence_html = """
        <html>
        <body>
            <div class="js-widget" data-ajax="/api">Content</div>
            <img data-src="image.jpg" class="lazyload">
        </body>
        </html>
        """

        medium_analysis = detector.analyze_html(medium_confidence_html)
        assert 0.3 < medium_analysis.confidence_score < 0.7

        # Low confidence case - minimal indicators
        low_confidence_html = """
        <html>
        <body>
            <h1>Static Content</h1>
            <p>Regular paragraph with lots of text content here.</p>
        </body>
        </html>
        """

        low_analysis = detector.analyze_html(low_confidence_html)
        assert low_analysis.confidence_score < 0.3

    def test_fallback_strategy_determination(self, detector):
        """Test fallback strategy determination."""
        # JavaScript strategy - high confidence
        js_html = """
        <html>
        <head><script src="react.js"></script><script src="vue.js"></script></head>
        <body><div id="app"></div><script>render();</script></body>
        </html>
        """

        js_analysis = detector.analyze_html(js_html)
        assert js_analysis.fallback_strategy == "javascript"

        # Hybrid strategy - medium confidence
        hybrid_html = """
        <html>
        <body>
            <div class="js-enhanced">Content</div>
            <img data-src="lazy.jpg" class="lazyload">
        </body>
        </html>
        """

        hybrid_analysis = detector.analyze_html(hybrid_html)
        assert hybrid_analysis.fallback_strategy in ["hybrid", "standard"]

        # Standard strategy - low confidence
        standard_html = """
        <html>
        <body>
            <h1>Blog Post</h1>
            <p>Static content with lots of text.</p>
        </body>
        </html>
        """

        standard_analysis = detector.analyze_html(standard_html)
        assert standard_analysis.fallback_strategy == "standard"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_should_use_javascript_rendering_true(self):
        """Test utility function returning True for dynamic content."""
        html = """
        <html>
        <head><script src="react.js"></script></head>
        <body><div id="react-root"></div></body>
        </html>
        """

        should_use_js, analysis = should_use_javascript_rendering(html, "https://example.com")

        assert should_use_js is True
        assert isinstance(analysis, ContentAnalysis)
        assert analysis.is_dynamic is True

    def test_should_use_javascript_rendering_false(self):
        """Test utility function returning False for static content."""
        html = """
        <html>
        <body>
            <h1>Static Page</h1>
            <p>This is static content with no JavaScript requirements.</p>
        </body>
        </html>
        """

        should_use_js, analysis = should_use_javascript_rendering(html)

        assert should_use_js is False
        assert isinstance(analysis, ContentAnalysis)
        assert analysis.is_dynamic is False

    def test_get_recommended_wait_conditions_default(self):
        """Test getting default wait conditions."""
        analysis = ContentAnalysis(is_dynamic=False, confidence_score=0.2)
        conditions = get_recommended_wait_conditions(analysis)

        assert conditions["wait_until"] == "networkidle"
        assert conditions["additional_wait_time"] == 1.0

    def test_get_recommended_wait_conditions_lazy_loading(self):
        """Test wait conditions for lazy loading content."""
        analysis = ContentAnalysis(
            is_dynamic=True, confidence_score=0.6, indicators_found=["lazy_loading"]
        )

        conditions = get_recommended_wait_conditions(analysis)

        assert conditions["additional_wait_time"] == 2.0
        assert "wait_for_function" in conditions
        assert "document.readyState" in conditions["wait_for_function"]

    def test_get_recommended_wait_conditions_react(self):
        """Test wait conditions for React applications."""
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.8,
            frameworks_detected=["react"],
            indicators_found=["js_frameworks_in_scripts"],
        )

        conditions = get_recommended_wait_conditions(analysis)

        assert conditions["wait_until"] == "networkidle"
        assert conditions["additional_wait_time"] == 2.0
        assert "window.React" in conditions["wait_for_function"]

    def test_get_recommended_wait_conditions_vue(self):
        """Test wait conditions for Vue.js applications."""
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.8,
            frameworks_detected=["vue"],
            indicators_found=["js_frameworks_in_scripts", "spa_attributes"],
        )

        conditions = get_recommended_wait_conditions(analysis)

        assert conditions["wait_until"] == "networkidle"
        assert conditions["additional_wait_time"] == 2.0
        assert "window.Vue" in conditions["wait_for_function"]

    def test_get_recommended_wait_conditions_angular(self):
        """Test wait conditions for Angular applications."""
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.8,
            frameworks_detected=["angular"],
            indicators_found=["js_frameworks_in_scripts", "spa_attributes"],
        )

        conditions = get_recommended_wait_conditions(analysis)

        assert conditions["wait_until"] == "networkidle"
        assert conditions["additional_wait_time"] == 2.0
        assert "window.ng" in conditions["wait_for_function"]

    def test_get_recommended_wait_conditions_ajax(self):
        """Test wait conditions for AJAX-heavy content."""
        analysis = ContentAnalysis(
            is_dynamic=True, confidence_score=0.6, indicators_found=["ajax_patterns"]
        )

        conditions = get_recommended_wait_conditions(analysis)

        assert conditions["additional_wait_time"] >= 1.5

    def test_get_recommended_wait_conditions_multiple_patterns(self):
        """Test wait conditions with multiple patterns."""
        analysis = ContentAnalysis(
            is_dynamic=True,
            confidence_score=0.9,
            frameworks_detected=["react"],
            indicators_found=["lazy_loading", "ajax_patterns", "js_frameworks_in_scripts"],
        )

        conditions = get_recommended_wait_conditions(analysis)

        # Should use the maximum wait time from different patterns
        assert conditions["additional_wait_time"] == 2.0  # Max of lazy loading
        assert "window.React" in conditions["wait_for_function"]
        assert conditions["wait_until"] == "networkidle"


# Property-based tests using hypothesis if we want to add them later
class TestDetectorEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def detector(self):
        return DynamicContentDetector()

    def test_empty_html(self, detector):
        """Test analysis of empty HTML."""
        analysis = detector.analyze_html("")

        assert analysis.is_dynamic is False
        # Empty HTML gets flagged for low content density (0.2 score)
        assert analysis.confidence_score == 0.2
        assert "low_content_density" in analysis.indicators_found
        assert analysis.fallback_strategy == "standard"
        assert analysis.metadata["content_density"] == 0.0

    def test_malformed_html(self, detector):
        """Test analysis of malformed HTML."""
        malformed_html = "<html><head><title>Test</head><body><div>Content</body>"

        # Should not raise an exception
        analysis = detector.analyze_html(malformed_html)
        assert isinstance(analysis, ContentAnalysis)

    def test_very_large_html(self, detector):
        """Test analysis of very large HTML document."""
        # Create large HTML document with high text to markup ratio
        large_content = "A" * 10000  # Just text, minimal markup
        large_html = f"<html><body><div>{large_content}</div></body></html>"

        analysis = detector.analyze_html(large_html)

        # Should handle large documents
        assert isinstance(analysis, ContentAnalysis)
        # Large documents with high content density won't have content_density in metadata
        # unless it's flagged as low (< 0.3). Let's verify it's not flagged as dynamic
        assert analysis.is_dynamic is False
        assert analysis.confidence_score < 0.5  # Should be low since it's mostly static text

    def test_html_with_special_characters(self, detector):
        """Test HTML with special characters and encoding."""
        html_with_special_chars = """
        <html>
        <body>
            <div>Content with special chars: é, ñ, 中文, 🚀</div>
            <script>
                const message = "Hello 世界! 🌍";
                console.log(message);
            </script>
        </body>
        </html>
        """

        # Should handle special characters without issues
        analysis = detector.analyze_html(html_with_special_chars)
        assert isinstance(analysis, ContentAnalysis)
