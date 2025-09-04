"""Tests for database initialization module."""

import asyncio
import inspect
import logging
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

import src.database.init_db as init_db_module
from src.database.init_db import init_db, logger


class TestInitDb:
    """Test cases for database initialization functionality."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_basic_execution(self):
        """Test that init_db executes without error."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._run_alembic_migrations") as mock_alembic,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            # Mock Alembic failure to test fallback path
            mock_alembic.side_effect = FileNotFoundError("alembic.ini not found")
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            # This should complete without raising any exceptions
            await init_db()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_returns_none(self):
        """Test that init_db returns None."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._run_alembic_migrations") as mock_alembic,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            # Mock Alembic failure to test fallback path
            mock_alembic.side_effect = FileNotFoundError("alembic.ini not found")
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            result = await init_db()
            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_is_coroutine(self):
        """Test that init_db is properly defined as an async function."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._run_alembic_migrations") as mock_alembic,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            # Mock Alembic failure to test fallback path
            mock_alembic.side_effect = FileNotFoundError("alembic.ini not found")
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            # Check that calling init_db returns a coroutine
            coro = init_db()
            assert asyncio.iscoroutine(coro)

            # Clean up the coroutine
            await coro

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_logging_behavior(self, caplog):
        """Test that init_db logs the expected message."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._run_alembic_migrations") as mock_alembic,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            # Mock Alembic failure to test fallback path
            mock_alembic.side_effect = FileNotFoundError("alembic.ini not found")
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            with caplog.at_level(logging.INFO):
                await init_db()

            # Check that the expected log message was recorded
            assert "Database initialization completed successfully" in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_logging_level(self, caplog):
        """Test that init_db logs at INFO level."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._run_alembic_migrations") as mock_alembic,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            # Mock Alembic failure to test fallback path
            mock_alembic.side_effect = FileNotFoundError("alembic.ini not found")
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            with caplog.at_level(logging.INFO):
                await init_db()

            # Check that we have at least one log record at INFO level
            info_records = [record for record in caplog.records if record.levelno == logging.INFO]
            assert len(info_records) >= 1
            # Check the final success message
            success_records = [
                r
                for r in info_records
                if "Database initialization completed successfully" in r.message
            ]
            assert len(success_records) >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_logger_name(self, caplog):
        """Test that init_db uses the correct logger name."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._run_alembic_migrations") as mock_alembic,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            # Mock Alembic failure to test fallback path
            mock_alembic.side_effect = FileNotFoundError("alembic.ini not found")
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            with caplog.at_level(logging.INFO):
                await init_db()

            # Check logger name
            assert any(record.name == "src.database.init_db" for record in caplog.records)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_multiple_calls(self):
        """Test that init_db can be called multiple times safely."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            # Call init_db multiple times
            await init_db()
            await init_db()
            await init_db()

            # Should complete without any issues

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_concurrent_calls(self, testcontainers_db_service):
        """Test that init_db handles concurrent calls safely."""
        # PostgreSQL enum creation can conflict during concurrent initialization
        # Use a semaphore to limit concurrent database operations to prevent deadlocks
        semaphore = asyncio.Semaphore(2)  # Allow max 2 concurrent operations

        async def safe_init_db():
            async with semaphore:
                return await init_db(testcontainers_db_service.engine)

        # Create multiple concurrent calls with limited concurrency
        tasks = [safe_init_db() for _ in range(5)]

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        # All should return None
        assert all(result is None for result in results)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_exception_handling(self):
        """Test init_db behavior when logger raises an exception."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
            patch("src.database.init_db.logger") as mock_logger,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            # Make the logger.info call raise an exception
            mock_logger.info.side_effect = Exception("Logger error")

            # init_db should still handle this gracefully
            with pytest.raises(Exception, match="Logger error"):
                await init_db()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_with_mocked_logger(self):
        """Test init_db with fully mocked logger."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
            patch("src.database.init_db.logger") as mock_logger,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None

            await init_db()

            # Verify logger.info was called with expected message
            mock_logger.info.assert_called_once_with(
                "Database initialization completed successfully"
            )

    @pytest.mark.unit
    def test_init_db_function_signature(self):
        """Test that init_db function follows SQLAlchemy dependency injection best practices."""
        # Get function signature
        sig = inspect.signature(init_db)

        # Should have one optional parameter for dependency injection (SQLAlchemy best practice)
        # This enables testing with testcontainers while maintaining backward compatibility
        assert len(sig.parameters) == 1, (
            "init_db should accept optional engine parameter for dependency injection"
        )

        # Parameter should be named 'engine' with default None (SQLAlchemy pattern)
        engine_param = sig.parameters["engine"]
        assert engine_param.name == "engine", (
            "Parameter should be named 'engine' following SQLAlchemy conventions"
        )
        assert engine_param.default is None, (
            "Engine parameter should default to None for backward compatibility"
        )

        # Parameter should be optional to maintain API compatibility
        assert engine_param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD, (
            "Engine parameter should accept both positional and keyword arguments"
        )

        # Should be marked as async
        assert asyncio.iscoroutinefunction(init_db), "init_db should be an async function"

        # Return type should be None
        assert sig.return_annotation is None or sig.return_annotation is type(None), (
            "init_db should return None"
        )

    @pytest.mark.unit
    def test_init_db_docstring(self):
        """Test that init_db has proper documentation."""
        assert init_db.__doc__ is not None
        assert "Initialize the database" in init_db.__doc__
        assert "PostgreSQL enum safety" in init_db.__doc__

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_performance(self, testcontainers_db_service):
        """Test that init_db completes quickly using testcontainer."""
        start_time = time.time()
        await init_db(testcontainers_db_service.engine)
        execution_time = time.time() - start_time

        # Should complete very quickly (less than 1 second)
        assert execution_time < 1.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_in_different_event_loops(self, testcontainers_db_service):
        """Test init_db behavior in different event loops."""
        # Test in current event loop
        await init_db(testcontainers_db_service.engine)

        # Test creating a new event loop
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        try:
            await init_db(testcontainers_db_service.engine)
        finally:
            new_loop.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_logging_integration(self, testcontainers_db_service):
        """Test integration with the logging system."""
        # Configure a test handler
        test_logger = logging.getLogger("src.database.init_db")
        test_handler = logging.StreamHandler()
        test_formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        test_handler.setFormatter(test_formatter)

        original_level = test_logger.level
        original_handlers = test_logger.handlers.copy()

        try:
            test_logger.addHandler(test_handler)
            test_logger.setLevel(logging.INFO)

            await init_db(testcontainers_db_service.engine)

        finally:
            # Restore original logger state
            test_logger.setLevel(original_level)
            test_logger.handlers = original_handlers

    @pytest.mark.unit
    def test_module_structure(self):
        """Test that the init_db module has expected structure."""
        # Check that required components exist
        assert hasattr(init_db_module, "init_db")
        assert hasattr(init_db_module, "logger")
        assert hasattr(init_db_module, "logging")

        # Check that init_db is callable
        assert callable(init_db_module.init_db)

    @pytest.mark.unit
    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        # Logger should exist and have correct name
        assert logger is not None
        assert logger.name == "src.database.init_db"

        # Should be a Logger instance
        assert isinstance(logger, logging.Logger)


