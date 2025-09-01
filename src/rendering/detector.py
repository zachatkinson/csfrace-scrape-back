"""Dynamic content detection and fallback strategies."""

import re
from dataclasses import dataclass, field
from typing import Any

import structlog
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class DynamicContentIndicators(BaseModel):
    """Configuration for detecting dynamic content patterns."""

    # JavaScript framework indicators
    js_frameworks: list[str] = Field(
        default=["react", "vue", "angular", "svelte", "ember", "backbone", "knockout", "jquery"]
    )

    # SPA (Single Page Application) indicators
    spa_indicators: list[str] = Field(
        default=[
            "ng-app",
            "ng-controller",
            "v-app",
            "react-root",
            "ember-application",
            "backbone-app",
        ]
    )

    # Dynamic loading indicators
    lazy_loading_selectors: list[str] = Field(
        default=[
            "[data-src]",
            "[lazy]",
            "[loading='lazy']",
            ".lazyload",
            ".lazy-image",
            ".skeleton",
        ]
    )

    # JavaScript-dependent elements
    js_dependent_classes: list[str] = Field(
        default=["js-", "javascript-", "no-js", "with-js", "react-", "vue-", "ng-", "ember-"]
    )

    # AJAX/Dynamic content patterns
    ajax_indicators: list[str] = Field(
        default=[
            "ajax",
            "xhr",
            "fetch",
            "dynamic",
            "async",
            "infinite-scroll",
            "load-more",
            "pagination-js",
        ]
    )

    # Meta tags that suggest SPA behavior
    spa_meta_patterns: list[str] = Field(
        default=["application/javascript", "text/javascript", "module", "spa", "pwa"]
    )


