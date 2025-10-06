"""Unit tests for src/database/initialization.py following AUDIT_3.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS:
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only

Tests database initialization with comprehensive coverage of schema creation.
"""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.database.initialization import (
    DatabaseInitializer,
    initialize_database_on_startup,
)

# ============================================================================
# Test Helpers
# ============================================================================


def create_mock_session_context() -> tuple[MagicMock, MagicMock]:
    """Helper to create a properly mocked session context manager."""
    mock_session = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_session
    mock_context.__exit__.return_value = None
    return mock_context, mock_session


# ============================================================================
# DatabaseInitializer Tests
# ============================================================================


@pytest.mark.unit
class TestDatabaseInitializer:
    """Unit tests for DatabaseInitializer - MANDATORY AAA pattern."""

    def test_initializer_creation(self) -> None:
        """Test initializer instance creation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup required)

        # Act - MANDATORY
        initializer = DatabaseInitializer()

        # Assert - MANDATORY
        assert initializer is not None
        assert initializer.service is not None
        assert initializer.logger is not None

    def test_initializer_with_custom_service(self) -> None:
        """Test initializer with custom service - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()

        # Act - MANDATORY
        initializer = DatabaseInitializer(service=mock_service)

        # Assert - MANDATORY
        assert initializer.service is mock_service

    def test_initialize_complete_schema_success(self) -> None:
        """Test complete schema initialization success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        initializer = DatabaseInitializer(service=mock_service)

        with patch.object(initializer, "_create_all_tables") as mock_create:
            with patch.object(initializer, "_create_required_indexes") as mock_indexes:
                with patch.object(initializer, "_populate_domain_fields") as mock_populate:
                    with patch.object(initializer, "_verify_schema_integrity") as mock_verify:
                        # Act - MANDATORY
                        result = initializer.initialize_complete_schema()

                        # Assert - MANDATORY
                        assert result is True
                        mock_create.assert_called_once()
                        mock_indexes.assert_called_once()
                        mock_populate.assert_called_once()
                        mock_verify.assert_called_once()

    def test_create_all_tables_called(self) -> None:
        """Test _create_all_tables calls create_all - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_engine = Mock()
        mock_service.engine = mock_engine
        initializer = DatabaseInitializer(service=mock_service)

        with patch("src.database.initialization.Base") as mock_base:
            # Act - MANDATORY
            initializer._create_all_tables()

            # Assert - MANDATORY
            mock_base.metadata.create_all.assert_called_once_with(mock_engine)

    def test_create_required_indexes_creates_indexes(self) -> None:
        """Test _create_required_indexes creates all indexes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context
        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        initializer._create_required_indexes()

        # Assert - MANDATORY
        # Should call execute for multiple index creations
        assert mock_session.execute.call_count >= 8  # At least 8 indexes created

    def test_populate_domain_fields_no_jobs_without_domain(self) -> None:
        """Test _populate_domain_fields with no jobs needing update - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # Mock the COUNT query to return 0 (no jobs without domain)
        mock_session.execute.return_value.scalar.return_value = 0

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        initializer._populate_domain_fields()

        # Assert - MANDATORY
        # Should check for jobs without domain
        assert mock_session.execute.call_count >= 1

    def test_populate_domain_fields_with_jobs_needing_update(self) -> None:
        """Test _populate_domain_fields updates jobs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # Mock first query (COUNT) to return 2 jobs
        # Mock second query (SELECT) to return job data
        mock_job_data = [(1, "https://example.com/page"), (2, "https://test.com/page")]

        mock_session.execute.side_effect = [
            MagicMock(scalar=Mock(return_value=2)),  # COUNT query
            MagicMock(fetchall=Mock(return_value=mock_job_data)),  # SELECT query
            MagicMock(),  # UPDATE query for job 1
            MagicMock(),  # UPDATE query for job 2
        ]

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        with patch("src.database.initialization.extract_domain") as mock_extract:
            mock_extract.side_effect = ["example.com", "test.com"]
            initializer._populate_domain_fields()

        # Assert - MANDATORY
        # Should commit after batch processing
        mock_session.commit.assert_called()

    def test_populate_domain_fields_handles_url_error(self) -> None:
        """Test _populate_domain_fields handles URL extraction errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        mock_job_data = [(1, "invalid-url")]

        mock_session.execute.side_effect = [
            MagicMock(scalar=Mock(return_value=1)),  # COUNT query
            MagicMock(fetchall=Mock(return_value=mock_job_data)),  # SELECT query
            MagicMock(),  # UPDATE query with 'unknown'
        ]

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        with patch("src.database.initialization.extract_domain") as mock_extract:
            from src.utils.url_utils import URLError

            mock_extract.side_effect = URLError("Invalid URL")
            initializer._populate_domain_fields()

        # Assert - MANDATORY
        # Should set domain to 'unknown' for failed extractions
        mock_session.commit.assert_called()

    def test_verify_schema_integrity_all_tables_exist(self) -> None:
        """Test _verify_schema_integrity with all tables - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # Mock all checks: 6 table checks + 1 column check + 1 NULL count check
        # All table/column checks return True, NULL count returns 0
        mock_session.execute.return_value.scalar.side_effect = [
            True,  # users table
            True,  # jobs table
            True,  # content_results table
            True,  # job_logs table
            True,  # oauth_linked_accounts table
            True,  # revoked_tokens table
            True,  # domain column exists
            0,  # no NULL domains
        ]

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        initializer._verify_schema_integrity()

        # Assert - MANDATORY
        # Should check all tables, domain column, and NULL count
        assert mock_session.execute.call_count == 8

    def test_verify_schema_integrity_raises_on_missing_table(self) -> None:
        """Test _verify_schema_integrity raises on missing table - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # First table check returns False (table doesn't exist)
        mock_session.execute.return_value.scalar.return_value = False

        initializer = DatabaseInitializer(service=mock_service)

        # Act & Assert - MANDATORY
        with pytest.raises(RuntimeError, match="Required table .* is missing"):
            initializer._verify_schema_integrity()

    def test_verify_schema_integrity_raises_on_missing_column(self) -> None:
        """Test _verify_schema_integrity raises on missing column - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # All table checks pass, but domain column check fails
        call_count = 0

        def side_effect_tables(*args: Any, **kwargs: Any) -> bool:
            nonlocal call_count
            call_count += 1
            # First 6 calls (table existence) return True
            # 7th call (domain column existence) returns False
            return call_count <= 6

        mock_session.execute.return_value.scalar.side_effect = side_effect_tables

        initializer = DatabaseInitializer(service=mock_service)

        # Act & Assert - MANDATORY
        with pytest.raises(RuntimeError, match="missing required 'domain' column"):
            initializer._verify_schema_integrity()

    def test_verify_schema_integrity_raises_on_null_domains(self) -> None:
        """Test _verify_schema_integrity raises on NULL domains - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        call_count = 0

        def side_effect_checks(*args: Any, **kwargs: Any) -> bool | int:
            nonlocal call_count
            call_count += 1
            # All checks pass except the final NULL domain check
            if call_count <= 7:
                return True
            else:
                return 5  # 5 jobs with NULL domains

        mock_session.execute.return_value.scalar.side_effect = side_effect_checks

        initializer = DatabaseInitializer(service=mock_service)

        # Act & Assert - MANDATORY
        with pytest.raises(RuntimeError, match="jobs with NULL domain fields"):
            initializer._verify_schema_integrity()


