"""Database engine configuration and utilities.

This module contains database engine creation and configuration
following SQLAlchemy 2.0 best practices.
"""

from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import ConnectionPoolEntry, PoolResetState

from src.core.logging_hierarchy import get_database_logger

logger = get_database_logger()


def create_database_engine(echo: bool = False) -> Engine:
    """Create SQLAlchemy engine optimized for PostgreSQL 17.6.

    Args:
        echo: Whether to echo SQL statements (for debugging)

    Returns:
        SQLAlchemy Engine instance configured for PostgreSQL 17.6+
    """
    from ..utils import get_database_url

    database_url = get_database_url()

    # PostgreSQL 17.6 optimized configuration following 2025 best practices
    engine = create_engine(
        database_url,
        echo=echo,
        # Connection pool settings optimized for concurrent web scraping
        pool_size=20,  # Base connections (increased for concurrent scraping)
        max_overflow=30,  # Additional connections under load
        pool_timeout=30,  # Timeout to get connection from pool
        pool_recycle=3600,  # Recycle connections every hour
        pool_pre_ping=True,  # Validate connections before use
        # Set isolation level directly on engine (SQLAlchemy 2.0 way)
        isolation_level="READ_COMMITTED",
        # PostgreSQL 17.6 specific optimizations
        connect_args={
            "connect_timeout": 10,  # Connection establishment timeout
            "application_name": "csfrace-scraper",  # For monitoring/debugging
        },
    )

    # PostgreSQL connection reset handler for proper resource management
    @event.listens_for(engine, "reset")
    def _reset_postgresql(
        dbapi_connection: Any, _connection_record: ConnectionPoolEntry, reset_state: PoolResetState
    ) -> None:
        """Reset PostgreSQL connections properly following best practices."""
        if not reset_state.terminate_only:
            # Use cursor for SQL commands - psycopg connection doesn't have execute method
            with dbapi_connection.cursor() as cursor:
                cursor.execute("CLOSE ALL")  # Close cursors
                cursor.execute("RESET ALL")  # Reset session variables
                cursor.execute("DISCARD TEMP")  # Clean up temp tables
        dbapi_connection.rollback()  # Ensure clean transaction state

    return engine