@dataclass
class ContentAnalysis:
    """Analysis result for content type detection."""

    is_dynamic: bool
    confidence_score: float  # 0.0 to 1.0
    indicators_found: list[str] = field(default_factory=list)
    frameworks_detected: list[str] = field(default_factory=list)
    fallback_strategy: str = "standard"  # standard, javascript, hybrid
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DynamicContentDetector:
    """Detector for identifying pages that require JavaScript rendering."""

    def __init__(self, indicators: DynamicContentIndicators | None = None):
        self.indicators = indicators or DynamicContentIndicators()

        # Compile regex patterns for efficiency
        self._js_framework_patterns = [
            re.compile(rf"\b{fw}\b", re.IGNORECASE) for fw in self.indicators.js_frameworks
        ]

        self._spa_patterns = [
            re.compile(rf"\b{indicator}\b", re.IGNORECASE)
            for indicator in self.indicators.spa_indicators
        ]

    def analyze_html(self, html: str, url: str | None = None) -> ContentAnalysis:
        """Analyze HTML content to detect dynamic content requirements."""
        # Handle empty or minimal HTML content
        if not html or html.strip() == "":
            return ContentAnalysis(
                is_dynamic=False,
                confidence_score=0.0,
                indicators_found=[],
                frameworks_detected=[],
                fallback_strategy="standard",
                reasons=["Empty HTML content"],
                metadata={},
            )

        soup = BeautifulSoup(html, "html.parser")

        indicators_found = []
        frameworks_detected = []
        reasons = []
        metadata = {}

        # Check for JavaScript frameworks in script tags
        frameworks_in_scripts = self._detect_frameworks_in_scripts(soup)
        if frameworks_in_scripts:
            frameworks_detected.extend(frameworks_in_scripts)
            indicators_found.append("js_frameworks_in_scripts")
            reasons.append(f"JavaScript frameworks detected: {', '.join(frameworks_in_scripts)}")

        # Check for SPA indicators in HTML attributes
        spa_attributes = self._detect_spa_attributes(soup)
        if spa_attributes:
            indicators_found.append("spa_attributes")
            reasons.append(f"SPA attributes found: {', '.join(spa_attributes)}")

        # Check for lazy loading elements
        lazy_elements = self._detect_lazy_loading(soup)
        if lazy_elements > 0:
            indicators_found.append("lazy_loading")
            reasons.append(f"Found {lazy_elements} lazy-loaded elements")
            metadata["lazy_elements_count"] = lazy_elements

        # Check for JavaScript-dependent CSS classes
        js_classes = self._detect_js_dependent_classes(soup)
        if js_classes:
            indicators_found.append("js_dependent_classes")
            reasons.append(f"JavaScript-dependent classes: {', '.join(js_classes[:5])}")

        # Check for AJAX/dynamic content indicators
        ajax_indicators = self._detect_ajax_patterns(soup)
        if ajax_indicators:
            indicators_found.append("ajax_patterns")
            reasons.append(f"AJAX patterns detected: {', '.join(ajax_indicators)}")

        # Check for minimal/skeleton content (often indicates client-side rendering)
        content_density = self._analyze_content_density(soup)
        if content_density < 0.3:  # Very low content density
            indicators_found.append("low_content_density")
            reasons.append(
                f"Low content density ({content_density:.2f}) suggests client-side rendering"
            )
            metadata["content_density"] = int(content_density)

        # Check for meta tags suggesting SPA
        spa_meta = self._detect_spa_meta_tags(soup)
        if spa_meta:
            indicators_found.append("spa_meta_tags")
            reasons.append("Meta tags suggest single-page application")

        # Check for empty body with scripts (classic SPA pattern)
        empty_body_with_scripts = self._detect_empty_body_pattern(soup)
        if empty_body_with_scripts:
            indicators_found.append("empty_body_with_scripts")
            reasons.append("Empty body with scripts detected (SPA pattern)")

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            indicators_found, frameworks_detected, content_density
        )

        # Determine if content is dynamic based on indicators
        is_dynamic = confidence_score > 0.5 or len(indicators_found) >= 2

        # Determine fallback strategy
        fallback_strategy = self._determine_fallback_strategy(
            confidence_score, indicators_found, frameworks_detected
        )

        logger.debug(
            "Content analysis completed",
            url=url,
            is_dynamic=is_dynamic,
            confidence_score=confidence_score,
            indicators_count=len(indicators_found),
            frameworks_detected=frameworks_detected,
            fallback_strategy=fallback_strategy,
        )

        return ContentAnalysis(
            is_dynamic=is_dynamic,
            confidence_score=confidence_score,
            indicators_found=indicators_found,
            frameworks_detected=frameworks_detected,
            fallback_strategy=fallback_strategy,
            reasons=reasons,
            metadata=metadata,
        )

    def _detect_frameworks_in_scripts(self, soup: BeautifulSoup) -> list[str]:
        """Detect JavaScript frameworks in script tags."""
        frameworks = set()

        # Check script src attributes
        for script in soup.find_all("script", src=True):
            src = script["src"].lower()
            for i, pattern in enumerate(self._js_framework_patterns):
                if pattern.search(src):
                    frameworks.add(self.indicators.js_frameworks[i])

        # Check inline scripts
        for script in soup.find_all("script", string=True):
            script_content = script.string.lower()
            for i, pattern in enumerate(self._js_framework_patterns):
                if pattern.search(script_content):
                    frameworks.add(self.indicators.js_frameworks[i])

        return list(frameworks)

    def _detect_spa_attributes(self, soup: BeautifulSoup) -> list[str]:
        """Detect SPA-specific attributes in HTML."""
        attributes = set()

        # Check for SPA framework attributes
        for indicator in self.indicators.spa_indicators:
            if soup.find(attrs={indicator: True}) or soup.find(class_=re.compile(indicator, re.I)):
                attributes.add(indicator)

        return list(attributes)

    def _detect_lazy_loading(self, soup: BeautifulSoup) -> int:
        """Count lazy loading elements."""
        count = 0

        for selector in self.indicators.lazy_loading_selectors:
            try:
                elements = soup.select(selector)
                count += len(elements)
            except Exception as e:
                logger.debug(
                    "Error checking lazy loading selector", selector=selector, error=str(e)
                )

        return count

    def _detect_js_dependent_classes(self, soup: BeautifulSoup) -> list[str]:
        """Detect CSS classes that suggest JavaScript dependency."""
        js_classes = set()

        # Find all elements with class attributes
        for element in soup.find_all(class_=True):
            classes = element.get("class", [])
            if isinstance(classes, str):
                classes = [classes]

            for class_name in classes:
                for prefix in self.indicators.js_dependent_classes:
                    if class_name.lower().startswith(prefix.lower()):
                        js_classes.add(class_name)

        return list(js_classes)

    def _detect_ajax_patterns(self, soup: BeautifulSoup) -> list[str]:
        """Detect AJAX and dynamic loading patterns."""
        patterns_found = set()

        # Check in script content
        for script in soup.find_all("script", string=True):
            script_content = script.string.lower()
            for indicator in self.indicators.ajax_indicators:
                if indicator in script_content:
                    patterns_found.add(indicator)

        # Check in data attributes
        for element in soup.find_all(attrs={"data-": True}):
            for attr_name in element.attrs:
                if attr_name.lower().startswith("data-"):
                    attr_value = str(element.attrs[attr_name]).lower()
                    for indicator in self.indicators.ajax_indicators:
                        if indicator in attr_value or indicator in attr_name.lower():
                            patterns_found.add(indicator)

        return list(patterns_found)

    def _analyze_content_density(self, soup: BeautifulSoup) -> float:
        """Analyze the density of actual content vs markup."""
        # Get total HTML length
        total_html = len(str(soup))
        if total_html == 0:
            return 0.0

        # Get text content length
        text_content = soup.get_text(strip=True)
        text_length = len(text_content)

        # Calculate ratio of text to HTML
        density = text_length / total_html
        return min(density, 1.0)  # Cap at 1.0

    def _detect_spa_meta_tags(self, soup: BeautifulSoup) -> bool:
        """Check for meta tags that suggest SPA behavior."""
        meta_tags = soup.find_all("meta")

        for meta in meta_tags:
            content = meta.get("content", "").lower()
            name = meta.get("name", "").lower()
            property_val = meta.get("property", "").lower()

            for pattern in self.indicators.spa_meta_patterns:
                if pattern in content or pattern in name or pattern in property_val:
                    return True

        return False

    def _detect_empty_body_pattern(self, soup: BeautifulSoup) -> bool:
        """Detect empty body with only scripts (classic SPA pattern)."""
        body = soup.find("body")
        if not body:
            return False

        # Count non-script elements in body
        if not isinstance(body, Tag):
            return False
        non_script_elements = [
            elem
            for elem in body.find_all()
            if elem.name not in ["script", "noscript", "style", "link", "meta"]
        ]

        # Check if body is mostly empty except for scripts
        if not isinstance(body, Tag):
            return False
        script_count = len(body.find_all("script"))

        return len(non_script_elements) <= 2 and script_count >= 1

    def _calculate_confidence_score(
        self, indicators: list[str], frameworks: list[str], content_density: float
    ) -> float:
        """Calculate confidence score for dynamic content detection."""
        score = 0.0

        # Base score from indicators
        indicator_weights = {
            "js_frameworks_in_scripts": 0.3,
            "spa_attributes": 0.25,
            "lazy_loading": 0.15,
            "js_dependent_classes": 0.1,
            "ajax_patterns": 0.2,
            "low_content_density": 0.2,
            "spa_meta_tags": 0.15,
            "empty_body_with_scripts": 0.35,
        }

        for indicator in indicators:
            score += indicator_weights.get(indicator, 0.1)

        # Boost score for known frameworks
        framework_boost = min(len(frameworks) * 0.2, 0.4)
        score += framework_boost

        # Penalize very high content density (suggests static content)
        if content_density > 0.8:
            score *= 0.7

        return min(score, 1.0)

    def _determine_fallback_strategy(
        self, confidence_score: float, indicators: list[str], frameworks: list[str]
    ) -> str:
        """Determine the appropriate fallback strategy."""
        # High confidence or critical indicators = full JavaScript rendering
        if (
            confidence_score > 0.8
            or "empty_body_with_scripts" in indicators
            or len(frameworks) >= 2
        ):
            return "javascript"

        # Medium confidence = hybrid approach (try static first, fallback to JS)
        elif confidence_score > 0.5:
            return "hybrid"

        # Low confidence = standard HTTP scraping
        else:
            return "standard"


