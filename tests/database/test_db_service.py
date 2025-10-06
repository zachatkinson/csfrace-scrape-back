"""Comprehensive tests for src/database/service.py.

Test coverage: 210 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.

DatabaseService is a facade that delegates to specialized services:
- JobService (job management, batch operations)
- ContentService (content storage)
- LoggingService (logging operations)
- StatisticsService (metrics and analytics)
- CleanupService (maintenance operations)

Tests verify delegation patterns, session management, and error handling.
"""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.common.status import JobPriority, JobStatus
from src.database.models import ContentResult, JobLog, ScrapingJob
from src.database.service import (
    DatabaseService,
    JobCreateRequest,
    JobLogRequest,
    _add_job_log_safe,
    _close_all_sessions_safe,
)

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def mock_engine() -> Mock:
    """Factory for mock SQLAlchemy engine - DRY principle."""
    engine = Mock(spec=Engine)
    engine.connect = MagicMock()
    engine.dispose = Mock()
    return engine


@pytest.fixture
def mock_session() -> Mock:
    """Factory for mock SQLAlchemy session - DRY principle."""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.expunge = Mock()
    return session


@pytest.fixture
def mock_session_maker(mock_session: Mock) -> Mock:
    """Factory for mock sessionmaker - DRY principle."""
    session_maker = Mock(spec=sessionmaker)
    session_maker.return_value = mock_session
    session_maker.close_all = Mock()
    return session_maker


@pytest.fixture
def database_service_instance(mock_engine: Mock, mock_session_maker: Mock) -> DatabaseService:
    """Factory for DatabaseService instance - DRY principle."""
    with (
        patch("src.database.service.create_database_engine", return_value=mock_engine),
        patch("src.database.service.sessionmaker", return_value=mock_session_maker),
    ):
        service = DatabaseService(echo=False)
        service.SessionLocal = mock_session_maker
        return service


@pytest.fixture
def sample_job_request() -> JobCreateRequest:
    """Factory for sample JobCreateRequest - DRY principle."""
    return JobCreateRequest(
        url="https://example.com/test-page",
        output_directory="/tmp/output",
        user_id="user123",
        domain="example.com",
        slug="test-page",
        batch_id=None,
        priority="normal",
    )


@pytest.fixture
def sample_job_log_request() -> JobLogRequest:
    """Factory for sample JobLogRequest - DRY principle."""
    return JobLogRequest(
        job_id="job123",
        level="INFO",
        message="Test log message",
        component="scraper",
        operation="fetch",
        context_data={"url": "https://example.com"},
    )


@pytest.fixture
def sample_scraping_job() -> Mock:
    """Factory for sample ScrapingJob - DRY principle."""
    job = Mock(spec=ScrapingJob)
    job.id = "job123"
    job.url = "https://example.com/test"
    job.status = JobStatus.PENDING
    job.priority = JobPriority.NORMAL
    return job


# =============================================================================
# TEST DatabaseService - Initialization
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceInit:
    """Test DatabaseService initialization."""

    def test_init_creates_engine_and_session_maker(self) -> None:
        """Test initialization creates engine and session maker."""
        # Arrange
        mock_engine = Mock(spec=Engine)

        with (
            patch(
                "src.database.service.create_database_engine", return_value=mock_engine
            ) as mock_create,
            patch("src.database.service.sessionmaker") as mock_sessionmaker,
        ):
            # Act
            service = DatabaseService(echo=True)

            # Assert
            mock_create.assert_called_once_with(echo=True)
            mock_sessionmaker.assert_called_once()
            assert service.engine is mock_engine
            assert service.echo is True

    def test_create_with_engine_bypasses_init(self, mock_engine: Mock) -> None:
        """Test _create_with_engine class method bypasses __init__."""
        # Arrange & Act
        with patch("src.database.service.sessionmaker") as mock_sessionmaker:
            service = DatabaseService._create_with_engine(mock_engine)

            # Assert
            assert service.engine is mock_engine
            assert service.echo is False
            mock_sessionmaker.assert_called_once()


