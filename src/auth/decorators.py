"""Authentication service decorators for DRY error handling and transaction management."""

import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from sqlalchemy.orm import Session

from src.utils.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def handle_auth_errors(operation_name: str) -> Callable[[F], F]:
    """Decorator to provide consistent error handling for auth operations.

    Args:
        operation_name: Name of the operation for logging

    Returns:
        Decorated function with error handling
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                # ValueError indicates validation errors - re-raise as-is
                logger.warning(f"{operation_name} validation error", error=str(e))
                raise
            except Exception as e:
                # All other exceptions are internal errors
                logger.error(f"{operation_name} failed", error=str(e))
                if hasattr(args[0], "db") and isinstance(args[0].db, Session):
                    args[0].db.rollback()
                raise RuntimeError(f"Failed to {operation_name.lower()}: {str(e)}") from e

        return cast("F", wrapper)

    return decorator


def with_transaction_rollback[F: Callable[..., Any]](func: F) -> F:
    """Decorator to ensure database rollback on exceptions.

    Note: This assumes the first argument is 'self' with a 'db' attribute.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:
            # Attempt to rollback if we have a database session
            if args and hasattr(args[0], "db"):
                db_session = args[0].db
                # Check if it's a real session or a mock
                if hasattr(db_session, "rollback"):
                    try:
                        db_session.rollback()
                        logger.info("Database transaction rolled back due to error")
                    except Exception as rollback_error:
                        logger.error("Failed to rollback transaction", error=str(rollback_error))
            raise

    return cast("F", wrapper)
