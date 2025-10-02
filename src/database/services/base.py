"""Base database service class following DRY principles.

This module provides shared functionality for all database services,
eliminating code duplication while maintaining focused responsibilities.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.decorators import content_processing_error_handler, database_error_handler
from src.core.logging_hierarchy import get_database_logger

from ..models import Base, create_database_engine
from ..utils import create_postgresql_enums, get_standard_enum_definitions

logger = get_database_logger(__name__).logger


class BaseService:
    """Base class for all database services with shared functionality."""

    def __init__(self, echo: bool = False):
        """Initialize base service with database connection.

        Args:
            echo: Enable SQL query logging
        """
        self.echo = echo
        self.engine = create_database_engine(echo=echo)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.info("Database service initialized", echo=echo)

    @classmethod
    def _create_with_engine(cls, engine: Engine) -> "BaseService":
        """Create service instance with existing engine (for testing).

        Args:
            engine: Pre-configured SQLAlchemy engine

        Returns:
            Service instance using the provided engine
        """
        instance = cls.__new__(cls)
        instance.engine = engine
        instance.Session = sessionmaker(bind=engine, expire_on_commit=False)
        instance.echo = False
        logger.debug("Database service created with existing engine")
        return instance

    @database_error_handler("initialize database schema")
    def initialize_database(self) -> None:
        """Initialize database with tables and enums.

        Creates all tables and required PostgreSQL enums if they don't exist.
        This is idempotent - safe to call multiple times.
        """
        logger.info("Initializing database schema")

        # Create enums first (required by tables)
        self._create_enums_safely()

        # Create all tables
        Base.metadata.create_all(self.engine)
        logger.info("Database schema initialization completed")

    @database_error_handler("create PostgreSQL enums")
    def _create_enums_safely(self) -> None:
        """Create PostgreSQL enums safely with proper error handling."""
        logger.debug("Creating PostgreSQL enums")

        with self.engine.connect() as connection:
            enum_definitions = get_standard_enum_definitions()
            create_postgresql_enums(connection, enum_definitions)
            connection.commit()
            logger.debug("PostgreSQL enums created successfully")

    @contextmanager
    @database_error_handler("manage database session")
    def get_session(self) -> Generator[Session]:
        """Get database session with automatic cleanup.

        Yields:
            SQLAlchemy session with automatic commit/rollback handling

        Example:
            ```python
            with service.get_session() as session:
                job = session.query(ScrapingJob).first()
                # Session automatically closed
            ```
        """
        session = self.Session()
        try:
            logger.debug("Database session created")
            yield session
            session.commit()
            logger.debug("Database session committed")
        except Exception as e:
            logger.warning("Database session rollback", error=str(e))
            session.rollback()
            raise
        finally:
            session.close()
            logger.debug("Database session closed")

    @content_processing_error_handler("extract URL slug")
    def _extract_slug_from_url(self, url: str) -> str:
        """Extract slug from URL path for naming.

        Args:
            url: Full URL string

        Returns:
            URL slug or 'index' if extraction fails
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.strip("/")
        slug = path.split("/")[-1] if path else "index"
        # Clean up slug for filesystem safety
        import re

        slug = re.sub(r"[^\w\-_.]", "", slug)[:50]  # Max 50 chars
        logger.debug("Slug extracted", url=url, slug=slug)
        return slug or "index"

    @content_processing_error_handler("normalize priority value")
    def _normalize_priority(self, priority: str | object) -> int:
        """Normalize priority value to integer.

        Args:
            priority: Priority as string, enum, or object

        Returns:
            Integer priority value (1-10 scale)
        """
        if hasattr(priority, "value"):
            # Handle enum objects
            normalized = int(priority.value)
        elif isinstance(priority, str):
            # Handle string values
            priority_map = {"low": 1, "normal": 5, "high": 8, "urgent": 10}
            normalized = priority_map.get(priority.lower(), 5)
        else:
            # Handle direct integer or other types
            try:
                # Try to convert object to int, handle potential type issues
                normalized = (
                    int(priority) if isinstance(priority, (int, float)) else int(str(priority))
                )
            except (ValueError, TypeError):
                logger.warning(
                    f"Unable to parse priority '{priority}', using default", priority=priority
                )
                normalized = 5  # Default priority

        # Clamp to valid range
        normalized = max(1, min(10, normalized))
        logger.debug("Priority normalized", original=priority, normalized=normalized)
        return normalized
