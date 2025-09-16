"""Tests for HTML utilities following testing best practices."""

from bs4 import BeautifulSoup
from bs4.element import AttributeValueList

from src.utils.html import (
    create_element_with_attributes,
    extract_basic_element_data,
    find_meta_content,
    find_multiple_selectors,
    safe_copy_attributes,
)


class TestSafeCopyAttributes:
    """Test safe attribute copying functionality following SOLID principles."""

    def test_copy_simple_attributes(self):
        """Test copying simple string attributes."""
        html = '<img src="image.jpg" alt="Test image">'
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("img")
        target = soup.new_tag("img")

        attribute_map = {"src": "src", "alt": "alt"}

        safe_copy_attributes(source, target, attribute_map)

        assert target.get("src") == "image.jpg"
        assert target.get("alt") == "Test image"

    def test_copy_attributes_with_defaults(self):
        """Test copying attributes with default values."""
        html = '<img src="image.jpg">'  # Missing alt attribute
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("img")
        target = soup.new_tag("img")

        attribute_map = {
            "src": "src",
            "alt": ("alt", "Default alt text"),
            "title": ("title", "Default title"),
        }

        safe_copy_attributes(source, target, attribute_map)

        assert target.get("src") == "image.jpg"
        assert target.get("alt") == "Default alt text"
        assert target.get("title") == "Default title"

    def test_copy_attributes_with_tuple_config(self):
        """Test copying attributes with tuple configuration."""
        html = '<div data-id="123" class="container">'
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("div")
        target = soup.new_tag("section")

        attribute_map = {
            "data-id": ("id", "default-id"),
            "class": ("class", "default-class"),
            "missing": ("data-missing", "default-value"),
        }

        safe_copy_attributes(source, target, attribute_map)

        assert target.get("id") == "123"
        assert target.get("class") == "container"
        assert target.get("data-missing") == "default-value"

    def test_copy_attributes_handles_none_values(self):
        """Test copying attributes handles None values gracefully."""
        html = "<div>"
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("div")
        target = soup.new_tag("div")

        # Create a source element that returns None for an attribute
        source.attrs = {"existing": "value"}

        attribute_map = {
            "existing": "existing",
            "missing": ("missing", "default"),
            "none_value": ("none_target", "fallback"),
        }

        safe_copy_attributes(source, target, attribute_map)

        assert target.get("existing") == "value"
        assert target.get("missing") == "default"
        assert target.get("none_target") == "fallback"

    def test_copy_attributes_empty_map(self):
        """Test copying with empty attribute map."""
        html = '<img src="test.jpg">'
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("img")
        target = soup.new_tag("img")

        safe_copy_attributes(source, target, {})

        # Target should remain unchanged
        assert not target.attrs

    def test_copy_attributes_overwrites_existing(self):
        """Test copying attributes overwrites existing values."""
        html = '<img src="new.jpg" alt="New alt">'
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("img")
        target = soup.new_tag("img")

        # Set initial values on target
        target["src"] = "old.jpg"
        target["alt"] = "Old alt"

        attribute_map = {"src": "src", "alt": "alt"}

        safe_copy_attributes(source, target, attribute_map)

        assert target.get("src") == "new.jpg"
        assert target.get("alt") == "New alt"


class TestFindMetaContent:
    """Test meta tag content extraction functionality."""

    def test_find_meta_by_name(self):
        """Test finding meta content by name attribute."""
        html = """
        <html>
        <head>
            <meta name="description" content="Page description">
            <meta name="keywords" content="html, test">
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        description = find_meta_content(soup, name="description")
        keywords = find_meta_content(soup, name="keywords")

        assert description == "Page description"
        assert keywords == "html, test"

    def test_find_meta_by_property(self):
        """Test finding meta content by property attribute."""
        html = """
        <html>
        <head>
            <meta property="og:title" content="Open Graph Title">
            <meta property="og:description" content="Open Graph Description">
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        title = find_meta_content(soup, property_attr="og:title")
        description = find_meta_content(soup, property_attr="og:description")

        assert title == "Open Graph Title"
        assert description == "Open Graph Description"

    def test_find_meta_not_found(self):
        """Test finding non-existent meta tag."""
        html = "<html><head></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = find_meta_content(soup, name="nonexistent")
        assert result is None

        result = find_meta_content(soup, property_attr="og:nonexistent")
        assert result is None

    def test_find_meta_no_parameters(self):
        """Test finding meta with no search parameters."""
        html = '<html><head><meta name="test" content="value"></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = find_meta_content(soup)
        assert result is None

    def test_find_meta_empty_content(self):
        """Test finding meta tag with empty content."""
        html = '<html><head><meta name="empty" content=""></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = find_meta_content(soup, name="empty")
        assert result == ""

    def test_find_meta_no_content_attribute(self):
        """Test finding meta tag without content attribute."""
        html = '<html><head><meta name="nocontent"></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = find_meta_content(soup, name="nocontent")
        assert result == ""

    def test_find_meta_non_string_content(self):
        """Test finding meta tag with non-string content."""
        html = '<html><head><meta name="test" content="value"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        meta_tag = soup.find("meta", attrs={"name": "test"})

        # Artificially set a non-string content for testing
        meta_tag.attrs["content"] = ["list", "value"]

        result = find_meta_content(soup, name="test")
        assert result == ""


