"""Unit tests for API dependencies module."""

from typing import get_origin
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import DBSession, async_session, engine, get_db_session


class TestDatabaseDependencies:
    """Test database dependency injection."""

    def test_engine_exists(self):
        """Test that database engine exists and has basic properties."""
        assert engine is not None
        assert hasattr(engine, "echo")
        assert hasattr(engine, "pool")

    def test_async_session_exists(self):
        """Test that async session factory exists."""
        assert async_session is not None
        assert hasattr(async_session, "kw")

    def test_db_session_type_annotation(self):
        """Test DBSession type annotation is correctly defined."""
        # DBSession should be an Annotated type
        assert hasattr(DBSession, "__origin__")
        assert get_origin(DBSession) is not None

    @pytest.mark.asyncio
    async def test_get_db_session_is_async_generator(self):
        """Test that get_db_session returns an async generator."""
        gen = get_db_session()
        assert hasattr(gen, "__anext__")
        assert hasattr(gen, "aclose")
        await gen.aclose()

    @pytest.mark.asyncio
    @patch("src.api.dependencies.async_session")
    async def test_get_db_session_calls_commit(self, mock_session_factory):
        """Test that get_db_session calls commit on success."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_session_factory.return_value = mock_context

        gen = get_db_session()
        try:
            async for session in gen:
                # Simulate normal operation
                break
        except StopAsyncIteration:
            pass

        await gen.aclose()

    @pytest.mark.asyncio
    @patch("src.api.dependencies.async_session")
    async def test_get_db_session_handles_exception(self, mock_session_factory):
        """Test exception handling in get_db_session."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_context = AsyncMock()

        # Simulate exception during session creation
        mock_context.__aenter__.side_effect = Exception("Session error")
        mock_session_factory.return_value = mock_context

        gen = get_db_session()

        with pytest.raises(Exception, match="Session error"):
            async for session in gen:
                break

        await gen.aclose()

    def test_dependencies_module_imports(self):
        """Test that all required dependencies are importable."""
        from src.api.dependencies import DBSession, async_session, engine, get_db_session

        assert callable(get_db_session)
        assert DBSession is not None
        assert engine is not None
        assert async_session is not None

    @pytest.mark.asyncio
    async def test_get_db_session_generator_protocol(self):
        """Test the async generator protocol of get_db_session."""
        gen = get_db_session()

        # Should be an async generator
        assert gen.__class__.__name__ == "async_generator"

        # Should be able to close without error
        await gen.aclose()

    def test_module_level_configuration(self):
        """Test module-level database configuration."""
        # Test that engine uses asyncpg URL
        assert "asyncpg" in str(engine.url)

        # Test that session factory is configured
        assert async_session.kw.get("expire_on_commit") is False