# =============================================================================
# TEST DatabaseService - Database Initialization
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceDatabaseInit:
    """Test DatabaseService database initialization."""

    def test_initialize_database_creates_enums_and_tables(
        self, database_service_instance: DatabaseService
    ) -> None:
        """Test initialize_database creates enums and tables."""
        # Arrange
        with (
            patch.object(database_service_instance, "_create_enums_safely") as mock_create_enums,
            patch("src.database.service.Base.metadata.create_all") as mock_create_all,
        ):
            # Act
            database_service_instance.initialize_database()

            # Assert
            mock_create_enums.assert_called_once()
            mock_create_all.assert_called_once_with(
                bind=database_service_instance.engine, checkfirst=True
            )

    def test_create_enums_safely_creates_postgresql_enums(
        self, database_service_instance: DatabaseService
    ) -> None:
        """Test _create_enums_safely creates PostgreSQL enums."""
        # Arrange
        mock_connection = Mock()
        mock_connection.commit = Mock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = Mock(return_value=mock_connection)
        mock_context_manager.__exit__ = Mock(return_value=None)

        with (
            patch.object(
                database_service_instance.engine, "connect", return_value=mock_context_manager
            ),
            patch("src.database.service.create_postgresql_enums") as mock_create_enums,
            patch("src.database.service.get_standard_enum_definitions") as mock_get_enums,
        ):
            enum_defs = [("jobstatus", ["pending", "completed"])]
            mock_get_enums.return_value = enum_defs

            # Act
            database_service_instance._create_enums_safely()

            # Assert
            mock_get_enums.assert_called_once()
            mock_create_enums.assert_called_once_with(mock_connection, enum_defs)
            mock_connection.commit.assert_called_once()


