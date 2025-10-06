"""Base database model components.

This module contains the shared base class and common utilities
used across all domain models.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import MetaData

from src.core.logging_hierarchy import get_database_logger

logger = get_database_logger()


class Base(DeclarativeBase):
    """Base class for all database models."""


# PostgreSQL enum metadata event listener (SQLAlchemy best practice)
@event.listens_for(Base.metadata, "before_create")
def _create_enums_before_tables(target: MetaData, connection: Connection, **kw: Any) -> None:  # noqa: ARG001
    """Create PostgreSQL enum types before table creation.

    This event listener follows SQLAlchemy best practices for PostgreSQL enum handling
    by ensuring enum types exist before any table creation attempts.

    Args:
        target: SQLAlchemy metadata object (required by event listener protocol)
        connection: Database connection (used for enum creation)
        **kw: Additional SQLAlchemy event arguments (required by protocol)
    """
    # Lazy import to avoid circular dependencies
    from ..utils import create_postgresql_enums, get_standard_enum_definitions

    create_postgresql_enums(connection, get_standard_enum_definitions())
