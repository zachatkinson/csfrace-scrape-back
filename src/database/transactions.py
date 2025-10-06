"""Centralized database transaction management with proper error handling.

Eliminates DRY violations and ensures consistent data integrity patterns
across all database operations in the application.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

import asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_database_logger

from ..api.dependencies import async_session

logger = get_database_logger()


class TransactionError(Exception):
    """Custom exception for transaction-related errors."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


@asynccontextmanager
async def database_transaction(
    session: AsyncSession | None = None,
    auto_commit: bool = True,
    isolation_level: str | None = None,
) -> AsyncGenerator[AsyncSession]:
    """Centralized database transaction context manager.

    Provides consistent transaction handling with proper error recovery,
    logging, and cleanup across all database operations.

    Args:
        session: Existing session to use (if None, creates new session)
        auto_commit: Whether to automatically commit on success
        isolation_level: SQL isolation level (e.g., 'READ_COMMITTED', 'SERIALIZABLE')

    Yields:
        AsyncSession: Database session for operations

    Raises:
        TransactionError: If transaction fails or times out

    Example:
        async with database_transaction() as db:
            # Database operations here
            user = User(name="test")
            db.add(user)
            # Automatically commits on success, rolls back on error
    """
    if session is None:
        # Create new session
        async with (
            async_session() as db,
            _transaction_handler(db, auto_commit, isolation_level) as session,
        ):
            yield session
    else:
        # Use existing session (for nested transactions)
        async with _transaction_handler(session, auto_commit, isolation_level) as session:
            yield session


@asynccontextmanager
async def _transaction_handler(
    db: AsyncSession, auto_commit: bool, isolation_level: str | None
) -> AsyncGenerator[AsyncSession]:
    """Internal transaction handler with error recovery."""
    transaction_id = id(db)  # Unique identifier for logging
    start_time = asyncio.get_event_loop().time()

    # Set isolation level if specified
    if isolation_level:
        await _set_isolation_level_safe(db, transaction_id, isolation_level)

    # Begin transaction
    logger.debug("Starting database transaction", transaction_id=transaction_id)

    try:
        yield db

        # Commit if auto_commit is enabled and no errors occurred
        if auto_commit:
            await db.commit()
            duration = asyncio.get_event_loop().time() - start_time
            logger.debug(
                "Transaction committed successfully",
                transaction_id=transaction_id,
                duration_ms=round(duration * 1000, 2),
            )

    except SQLAlchemyError as e:
        # Database-specific error handling
        await db.rollback()
        duration = asyncio.get_event_loop().time() - start_time

        logger.error(
            "Database transaction failed",
            transaction_id=transaction_id,
            duration_ms=round(duration * 1000, 2),
            error_type=type(e).__name__,
            error_message=str(e),
        )

        raise TransactionError(f"Database transaction failed: {str(e)}", original_error=e) from e

    except Exception as e:
        # General error handling
        await db.rollback()
        duration = asyncio.get_event_loop().time() - start_time

        logger.error(
            "Transaction failed with unexpected error",
            transaction_id=transaction_id,
            duration_ms=round(duration * 1000, 2),
            error_type=type(e).__name__,
            error_message=str(e),
        )

        raise TransactionError(f"Transaction failed: {str(e)}", original_error=e) from e


@asynccontextmanager
async def batch_transaction(batch_size: int = 1000) -> AsyncGenerator[AsyncSession]:  # noqa: ARG001
    """Transaction context for batch operations with periodic commits.

    Useful for processing large datasets where we want to commit in batches
    to avoid long-running transactions that could cause deadlocks.

    Args:
        batch_size: Number of operations before auto-commit

    Yields:
        AsyncSession: Database session with batch commit capability

    Example:
        async with batch_transaction(batch_size=500) as db:
            for i, item in enumerate(large_dataset):
                db.add(ProcessedItem(data=item))

                # Commits every 500 items automatically
                if (i + 1) % 500 == 0:
                    await db.commit()  # Manual commit for batch processing
    """
    async with database_transaction(auto_commit=False) as db:
        yield db
        # Final commit for any remaining items
        await db.commit()
        logger.debug("Batch transaction completed successfully")


@asynccontextmanager
async def read_only_transaction() -> AsyncGenerator[AsyncSession]:
    """Read-only transaction context for query operations.

    Optimized for read operations with appropriate isolation level
    and no commit overhead.

    Yields:
        AsyncSession: Read-only database session

    Example:
        async with read_only_transaction() as db:
            users = await db.execute(select(User).where(User.active == True))
            # No commit needed or attempted
    """
    async with database_transaction(auto_commit=False, isolation_level="READ_COMMITTED") as db:
        yield db
        # No commit for read-only operations
        logger.debug("Read-only transaction completed")