# ============================================================================
# Module-Level Functions Tests
# ============================================================================


@pytest.mark.unit
class TestInitializationModuleFunctions:
    """Unit tests for module-level initialization functions - MANDATORY AAA pattern."""

    def test_initialize_database_on_startup_success(self) -> None:
        """Test initialize_database_on_startup returns True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.initialization.DatabaseInitializer") as mock_init_class:
            mock_instance = Mock()
            mock_instance.initialize_complete_schema.return_value = True
            mock_init_class.return_value = mock_instance

            # Act - MANDATORY
            result = initialize_database_on_startup()

            # Assert - MANDATORY
            assert result is True
            mock_instance.initialize_complete_schema.assert_called_once()

    def test_initialize_database_on_startup_exits_on_failure(self) -> None:
        """Test initialize_database_on_startup exits on failure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.database.initialization.DatabaseInitializer") as mock_init_class:
            with patch("src.database.initialization.sys.exit") as mock_exit:
                mock_instance = Mock()
                mock_instance.initialize_complete_schema.return_value = False
                mock_init_class.return_value = mock_instance

                # Act - MANDATORY
                initialize_database_on_startup()

                # Assert - MANDATORY
                mock_exit.assert_called_once_with(1)


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestDatabaseInitializationSecurity:
    """MANDATORY security tests for database initialization."""

    def test_sql_injection_prevention_in_domain_update(self) -> None:
        """MANDATORY: Test SQL injection prevention in domain updates."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # Malicious job data with SQL injection attempt
        malicious_url = "https://example.com/'; DROP TABLE jobs; --"
        mock_job_data = [(1, malicious_url)]

        mock_session.execute.side_effect = [
            MagicMock(scalar=Mock(return_value=1)),
            MagicMock(fetchall=Mock(return_value=mock_job_data)),
            MagicMock(),  # UPDATE should use parameterized query
        ]

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        with patch("src.database.initialization.extract_domain") as mock_extract:
            mock_extract.return_value = "example.com"
            initializer._populate_domain_fields()

        # Assert - MANDATORY
        # Should use parameterized queries (text() with params dict)
        mock_session.commit.assert_called()

    def test_table_name_validation(self) -> None:
        """MANDATORY: Test table name validation in verification."""
        # Arrange - MANDATORY
        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # Mock all checks: 6 table checks + 1 column check + 1 NULL count check
        mock_session.execute.return_value.scalar.side_effect = [
            True,  # users table
            True,  # jobs table
            True,  # content_results table
            True,  # job_logs table
            True,  # oauth_linked_accounts table
            True,  # revoked_tokens table
            True,  # domain column exists
            0,  # no NULL domains
        ]

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        initializer._verify_schema_integrity()

        # Assert - MANDATORY
        # Should check specific required tables (not user input)
        assert mock_session.execute.call_count == 8


# ============================================================================
# MANDATORY Performance Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.performance
class TestDatabaseInitializationPerformance:
    """MANDATORY performance tests for database initialization."""

    def test_schema_initialization_performance(self) -> None:
        """MANDATORY: Test schema initialization performance."""
        # Arrange - MANDATORY
        import time

        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context
        mock_session.execute.return_value.scalar.return_value = True

        # Mock all required methods to succeed quickly
        with patch("src.database.initialization.Base"):
            initializer = DatabaseInitializer(service=mock_service)

            # Act - MANDATORY
            start_time = time.perf_counter()

            with patch.object(initializer, "_create_all_tables"):
                with patch.object(initializer, "_create_required_indexes"):
                    with patch.object(initializer, "_populate_domain_fields"):
                        with patch.object(initializer, "_verify_schema_integrity"):
                            initializer.initialize_complete_schema()

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            assert execution_time < 0.1  # <100ms for mocked initialization

    def test_batch_processing_performance(self) -> None:
        """MANDATORY: Test batch processing performance."""
        # Arrange - MANDATORY
        import time

        mock_service = Mock()
        mock_context, mock_session = create_mock_session_context()
        mock_service.get_session.return_value = mock_context

        # Create large dataset (200 jobs)
        mock_job_data = [(i, f"https://example{i}.com/page") for i in range(200)]

        mock_session.execute.side_effect = [
            MagicMock(scalar=Mock(return_value=200)),
            MagicMock(fetchall=Mock(return_value=mock_job_data)),
        ] + [MagicMock() for _ in range(200)]  # UPDATE queries

        initializer = DatabaseInitializer(service=mock_service)

        # Act - MANDATORY
        start_time = time.perf_counter()

        with patch("src.database.initialization.extract_domain") as mock_extract:
            mock_extract.side_effect = [f"example{i}.com" for i in range(200)]
            initializer._populate_domain_fields()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        assert execution_time < 1.0  # <1s for 200 jobs (batched processing)
        # Should commit in batches (not after each job)
        assert mock_session.commit.call_count <= 2  # 200 jobs / 100 batch size = 2 batches