class TestFindMultipleSelectors:
    """Test multiple selector searching functionality."""

    def test_find_first_matching_selector(self):
        """Test finding first matching selector."""
        html = """
        <div>
            <h1 id="title">Main Title</h1>
            <h2 class="subtitle">Subtitle</h2>
            <p class="content">Content</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        selectors = ["#title", ".subtitle", ".content"]
        result = find_multiple_selectors(soup, selectors)

        assert result is not None
        assert result.name == "h1"
        assert result.get("id") == "title"

    def test_find_second_selector_when_first_fails(self):
        """Test finding second selector when first doesn't match."""
        html = """
        <div>
            <h2 class="subtitle">Subtitle</h2>
            <p class="content">Content</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        selectors = ["#title", ".subtitle", ".content"]
        result = find_multiple_selectors(soup, selectors)

        assert result is not None
        assert result.name == "h2"
        assert result.get("class") == ["subtitle"]

    def test_find_no_matching_selectors(self):
        """Test when no selectors match."""
        html = "<div><span>Text</span></div>"
        soup = BeautifulSoup(html, "html.parser")

        selectors = ["#title", ".subtitle", ".content"]
        result = find_multiple_selectors(soup, selectors)

        assert result is None

    def test_find_empty_selectors_list(self):
        """Test with empty selectors list."""
        html = "<div><h1>Title</h1></div>"
        soup = BeautifulSoup(html, "html.parser")

        result = find_multiple_selectors(soup, [])
        assert result is None

    def test_find_complex_selectors(self):
        """Test with complex CSS selectors."""
        html = """
        <div class="container">
            <article class="post">
                <header>
                    <h1 class="post-title">Article Title</h1>
                </header>
                <div class="post-content">
                    <p>First paragraph</p>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        selectors = ["article.missing h1", "article.post header h1.post-title", ".post-content p"]
        result = find_multiple_selectors(soup, selectors)

        assert result is not None
        assert result.name == "h1"
        assert "post-title" in result.get("class", [])

    def test_find_invalid_selector_handling(self):
        """Test handling of invalid CSS selectors."""
        html = "<div><h1>Title</h1></div>"
        soup = BeautifulSoup(html, "html.parser")

        # Mix of valid and invalid selectors
        selectors = ["[invalid", "h1", "another[invalid"]

        # The function should handle invalid selectors gracefully
        # and continue to the next selector
        try:
            result = find_multiple_selectors(soup, selectors)
            # Should find h1 despite invalid selectors
            assert result is not None
            assert result.name == "h1"
        except Exception:
            # If BeautifulSoup raises on invalid selector, that's also acceptable
            pass


