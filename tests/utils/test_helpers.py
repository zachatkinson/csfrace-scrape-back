"""Test helper functions and utilities."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
from bs4 import BeautifulSoup

from src.constants import TEST_CONSTANTS


class MockHTTPResponse:
    """Mock HTTP response for testing."""

    def __init__(self, status: int = 200, content: str = "", headers: dict[str, str] = None):
        self.status = status
        self.content = content
        self.headers = headers or {}
        self.text_content = content

    async def text(self) -> str:
        """Return response text."""
        return self.text_content

    async def read(self) -> bytes:
        """Return response bytes."""
        return self.content.encode('utf-8') if isinstance(self.content, str) else self.content

    def raise_for_status(self):
        """Raise exception for HTTP error status codes."""
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=None,
                history=None,
                status=self.status
            )


class AsyncContextManager:
    """Helper for creating async context managers in tests."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_mock_session(responses: dict[str, MockHTTPResponse]) -> AsyncMock:
    """Create mock aiohttp session with predefined responses.
    
    Args:
        responses: Dict mapping URLs to MockHTTPResponse objects
    
    Returns:
        Mock session that returns appropriate responses for URLs
    """
    session = AsyncMock(spec=aiohttp.ClientSession)

    def get_response(url, **kwargs):
        if url in responses:
            return AsyncContextManager(responses[url])
        else:
            # Default 404 response for unmocked URLs
            return AsyncContextManager(MockHTTPResponse(404, "Not Found"))

    session.get.side_effect = get_response
    return session


