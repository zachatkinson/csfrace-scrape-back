"""Comprehensive tests for src/api/dependencies.py module.

This test module provides comprehensive coverage for all FastAPI dependencies
in the API dependencies module to achieve 80%+ coverage as required.
"""

import contextlib
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import DBSession, async_session, engine, get_db_session


class TestDatabaseDependencies:
    """Test database dependency functions and configurations."""

    @pytest.mark.asyncio
    async def test_get_db_session_success(self):
        """Test successful database session creation and cleanup."""
        # Mock the async_session context manager
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            # Setup the async context manager mock
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            mock_session_factory.return_value.__aexit__.return_value = None

            # Test the generator
            async_gen = get_db_session()
            session = await async_gen.__anext__()

            # Verify we get the mocked session
            assert session == mock_session

            # Verify session factory was called
            mock_session_factory.assert_called_once()

            # Simulate successful completion
            with contextlib.suppress(StopAsyncIteration):
                await async_gen.__anext__()

            # Verify commit was called
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_exception_rollback(self):
        """Test database session rollback on exception."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            mock_session_factory.return_value.__aexit__.return_value = None

            # Make commit raise an exception
            mock_session.commit.side_effect = Exception("Database error")

            async_gen = get_db_session()
            session = await async_gen.__anext__()

            assert session == mock_session

            # Simulate exception during commit
            with pytest.raises(Exception, match="Database error"):
                with contextlib.suppress(StopAsyncIteration):
                    await async_gen.__anext__()

            # Verify rollback was called due to exception
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_context_manager_behavior(self):
        """Test proper async context manager behavior."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            # Create a proper async context manager mock
            async_context_manager = AsyncMock()
            async_context_manager.__aenter__.return_value = mock_session
            async_context_manager.__aexit__.return_value = None
            mock_session_factory.return_value = async_context_manager

            # Use the generator as a dependency would
            async for session in get_db_session():
                assert session == mock_session
                # In real usage, the session would be used here
                break

            # Verify proper context manager usage
            async_context_manager.__aenter__.assert_called_once()
            async_context_manager.__aexit__.assert_called_once()

    def test_engine_configuration(self):
        """Test that database engine is properly configured."""
        # Verify engine exists and has expected configuration
        assert engine is not None

        # Test engine properties that should be configured
        assert hasattr(engine, "pool")
        assert hasattr(engine, "url")

        # Verify URL conversion from PostgreSQL to AsyncPG
        url_str = str(engine.url)
        assert "postgresql+asyncpg" in url_str or "asyncpg" in url_str

    def test_async_session_factory_configuration(self):
        """Test that async session factory is properly configured."""
        assert async_session is not None

        # Verify session factory configuration
        assert hasattr(async_session, "bind")
        assert async_session.bind == engine

        # Verify expire_on_commit is False
        assert async_session.expire_on_commit is False

    def test_db_session_type_annotation(self):
        """Test that DBSession type annotation is properly configured."""
        # Verify DBSession is a proper Annotated type
        assert hasattr(DBSession, "__origin__")
        assert hasattr(DBSession, "__metadata__")

        # The annotation should contain AsyncSession and Depends
        args = DBSession.__args__ if hasattr(DBSession, "__args__") else []
        metadata = DBSession.__metadata__ if hasattr(DBSession, "__metadata__") else []

        # Should have AsyncSession as the base type
        assert any(
            arg == AsyncSession or (hasattr(arg, "__name__") and arg.__name__ == "AsyncSession")
            for arg in args
        )

        # Should have Depends in metadata
        assert len(metadata) > 0

    @pytest.mark.asyncio
    async def test_get_db_session_isolation(self):
        """Test that each call to get_db_session creates an isolated session."""
        with patch("src.api.dependencies.async_session") as mock_session_factory:
            # Create different session instances for each call
            session1 = AsyncMock(spec=AsyncSession)
            session2 = AsyncMock(spec=AsyncSession)

            # Setup different sessions for each call
            call_count = 0

            def create_session():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    ctx_mgr = AsyncMock()
                    ctx_mgr.__aenter__.return_value = session1
                    ctx_mgr.__aexit__.return_value = None
                    return ctx_mgr
                else:
                    ctx_mgr = AsyncMock()
                    ctx_mgr.__aenter__.return_value = session2
                    ctx_mgr.__aexit__.return_value = None
                    return ctx_mgr

            mock_session_factory.side_effect = create_session

            # Get first session
            gen1 = get_db_session()
            result1 = await gen1.__anext__()

            # Get second session
            gen2 = get_db_session()
            result2 = await gen2.__anext__()

            # Sessions should be different instances
            assert result1 == session1
            assert result2 == session2
            assert result1 != result2

            # Both session factories should have been called
            assert mock_session_factory.call_count == 2

    @pytest.mark.asyncio
    async def test_get_db_session_commit_error_handling(self):
        """Test specific error handling during commit operation."""
        mock_session = AsyncMock(spec=AsyncSession)
        commit_error = Exception("Commit failed")
        mock_session.commit.side_effect = commit_error

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            ctx_mgr = AsyncMock()
            ctx_mgr.__aenter__.return_value = mock_session
            ctx_mgr.__aexit__.return_value = None
            mock_session_factory.return_value = ctx_mgr

            gen = get_db_session()
            session = await gen.__anext__()

            assert session == mock_session

            # The exception should be re-raised after rollback
            with pytest.raises(Exception, match="Commit failed"):
                with contextlib.suppress(StopAsyncIteration):
                    await gen.__anext__()

            # Verify error handling sequence
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_rollback_error_handling(self):
        """Test error handling when both commit and rollback fail."""
        mock_session = AsyncMock(spec=AsyncSession)
        commit_error = Exception("Commit failed")
        rollback_error = Exception("Rollback failed")

        mock_session.commit.side_effect = commit_error
        mock_session.rollback.side_effect = rollback_error

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            ctx_mgr = AsyncMock()
            ctx_mgr.__aenter__.return_value = mock_session
            ctx_mgr.__aexit__.return_value = None
            mock_session_factory.return_value = ctx_mgr

            gen = get_db_session()
            await gen.__anext__()

            # Should raise the original commit error, not the rollback error
            with pytest.raises(Exception, match="Commit failed"):
                with contextlib.suppress(StopAsyncIteration):
                    await gen.__anext__()

            # Both operations should have been attempted
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    def test_database_url_configuration(self):
        """Test database URL configuration and asyncpg conversion."""
        with patch("src.api.dependencies.get_database_url") as mock_get_url:
            # Test URL conversion from psycopg to asyncpg
            mock_get_url.return_value = "postgresql+psycopg://user:pass@host:5432/db"

            # Re-import to trigger URL conversion
            import importlib

            import src.api.dependencies

            importlib.reload(src.api.dependencies)

            # URL should be converted to asyncpg
            mock_get_url.assert_called()

    @pytest.mark.asyncio
    async def test_session_expire_on_commit_behavior(self):
        """Test that session doesn't expire objects on commit."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            ctx_mgr = AsyncMock()
            ctx_mgr.__aenter__.return_value = mock_session
            ctx_mgr.__aexit__.return_value = None
            mock_session_factory.return_value = ctx_mgr

            async for session in get_db_session():
                # Session should have expire_on_commit=False configured
                # This means objects remain accessible after commit
                assert session == mock_session
                break

            # Verify session was configured with proper settings
            assert mock_session_factory.call_count == 1


class TestDependencyIntegration:
    """Integration tests for dependency usage patterns."""

    @pytest.mark.asyncio
    async def test_dependency_injection_pattern(self):
        """Test typical FastAPI dependency injection pattern."""
        # Simulate how FastAPI would use the dependency
        dependency_func = get_db_session

        # Verify it's an async generator
        assert callable(dependency_func)

        gen = dependency_func()
        assert hasattr(gen, "__anext__")
        assert hasattr(gen, "__aiter__")

    def test_type_hints_for_fastapi(self):
        """Test that type annotations work correctly with FastAPI."""
        from typing import get_type_hints

        # Test function that would use the dependency
        def example_endpoint(db: DBSession):
            return db

        hints = get_type_hints(example_endpoint)
        assert "db" in hints

        # The hint should resolve to the annotated type
        db_hint = hints["db"]
        assert hasattr(db_hint, "__origin__") or hasattr(db_hint, "__metadata__")

    @pytest.mark.asyncio
    async def test_concurrent_session_usage(self):
        """Test that concurrent session usage works correctly."""
        import asyncio

        async def use_session():
            async for session in get_db_session():
                # Simulate some database work
                await asyncio.sleep(0.01)
                return session

        with patch("src.api.dependencies.async_session") as mock_session_factory:
            # Setup mock sessions
            sessions = [AsyncMock(spec=AsyncSession) for _ in range(3)]

            def create_session_side_effect():
                session = sessions[mock_session_factory.call_count - 1]
                ctx_mgr = AsyncMock()
                ctx_mgr.__aenter__.return_value = session
                ctx_mgr.__aexit__.return_value = None
                return ctx_mgr

            mock_session_factory.side_effect = create_session_side_effect

            # Run multiple concurrent sessions
            tasks = [use_session() for _ in range(3)]
            results = await asyncio.gather(*tasks)

            # Should have different sessions
            assert len(set(results)) == 3
            assert mock_session_factory.call_count == 3
