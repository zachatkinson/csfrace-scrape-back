"""Comprehensive tests for src/database/transactions.py.

Test coverage: 103 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.

Tests focus on async transaction management, error handling, retry logic,
and parallel execution patterns for database operations.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.transactions import (
    TransactionError,
    TransactionManager,
    _execute_parallel_operations_safe,
    _set_isolation_level_safe,
    batch_transaction,
    database_transaction,
    execute_with_retry,
    execute_with_transaction,
    read_only_transaction,
)

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def mock_async_session():
    """Factory for mock AsyncSession - DRY principle."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_async_session_context(mock_async_session):
    """Factory for async session context manager - DRY principle."""

    class AsyncSessionContext:
        async def __aenter__(self):
            return mock_async_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    return AsyncSessionContext()


@pytest.fixture
def sample_async_operation():
    """Factory for sample async operation - DRY principle."""

    async def operation(db: AsyncSession):
        """Sample operation that uses database session."""
        result = Mock()
        result.data = "test_data"
        return result

    return operation


# =============================================================================
# TEST TransactionError - Custom Exception
# =============================================================================


@pytest.mark.unit
class TestTransactionError:
    """Test TransactionError custom exception."""

    def test_transaction_error_with_message_only(self):
        """Test TransactionError with message only."""
        # Act
        error = TransactionError("Test error message")

        # Assert
        assert str(error) == "Test error message"
        assert error.original_error is None

    def test_transaction_error_with_original_error(self):
        """Test TransactionError with original error."""
        # Arrange
        original = ValueError("Original error")

        # Act
        error = TransactionError("Test error message", original_error=original)

        # Assert
        assert str(error) == "Test error message"
        assert error.original_error is original


# =============================================================================
# TEST database_transaction - Context Manager
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDatabaseTransaction:
    """Test database_transaction context manager."""

    async def test_database_transaction_creates_new_session_when_none_provided(self):
        """Test creates new session when none provided."""
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()

        class AsyncSessionContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        # Mock async_session to return context manager (not coroutine)
        mock_async_session_factory = MagicMock(return_value=AsyncSessionContextManager())

        with patch("src.database.transactions.async_session", mock_async_session_factory):
            with patch("src.database.transactions._transaction_handler") as mock_handler:
                mock_handler.return_value = AsyncMock()
                mock_handler.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_handler.return_value.__aexit__ = AsyncMock(return_value=None)

                # Act
                async with database_transaction() as db:
                    pass

                # Assert
                assert db is mock_session
                mock_async_session_factory.assert_called_once()

    async def test_database_transaction_uses_existing_session(self, mock_async_session):
        """Test uses existing session when provided."""
        # Arrange
        with patch("src.database.transactions._transaction_handler") as mock_handler:
            mock_handler.return_value = AsyncMock()
            mock_handler.return_value.__aenter__ = AsyncMock(return_value=mock_async_session)
            mock_handler.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            async with database_transaction(session=mock_async_session) as db:
                # Assert within context
                assert db is mock_async_session

            # Assert handler was called with existing session
            mock_handler.assert_called_once()
            assert mock_handler.call_args[0][0] is mock_async_session