def create_sample_soup(content: str = None) -> BeautifulSoup:
    """Create BeautifulSoup object from sample or provided content.
    
    Args:
        content: HTML content string, uses default if None
    
    Returns:
        BeautifulSoup object
    """
    if content is None:
        content = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Test Heading</h1>
            <p>Test paragraph with <strong>bold</strong> text.</p>
        </body>
        </html>
        """

    return BeautifulSoup(content, "html.parser")


def assert_html_contains(html: str, expected_elements: list[str]):
    """Assert that HTML contains expected elements.
    
    Args:
        html: HTML string to check
        expected_elements: List of expected element selectors or text content
    """
    soup = BeautifulSoup(html, "html.parser")

    for element in expected_elements:
        if element.startswith('.') or element.startswith('#') or element in ['p', 'h1', 'h2', 'div']:
            # CSS selector
            assert soup.select(element), f"Element '{element}' not found in HTML"
        else:
            # Text content
            assert element in html, f"Text '{element}' not found in HTML"


def assert_html_not_contains(html: str, unwanted_elements: list[str]):
    """Assert that HTML does not contain unwanted elements.
    
    Args:
        html: HTML string to check
        unwanted_elements: List of unwanted element selectors or text content
    """
    soup = BeautifulSoup(html, "html.parser")

    for element in unwanted_elements:
        if element.startswith('.') or element.startswith('#') or element in ['script', 'style', 'noscript']:
            # CSS selector
            assert not soup.select(element), f"Unwanted element '{element}' found in HTML"
        else:
            # Text content
            assert element not in html, f"Unwanted text '{element}' found in HTML"


class TestDataGenerator:
    """Generate test data for various scenarios."""

    @staticmethod
    def create_wordpress_blocks() -> str:
        """Create sample WordPress blocks HTML."""
        return """
        <div class="wp-block-group">
            <div class="wp-block-columns">
                <div class="wp-block-column">
                    <p><strong>Bold text</strong> and <em>italic text</em></p>
                </div>
            </div>
            <figure class="wp-block-image">
                <img src="/test-image.jpg" alt="Test image">
            </figure>
            <div class="wp-block-buttons">
                <div class="wp-block-button">
                    <a class="wp-block-button__link" href="/test">Button</a>
                </div>
            </div>
        </div>
        """

    @staticmethod
    def create_kadence_layout() -> str:
        """Create sample Kadence layout HTML."""
        return """
        <div class="wp-block-kadence-rowlayout">
            <div class="kt-row-column-wrap">
                <div class="wp-block-kadence-column">
                    <p>Kadence column content</p>
                </div>
            </div>
        </div>
        """

    @staticmethod
    def create_image_gallery() -> str:
        """Create sample image gallery HTML."""
        return """
        <div class="wp-block-gallery">
            <figure><img src="/image1.jpg" alt="Image 1"></figure>
            <figure><img src="/image2.jpg" alt="Image 2"></figure>
            <figure><img src="/image3.jpg" alt="Image 3"></figure>
        </div>
        """

    @staticmethod
    def create_embed_content() -> str:
        """Create sample embed content HTML."""
        return """
        <figure class="wp-block-embed wp-block-embed-youtube">
            <div class="wp-block-embed__wrapper">
                <iframe src="https://www.youtube.com/embed/test123"></iframe>
            </div>
        </figure>
        <figure class="wp-block-embed wp-block-embed-instagram">
            <blockquote class="instagram-media">
                <a href="https://www.instagram.com/p/test/">Instagram post</a>
            </blockquote>
        </figure>
        """

    @staticmethod
    def create_complex_content() -> str:
        """Create complex content with multiple block types."""
        return f"""
        <article>
            {TestDataGenerator.create_wordpress_blocks()}
            {TestDataGenerator.create_kadence_layout()}
            {TestDataGenerator.create_image_gallery()}
            {TestDataGenerator.create_embed_content()}
            <blockquote class="wp-block-quote">
                <p>Sample quote</p>
                <cite>Author</cite>
            </blockquote>
        </article>
        """


class AsyncTestHelper:
    """Helper for async testing scenarios."""

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run coroutine with timeout.
        
        Args:
            coro: Coroutine to run
            timeout: Timeout in seconds
        
        Returns:
            Coroutine result
        
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        return await asyncio.wait_for(coro, timeout=timeout)

    @staticmethod
    async def simulate_delay(delay: float = 0.1):
        """Simulate async delay."""
        await asyncio.sleep(delay)

    @staticmethod
    def create_async_mock_with_return(return_value: Any) -> AsyncMock:
        """Create async mock that returns specific value."""
        mock = AsyncMock()
        mock.return_value = return_value
        return mock


class FileTestHelper:
    """Helper for file-related tests."""

    @staticmethod
    def create_temp_dir() -> Path:
        """Create temporary directory for testing."""
        return Path(tempfile.mkdtemp())

    @staticmethod
    def create_test_file(directory: Path, filename: str, content: str) -> Path:
        """Create test file with content.
        
        Args:
            directory: Directory to create file in
            filename: Name of file
            content: File content
        
        Returns:
            Path to created file
        """
        file_path = directory / filename
        file_path.write_text(content, encoding='utf-8')
        return file_path

    @staticmethod
    def create_test_image(directory: Path, filename: str = "test_image.jpg") -> Path:
        """Create test image file.
        
        Args:
            directory: Directory to create file in
            filename: Image filename
        
        Returns:
            Path to created image file
        """
        image_path = directory / filename
        # Create fake image data
        image_path.write_bytes(TEST_CONSTANTS.TEST_IMAGE_CONTENT)
        return image_path


class CacheTestHelper:
    """Helper for cache-related tests."""

    @staticmethod
    def create_cache_entry_data(key: str = "test_key", value: Any = "test_value") -> dict[str, Any]:
        """Create cache entry data dictionary.
        
        Args:
            key: Cache key
            value: Cache value
        
        Returns:
            Cache entry data dictionary
        """
        import time
        return {
            "key": key,
            "value": value,
            "created_at": time.time(),
            "ttl": 3600,
            "content_type": "generic",
            "size_bytes": len(str(value)),
            "compressed": False
        }


class PluginTestHelper:
    """Helper for plugin-related tests."""

    @staticmethod
    def create_mock_plugin_info(name: str = "test_plugin") -> dict[str, Any]:
        """Create mock plugin info dictionary.
        
        Args:
            name: Plugin name
        
        Returns:
            Plugin info dictionary
        """
        from src.plugins.base import PluginType

        return {
            "name": name,
            "version": "1.0.0",
            "description": f"Test plugin: {name}",
            "author": "Test Author",
            "plugin_type": PluginType.HTML_PROCESSOR
        }

    @staticmethod
    def create_processing_context(url: str = None) -> dict[str, Any]:
        """Create processing context for plugin testing.
        
        Args:
            url: Source URL
        
        Returns:
            Processing context dictionary
        """
        return {
            "url": url or TEST_CONSTANTS.SAMPLE_POST_URL,
            "timestamp": "2024-01-15T10:00:00Z",
            "user_agent": "test-converter/1.0",
            "processing_stage": "html_processing"
        }


def compare_html_structure(html1: str, html2: str, ignore_whitespace: bool = True) -> bool:
    """Compare HTML structure ignoring formatting differences.
    
    Args:
        html1: First HTML string
        html2: Second HTML string
        ignore_whitespace: Whether to ignore whitespace differences
    
    Returns:
        True if structures are equivalent
    """
    soup1 = BeautifulSoup(html1, "html.parser")
    soup2 = BeautifulSoup(html2, "html.parser")

    if ignore_whitespace:
        # Remove extra whitespace
        for soup in [soup1, soup2]:
            for text in soup.find_all(string=True):
                if text.strip():
                    text.replace_with(text.strip())
                else:
                    text.extract()

    return str(soup1) == str(soup2)


def extract_urls_from_html(html: str) -> list[str]:
    """Extract all URLs from HTML content.
    
    Args:
        html: HTML content
    
    Returns:
        List of URLs found in the HTML
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    # Extract from various elements
    for element in soup.find_all(['a', 'img', 'iframe', 'script', 'link']):
        for attr in ['href', 'src', 'data-src']:
            if element.get(attr):
                urls.append(element[attr])

    return urls


def count_html_elements(html: str, tag_name: str) -> int:
    """Count occurrences of specific HTML elements.
    
    Args:
        html: HTML content
        tag_name: HTML tag name to count
    
    Returns:
        Number of elements found
    """
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.find_all(tag_name))


def get_html_text_content(html: str) -> str:
    """Extract text content from HTML.
    
    Args:
        html: HTML content
    
    Returns:
        Extracted text content
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=' ', strip=True)


# Performance testing helpers
class PerformanceTestHelper:
    """Helper for performance testing."""

    @staticmethod
    def time_async_operation(operation):
        """Decorator to time async operations."""
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            result = await operation(*args, **kwargs)
            end_time = time.time()

            # Attach timing info to result if possible
            if hasattr(result, '__dict__'):
                result._execution_time = end_time - start_time

            return result
        return wrapper

    @staticmethod
    def create_large_html_content(element_count: int = 1000) -> str:
        """Create large HTML content for performance testing.
        
        Args:
            element_count: Number of elements to create
        
        Returns:
            Large HTML content string
        """
        elements = []
        for i in range(element_count):
            elements.append(f"<p>This is paragraph number {i} with some content.</p>")

        return f"<html><body>{''.join(elements)}</body></html>"