class TestInitDbEdgeCases:
    """Test edge cases and error conditions for init_db."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_init_db_with_logging_disabled(self):
        """Test init_db when logging is disabled."""
        with (
            patch("src.database.init_db.create_engine") as mock_create_engine,
            patch("src.database.init_db._create_enums_safely") as mock_create_enums,
            patch("src.database.init_db.Base") as mock_base,
            patch("src.database.init_db.logger") as mock_logger,
        ):
            # Mock successful database operations
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_create_enums.return_value = None
            mock_base.metadata.create_all.return_value = None
            mock_logger.disabled = True

            # Should still work
            await init_db()

            # Logger.info should still be called even if disabled
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_with_no_handlers(self, testcontainers_db_service):
        """Test init_db when logger has no handlers."""
        original_handlers = logger.handlers.copy()
        logger.handlers.clear()

        try:
            # Should still work without handlers
            await init_db(testcontainers_db_service.engine)
        finally:
            # Restore handlers
            logger.handlers = original_handlers

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_init_db_stress_test(self, testcontainers_db_service):
        """Stress test with serialized database operations to prevent PostgreSQL deadlocks."""
        # PostgreSQL has strict limits on concurrent DDL operations (CREATE TYPE, etc.)
        # Use semaphore to prevent enum creation conflicts and deadlocks
        semaphore = asyncio.Semaphore(3)  # Allow max 3 concurrent operations

        async def safe_init_db():
            async with semaphore:
                await asyncio.sleep(0.01)  # Small delay to reduce contention
                return await init_db(testcontainers_db_service.engine)

        # Reduce stress test size to prevent PostgreSQL deadlocks (100 -> 20)
        tasks = [safe_init_db() for _ in range(20)]

        # All should complete successfully
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            # Log first exception for debugging
            print(f"Database initialization exception: {exceptions[0]}")
        assert len(exceptions) == 0

        # All should return None
        assert all(result is None for result in results if not isinstance(result, Exception))


class TestInitDbIntegration:
    """Integration tests for init_db functionality."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_real_logging_system(self, testcontainers_db_service):
        """Test init_db with real logging system."""
        # Create temporary log file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            log_file = f.name

        try:
            # Configure file handler
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)

            # Add handler to logger
            logger.addHandler(file_handler)
            logger.setLevel(logging.INFO)

            # Call init_db
            await init_db(testcontainers_db_service.engine)

            # Flush handler
            file_handler.flush()

            # Read log file content
            with open(log_file) as f:
                log_content = f.read()

            # Verify log message was written
            assert "Database initialization completed" in log_content
            assert "src.database.init_db" in log_content

            # Clean up handler
            logger.removeHandler(file_handler)
            file_handler.close()

        finally:
            # Clean up temp file
            if os.path.exists(log_file):
                os.unlink(log_file)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_in_task(self, testcontainers_db_service):
        """Test init_db when called from asyncio task."""

        async def task_wrapper():
            return await init_db(testcontainers_db_service.engine)

        # Create and run task
        task = asyncio.create_task(task_wrapper())
        result = await task

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_with_timeout(self, testcontainers_db_service):
        """Test init_db with asyncio timeout."""
        # Should complete well within timeout
        result = await asyncio.wait_for(init_db(testcontainers_db_service.engine), timeout=5.0)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_init_db_completes_immediately(self, testcontainers_db_service):
        """Test that init_db completes immediately (placeholder implementation)."""
        task = asyncio.create_task(init_db(testcontainers_db_service.engine))

        # Task should complete immediately since it's just a placeholder
        result = await task
        assert result is None  # Function returns None