# =============================================================================
# TEST DatabaseService - Session Management
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceSessionManagement:
    """Test DatabaseService session management."""

    def test_get_session_yields_session(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_session yields a database session."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        # Act
        with database_service_instance.get_session() as session:
            # Assert within context
            assert session is mock_session

        # Assert after context
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_get_session_commits_on_success(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_session commits transaction on success."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        # Act
        with database_service_instance.get_session():
            pass

        # Assert
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_get_session_rollback_on_exception(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_session rolls back on exception."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        # Act & Assert
        with pytest.raises(ValueError):
            with database_service_instance.get_session():
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()


# =============================================================================
# TEST DatabaseService - Job Management Operations
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceJobOperations:
    """Test DatabaseService job management operations."""

    def test_create_job_delegates_to_job_service(
        self,
        database_service_instance: DatabaseService,
        mock_session: Mock,
        sample_job_request: JobCreateRequest,
        sample_scraping_job: Mock,
    ) -> None:
        """Test create_job delegates to JobService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.create_job = Mock(return_value=sample_scraping_job)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.create_job(sample_job_request)

            # Assert
            mock_job_service_class.assert_called_once_with(mock_session)
            mock_job_service.create_job.assert_called_once()
            mock_session.expunge.assert_called_once_with(sample_scraping_job)
            assert result is sample_scraping_job

    def test_get_job_delegates_to_job_service(
        self,
        database_service_instance: DatabaseService,
        mock_session: Mock,
        sample_scraping_job: Mock,
    ) -> None:
        """Test get_job delegates to JobService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_job = Mock(return_value=sample_scraping_job)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_job("job123")

            # Assert
            mock_job_service.get_job.assert_called_once_with("job123")
            mock_session.expunge.assert_called_once_with(sample_scraping_job)
            assert result is sample_scraping_job

    def test_get_job_returns_none_when_not_found(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_job returns None when job not found."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_job = Mock(return_value=None)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_job("nonexistent")

            # Assert
            assert result is None
            mock_session.expunge.assert_not_called()

    def test_update_job_status_converts_status_types(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test update_job_status converts status and duration types."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        updated_job = Mock(spec=ScrapingJob)

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.update_job_status = Mock(return_value=updated_job)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.update_job_status(
                "job123", "completed", "Success", 2.5
            )

            # Assert
            mock_job_service.update_job_status.assert_called_once_with(
                "job123", JobStatus.COMPLETED, "Success", 2500
            )
            assert result is True

    def test_get_pending_jobs_delegates_with_limit(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_pending_jobs delegates to JobService with limit."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        pending_jobs = [Mock(spec=ScrapingJob), Mock(spec=ScrapingJob)]

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_pending_jobs = Mock(return_value=pending_jobs)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_pending_jobs(limit=50)

            # Assert
            mock_job_service.get_pending_jobs.assert_called_once_with(50)
            assert result == pending_jobs

    def test_get_jobs_by_status_converts_status_type(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_jobs_by_status converts status to enum."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        jobs = [Mock(spec=ScrapingJob)]

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_jobs_by_status = Mock(return_value=jobs)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_jobs_by_status("pending", limit=100, offset=10)

            # Assert
            mock_job_service.get_jobs_by_status.assert_called_once_with(
                JobStatus.PENDING, 100, None, 10
            )
            assert result == jobs

    def test_get_retry_jobs_delegates_with_max_jobs(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_retry_jobs delegates to JobService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        retry_jobs = [Mock(spec=ScrapingJob)]

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_retry_jobs = Mock(return_value=retry_jobs)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_retry_jobs(max_jobs=25)

            # Assert
            mock_job_service.get_retry_jobs.assert_called_once_with(25)
            assert result == retry_jobs


# =============================================================================
# TEST DatabaseService - Batch Operations
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceBatchOperations:
    """Test DatabaseService batch operations."""

    def test_create_jobs_delegates_to_job_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test create_jobs delegates to JobService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        urls = ["https://example.com/1", "https://example.com/2"]
        created_jobs = [Mock(spec=ScrapingJob), Mock(spec=ScrapingJob)]

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.create_jobs = Mock(return_value=created_jobs)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.create_jobs(urls, output_directory="/tmp")

            # Assert
            mock_job_service.create_jobs.assert_called_once_with(urls, output_directory="/tmp")
            assert result == created_jobs

    def test_get_batch_jobs_delegates_to_job_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_batch_jobs delegates to JobService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        batch_jobs = [Mock(spec=ScrapingJob)]

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_batch_jobs = Mock(return_value=batch_jobs)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_batch_jobs("batch123")

            # Assert
            mock_job_service.get_batch_jobs.assert_called_once_with("batch123")
            assert result == batch_jobs

    def test_get_batch_summary_delegates_to_job_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_batch_summary delegates to JobService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        summary = {"total": 10, "completed": 5, "failed": 2, "pending": 3}

        with patch("src.database.service.JobService") as mock_job_service_class:
            mock_job_service = Mock()
            mock_job_service.get_batch_summary = Mock(return_value=summary)
            mock_job_service_class.return_value = mock_job_service

            # Act
            result = database_service_instance.get_batch_summary("batch123")

            # Assert
            mock_job_service.get_batch_summary.assert_called_once_with("batch123")
            assert result == summary


# =============================================================================
# TEST DatabaseService - Content Operations
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceContentOperations:
    """Test DatabaseService content operations."""

    def test_save_content_result_delegates_to_content_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test save_content_result delegates to ContentService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        content_result = Mock(spec=ContentResult)
        # Mock all attributes to prevent DetachedInstanceError
        content_result.id = "content123"
        content_result.job_id = "job123"
        content_result.original_html = "<html></html>"
        content_result.converted_html = "<div></div>"
        content_result.shopify_html = None
        content_result.html_file_path = "/tmp/file.html"
        content_result.metadata_file_path = "/tmp/metadata.txt"
        content_result.images_directory = "/tmp/images"
        content_result.title = "Test Title"
        content_result.meta_description = "Test Description"
        content_result.published_date = None
        content_result.author = None
        content_result.tags = []
        content_result.categories = []
        content_result.og_title = None
        content_result.og_description = None
        content_result.og_image = None
        content_result.twitter_card = None
        content_result.word_count = 100
        content_result.image_count = 5
        content_result.link_count = 10
        content_result.processing_time_seconds = 1.5
        content_result.extra_metadata = {}
        content_result.conversion_stats = {}
        content_result.created_at = None
        content_result.updated_at = None

        with patch("src.database.service.ContentService") as mock_content_service_class:
            mock_content_service = Mock()
            mock_content_service.save_content_result = Mock(return_value=content_result)
            mock_content_service_class.return_value = mock_content_service

            # Act
            result = database_service_instance.save_content_result(
                job_id="job123",
                html_content="<html>Test</html>",
                metadata={"title": "Test"},
                file_paths={"html": "/tmp/file.html"},
                word_count=100,
            )

            # Assert
            mock_content_service.save_content_result.assert_called_once()
            call_args = mock_content_service.save_content_result.call_args
            assert call_args[0][0] == "job123"
            assert call_args[0][1] == "<html>Test</html>"
            assert call_args[0][2] == "html"
            assert "title" in call_args[0][3]
            assert "word_count" in call_args[0][3]
            mock_session.expunge.assert_called_once_with(content_result)
            assert result is content_result


# =============================================================================
# TEST DatabaseService - Logging Operations
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceLoggingOperations:
    """Test DatabaseService logging operations."""

    def test_add_job_log_delegates_to_helper_function(
        self, database_service_instance: DatabaseService, sample_job_log_request: JobLogRequest
    ) -> None:
        """Test add_job_log delegates to _add_job_log_safe."""
        # Arrange
        job_log = Mock(spec=JobLog)

        with patch("src.database.service._add_job_log_safe", return_value=job_log) as mock_helper:
            # Act
            result = database_service_instance.add_job_log(sample_job_log_request)

            # Assert
            mock_helper.assert_called_once_with(database_service_instance, sample_job_log_request)
            assert result is job_log

    def test_add_job_log_safe_helper_converts_request(
        self,
        database_service_instance: DatabaseService,
        mock_session: Mock,
        sample_job_log_request: JobLogRequest,
    ) -> None:
        """Test _add_job_log_safe converts request format."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        job_log = Mock(spec=JobLog)

        with patch("src.database.service.LoggingService") as mock_logging_service_class:
            mock_logging_service = Mock()
            mock_logging_service.add_job_log = Mock(return_value=job_log)
            mock_logging_service_class.return_value = mock_logging_service

            # Act
            result = _add_job_log_safe(database_service_instance, sample_job_log_request)

            # Assert
            mock_logging_service.add_job_log.assert_called_once()
            assert result is job_log


# =============================================================================
# TEST DatabaseService - Statistics Operations
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceStatisticsOperations:
    """Test DatabaseService statistics operations."""

    def test_get_job_statistics_delegates_to_statistics_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_job_statistics delegates to StatisticsService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        stats: dict[str, Any] = {"total_jobs": 100, "completed": 80, "failed": 20}

        with patch("src.database.service.StatisticsService") as mock_stats_service_class:
            mock_stats_service = Mock()
            mock_stats_service.get_job_statistics = Mock(return_value=stats)
            mock_stats_service_class.return_value = mock_stats_service

            # Act
            result = database_service_instance.get_job_statistics(days=14)

            # Assert
            mock_stats_service.get_job_statistics.assert_called_once_with(14)
            assert result == stats

    def test_get_performance_metrics_delegates_to_statistics_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_performance_metrics delegates to StatisticsService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        metrics: dict[str, Any] = {"avg_processing_time": 2.5, "p95": 5.0}

        with patch("src.database.service.StatisticsService") as mock_stats_service_class:
            mock_stats_service = Mock()
            mock_stats_service.get_performance_metrics = Mock(return_value=metrics)
            mock_stats_service_class.return_value = mock_stats_service

            # Act
            result = database_service_instance.get_performance_metrics(days=7)

            # Assert
            mock_stats_service.get_performance_metrics.assert_called_once_with(None, 7)
            assert result == metrics

    def test_get_domain_statistics_wraps_result_in_list(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_domain_statistics wraps dict in list."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        stats: dict[str, Any] = {"domain": "example.com", "total_jobs": 50}

        with patch("src.database.service.StatisticsService") as mock_stats_service_class:
            mock_stats_service = Mock()
            mock_stats_service.get_job_statistics = Mock(return_value=stats)
            mock_stats_service_class.return_value = mock_stats_service

            # Act
            result = database_service_instance.get_domain_statistics(days=30)

            # Assert
            mock_stats_service.get_job_statistics.assert_called_once_with(30)
            assert result == [stats]

    def test_get_processing_time_percentiles_delegates_to_statistics_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_processing_time_percentiles delegates to StatisticsService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        percentiles: dict[str, Any] = {"p50": 2.0, "p95": 5.0, "p99": 10.0}

        with patch("src.database.service.StatisticsService") as mock_stats_service_class:
            mock_stats_service = Mock()
            mock_stats_service.get_performance_metrics = Mock(return_value=percentiles)
            mock_stats_service_class.return_value = mock_stats_service

            # Act
            result = database_service_instance.get_processing_time_percentiles(days=7)

            # Assert
            mock_stats_service.get_performance_metrics.assert_called_once_with(None, 7)
            assert result == percentiles


# =============================================================================
# TEST DatabaseService - Cleanup Operations
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceCleanupOperations:
    """Test DatabaseService cleanup operations."""

    def test_cleanup_jobs_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test cleanup_jobs delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.CleanupService") as mock_cleanup_service_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.cleanup_jobs = Mock(return_value=15)
            mock_cleanup_service_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.cleanup_jobs(days=7)

            # Assert
            mock_cleanup_service.cleanup_jobs.assert_called_once_with(7)
            assert result == 15

    def test_cleanup_failed_jobs_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test cleanup_failed_jobs delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.CleanupService") as mock_cleanup_service_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.cleanup_failed_jobs = Mock(return_value=5)
            mock_cleanup_service_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.cleanup_failed_jobs(days=3)

            # Assert
            mock_cleanup_service.cleanup_failed_jobs.assert_called_once_with(3)
            assert result == 5

    def test_cleanup_orphaned_content_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test cleanup_orphaned_content delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.CleanupService") as mock_cleanup_service_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.cleanup_orphaned_content = Mock(return_value=10)
            mock_cleanup_service_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.cleanup_orphaned_content()

            # Assert
            mock_cleanup_service.cleanup_orphaned_content.assert_called_once()
            assert result == 10

    def test_cleanup_orphaned_logs_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test cleanup_orphaned_logs delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)

        with patch("src.database.service.CleanupService") as mock_cleanup_service_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.cleanup_orphaned_logs = Mock(return_value=8)
            mock_cleanup_service_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.cleanup_orphaned_logs()

            # Assert
            mock_cleanup_service.cleanup_orphaned_logs.assert_called_once()
            assert result == 8

    def test_cleanup_all_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test cleanup_all delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        cleanup_summary: dict[str, Any] = {
            "old_jobs_deleted": 15,
            "failed_jobs_deleted": 5,
            "orphaned_content_deleted": 10,
            "orphaned_logs_deleted": 8,
        }

        # Patch at the import location in service.py where it's used
        with patch("src.database.services.cleanup_service.CleanupService") as mock_cleanup_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.cleanup_all = Mock(return_value=cleanup_summary)
            mock_cleanup_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.cleanup_all(old_jobs_days=7, failed_jobs_days=3)

            # Assert
            mock_cleanup_service.cleanup_all.assert_called_once_with(7, 3)
            assert result == cleanup_summary

    def test_get_database_size_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_database_size delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        size_info: dict[str, Any] = {"total_size": "100 MB", "tables_size": "80 MB"}

        # Patch at the import location in service.py where it's used
        with patch("src.database.services.cleanup_service.CleanupService") as mock_cleanup_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.get_database_size = Mock(return_value=size_info)
            mock_cleanup_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.get_database_size()

            # Assert
            mock_cleanup_service.get_database_size.assert_called_once()
            assert result == size_info

    def test_get_table_sizes_delegates_to_cleanup_service(
        self, database_service_instance: DatabaseService, mock_session: Mock
    ) -> None:
        """Test get_table_sizes delegates to CleanupService."""
        # Arrange
        database_service_instance.SessionLocal = Mock(return_value=mock_session)
        table_sizes: list[dict[str, Any]] = [
            {"table": "jobs", "size": "50 MB"},
            {"table": "content", "size": "30 MB"},
        ]

        # Patch at the import location in service.py where it's used
        with patch("src.database.services.cleanup_service.CleanupService") as mock_cleanup_class:
            mock_cleanup_service = Mock()
            mock_cleanup_service.get_table_sizes = Mock(return_value=table_sizes)
            mock_cleanup_class.return_value = mock_cleanup_service

            # Act
            result = database_service_instance.get_table_sizes()

            # Assert
            mock_cleanup_service.get_table_sizes.assert_called_once()
            assert result == table_sizes


# =============================================================================
# TEST DatabaseService - Session Cleanup
# =============================================================================


@pytest.mark.unit
class TestDatabaseServiceSessionCleanup:
    """Test DatabaseService session cleanup."""

    def test_close_all_sessions_delegates_to_helper(
        self, database_service_instance: DatabaseService
    ) -> None:
        """Test close_all_sessions delegates to _close_all_sessions_safe."""
        # Arrange
        with patch("src.database.service._close_all_sessions_safe") as mock_helper:
            # Act
            database_service_instance.close_all_sessions()

            # Assert
            mock_helper.assert_called_once_with(database_service_instance)

    def test_close_all_sessions_safe_closes_session_maker(
        self, database_service_instance: DatabaseService, mock_session_maker: Mock
    ) -> None:
        """Test _close_all_sessions_safe closes SessionLocal."""
        # Arrange
        database_service_instance.SessionLocal = mock_session_maker

        # Act
        _close_all_sessions_safe(database_service_instance)

        # Assert
        mock_session_maker.close_all.assert_called_once()

    def test_close_all_sessions_safe_disposes_engine(
        self, database_service_instance: DatabaseService, mock_engine: Mock
    ) -> None:
        """Test _close_all_sessions_safe disposes engine."""
        # Arrange
        database_service_instance.engine = mock_engine

        # Act
        _close_all_sessions_safe(database_service_instance)

        # Assert
        mock_engine.dispose.assert_called_once()

    def test_close_all_sessions_safe_handles_missing_attributes(self) -> None:
        """Test _close_all_sessions_safe handles missing attributes gracefully."""
        # Arrange
        service = Mock(spec=DatabaseService)
        service.engine = None
        delattr(service, "SessionLocal")

        # Act - should not raise
        _close_all_sessions_safe(service)

        # Assert - no errors raised

    def test_close_all_sessions_safe_handles_exceptions(
        self, database_service_instance: DatabaseService, mock_engine: Mock
    ) -> None:
        """Test _close_all_sessions_safe handles exceptions gracefully."""
        # Arrange
        database_service_instance.engine = mock_engine
        mock_engine.dispose.side_effect = Exception("Dispose failed")

        # Act - should not raise
        _close_all_sessions_safe(database_service_instance)

        # Assert - no errors raised, exception handled internally