# =============================================================================
# TEST _transaction_handler - Internal Handler
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestTransactionHandler:
    """Test _transaction_handler internal transaction handler."""

    async def test_transaction_handler_commits_on_success(self, mock_async_session):
        """Test transaction handler commits on success with auto_commit=True."""
        # Arrange
        from src.database.transactions import _transaction_handler

        # Act
        async with _transaction_handler(mock_async_session, auto_commit=True, isolation_level=None):
            # Simulate successful operation
            pass

        # Assert
        mock_async_session.commit.assert_awaited_once()
        mock_async_session.rollback.assert_not_awaited()

    async def test_transaction_handler_no_commit_when_auto_commit_false(self, mock_async_session):
        """Test transaction handler doesn't commit when auto_commit=False."""
        # Arrange
        from src.database.transactions import _transaction_handler

        # Act
        async with _transaction_handler(
            mock_async_session, auto_commit=False, isolation_level=None
        ):
            pass

        # Assert
        mock_async_session.commit.assert_not_awaited()
        mock_async_session.rollback.assert_not_awaited()

    async def test_transaction_handler_rollback_on_sqlalchemy_error(self, mock_async_session):
        """Test transaction handler rolls back on SQLAlchemyError."""
        # Arrange
        from src.database.transactions import _transaction_handler

        # Act & Assert
        with pytest.raises(TransactionError, match="Database transaction failed"):
            async with _transaction_handler(
                mock_async_session, auto_commit=True, isolation_level=None
            ):
                raise SQLAlchemyError("Test database error")

        mock_async_session.rollback.assert_awaited_once()
        mock_async_session.commit.assert_not_awaited()

    async def test_transaction_handler_rollback_on_general_exception(self, mock_async_session):
        """Test transaction handler rolls back on general Exception."""
        # Arrange
        from src.database.transactions import _transaction_handler

        # Act & Assert
        with pytest.raises(TransactionError, match="Transaction failed"):
            async with _transaction_handler(
                mock_async_session, auto_commit=True, isolation_level=None
            ):
                raise ValueError("Test error")

        mock_async_session.rollback.assert_awaited_once()
        mock_async_session.commit.assert_not_awaited()

    async def test_transaction_handler_sets_isolation_level(self, mock_async_session):
        """Test transaction handler sets isolation level when specified."""
        # Arrange
        from src.database.transactions import _transaction_handler

        with patch("src.database.transactions._set_isolation_level_safe") as mock_set_level:
            mock_set_level.return_value = AsyncMock()

            # Act
            async with _transaction_handler(
                mock_async_session, auto_commit=False, isolation_level="SERIALIZABLE"
            ):
                pass

            # Assert
            mock_set_level.assert_awaited_once()
            call_args = mock_set_level.call_args
            assert call_args[0][0] is mock_async_session
            assert call_args[0][2] == "SERIALIZABLE"


# =============================================================================
# TEST batch_transaction - Batch Processing
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestBatchTransaction:
    """Test batch_transaction context manager."""

    async def test_batch_transaction_creates_transaction_with_auto_commit_false(self):
        """Test batch_transaction creates transaction with auto_commit=False."""
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            async with batch_transaction(batch_size=500) as db:
                assert db is mock_session

            # Assert
            mock_db_trans.assert_called_once_with(auto_commit=False)

    async def test_batch_transaction_commits_at_end(self):
        """Test batch_transaction commits at the end."""
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            async with batch_transaction():
                pass

            # Assert
            mock_session.commit.assert_awaited_once()


# =============================================================================
# TEST read_only_transaction - Read-Only Operations
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestReadOnlyTransaction:
    """Test read_only_transaction context manager."""

    async def test_read_only_transaction_uses_correct_isolation_level(self):
        """Test read_only_transaction uses READ_COMMITTED isolation level."""
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            async with read_only_transaction() as db:
                assert db is mock_session

            # Assert
            mock_db_trans.assert_called_once_with(
                auto_commit=False, isolation_level="READ_COMMITTED"
            )

    async def test_read_only_transaction_no_commit(self):
        """Test read_only_transaction doesn't commit."""
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            async with read_only_transaction():
                pass

            # Assert - verify auto_commit=False was passed
            mock_db_trans.assert_called_once_with(
                auto_commit=False, isolation_level="READ_COMMITTED"
            )


# =============================================================================
# TEST TransactionManager - Advanced Operations
# =============================================================================


