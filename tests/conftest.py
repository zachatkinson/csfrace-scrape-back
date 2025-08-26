"""Shared fixtures and test configuration for pytest."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from src.caching.base import CacheConfig
from src.caching.file_cache import FileCache
from src.constants import TEST_CONSTANTS


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for testing."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    return session


@pytest.fixture
def mock_responses():
    """Mock HTTP responses with aioresponses."""
    with aioresponses() as m:
        yield m


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def cache_config(temp_dir):
    """Create test cache configuration."""
    return CacheConfig(
        cache_dir=temp_dir / ".test_cache",
        ttl_default=30,  # Short TTL for testing
        max_cache_size_mb=10,  # Small cache for testing
        redis_host=TEST_CONSTANTS.TEST_REDIS_HOST,
        redis_port=TEST_CONSTANTS.TEST_REDIS_PORT,
        redis_db=TEST_CONSTANTS.TEST_REDIS_DB,
        redis_key_prefix=TEST_CONSTANTS.TEST_REDIS_KEY_PREFIX,
        cleanup_on_startup=True,
    )


@pytest_asyncio.fixture
async def file_cache(cache_config):
    """Create test file cache instance."""
    cache = FileCache(cache_config)
    # FileCache initializes in constructor, no separate initialize method needed
    yield cache
    await cache.cleanup_expired()
    await cache.clear()


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Blog Post</title>
        <meta name="description" content="A test blog post for unit testing">
        <meta property="og:title" content="OG Test Title">
        <meta property="og:description" content="OG test description">
    </head>
    <body>
        <article class="wp-block-group">
            <h1>Test Blog Post</h1>
            <div class="wp-block-columns">
                <div class="wp-block-column">
                    <p><strong>Bold text</strong> and <em>italic text</em></p>
                    <p style="text-align: center;">Centered text</p>
                </div>
            </div>
            <figure class="wp-block-image">
                <img src="/test-image.jpg" alt="Test image" title="Test Title">
                <figcaption>Test image caption</figcaption>
            </figure>
            <div class="wp-block-buttons">
                <div class="wp-block-button">
                    <a class="wp-block-button__link" href="/test-link">Test Button</a>
                </div>
            </div>
            <blockquote class="wp-block-quote">
                <p>Test quote content</p>
                <cite>Test Author</cite>
            </blockquote>
            <figure class="wp-block-embed wp-block-embed-youtube">
                <div class="wp-block-embed__wrapper">
                    <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
                </div>
            </figure>
        </article>
        <script>console.log('test');</script>
    </body>
    </html>
    """


@pytest.fixture
def sample_soup(sample_html):
    """BeautifulSoup object from sample HTML."""
    return BeautifulSoup(sample_html, "html.parser")


@pytest.fixture
def sample_metadata():
    """Sample metadata dictionary."""
    return {
        "title": TEST_CONSTANTS.SAMPLE_HTML_TITLE,
        "description": TEST_CONSTANTS.SAMPLE_HTML_DESCRIPTION,
        "url": TEST_CONSTANTS.SAMPLE_POST_URL,
        "og_title": "OG Test Title",
        "og_description": "OG test description",
        "word_count": 50,
        "reading_time": 1,
        "images": ["/test-image.jpg"],
    }


@pytest.fixture
def sample_image_data():
    """Sample image data for testing."""
    return TEST_CONSTANTS.TEST_IMAGE_CONTENT


@pytest.fixture
def sample_wordpress_content():
    """Sample WordPress content with various blocks."""
    return """
    <div class="wp-block-group">
        <div class="wp-block-kadence-spacer"></div>
        <div class="wp-block-columns">
            <div class="wp-block-column">
                <p style="font-size: 18px; color: #333;">Custom styled text</p>
                <p class="has-text-align-center">Centered paragraph</p>
            </div>
        </div>
        <div class="wp-block-gallery">
            <figure><img src="/image1.jpg" alt="Image 1"></figure>
            <figure><img src="/image2.jpg" alt="Image 2"></figure>
        </div>
        <div class="wp-block-buttons">
            <div class="wp-block-button is-style-fill">
                <a class="wp-block-button__link has-vivid-red-background-color" href="/action">
                    Action Button
                </a>
            </div>
        </div>
    </div>
    """


@pytest.fixture
def mock_wordpress_server(mock_responses):
    """Mock WordPress server responses."""
    # Mock robots.txt
    mock_responses.get(
        f"{TEST_CONSTANTS.BASE_TEST_URL}/robots.txt", body="User-agent: *\nAllow: /\nCrawl-delay: 1"
    )

    # Mock sample post
    mock_responses.get(
        TEST_CONSTANTS.SAMPLE_POST_URL,
        body="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sample WordPress Post</title>
            <meta name="description" content="Sample post content">
        </head>
        <body>
            <article>
                <h1>Sample Post</h1>
                <p>This is sample content.</p>
            </article>
        </body>
        </html>
        """,
    )

    # Mock image
    mock_responses.get(
        f"{TEST_CONSTANTS.BASE_TEST_URL}{TEST_CONSTANTS.SAMPLE_IMAGE_URL}",
        body=TEST_CONSTANTS.TEST_IMAGE_CONTENT,
        headers={"Content-Type": "image/jpeg"},
    )

    return mock_responses


@pytest.fixture
def plugin_config():
    """Sample plugin configuration."""
    from src.plugins.base import PluginConfig, PluginType

    return PluginConfig(
        name="test_plugin",
        version="1.0.0",
        plugin_type=PluginType.HTML_PROCESSOR,
        enabled=True,
        priority=100,
        settings={"test_setting": "test_value"},
    )


@pytest_asyncio.fixture
async def mock_redis_cache():
    """Mock Redis cache for testing."""
    try:
        from src.caching.redis_cache import RedisCache

        cache = MagicMock(spec=RedisCache)
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=True)
        cache.clear = AsyncMock(return_value=True)
        cache.stats = AsyncMock(return_value={"hits": 0, "misses": 0, "total_entries": 0})
        return cache
    except ImportError:
        # Redis not available, return None
        return None


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "redis: marks tests that require Redis")


# Skip Redis tests if not available
def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle missing dependencies."""
    import importlib.util

    redis_available = importlib.util.find_spec("redis") is not None

    if not redis_available:
        skip_redis = pytest.mark.skip(reason="Redis not available")
        for item in items:
            if "redis" in item.keywords:
                item.add_marker(skip_redis)