# Utility functions
def should_use_javascript_rendering(
    html: str, url: str | None = None
) -> tuple[bool, ContentAnalysis]:
    """Quick utility to determine if JavaScript rendering is needed."""
    detector = DynamicContentDetector()
    analysis = detector.analyze_html(html, url)
    return analysis.is_dynamic, analysis


def get_recommended_wait_conditions(analysis: ContentAnalysis) -> dict[str, Any]:
    """Get recommended wait conditions based on content analysis."""
    conditions = {"wait_until": "networkidle", "additional_wait_time": 1.0}

    # Adjust based on detected patterns
    if "lazy_loading" in analysis.indicators_found:
        conditions["additional_wait_time"] = 2.0
        conditions["wait_for_function"] = "() => document.readyState === 'complete'"

    if "ajax_patterns" in analysis.indicators_found:
        current_wait = conditions.get("additional_wait_time", 0.0)
        if isinstance(current_wait, int | float):
            conditions["additional_wait_time"] = max(float(current_wait), 1.5)
        else:
            conditions["additional_wait_time"] = 1.5

    if any(fw in ["react", "vue", "angular"] for fw in analysis.frameworks_detected):
        conditions["wait_until"] = "networkidle"
        conditions["additional_wait_time"] = 2.0

        # Framework-specific wait conditions
        if "react" in analysis.frameworks_detected:
            conditions["wait_for_function"] = (
                "() => window.React && document.readyState === 'complete'"
            )
        elif "vue" in analysis.frameworks_detected:
            conditions["wait_for_function"] = (
                "() => window.Vue && document.readyState === 'complete'"
            )
        elif "angular" in analysis.frameworks_detected:
            conditions["wait_for_function"] = (
                "() => window.ng && document.readyState === 'complete'"
            )

    return conditions