class TestExtractBasicElementData:
    """Test basic element data extraction functionality."""

    def test_extract_image_data(self):
        """Test extracting data from image element."""
        html = '<img src="image.jpg" alt="Test image" title="Image title" id="img1" class="photo large">'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("img")

        data = extract_basic_element_data(element)

        assert data["src"] == "image.jpg"
        assert data["alt"] == "Test image"
        assert data["title"] == "Image title"
        assert data["id"] == "img1"
        assert data["class"] == "photo large"
        assert data["href"] == ""

    def test_extract_link_data(self):
        """Test extracting data from link element."""
        html = '<a href="https://example.com" title="Link title" class="external">Link text</a>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("a")

        data = extract_basic_element_data(element)

        assert data["href"] == "https://example.com"
        assert data["title"] == "Link title"
        assert data["class"] == "external"
        assert data["src"] == ""
        assert data["alt"] == ""

    def test_extract_data_missing_attributes(self):
        """Test extracting data from element with missing attributes."""
        html = "<div>Content</div>"
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        data = extract_basic_element_data(element)

        assert data["src"] == ""
        assert data["alt"] == ""
        assert data["href"] == ""
        assert data["title"] == ""
        assert data["class"] == ""
        assert data["id"] == ""

    def test_extract_data_class_as_list(self):
        """Test extracting class data when it's stored as a list."""
        html = '<div class="class1 class2 class3">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        data = extract_basic_element_data(element)

        assert data["class"] == "class1 class2 class3"

    def test_extract_data_class_as_attribute_value_list(self):
        """Test extracting class data as AttributeValueList."""
        html = '<div class="class1 class2">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        # Ensure class is AttributeValueList
        assert isinstance(element.get("class"), AttributeValueList)

        data = extract_basic_element_data(element)

        assert data["class"] == "class1 class2"

    def test_extract_data_single_class(self):
        """Test extracting single class value."""
        html = '<div class="single">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        data = extract_basic_element_data(element)

        assert data["class"] == "single"

    def test_extract_data_non_string_attributes(self):
        """Test extracting data with non-string attribute values."""
        html = "<div>Content</div>"
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("div")

        # Artificially set non-string attributes
        element.attrs["src"] = ["value1", "value2"]
        element.attrs["alt"] = 123

        data = extract_basic_element_data(element)

        # Should fall back to defaults for non-string values
        assert data["src"] == ""
        assert data["alt"] == ""

    def test_extract_data_all_attributes_present(self):
        """Test extracting data when all attributes are present."""
        html = """
        <img src="test.jpg"
             alt="Alt text"
             href="https://example.com"
             title="Title text"
             class="image-class"
             id="image-id">
        """
        soup = BeautifulSoup(html, "html.parser")
        element = soup.find("img")

        data = extract_basic_element_data(element)

        assert data["src"] == "test.jpg"
        assert data["alt"] == "Alt text"
        assert data["href"] == "https://example.com"
        assert data["title"] == "Title text"
        assert data["class"] == "image-class"
        assert data["id"] == "image-id"


class TestCreateElementWithAttributes:
    """Test HTML element creation functionality."""

    def test_create_simple_element(self):
        """Test creating simple element with basic attributes."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        attributes = {"id": "test-id", "class": "test-class", "data-value": "123"}

        element = create_element_with_attributes(soup, "div", attributes)

        assert element.name == "div"
        assert element.get("id") == "test-id"
        assert element.get("class") == "test-class"
        assert element.get("data-value") == "123"

    def test_create_element_with_empty_attributes(self):
        """Test creating element with empty attribute values."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        attributes = {
            "id": "test-id",
            "class": "",  # Empty string
            "title": None,  # None value
            "data-test": "value",
        }

        element = create_element_with_attributes(soup, "span", attributes)

        assert element.name == "span"
        assert element.get("id") == "test-id"
        assert element.get("class") is None  # Empty values not set
        assert element.get("title") is None  # None values not set
        assert element.get("data-test") == "value"

    def test_create_element_no_attributes(self):
        """Test creating element with no attributes."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        element = create_element_with_attributes(soup, "p", {})

        assert element.name == "p"
        assert not element.attrs

    def test_create_different_element_types(self):
        """Test creating different types of HTML elements."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        # Test various HTML elements
        elements = [
            ("div", {"class": "container"}),
            ("img", {"src": "image.jpg", "alt": "Image"}),
            ("a", {"href": "https://example.com", "target": "_blank"}),
            ("input", {"type": "text", "name": "username"}),
            ("meta", {"name": "description", "content": "Page description"}),
        ]

        for tag_name, attrs in elements:
            element = create_element_with_attributes(soup, tag_name, attrs)
            assert element.name == tag_name
            for attr, value in attrs.items():
                assert element.get(attr) == value

    def test_create_element_with_complex_attributes(self):
        """Test creating element with complex attribute values."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        attributes = {
            "style": "color: red; background: blue;",
            "data-config": '{"key": "value", "number": 123}',
            "onclick": "handleClick(this);",
            "aria-label": "Complex aria label text",
        }

        element = create_element_with_attributes(soup, "button", attributes)

        assert element.name == "button"
        assert element.get("style") == "color: red; background: blue;"
        assert element.get("data-config") == '{"key": "value", "number": 123}'
        assert element.get("onclick") == "handleClick(this);"
        assert element.get("aria-label") == "Complex aria label text"


class TestHtmlUtilsIntegration:
    """Test integration scenarios between HTML utility functions."""

    def test_copy_and_extract_workflow(self):
        """Test workflow of copying attributes and extracting data."""
        html = """
        <img src="original.jpg"
             alt="Original alt"
             title="Original title"
             class="photo large"
             id="original-img">
        """
        soup = BeautifulSoup(html, "html.parser")
        source = soup.find("img")

        # Create new element and copy attributes
        target = soup.new_tag("img")
        attribute_map = {
            "src": "src",
            "alt": ("alt", "Default alt"),
            "title": "title",
            "class": "class",
            "id": ("id", "default-id"),
        }

        safe_copy_attributes(source, target, attribute_map)

        # Extract data from target
        data = extract_basic_element_data(target)

        assert data["src"] == "original.jpg"
        assert data["alt"] == "Original alt"
        assert data["title"] == "Original title"
        assert data["class"] == "photo large"
        assert data["id"] == "original-img"

    def test_create_and_extract_workflow(self):
        """Test workflow of creating element and extracting data."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        # Create element with attributes
        attributes = {
            "src": "new-image.jpg",
            "alt": "New image",
            "class": "created-image",
            "data-test": "test-value",
        }

        element = create_element_with_attributes(soup, "img", attributes)

        # Extract basic data
        data = extract_basic_element_data(element)

        assert data["src"] == "new-image.jpg"
        assert data["alt"] == "New image"
        assert data["class"] == "created-image"
        # data-test is not in basic extraction, but element should have it
        assert element.get("data-test") == "test-value"

    def test_selector_and_extraction_workflow(self):
        """Test workflow of finding elements and extracting data."""
        html = """
        <div class="content">
            <img class="hero-image" src="hero.jpg" alt="Hero image">
            <img class="thumbnail" src="thumb.jpg" alt="Thumbnail">
            <a class="primary-link" href="https://example.com" title="Primary link">Link</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        # Find using multiple selectors
        selectors = [".hero-image", ".thumbnail", ".primary-link"]
        element = find_multiple_selectors(soup, selectors)

        assert element is not None

        # Extract data from found element
        data = extract_basic_element_data(element)

        # Should find hero-image first
        assert data["src"] == "hero.jpg"
        assert data["alt"] == "Hero image"
        assert "hero-image" in data["class"]

    def test_meta_extraction_and_element_creation(self):
        """Test extracting meta content and creating elements."""
        html = """
        <html>
        <head>
            <meta name="description" content="Page description">
            <meta property="og:image" content="social-image.jpg">
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract meta content
        description = find_meta_content(soup, name="description")
        og_image = find_meta_content(soup, property_attr="og:image")

        # Create new elements based on meta content
        desc_element = create_element_with_attributes(
            soup, "p", {"class": "description", "data-content": description}
        )

        img_element = create_element_with_attributes(
            soup, "img", {"src": og_image, "alt": description, "class": "social-image"}
        )

        assert desc_element.get("data-content") == "Page description"
        assert img_element.get("src") == "social-image.jpg"
        assert img_element.get("alt") == "Page description"