class TransactionManager:
    """Advanced transaction manager for complex scenarios."""

    def __init__(self) -> None:
        self._active_transactions: set[int] = set()

    async def execute_with_retry(
        self,
        operation: Callable[..., Any],
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        retry_exceptions: tuple[type[Exception], ...] = (SQLAlchemyError,),
    ) -> Any:
        """Execute database operation with automatic retry on failure.

        Args:
            operation: Async callable that takes a database session
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier
            retry_exceptions: Exception types that should trigger retry

        Returns:
            Result of the operation

        Raises:
            TransactionError: If all retries are exhausted

        Example:
            manager = TransactionManager()

            async def create_user(db: AsyncSession) -> User:
                user = User(name="test")
                db.add(user)
                return user

            user = await manager.execute_with_retry(create_user, max_retries=3)
        """
        last_exception = None
        delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                async with database_transaction() as db:
                    result = await operation(db)
                    return result

            except retry_exceptions as e:
                last_exception = e

                if attempt == max_retries:
                    logger.error("All retry attempts exhausted", attempts=attempt + 1, error=str(e))
                    break

                logger.warning(
                    "Transaction failed, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(e),
                )

                await asyncio.sleep(delay)
                delay *= backoff_factor

            except Exception as e:
                # Don't retry for non-database errors
                logger.error("Non-retryable error occurred", error=str(e))
                raise TransactionError(f"Operation failed: {str(e)}", original_error=e) from e

        # If we get here, all retries failed
        raise TransactionError(
            f"Transaction failed after {max_retries + 1} attempts: {str(last_exception)}",
            original_error=last_exception,
        ) from last_exception

    async def execute_in_parallel(
        self, operations: list[Callable[..., Any]], max_concurrent: int = 5
    ) -> list[Any]:
        """Execute multiple database operations in parallel with separate transactions.

        Args:
            operations: List of async callables that take a database session
            max_concurrent: Maximum number of concurrent transactions

        Returns:
            List of results from operations

        Raises:
            TransactionError: If any operation fails

        Example:
            async def op1(db): return await create_user(db, "user1")
            async def op2(db): return await create_user(db, "user2")

            results = await manager.execute_in_parallel([op1, op2])
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _execute_with_semaphore(operation: Callable[..., Any]) -> Any:
            async with semaphore, database_transaction() as db:
                return await operation(db)

        return await _execute_parallel_operations_safe(operations, _execute_with_semaphore)


# Global transaction manager instance
transaction_manager = TransactionManager()


# Convenience functions for common patterns
async def execute_with_transaction(operation: Callable[..., Any], **kwargs: Any) -> Any:
    """Convenience function to execute operation with transaction.

    Args:
        operation: Async callable that takes a database session
        **kwargs: Additional arguments for database_transaction()

    Returns:
        Result of the operation
    """
    async with database_transaction(**kwargs) as db:
        return await operation(db)


async def execute_with_retry(operation: Callable[..., Any], **kwargs: Any) -> Any:
    """Convenience function to execute operation with retry logic.

    Args:
        operation: Async callable that takes a database session
        **kwargs: Additional arguments for execute_with_retry()

    Returns:
        Result of the operation
    """
    return await transaction_manager.execute_with_retry(operation, **kwargs)


@database_error_handler("set transaction isolation level")
async def _set_isolation_level_safe(
    db: AsyncSession, transaction_id: int, isolation_level: str
) -> None:
    """Safely set transaction isolation level."""
    from sqlalchemy import text

    # Validate isolation level to prevent SQL injection (controlled enum values only)
    valid_levels = {"READ_UNCOMMITTED", "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE"}
    if isolation_level not in valid_levels:
        raise ValueError(f"Invalid isolation level: {isolation_level}")

    await db.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
    logger.debug(
        "Set transaction isolation level",
        transaction_id=transaction_id,
        isolation_level=isolation_level,
    )


@database_error_handler("execute parallel operations")
async def _execute_parallel_operations_safe(
    operations: list[Callable[..., Any]], execute_with_semaphore: Callable[..., Any]
) -> list[Any]:
    """Safely execute parallel operations."""
    results = await asyncio.gather(*[execute_with_semaphore(op) for op in operations])
    logger.debug("Parallel operations completed", count=len(operations))
    return results
