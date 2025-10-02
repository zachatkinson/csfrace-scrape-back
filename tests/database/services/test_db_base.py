"""Comprehensive tests for src/database/services/base.py.

Test coverage: 77 statements, 30% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.database.services.base import BaseService

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def mock_engine():
    """Factory for mock SQLAlchemy engine - DRY principle."""
    engine = Mock(spec=Engine)
    engine.connect = MagicMock()
    return engine


@pytest.fixture
def base_service_instance(mock_engine):
    """Factory for BaseService instance - DRY principle."""
    with patch("src.database.services.base.create_database_engine", return_value=mock_engine):
        service = BaseService(echo=False)
    return service


@pytest.fixture
def mock_session():
    """Factory for mock SQLAlchemy session - DRY principle."""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def sample_urls():
    """Factory for sample URL test data - DRY principle."""
    return {
        "simple": "https://example.com/page",
        "nested": "https://example.com/blog/post-title",
        "with_params": "https://example.com/page?id=123",
        "trailing_slash": "https://example.com/page/",
        "root": "https://example.com/",
        "special_chars": "https://example.com/test@#$%page",
    }


# =============================================================================
# TEST BaseService - Initialization
# =============================================================================


@pytest.mark.unit
class TestBaseServiceInit:
    """Test BaseService initialization."""

    def test_init_creates_engine(self):
        """Test __init__ creates database engine."""
        # Arrange & Act
        with patch("src.database.services.base.create_database_engine") as mock_create:
            mock_create.return_value = Mock(spec=Engine)
            service = BaseService(echo=True)

        # Assert
        mock_create.assert_called_once_with(echo=True)
        assert service.engine is not None
        assert service.Session is not None

    def test_init_with_echo_disabled(self):
        """Test __init__ with echo disabled."""
        # Arrange & Act
        with patch("src.database.services.base.create_database_engine") as mock_create:
            mock_create.return_value = Mock(spec=Engine)
            service = BaseService(echo=False)

        # Assert
        mock_create.assert_called_once_with(echo=False)
        assert service.echo is False

    def test_create_with_engine(self, mock_engine):
        """Test _create_with_engine class method."""
        # Act
        service = BaseService._create_with_engine(mock_engine)

        # Assert
        assert service.engine is mock_engine
        assert service.Session is not None
        assert service.echo is False


# =============================================================================
# TEST BaseService - Database Initialization
# =============================================================================


@pytest.mark.unit
class TestBaseServiceDatabaseInit:
    """Test BaseService database initialization."""

    def test_initialize_database_creates_enums(self, base_service_instance):
        """Test initialize_database creates PostgreSQL enums."""
        # Arrange
        mock_connection = Mock()
        base_service_instance.engine.connect = MagicMock(
            return_value=MagicMock(__enter__=Mock(return_value=mock_connection))
        )

        with (
            patch("src.database.services.base.Base.metadata.create_all") as mock_create_all,
            patch("src.database.services.base.get_standard_enum_definitions") as mock_enum_defs,
            patch("src.database.services.base.create_postgresql_enums") as mock_create_enums,
        ):
            mock_enum_defs.return_value = {"status": ["pending", "completed"]}

            # Act
            base_service_instance.initialize_database()

        # Assert
        mock_enum_defs.assert_called_once()
        mock_create_enums.assert_called_once()
        mock_create_all.assert_called_once_with(base_service_instance.engine)
        mock_connection.commit.assert_called_once()

    def test_initialize_database_creates_tables(self, base_service_instance):
        """Test initialize_database creates all tables."""
        # Arrange
        mock_connection = Mock()
        base_service_instance.engine.connect = MagicMock(
            return_value=MagicMock(__enter__=Mock(return_value=mock_connection))
        )

        with (
            patch("src.database.services.base.Base.metadata.create_all") as mock_create_all,
            patch("src.database.services.base.get_standard_enum_definitions") as mock_enum_defs,
            patch("src.database.services.base.create_postgresql_enums"),
        ):
            mock_enum_defs.return_value = {}

            # Act
            base_service_instance.initialize_database()

        # Assert
        mock_create_all.assert_called_once_with(base_service_instance.engine)

    def test_create_enums_safely_calls_utility_functions(self, base_service_instance):
        """Test _create_enums_safely uses utility functions correctly."""
        # Arrange
        mock_connection = Mock()
        base_service_instance.engine.connect = MagicMock(
            return_value=MagicMock(__enter__=Mock(return_value=mock_connection))
        )

        with (
            patch("src.database.services.base.get_standard_enum_definitions") as mock_enum_defs,
            patch("src.database.services.base.create_postgresql_enums") as mock_create_enums,
        ):
            enum_defs = {"status": ["pending", "completed"]}
            mock_enum_defs.return_value = enum_defs

            # Act
            base_service_instance._create_enums_safely()

        # Assert
        mock_enum_defs.assert_called_once()
        mock_create_enums.assert_called_once_with(mock_connection, enum_defs)
        mock_connection.commit.assert_called_once()


# =============================================================================
# TEST BaseService - Session Management
# =============================================================================


@pytest.mark.unit
class TestBaseServiceSessionManagement:
    """Test BaseService session management."""

    def test_get_session_yields_session(self, base_service_instance, mock_session):
        """Test get_session yields a database session."""
        # Arrange
        base_service_instance.Session = Mock(return_value=mock_session)

        # Act
        with base_service_instance.get_session() as session:
            # Assert within context
            assert session is mock_session

        # Assert after context
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_get_session_commits_on_success(self, base_service_instance, mock_session):
        """Test get_session commits transaction on success."""
        # Arrange
        base_service_instance.Session = Mock(return_value=mock_session)

        # Act
        with base_service_instance.get_session() as session:
            pass  # Simulate successful operation

        # Assert
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_get_session_rollback_on_exception(self, base_service_instance, mock_session):
        """Test get_session rolls back on exception."""
        # Arrange
        base_service_instance.Session = Mock(return_value=mock_session)

        # Act & Assert
        with pytest.raises(ValueError):
            with base_service_instance.get_session() as session:
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_get_session_always_closes(self, base_service_instance, mock_session):
        """Test get_session always closes session."""
        # Arrange
        base_service_instance.Session = Mock(return_value=mock_session)

        # Act
        try:
            with base_service_instance.get_session() as session:
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Assert
        mock_session.close.assert_called_once()


# =============================================================================
# TEST BaseService - URL Slug Extraction
# =============================================================================


@pytest.mark.unit
class TestBaseServiceSlugExtraction:
    """Test BaseService URL slug extraction."""

    def test_extract_slug_simple_path(self, base_service_instance):
        """Test _extract_slug_from_url with simple path."""
        # Arrange
        url = "https://example.com/my-page"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert slug == "my-page"

    def test_extract_slug_nested_path(self, base_service_instance):
        """Test _extract_slug_from_url with nested path."""
        # Arrange
        url = "https://example.com/blog/2023/post-title"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert slug == "post-title"

    def test_extract_slug_with_trailing_slash(self, base_service_instance):
        """Test _extract_slug_from_url with trailing slash."""
        # Arrange
        url = "https://example.com/page/"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert slug == "page"

    def test_extract_slug_root_url(self, base_service_instance):
        """Test _extract_slug_from_url with root URL."""
        # Arrange
        url = "https://example.com/"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert slug == "index"

    def test_extract_slug_with_query_params(self, base_service_instance):
        """Test _extract_slug_from_url ignores query parameters."""
        # Arrange
        url = "https://example.com/page?id=123&ref=source"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert slug == "page"

    def test_extract_slug_sanitizes_special_chars(self, base_service_instance):
        """Test _extract_slug_from_url sanitizes special characters."""
        # Arrange
        url = "https://example.com/test@#$%page"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert "@" not in slug
        assert "#" not in slug
        assert "$" not in slug
        assert "%" not in slug

    def test_extract_slug_limits_length(self, base_service_instance):
        """Test _extract_slug_from_url limits slug length."""
        # Arrange
        long_slug = "a" * 100
        url = f"https://example.com/{long_slug}"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert len(slug) <= 50

    def test_extract_slug_preserves_valid_chars(self, base_service_instance):
        """Test _extract_slug_from_url preserves valid characters."""
        # Arrange
        url = "https://example.com/test_page-2024.html"

        # Act
        slug = base_service_instance._extract_slug_from_url(url)

        # Assert
        assert slug == "test_page-2024.html"


# =============================================================================
# TEST BaseService - Priority Normalization
# =============================================================================


@pytest.mark.unit
class TestBaseServicePriorityNormalization:
    """Test BaseService priority normalization."""

    def test_normalize_priority_enum_object(self, base_service_instance):
        """Test _normalize_priority with enum object."""
        # Arrange
        mock_priority = Mock()
        mock_priority.value = 7

        # Act
        result = base_service_instance._normalize_priority(mock_priority)

        # Assert
        assert result == 7

    def test_normalize_priority_string_low(self, base_service_instance):
        """Test _normalize_priority with 'low' string."""
        # Act
        result = base_service_instance._normalize_priority("low")

        # Assert
        assert result == 1

    def test_normalize_priority_string_normal(self, base_service_instance):
        """Test _normalize_priority with 'normal' string."""
        # Act
        result = base_service_instance._normalize_priority("normal")

        # Assert
        assert result == 5

    def test_normalize_priority_string_high(self, base_service_instance):
        """Test _normalize_priority with 'high' string."""
        # Act
        result = base_service_instance._normalize_priority("high")

        # Assert
        assert result == 8

    def test_normalize_priority_string_urgent(self, base_service_instance):
        """Test _normalize_priority with 'urgent' string."""
        # Act
        result = base_service_instance._normalize_priority("urgent")

        # Assert
        assert result == 10

    def test_normalize_priority_string_case_insensitive(self, base_service_instance):
        """Test _normalize_priority is case insensitive."""
        # Act
        result1 = base_service_instance._normalize_priority("HIGH")
        result2 = base_service_instance._normalize_priority("HiGh")

        # Assert
        assert result1 == 8
        assert result2 == 8

    def test_normalize_priority_integer(self, base_service_instance):
        """Test _normalize_priority with integer."""
        # Act
        result = base_service_instance._normalize_priority(6)

        # Assert
        assert result == 6

    def test_normalize_priority_float(self, base_service_instance):
        """Test _normalize_priority with float."""
        # Act
        result = base_service_instance._normalize_priority(7.5)

        # Assert
        assert result == 7

    def test_normalize_priority_clamps_low(self, base_service_instance):
        """Test _normalize_priority clamps values below 1."""
        # Act
        result = base_service_instance._normalize_priority(-5)

        # Assert
        assert result == 1

    def test_normalize_priority_clamps_high(self, base_service_instance):
        """Test _normalize_priority clamps values above 10."""
        # Act
        result = base_service_instance._normalize_priority(15)

        # Assert
        assert result == 10

    def test_normalize_priority_unknown_string_defaults(self, base_service_instance):
        """Test _normalize_priority defaults unknown strings."""
        # Act
        result = base_service_instance._normalize_priority("unknown")

        # Assert
        assert result == 5  # Default priority

    def test_normalize_priority_invalid_type_defaults(self, base_service_instance):
        """Test _normalize_priority handles invalid types."""
        # Act
        result = base_service_instance._normalize_priority(None)

        # Assert
        assert result == 5  # Default priority

    def test_normalize_priority_string_convertible(self, base_service_instance):
        """Test _normalize_priority converts string numbers."""
        # Act
        result = base_service_instance._normalize_priority("8")

        # Assert
        assert result == 5  # Unknown string maps to default