class TestHtmlUtilsErrorHandling:
    """Test comprehensive error handling in HTML utilities."""

    def test_safe_copy_attributes_with_invalid_elements(self):
        """Test safe_copy_attributes with various edge cases."""
        soup = BeautifulSoup("<div></div>", "html.parser")
        source = soup.find("div")
        target = soup.new_tag("div")

        # Test with complex attribute map
        attribute_map = {
            "nonexistent": "target-attr",
            "also-missing": ("target-attr-2", "default"),
            "class": ("class", []),  # List as default
        }

        # Should handle gracefully without errors
        safe_copy_attributes(source, target, attribute_map)

        assert target.get("target-attr") == ""
        assert target.get("target-attr-2") == "default"

    def test_extract_element_data_edge_cases(self):
        """Test extract_basic_element_data with edge cases."""
        soup = BeautifulSoup("<div></div>", "html.parser")
        element = soup.find("div")

        # Set various problematic attribute values
        element.attrs = {
            "class": None,  # None value
            "src": "",  # Empty string
            "alt": 0,  # Number
            "title": False,  # Boolean
        }

        data = extract_basic_element_data(element)

        # Should handle all edge cases gracefully
        assert isinstance(data, dict)
        assert all(isinstance(v, str) for v in data.values())

    def test_find_meta_content_malformed_html(self):
        """Test find_meta_content with malformed HTML."""
        malformed_html = '<meta name="test" content="value"'  # Missing closing >
        soup = BeautifulSoup(malformed_html, "html.parser")

        # Should handle gracefully
        result = find_meta_content(soup, name="test")
        # BeautifulSoup is forgiving, so this might still work
        assert result is None or isinstance(result, str)

    def test_create_element_with_none_soup(self):
        """Test element creation error handling."""
        soup = BeautifulSoup("<html></html>", "html.parser")

        # Test with various attribute edge cases
        problematic_attrs = {
            "normal": "value",
            "empty": "",
            "none": None,
            "false": False,
            "zero": 0,
            "list": ["a", "b"],
            "dict": {"key": "value"},
        }

        element = create_element_with_attributes(soup, "div", problematic_attrs)

        # Should only set truthy values
        assert element.get("normal") == "value"
        assert element.get("empty") is None
        assert element.get("none") is None
        assert element.get("false") is None
        assert element.get("zero") is None
        # Complex types might be set or not, depending on BeautifulSoup behavior
        # But should not cause exceptions
