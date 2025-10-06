"""Comprehensive tests for HTML utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests HTML processing utilities with complete coverage:
- Safe attribute copying with defaults
- Meta tag content extraction
- Multiple selector matching
- Element data extraction
- Element creation with attributes
- Edge cases and error handling

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive HTML processing scenario testing
- Performance benchmarks with specific thresholds
"""

import time

import pytest
from bs4 import BeautifulSoup, Tag

from src.utils.html import (
    create_element_with_attributes,
    extract_basic_element_data,
    find_meta_content,
    find_multiple_selectors,
    safe_copy_attributes,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_soup() -> BeautifulSoup:
    """Factory for sample BeautifulSoup object - DRY principle."""
    html = """
    <html>
        <head>
            <meta name="description" content="Test description">
            <meta property="og:title" content="OpenGraph Title">
            <meta property="og:image" content="https://example.com/image.jpg">
        </head>
        <body>
            <div id="main" class="container wrapper">
                <img src="/image.jpg" alt="Test Image" title="Image Title">
                <a href="https://example.com" title="Link Title">Link Text</a>
                <div class="content">Content</div>
            </div>
        </body>
    </html>
    """
    return BeautifulSoup(html, "html.parser")


@pytest.fixture
def sample_img_tag(sample_soup: BeautifulSoup) -> Tag:
    """Factory for sample img tag - DRY principle."""
    img = sample_soup.find("img")
    assert img is not None
    assert isinstance(img, Tag)
    return img


@pytest.fixture
def sample_link_tag(sample_soup: BeautifulSoup) -> Tag:
    """Factory for sample link tag - DRY principle."""
    link = sample_soup.find("a")
    assert link is not None
    assert isinstance(link, Tag)
    return link


@pytest.fixture
def sample_div_tag(sample_soup: BeautifulSoup) -> Tag:
    """Factory for sample div tag - DRY principle."""
    div = sample_soup.find("div", id="main")
    assert div is not None
    assert isinstance(div, Tag)
    return div


# ============================================================================
# safe_copy_attributes Tests
# ============================================================================


@pytest.mark.unit
class TestSafeCopyAttributes:
    """Tests for safe_copy_attributes function."""

    def test_safe_copy_attributes_simple_mapping(
        self, sample_soup: BeautifulSoup, sample_img_tag: Tag
    ) -> None:
        """Test safe_copy_attributes with simple mapping - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        target = sample_soup.new_tag("img")
        attribute_map: dict[str, str | tuple[str, str]] = {"src": "src", "alt": "alt"}

        # Act - MANDATORY
        safe_copy_attributes(sample_img_tag, target, attribute_map)

        # Assert - MANDATORY
        assert target.get("src") == "/image.jpg"
        assert target.get("alt") == "Test Image"

    def test_safe_copy_attributes_with_defaults(
        self, sample_soup: BeautifulSoup, sample_img_tag: Tag
    ) -> None:
        """Test safe_copy_attributes with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        target = sample_soup.new_tag("img")
        attribute_map: dict[str, str | tuple[str, str]] = {
            "src": "src",
            "alt": ("alt", ""),
            "missing": ("data-missing", "default_value"),
        }

        # Act - MANDATORY
        safe_copy_attributes(sample_img_tag, target, attribute_map)

        # Assert - MANDATORY
        assert target.get("src") == "/image.jpg"
        assert target.get("alt") == "Test Image"
        assert target.get("data-missing") == "default_value"

    def test_safe_copy_attributes_missing_source_attr(
        self, sample_soup: BeautifulSoup, sample_img_tag: Tag
    ) -> None:
        """Test safe_copy_attributes with missing source attribute - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        target = sample_soup.new_tag("img")
        attribute_map: dict[str, str | tuple[str, str]] = {"nonexistent": ("data-attr", "fallback")}

        # Act - MANDATORY
        safe_copy_attributes(sample_img_tag, target, attribute_map)

        # Assert - MANDATORY
        assert target.get("data-attr") == "fallback"

    def test_safe_copy_attributes_mixed_mappings(
        self, sample_soup: BeautifulSoup, sample_img_tag: Tag
    ) -> None:
        """Test safe_copy_attributes with mixed mapping types - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        target = sample_soup.new_tag("img")
        attribute_map: dict[str, str | tuple[str, str]] = {
            "src": "src",  # Simple string mapping
            "alt": ("alt", "No alt text"),  # Tuple with default
            "title": ("title", "No title"),  # Tuple with default
        }

        # Act - MANDATORY
        safe_copy_attributes(sample_img_tag, target, attribute_map)

        # Assert - MANDATORY
        assert target.get("src") == "/image.jpg"
        assert target.get("alt") == "Test Image"
        assert target.get("title") == "Image Title"

    def test_safe_copy_attributes_empty_map(
        self, sample_soup: BeautifulSoup, sample_img_tag: Tag
    ) -> None:
        """Test safe_copy_attributes with empty map - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        target = sample_soup.new_tag("img")
        attribute_map: dict[str, str | tuple[str, str]] = {}

        # Act - MANDATORY
        safe_copy_attributes(sample_img_tag, target, attribute_map)

        # Assert - MANDATORY
        assert len(target.attrs) == 0


# ============================================================================
# find_meta_content Tests
# ============================================================================


@pytest.mark.unit
class TestFindMetaContent:
    """Tests for find_meta_content function."""

    def test_find_meta_content_by_name(self, sample_soup: BeautifulSoup) -> None:
        """Test find_meta_content by name attribute - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        meta_name = "description"

        # Act - MANDATORY
        result = find_meta_content(sample_soup, name=meta_name)

        # Assert - MANDATORY
        assert result == "Test description"

    def test_find_meta_content_by_property(self, sample_soup: BeautifulSoup) -> None:
        """Test find_meta_content by property attribute - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        property_attr = "og:title"

        # Act - MANDATORY
        result = find_meta_content(sample_soup, property_attr=property_attr)

        # Assert - MANDATORY
        assert result == "OpenGraph Title"

    def test_find_meta_content_og_image(self, sample_soup: BeautifulSoup) -> None:
        """Test find_meta_content for og:image - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        property_attr = "og:image"

        # Act - MANDATORY
        result = find_meta_content(sample_soup, property_attr=property_attr)

        # Assert - MANDATORY
        assert result == "https://example.com/image.jpg"

    def test_find_meta_content_nonexistent_name(self, sample_soup: BeautifulSoup) -> None:
        """Test find_meta_content with nonexistent name - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        meta_name = "nonexistent"

        # Act - MANDATORY
        result = find_meta_content(sample_soup, name=meta_name)

        # Assert - MANDATORY
        assert result is None

    def test_find_meta_content_nonexistent_property(self, sample_soup: BeautifulSoup) -> None:
        """Test find_meta_content with nonexistent property - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        property_attr = "og:nonexistent"

        # Act - MANDATORY
        result = find_meta_content(sample_soup, property_attr=property_attr)

        # Assert - MANDATORY
        assert result is None

    def test_find_meta_content_no_parameters(self, sample_soup: BeautifulSoup) -> None:
        """Test find_meta_content with no parameters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no parameters)

        # Act - MANDATORY
        result = find_meta_content(sample_soup)

        # Assert - MANDATORY
        assert result is None

    def test_find_meta_content_empty_content(self) -> None:
        """Test find_meta_content with empty content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<html><head><meta name="empty" content=""></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        # Act - MANDATORY
        result = find_meta_content(soup, name="empty")

        # Assert - MANDATORY
        assert result == ""


# ============================================================================
# find_multiple_selectors Tests
# ============================================================================


@pytest.mark.unit
class TestFindMultipleSelectors:
    """Tests for find_multiple_selectors function."""

    def test_find_multiple_selectors_first_match(self, sample_soup: BeautifulSoup) -> None:
        """Test find_multiple_selectors first selector matches - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        selectors: list[str] = ["#main", ".nonexistent", "body"]

        # Act - MANDATORY
        result = find_multiple_selectors(sample_soup, selectors)

        # Assert - MANDATORY
        assert result is not None
        assert result.get("id") == "main"

    def test_find_multiple_selectors_second_match(self, sample_soup: BeautifulSoup) -> None:
        """Test find_multiple_selectors second selector matches - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        selectors: list[str] = [".nonexistent", ".content", "#main"]

        # Act - MANDATORY
        result = find_multiple_selectors(sample_soup, selectors)

        # Assert - MANDATORY
        assert result is not None
        class_attr = result.get("class")
        if isinstance(class_attr, list):
            assert "content" in class_attr

    def test_find_multiple_selectors_no_match(self, sample_soup: BeautifulSoup) -> None:
        """Test find_multiple_selectors no selectors match - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        selectors: list[str] = [".nonexistent1", ".nonexistent2", "#nonexistent"]

        # Act - MANDATORY
        result = find_multiple_selectors(sample_soup, selectors)

        # Assert - MANDATORY
        assert result is None

    def test_find_multiple_selectors_empty_list(self, sample_soup: BeautifulSoup) -> None:
        """Test find_multiple_selectors with empty list - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        selectors: list[str] = []

        # Act - MANDATORY
        result = find_multiple_selectors(sample_soup, selectors)

        # Assert - MANDATORY
        assert result is None

    def test_find_multiple_selectors_complex_selectors(self, sample_soup: BeautifulSoup) -> None:
        """Test find_multiple_selectors with complex selectors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        selectors: list[str] = ["div.nonexistent img", "#main img", "body > img"]

        # Act - MANDATORY
        result = find_multiple_selectors(sample_soup, selectors)

        # Assert - MANDATORY
        assert result is not None
        assert result.name == "img"


# ============================================================================
# extract_basic_element_data Tests
# ============================================================================


@pytest.mark.unit
class TestExtractBasicElementData:
    """Tests for extract_basic_element_data function."""

    def test_extract_basic_element_data_img_tag(self, sample_img_tag: Tag) -> None:
        """Test extract_basic_element_data from img tag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = extract_basic_element_data(sample_img_tag)

        # Assert - MANDATORY
        assert result["src"] == "/image.jpg"
        assert result["alt"] == "Test Image"
        assert result["title"] == "Image Title"
        assert result["href"] == ""  # Not present in img
        assert result["class"] == ""
        assert result["id"] == ""

    def test_extract_basic_element_data_link_tag(self, sample_link_tag: Tag) -> None:
        """Test extract_basic_element_data from link tag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = extract_basic_element_data(sample_link_tag)

        # Assert - MANDATORY
        assert result["href"] == "https://example.com"
        assert result["title"] == "Link Title"
        assert result["src"] == ""  # Not present in link
        assert result["alt"] == ""

    def test_extract_basic_element_data_div_with_classes(self, sample_div_tag: Tag) -> None:
        """Test extract_basic_element_data from div with classes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = extract_basic_element_data(sample_div_tag)

        # Assert - MANDATORY
        assert result["id"] == "main"
        assert "container" in result["class"]
        assert "wrapper" in result["class"]

    def test_extract_basic_element_data_minimal_element(self, sample_soup: BeautifulSoup) -> None:
        """Test extract_basic_element_data from minimal element - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        minimal = sample_soup.new_tag("div")

        # Act - MANDATORY
        result = extract_basic_element_data(minimal)

        # Assert - MANDATORY
        assert result["src"] == ""
        assert result["alt"] == ""
        assert result["href"] == ""
        assert result["title"] == ""
        assert result["class"] == ""
        assert result["id"] == ""

    def test_extract_basic_element_data_single_class(self) -> None:
        """Test extract_basic_element_data with single class - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<div class="single-class">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")
        assert element is not None
        assert isinstance(element, Tag)

        # Act - MANDATORY
        result = extract_basic_element_data(element)

        # Assert - MANDATORY
        assert result["class"] == "single-class"

    def test_extract_basic_element_data_class_list(self) -> None:
        """Test extract_basic_element_data with class list - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html = '<div class="class1 class2 class3">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")
        assert element is not None
        assert isinstance(element, Tag)

        # Act - MANDATORY
        result = extract_basic_element_data(element)

        # Assert - MANDATORY
        assert "class1" in result["class"]
        assert "class2" in result["class"]
        assert "class3" in result["class"]


# ============================================================================
# create_element_with_attributes Tests
# ============================================================================


@pytest.mark.unit
class TestCreateElementWithAttributes:
    """Tests for create_element_with_attributes function."""

    def test_create_element_with_attributes_img(self, sample_soup: BeautifulSoup) -> None:
        """Test create_element_with_attributes for img - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tag_name = "img"
        attributes: dict[str, str | None] = {
            "src": "/test.jpg",
            "alt": "Test",
            "title": "Test Image",
        }

        # Act - MANDATORY
        result = create_element_with_attributes(sample_soup, tag_name, attributes)

        # Assert - MANDATORY
        assert result.name == "img"
        assert result.get("src") == "/test.jpg"
        assert result.get("alt") == "Test"
        assert result.get("title") == "Test Image"

    def test_create_element_with_attributes_link(self, sample_soup: BeautifulSoup) -> None:
        """Test create_element_with_attributes for link - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tag_name = "a"
        attributes: dict[str, str | None] = {
            "href": "https://example.com",
            "title": "Link",
            "target": "_blank",
        }

        # Act - MANDATORY
        result = create_element_with_attributes(sample_soup, tag_name, attributes)

        # Assert - MANDATORY
        assert result.name == "a"
        assert result.get("href") == "https://example.com"
        assert result.get("title") == "Link"
        assert result.get("target") == "_blank"

    def test_create_element_with_attributes_empty_values(self, sample_soup: BeautifulSoup) -> None:
        """Test create_element_with_attributes skips empty values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tag_name = "div"
        attributes: dict[str, str | None] = {"id": "test", "class": "", "data-value": None}

        # Act - MANDATORY
        result = create_element_with_attributes(sample_soup, tag_name, attributes)

        # Assert - MANDATORY
        assert result.get("id") == "test"
        assert "class" not in result.attrs  # Empty string skipped
        assert "data-value" not in result.attrs  # None skipped

    def test_create_element_with_attributes_no_attributes(self, sample_soup: BeautifulSoup) -> None:
        """Test create_element_with_attributes with no attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tag_name = "div"
        attributes: dict[str, str | None] = {}

        # Act - MANDATORY
        result = create_element_with_attributes(sample_soup, tag_name, attributes)

        # Assert - MANDATORY
        assert result.name == "div"
        assert len(result.attrs) == 0

    def test_create_element_with_attributes_complex(self, sample_soup: BeautifulSoup) -> None:
        """Test create_element_with_attributes with complex attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tag_name = "div"
        attributes: dict[str, str | None] = {
            "id": "container",
            "class": "wrapper main",
            "data-id": "123",
            "data-type": "content",
        }

        # Act - MANDATORY
        result = create_element_with_attributes(sample_soup, tag_name, attributes)

        # Assert - MANDATORY
        assert result.get("id") == "container"
        assert result.get("class") == "wrapper main"
        assert result.get("data-id") == "123"
        assert result.get("data-type") == "content"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHTMLUtilsPerformance:
    """MANDATORY performance tests for HTML utilities."""

    def test_extract_basic_element_data_performance(self, sample_soup: BeautifulSoup) -> None:
        """MANDATORY performance test - element data extraction speed."""
        # Arrange - MANDATORY
        elements = [sample_soup.new_tag("div") for _ in range(1000)]
        for i, elem in enumerate(elements):
            elem["id"] = f"elem{i}"
            elem["class"] = "test-class"

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            for elem in elements:
                extract_basic_element_data(elem)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        total_operations = iterations * len(elements)
        avg_time = execution_time / total_operations
        assert avg_time < 0.00001  # <0.01ms per extraction

    def test_find_meta_content_performance(self) -> None:
        """MANDATORY performance test - meta content search speed."""
        # Arrange - MANDATORY
        html = """
        <html>
        <head>
            <meta name="description" content="Test">
            <meta property="og:title" content="Title">
            <meta property="og:image" content="Image">
        </head>
        </html>
        """
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            soup = BeautifulSoup(html, "html.parser")
            find_meta_content(soup, name="description")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per search (includes parsing)
        assert execution_time < 10.0  # Total <10s for 10000 searches

    def test_create_element_with_attributes_performance(self, sample_soup: BeautifulSoup) -> None:
        """MANDATORY performance test - element creation speed."""
        # Arrange - MANDATORY
        attributes: dict[str, str | None] = {"id": "test", "class": "wrapper", "data-value": "123"}
        iterations = 50000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            create_element_with_attributes(sample_soup, "div", attributes)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00002  # <0.02ms per creation
        assert execution_time < 1.0  # Total <1s for 50000 creations
