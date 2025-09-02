"""Shared fixtures and test configuration for pytest."""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio
import structlog
from aioresponses import aioresponses
from bs4 import BeautifulSoup
from testcontainers.postgres import PostgresContainer

from src.caching.base import CacheConfig
from src.caching.file_cache import FileCache
from src.constants import TEST_CONSTANTS

# CRITICAL: Configure structlog IMMEDIATELY after imports to prevent warnings
# This prevents modules from caching loggers with default configuration
structlog.reset_defaults()
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        # NOTE: format_exc_info intentionally omitted per structlog best practices
        # Use plain_traceback to avoid warnings about pretty exception formatting
        structlog.dev.ConsoleRenderer(exception_formatter=structlog.dev.plain_traceback),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    context_class=dict,
    cache_logger_on_first_use=False,  # Don't cache during tests to allow reconfiguration
)


@pytest.fixture
def mock_sleep(monkeypatch):
    """Mock asyncio.sleep to return immediately for faster tests."""

    async def instant_sleep(delay):
        # Return immediately without actually sleeping
        # This significantly speeds up tests that simulate timing
        return None

    monkeypatch.setattr(asyncio, "sleep", instant_sleep)
    return instant_sleep


@pytest.fixture
def mock_time_sleep(monkeypatch):
    """Mock time.sleep to return immediately for faster tests."""

    def instant_sleep(delay):
        # Return immediately without actually sleeping
        return None

    monkeypatch.setattr(time, "sleep", instant_sleep)
    return instant_sleep


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """Create PostgreSQL connection for database tests.

    Uses GitHub Actions service container in CI, testcontainers locally.
    """
    import os

    # Check if running in CI with service container
    if all(
        env_var in os.environ for env_var in ["DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME"]
    ):
        # Use CI service container
        class CIPostgresContainer:
            def __init__(self):
                self.host = os.environ["DATABASE_HOST"]
                self.port = int(os.environ["DATABASE_PORT"])
                self.dbname = os.environ["DATABASE_NAME"]
                self.username = os.environ["DATABASE_USER"]
                self.password = os.environ["DATABASE_PASSWORD"]

            def get_container_host_ip(self):
                return self.host

            def get_exposed_port(self, port):
                return self.port

        yield CIPostgresContainer()
    else:
        # Use testcontainers for local development
        with PostgresContainer(
            image="postgres:17.6",
            dbname="test_db",
            username="test_user",
            password="test_password",
            port=5432,
        ) as postgres:
            # Use connection retry instead of sleep for container readiness
            max_retries = 30
            for _ in range(max_retries):
                try:
                    postgres.get_connection_url()
                    # Test actual connection
                    import psycopg2

                    conn = psycopg2.connect(postgres.get_connection_url())
                    conn.close()
                    break
                except Exception:
                    time.sleep(0.1)  # Very short sleep for retry
            yield postgres


@pytest.fixture(scope="session")
def postgres_engine(postgres_container):
    """Create SQLAlchemy engine connected to test container.

    Following DRY principles - reuses existing postgres_container fixture.
    """
    from sqlalchemy import create_engine

    from src.database.models import Base

    if hasattr(postgres_container, "host"):
        # CI container (our custom CIPostgresContainer class)
        db_url = f"postgresql+psycopg://{postgres_container.username}:{postgres_container.password}@{postgres_container.host}:{postgres_container.port}/{postgres_container.dbname}"
    else:
        # Testcontainer (actual PostgresContainer from testcontainers library)
        # Get connection details and build URL with psycopg driver
        host = postgres_container.get_container_host_ip()
        port = postgres_container.get_exposed_port(5432)
        username = postgres_container.username or "test"
        password = postgres_container.password or "test"
        dbname = postgres_container.dbname or "test"
        db_url = f"postgresql+psycopg://{username}:{password}@{host}:{port}/{dbname}"

    engine = create_engine(db_url, echo=False)

    # Create database schema following SQLAlchemy best practices for concurrent environments
    # Reference: https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.MetaData.create_all
    # Use checkfirst=True to prevent duplicate table creation attempts
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception as e:
        # Handle PostgreSQL enum creation conflicts during parallel test execution
        # PostgreSQL enums don't support "IF NOT EXISTS" natively, so we handle conflicts gracefully
        error_msg = str(e).lower()
        is_enum_conflict = any(
            phrase in error_msg
            for phrase in [
                "already exists",
                "duplicate key",
                "pg_type_typname_nsp_index",
                "jobstatus",
            ]
        )

        if is_enum_conflict:
            # Expected during concurrent test runs - enum already created by another process
            # This is safe to ignore as schema creation is idempotent
            import logging

            logging.getLogger(__name__).debug(
                f"PostgreSQL enum already exists (concurrent test execution): {e}"
            )
        else:
            # Unexpected error - re-raise for investigation
            raise

    yield engine

    # Cleanup: Drop all tables and types
    try:
        Base.metadata.drop_all(engine)
    except Exception as e:
        # Cleanup errors are not critical for test execution
        import logging

        logging.getLogger(__name__).debug(f"Database cleanup warning: {e}")
    finally:
        engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine):
    """Create database session with automatic cleanup between tests."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=postgres_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()

        # Clean tables between tests
        with postgres_engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename != 'alembic_version'
            """)
            )
            tables = [row[0] for row in result]

            if tables:
                conn.execute(text("SET session_replication_role = 'replica'"))
                for table in tables:
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                conn.execute(text("SET session_replication_role = 'origin'"))
                conn.commit()

        session.close()


@pytest.fixture
def testcontainers_db_service(postgres_engine):
    """Create DatabaseService instance using test container."""
    from sqlalchemy import text

    from src.database.service import DatabaseService

    service = DatabaseService._create_with_engine(postgres_engine)

    # Ensure clean state before test
    with postgres_engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename != 'alembic_version'
        """)
        )
        tables = [row[0] for row in result]

        if tables:
            conn.execute(text("SET session_replication_role = 'replica'"))
            for table in tables:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            conn.execute(text("SET session_replication_role = 'origin'"))
            conn.commit()

    yield service

    # Clean up after test
    with postgres_engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename != 'alembic_version'
        """)
        )
        tables = [row[0] for row in result]

        if tables:
            conn.execute(text("SET session_replication_role = 'replica'"))
            for table in tables:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            conn.execute(text("SET session_replication_role = 'origin'"))
            conn.commit()


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
        version="1.1.0",
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
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "redis: marks tests that require Redis")
    config.addinivalue_line("markers", "database: marks tests that require PostgreSQL container")

    pass


# Skip tests if dependencies not available
def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle missing dependencies."""
    import importlib.util
    import subprocess

    redis_available = importlib.util.find_spec("redis") is not None

    # Check if Docker is available for testcontainers
    docker_available = False
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True, timeout=5)
        docker_available = True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        docker_available = False

    if not redis_available:
        skip_redis = pytest.mark.skip(reason="Redis not available")
        for item in items:
            if "redis" in item.keywords:
                item.add_marker(skip_redis)

    if not docker_available:
        skip_docker = pytest.mark.skip(reason="Docker not available for testcontainers")
        for item in items:
            if "database" in item.keywords:
                item.add_marker(skip_docker)
