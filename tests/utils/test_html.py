"""Unit tests for HTML utilities module."""

import pytest
from bs4 import BeautifulSoup

from src.utils.html import (
    create_element_with_attributes,
    extract_basic_element_data,
    find_meta_content,
    find_multiple_selectors,
    safe_copy_attributes,
)


class TestHTMLUtilities:
    """Test HTML utility functions."""

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content for testing."""
        return """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
            <meta property="og:title" content="OG Title">
            <meta name="keywords" content="test, html">
        </head>
        <body>
            <h1 class="main-title" id="title">Main Title</h1>
            <div class="content">
                <p>Test paragraph</p>
                <img src="image.jpg" alt="Test Image" title="Image Title">
                <a href="https://example.com" title="Link Title">Link</a>
            </div>
        </body>
        </html>
        """

    @pytest.fixture
    def soup(self, sample_html):
        """BeautifulSoup object for testing."""
        return BeautifulSoup(sample_html, "html.parser")

    def test_safe_copy_attributes_basic(self, soup):
        """Test basic attribute copying."""
        img = soup.find("img")
        new_img = soup.new_tag("img")
        
        safe_copy_attributes(img, new_img, {
            "src": "src",
            "alt": "alt",
            "title": "title"
        })
        
        assert new_img["src"] == "image.jpg"
        assert new_img["alt"] == "Test Image"
        assert new_img["title"] == "Image Title"

    def test_safe_copy_attributes_with_defaults(self, soup):
        """Test attribute copying with default values."""
        img = soup.find("img")
        new_img = soup.new_tag("img")
        
        safe_copy_attributes(img, new_img, {
            "src": "src",
            "alt": ("alt", "No description"),
            "missing": ("data-missing", "default_value")
        })
        
        assert new_img["src"] == "image.jpg"
        assert new_img["alt"] == "Test Image"
        assert new_img["data-missing"] == "default_value"

    def test_find_meta_content_by_name(self, soup):
        """Test finding meta content by name attribute."""
        description = find_meta_content(soup, name="description")
        keywords = find_meta_content(soup, name="keywords")
        missing = find_meta_content(soup, name="missing")
        
        assert description == "Test description"
        assert keywords == "test, html"
        assert missing is None

    def test_find_meta_content_by_property(self, soup):
        """Test finding meta content by property attribute."""
        og_title = find_meta_content(soup, property="og:title")
        missing = find_meta_content(soup, property="og:missing")
        
        assert og_title == "OG Title"
        assert missing is None

    def test_find_meta_content_no_params(self, soup):
        """Test find_meta_content with no parameters."""
        result = find_meta_content(soup)
        assert result is None

    def test_find_multiple_selectors_first_match(self, soup):
        """Test finding element with first matching selector."""
        selectors = ["h2", "h1", "h3"]
        element = find_multiple_selectors(soup, selectors)
        
        assert element is not None
        assert element.name == "h1"
        assert element.get_text() == "Main Title"

    def test_find_multiple_selectors_no_match(self, soup):
        """Test finding element when no selectors match."""
        selectors = ["h2", "h3", "h4"]
        element = find_multiple_selectors(soup, selectors)
        
        assert element is None

    def test_find_multiple_selectors_complex(self, soup):
        """Test finding element with complex selectors."""
        selectors = ["div.missing", "div.content p", "span"]
        element = find_multiple_selectors(soup, selectors)
        
        assert element is not None
        assert element.name == "p"
        assert element.get_text() == "Test paragraph"

    def test_extract_basic_element_data_img(self, soup):
        """Test extracting data from img element."""
        img = soup.find("img")
        data = extract_basic_element_data(img)
        
        assert data["src"] == "image.jpg"
        assert data["alt"] == "Test Image"
        assert data["title"] == "Image Title"
        assert data["href"] == ""  # Not an anchor
        assert data["class"] == ""
        assert data["id"] == ""

    def test_extract_basic_element_data_anchor(self, soup):
        """Test extracting data from anchor element."""
        anchor = soup.find("a")
        data = extract_basic_element_data(anchor)
        
        assert data["href"] == "https://example.com"
        assert data["title"] == "Link Title"
        assert data["src"] == ""  # Not an image
        assert data["alt"] == ""
        assert data["class"] == ""
        assert data["id"] == ""

    def test_extract_basic_element_data_with_class_and_id(self, soup):
        """Test extracting data from element with class and id."""
        h1 = soup.find("h1")
        data = extract_basic_element_data(h1)
        
        assert data["class"] == "main-title"
        assert data["id"] == "title"
        assert data["src"] == ""
        assert data["href"] == ""
        assert data["alt"] == ""
        assert data["title"] == ""

    def test_extract_basic_element_data_multiple_classes(self):
        """Test extracting data from element with multiple classes."""
        html = '<div class="class1 class2 class3">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        div = soup.find("div")
        
        data = extract_basic_element_data(div)
        assert data["class"] == "class1 class2 class3"

    def test_create_element_with_attributes(self, soup):
        """Test creating element with attributes."""
        attributes = {
            "src": "test.jpg",
            "alt": "Test image",
            "class": "image-class",
            "id": "test-img"
        }
        
        img = create_element_with_attributes(soup, "img", attributes)
        
        assert img.name == "img"
        assert img["src"] == "test.jpg"
        assert img["alt"] == "Test image"
        assert img["class"] == "image-class"
        assert img["id"] == "test-img"

    def test_create_element_with_empty_attributes(self, soup):
        """Test creating element with empty attributes."""
        attributes = {
            "src": "test.jpg",
            "alt": "",  # Empty value should not be set
            "title": None,  # None value should not be set
            "class": "image-class"
        }
        
        img = create_element_with_attributes(soup, "img", attributes)
        
        assert img["src"] == "test.jpg"
        assert img["class"] == "image-class"
        assert "alt" not in img.attrs
        assert "title" not in img.attrs

    def test_create_element_no_attributes(self, soup):
        """Test creating element with no attributes."""
        div = create_element_with_attributes(soup, "div", {})
        
        assert div.name == "div"
        assert len(div.attrs) == 0

    def test_utilities_with_empty_soup(self):
        """Test utilities with empty HTML."""
        soup = BeautifulSoup("", "html.parser")
        
        assert find_meta_content(soup, name="description") is None
        assert find_multiple_selectors(soup, ["p", "div"]) is None
        
        # These should still work with empty soup
        element = create_element_with_attributes(soup, "div", {"class": "test"})
        assert element.name == "div"
        assert element["class"] == "test"