@pytest.mark.unit
class TestTransactionManager:
    """Test TransactionManager class."""

    def test_transaction_manager_init(self):
        """Test TransactionManager initialization."""
        # Act
        manager = TransactionManager()

        # Assert
        assert isinstance(manager._active_transactions, set)
        assert len(manager._active_transactions) == 0

    @pytest.mark.asyncio
    async def test_execute_with_retry_succeeds_on_first_attempt(self):
        """Test execute_with_retry succeeds on first attempt."""
        # Arrange
        manager = TransactionManager()
        mock_result = Mock()
        mock_result.data = "success"

        async def successful_operation(db):
            return mock_result

        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            result = await manager.execute_with_retry(successful_operation, max_retries=3)

            # Assert
            assert result is mock_result

    @pytest.mark.asyncio
    async def test_execute_with_retry_retries_on_sqlalchemy_error(self):
        """Test execute_with_retry retries on SQLAlchemyError."""
        # Arrange
        manager = TransactionManager()
        attempt_count = 0
        mock_result = Mock()

        async def failing_then_succeeding_operation(db):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise SQLAlchemyError("Temporary error")
            return mock_result

        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            result = await manager.execute_with_retry(
                failing_then_succeeding_operation, max_retries=3, backoff_factor=1.5
            )

            # Assert
            assert result is mock_result
            assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausts_retries(self):
        """Test execute_with_retry exhausts all retries on persistent error."""
        # Arrange
        manager = TransactionManager()

        async def always_failing_operation(db):
            raise SQLAlchemyError("Persistent error")

        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act & Assert
            with pytest.raises(TransactionError, match="Transaction failed after 3 attempts"):
                await manager.execute_with_retry(always_failing_operation, max_retries=2)

    @pytest.mark.asyncio
    async def test_execute_with_retry_no_retry_on_non_database_error(self):
        """Test execute_with_retry doesn't retry on non-database errors."""
        # Arrange
        manager = TransactionManager()

        async def non_retryable_operation(db):
            raise ValueError("Non-retryable error")

        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act & Assert
            with pytest.raises(TransactionError, match="Operation failed"):
                await manager.execute_with_retry(non_retryable_operation, max_retries=3)

    @pytest.mark.asyncio
    async def test_execute_in_parallel_runs_operations_concurrently(self):
        """Test execute_in_parallel runs multiple operations concurrently."""
        # Arrange
        manager = TransactionManager()
        results = []

        async def operation1(db):
            results.append(1)
            return "result1"

        async def operation2(db):
            results.append(2)
            return "result2"

        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            operation_results = await manager.execute_in_parallel(
                [operation1, operation2], max_concurrent=5
            )

            # Assert
            assert len(operation_results) == 2
            assert "result1" in operation_results
            assert "result2" in operation_results
            assert len(results) == 2


# =============================================================================
# TEST Convenience Functions
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestConvenienceFunctions:
    """Test convenience functions."""

    async def test_execute_with_transaction_wraps_operation(self):
        """Test execute_with_transaction wraps operation in transaction."""
        # Arrange
        mock_result = Mock()

        async def operation(db):
            return mock_result

        mock_session = AsyncMock(spec=AsyncSession)

        with patch("src.database.transactions.database_transaction") as mock_db_trans:
            mock_db_trans.return_value = AsyncMock()
            mock_db_trans.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            result = await execute_with_transaction(operation, auto_commit=True)

            # Assert
            assert result is mock_result
            mock_db_trans.assert_called_once_with(auto_commit=True)

    async def test_execute_with_retry_convenience_delegates_to_manager(self):
        """Test execute_with_retry convenience function delegates to TransactionManager."""
        # Arrange
        mock_result = Mock()

        async def operation(db):
            return mock_result

        with patch.object(
            TransactionManager, "execute_with_retry", return_value=mock_result
        ) as mock_retry:
            # Act
            result = await execute_with_retry(operation, max_retries=5)

            # Assert
            assert result is mock_result
            mock_retry.assert_called_once()


# =============================================================================
# TEST Helper Functions
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestHelperFunctions:
    """Test helper functions."""

    async def test_set_isolation_level_safe_validates_level(self, mock_async_session):
        """Test _set_isolation_level_safe validates isolation level."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid isolation level"):
            await _set_isolation_level_safe(mock_async_session, 123, "INVALID_LEVEL")

    async def test_set_isolation_level_safe_sets_valid_level(self, mock_async_session):
        """Test _set_isolation_level_safe sets valid isolation level."""
        # Act
        await _set_isolation_level_safe(mock_async_session, 123, "SERIALIZABLE")

        # Assert
        mock_async_session.execute.assert_awaited_once()
        # Verify SQL command was executed
        call_args = mock_async_session.execute.call_args[0][0]
        assert "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE" in str(call_args)

    async def test_execute_parallel_operations_safe_gathers_results(self):
        """Test _execute_parallel_operations_safe gathers all results."""

        # Arrange
        async def operation1():
            return "result1"

        async def operation2():
            return "result2"

        async def mock_execute_with_semaphore(op):
            return await op()

        operations = [operation1, operation2]

        # Act
        results = await _execute_parallel_operations_safe(operations, mock_execute_with_semaphore)

        # Assert
        assert len(results) == 2
        assert "result1" in results
        assert "result2" in results
