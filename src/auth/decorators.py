"""Authentication service decorators using centralized DRY error handling."""

# Import centralized error handlers to eliminate duplicate exception patterns
from src.core.decorators import auth_error_handler, database_error_handler


# Modern decorator exports - ZERO TOLERANCE for legacy patterns
def handle_auth_errors(operation_name: str):
    """Modern auth error handler using centralized auth_error_handler."""
    return auth_error_handler(operation_name)


def with_transaction_rollback(func):
    """Modern transaction rollback handler using centralized database_error_handler."""
    return database_error_handler("database transaction")(func)
