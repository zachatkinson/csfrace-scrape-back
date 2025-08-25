"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock

import aiohttp
import pytest
from bs4 import BeautifulSoup

from src.core.converter import AsyncWordPressConverter
from src.processors.html_processor import HTMLProcessor
from src.processors.image_downloader import AsyncImageDownloader
from src.processors.metadata_extractor import MetadataExtractor


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_html() -> str:
    """Sample WordPress HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Blog Post</title>
        <meta name="description" content="A test blog post for unit testing">
        <meta property="article:published_time" content="2024-01-15T10:00:00Z">
    </head>
    <body>
        <div class="entry-content">
            <p>This is a test paragraph with <b>bold</b> and <i>italic</i> text.</p>
            
            <div class="has-text-align-center">
                <p>Centered text content</p>
            </div>
            
            <div class="wp-block-kadence-rowlayout">
                <div class="kt-has-2-columns">
                    <div class="wp-block-kadence-column">
                        <div class="kt-inside-inner-col">
                            <h3>Column 1 Title</h3>
                            <p>Column 1 content</p>
                        </div>
                    </div>
                    <div class="wp-block-kadence-column">
                        <div class="kt-inside-inner-col">
                            <h3>Column 2 Title</h3>
                            <p>Column 2 content</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="wp-block-image">
                <img src="/test-image.jpg" alt="Test image">
            </div>
            
            <div class="wp-block-kadence-advancedbtn">
                <a class="button" href="https://external-site.com">External Link</a>
            </div>
            
            <figure class="wp-block-pullquote">
                <blockquote>
                    <p>This is a test quote</p>
                    <cite>Test Author</cite>
                </blockquote>
            </figure>
            
            <figure class="wp-block-embed-youtube">
                <div class="wp-block-embed__wrapper">
                    <iframe src="https://www.youtube.com/embed/test123" title="Test Video"></iframe>
                </div>
                <figcaption>Test video caption</figcaption>
            </figure>
            
            <script>alert('This should be removed');</script>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_soup(sample_html: str) -> BeautifulSoup:
    """BeautifulSoup object from sample HTML."""
    return BeautifulSoup(sample_html, "html.parser")


@pytest.fixture
def html_processor() -> HTMLProcessor:
    """HTML processor instance."""
    return HTMLProcessor()


@pytest.fixture
def metadata_extractor() -> MetadataExtractor:
    """Metadata extractor instance."""
    return MetadataExtractor("https://test.example.com/blog/test-post")


@pytest.fixture
def image_downloader(temp_dir: Path) -> AsyncImageDownloader:
    """Image downloader instance with temporary directory."""
    return AsyncImageDownloader(temp_dir / "images", max_concurrent=2)


@pytest.fixture
async def mock_session() -> AsyncGenerator[AsyncMock, None]:
    """Mock aiohttp session for testing."""
    session = AsyncMock(spec=aiohttp.ClientSession)

    # Mock response for successful requests
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = "test response"
    mock_response.content_length = 1024
    mock_response.headers = {"content-type": "image/jpeg"}
    mock_response.content.iter_chunked.return_value = [b"test data"]

    session.get.return_value.__aenter__.return_value = mock_response

    yield session


@pytest.fixture
def converter(temp_dir: Path) -> AsyncWordPressConverter:
    """Async converter instance with temporary directory."""
    return AsyncWordPressConverter(
        base_url="https://test.example.com/blog/test-post", output_dir=temp_dir
    )


@pytest.fixture
def mock_robots_content() -> str:
    """Sample robots.txt content for testing."""
    return """
User-agent: *
Disallow: /admin/
Disallow: /private/
Crawl-delay: 2

User-agent: Googlebot
Crawl-delay: 1

User-agent: BadBot
Disallow: /
    """


@pytest.fixture
def image_urls() -> list[str]:
    """Sample image URLs for testing."""
    return [
        "https://test.example.com/image1.jpg",
        "https://test.example.com/image2.png",
        "https://test.example.com/image3.webp",
    ]


# Pytest marks for different test categories
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
