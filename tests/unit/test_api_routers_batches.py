"""Unit tests for batches router endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from src.api.routers.batches import create_batch, get_batch, list_batches
from src.api.schemas import BatchCreate, BatchListResponse, BatchResponse, BatchWithJobsResponse
from src.database.models import Batch, JobStatus, ScrapingJob


class TestBatchRouterEndpoints:
    """Test batch router endpoint functions."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def batch_create_data(self):
        """Sample batch creation data."""
        return BatchCreate(
            name="Test Batch",
            description="A test batch for API testing",
            urls=["https://example.com/page1", "https://example.com/page2"],
            max_concurrent=5,
            continue_on_error=True,
            create_archives=False,
            cleanup_after_archive=False,
            batch_config={"retry_failed": True},
        )

    @pytest.fixture
    def sample_batch(self):
        """Sample Batch instance."""
        from datetime import datetime, timezone

        return Batch(
            id=1,
            name="Sample Batch",
            description="A sample batch",
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            max_concurrent=10,
            continue_on_error=True,
            output_base_directory="batch_output/sample",
            create_archives=False,
            cleanup_after_archive=False,
            total_jobs=2,
            completed_jobs=0,
            failed_jobs=0,
            skipped_jobs=0,
        )

    @pytest.fixture
    def sample_batch_with_jobs(self, sample_batch):
        """Sample Batch with associated jobs."""
        from datetime import datetime, timezone

        from src.database.models import JobPriority

        job1 = ScrapingJob(
            id=1,
            url="https://example.com/page1",
            domain="example.com",
            slug="page1",
            batch_id=sample_batch.id,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
            retry_count=0,
            max_retries=3,
            timeout_seconds=30,
            output_directory="converted_content/page1",
            skip_existing=False,
            success=False,
            images_downloaded=0,
        )
        job2 = ScrapingJob(
            id=2,
            url="https://example.com/page2",
            domain="example.com",
            slug="page2",
            batch_id=sample_batch.id,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
            retry_count=0,
            max_retries=3,
            timeout_seconds=30,
            output_directory="converted_content/page2",
            skip_existing=False,
            success=False,
            images_downloaded=0,
        )
        sample_batch.jobs = [job1, job2]
        return sample_batch

    @pytest.mark.asyncio
    async def test_create_batch_success(self, mock_db_session, batch_create_data, sample_batch):
        """Test successful batch creation."""
        with patch(
            "src.api.routers.batches.BatchCRUD.create_batch", return_value=sample_batch
        ) as mock_create:
            result = await create_batch(batch_create_data, mock_db_session)

            assert isinstance(result, BatchResponse)
            assert result.id == sample_batch.id
            assert result.name == sample_batch.name
            assert result.description == sample_batch.description
            assert result.total_jobs == sample_batch.total_jobs

            mock_create.assert_called_once_with(mock_db_session, batch_create_data)

    @pytest.mark.asyncio
    async def test_create_batch_database_error(self, mock_db_session, batch_create_data):
        """Test batch creation with database error."""
        with patch("src.api.routers.batches.BatchCRUD.create_batch") as mock_create:
            mock_create.side_effect = SQLAlchemyError("Database connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await create_batch(batch_create_data, mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to create batch" in exc_info.value.detail
            assert "Database connection failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_batches_success(self, mock_db_session):
        """Test successful batch listing."""
        from datetime import datetime, timezone

        batches = [
            Batch(
                id=1,
                name="Batch 1",
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                max_concurrent=10,
                continue_on_error=True,
                output_base_directory="test_output",
                create_archives=False,
                cleanup_after_archive=False,
                total_jobs=5,
                completed_jobs=0,
                failed_jobs=0,
                skipped_jobs=0,
            ),
            Batch(
                id=2,
                name="Batch 2",
                status=JobStatus.RUNNING,
                created_at=datetime.now(timezone.utc),
                max_concurrent=10,
                continue_on_error=True,
                output_base_directory="test_output",
                create_archives=False,
                cleanup_after_archive=False,
                total_jobs=3,
                completed_jobs=0,
                failed_jobs=0,
                skipped_jobs=0,
            ),
        ]

        with patch(
            "src.api.routers.batches.BatchCRUD.get_batches", return_value=(batches, 2)
        ) as mock_get_batches:
            result = await list_batches(mock_db_session, page=1, page_size=10)

            assert isinstance(result, BatchListResponse)
            assert len(result.batches) == 2
            assert result.total == 2
            assert result.page == 1
            assert result.page_size == 10
            assert result.total_pages == 1

            mock_get_batches.assert_called_once_with(mock_db_session, skip=0, limit=10)

    @pytest.mark.asyncio
    async def test_list_batches_pagination_calculation(self, mock_db_session):
        """Test pagination calculation in batch listing."""
        from datetime import datetime, timezone

        batches = [
            Batch(
                id=1,
                name="Batch 1",
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                max_concurrent=10,
                continue_on_error=True,
                output_base_directory="test_output",
                create_archives=False,
                cleanup_after_archive=False,
                total_jobs=1,
                completed_jobs=0,
                failed_jobs=0,
                skipped_jobs=0,
            )
        ]

        with patch("src.api.routers.batches.BatchCRUD.get_batches", return_value=(batches, 47)):
            result = await list_batches(mock_db_session, page=3, page_size=15)

            assert result.page == 3
            assert result.page_size == 15
            assert result.total == 47
            assert result.total_pages == 4  # ceil(47/15) = 4

    @pytest.mark.asyncio
    async def test_list_batches_skip_calculation(self, mock_db_session):
        """Test skip calculation for different pages."""
        with patch(
            "src.api.routers.batches.BatchCRUD.get_batches", return_value=([], 0)
        ) as mock_get_batches:
            # Test page 4 with page_size 25
            await list_batches(mock_db_session, page=4, page_size=25)

            # skip should be (4-1) * 25 = 75
            mock_get_batches.assert_called_once_with(mock_db_session, skip=75, limit=25)

    @pytest.mark.asyncio
    async def test_list_batches_database_error(self, mock_db_session):
        """Test batch listing with database error."""
        with patch("src.api.routers.batches.BatchCRUD.get_batches") as mock_get_batches:
            mock_get_batches.side_effect = SQLAlchemyError("Connection timeout")

            with pytest.raises(HTTPException) as exc_info:
                await list_batches(mock_db_session, page=1, page_size=50)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to retrieve batches" in exc_info.value.detail
            assert "Connection timeout" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_batch_success(self, mock_db_session, sample_batch_with_jobs):
        """Test successful batch retrieval."""
        with patch(
            "src.api.routers.batches.BatchCRUD.get_batch", return_value=sample_batch_with_jobs
        ) as mock_get:
            result = await get_batch(1, mock_db_session)

            assert isinstance(result, BatchWithJobsResponse)
            assert result.id == sample_batch_with_jobs.id
            assert result.name == sample_batch_with_jobs.name
            assert len(result.jobs) == 2

            mock_get.assert_called_once_with(mock_db_session, 1)

    @pytest.mark.asyncio
    async def test_get_batch_not_found(self, mock_db_session):
        """Test batch retrieval when batch doesn't exist."""
        with patch("src.api.routers.batches.BatchCRUD.get_batch", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_batch(999, mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Batch 999 not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_batch_database_error(self, mock_db_session):
        """Test batch retrieval with database error."""
        with patch("src.api.routers.batches.BatchCRUD.get_batch") as mock_get:
            mock_get.side_effect = SQLAlchemyError("Query execution failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_batch(1, mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to retrieve batch" in exc_info.value.detail
            assert "Query execution failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_batches_empty_result(self, mock_db_session):
        """Test batch listing when no batches exist."""
        with patch("src.api.routers.batches.BatchCRUD.get_batches", return_value=([], 0)):
            result = await list_batches(mock_db_session, page=1, page_size=50)

            assert result.batches == []
            assert result.total == 0
            assert result.total_pages == 0

    @pytest.mark.asyncio
    async def test_list_batches_single_page(self, mock_db_session):
        """Test batch listing with single page result."""
        from datetime import datetime, timezone

        batches = [
            Batch(
                id=1,
                name="Single Batch",
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                max_concurrent=10,
                continue_on_error=True,
                output_base_directory="test_output",
                create_archives=False,
                cleanup_after_archive=False,
                total_jobs=1,
                completed_jobs=0,
                failed_jobs=0,
                skipped_jobs=0,
            )
        ]

        with patch("src.api.routers.batches.BatchCRUD.get_batches", return_value=(batches, 1)):
            result = await list_batches(mock_db_session, page=1, page_size=50)

            assert len(result.batches) == 1
            assert result.total == 1
            assert result.total_pages == 1

    @pytest.mark.asyncio
    async def test_batch_response_model_validation(self, mock_db_session, sample_batch):
        """Test BatchResponse model validation."""
        with patch("src.api.routers.batches.BatchCRUD.create_batch", return_value=sample_batch):
            result = await create_batch(
                BatchCreate(name="Test", urls=["https://test.com"]), mock_db_session
            )

            # Verify all required fields are present
            assert hasattr(result, "id")
            assert hasattr(result, "name")
            assert hasattr(result, "status")
            assert hasattr(result, "created_at")
            assert hasattr(result, "total_jobs")
            assert hasattr(result, "max_concurrent")

    @pytest.mark.asyncio
    async def test_batch_with_jobs_response_validation(
        self, mock_db_session, sample_batch_with_jobs
    ):
        """Test BatchWithJobsResponse model validation."""
        with patch(
            "src.api.routers.batches.BatchCRUD.get_batch", return_value=sample_batch_with_jobs
        ):
            result = await get_batch(1, mock_db_session)

            # Should include jobs field
            assert hasattr(result, "jobs")
            assert isinstance(result.jobs, list)
            assert len(result.jobs) == 2

    @pytest.mark.asyncio
    async def test_batch_list_response_validation(self, mock_db_session):
        """Test BatchListResponse model validation."""
        from datetime import datetime, timezone

        batches = [
            Batch(
                id=1,
                name="Test",
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                max_concurrent=10,
                continue_on_error=True,
                output_base_directory="test_output",
                create_archives=False,
                cleanup_after_archive=False,
                total_jobs=1,
                completed_jobs=0,
                failed_jobs=0,
                skipped_jobs=0,
            )
        ]

        with patch("src.api.routers.batches.BatchCRUD.get_batches", return_value=(batches, 1)):
            result = await list_batches(mock_db_session, page=1, page_size=50)

            # Verify pagination structure
            assert isinstance(result.batches, list)
            assert isinstance(result.total, int)
            assert isinstance(result.page, int)
            assert isinstance(result.page_size, int)
            assert isinstance(result.total_pages, int)

    @pytest.mark.asyncio
    async def test_create_batch_model_validation_passthrough(self, mock_db_session, sample_batch):
        """Test that BatchCreate data is properly passed to CRUD layer."""
        batch_data = BatchCreate(
            name="Validation Test",
            description="Testing model validation",
            urls=["https://example.com/test"],
            max_concurrent=7,
            continue_on_error=False,
            output_base_directory="/custom/path",
            create_archives=True,
            cleanup_after_archive=True,
            batch_config={"test_setting": "value"},
        )

        with patch(
            "src.api.routers.batches.BatchCRUD.create_batch", return_value=sample_batch
        ) as mock_create:
            await create_batch(batch_data, mock_db_session)

            # Verify the exact data was passed through
            call_args = mock_create.call_args
            passed_batch_data = call_args[0][1]  # Second argument (first is db_session)

            assert passed_batch_data == batch_data

    @pytest.mark.asyncio
    async def test_batch_router_error_message_formatting(self, mock_db_session, batch_create_data):
        """Test that error messages are properly formatted."""
        error_scenarios = [
            ("Connection timeout", "Failed to create batch: Connection timeout"),
            ("Invalid constraint", "Failed to create batch: Invalid constraint"),
            ("Unique violation", "Failed to create batch: Unique violation"),
        ]

        for db_error, expected_message in error_scenarios:
            with patch("src.api.routers.batches.BatchCRUD.create_batch") as mock_create:
                mock_create.side_effect = SQLAlchemyError(db_error)

                with pytest.raises(HTTPException) as exc_info:
                    await create_batch(batch_create_data, mock_db_session)

                assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert expected_message in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_batches_edge_case_page_calculations(self, mock_db_session):
        """Test edge cases in pagination calculations."""
        test_cases = [
            # (total_items, page_size, expected_total_pages)
            (0, 10, 0),
            (1, 10, 1),
            (10, 10, 1),
            (11, 10, 2),
            (99, 10, 10),
            (100, 10, 10),
            (101, 10, 11),
        ]

        for total_items, page_size, expected_total_pages in test_cases:
            with patch(
                "src.api.routers.batches.BatchCRUD.get_batches", return_value=([], total_items)
            ):
                result = await list_batches(mock_db_session, page=1, page_size=page_size)

                assert result.total_pages == expected_total_pages
                assert result.total == total_items

    @pytest.mark.asyncio
    async def test_get_batch_with_empty_jobs_list(self, mock_db_session, sample_batch):
        """Test getting batch with no associated jobs."""
        sample_batch.jobs = []

        with patch("src.api.routers.batches.BatchCRUD.get_batch", return_value=sample_batch):
            result = await get_batch(1, mock_db_session)

            assert isinstance(result, BatchWithJobsResponse)
            assert result.jobs == []
            assert len(result.jobs) == 0

    @pytest.mark.asyncio
    async def test_batch_response_includes_all_batch_fields(self, mock_db_session, sample_batch):
        """Test that BatchResponse includes all expected batch fields."""
        with patch("src.api.routers.batches.BatchCRUD.create_batch", return_value=sample_batch):
            result = await create_batch(
                BatchCreate(name="Field Test", urls=["https://test.com"]), mock_db_session
            )

            # Check all expected fields are present
            expected_fields = [
                "id",
                "name",
                "description",
                "status",
                "created_at",
                "max_concurrent",
                "continue_on_error",
                "output_base_directory",
                "create_archives",
                "cleanup_after_archive",
                "total_jobs",
                "completed_jobs",
                "failed_jobs",
                "skipped_jobs",
                "success_rate",
            ]

            for field in expected_fields:
                assert hasattr(result, field), f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_batch_with_jobs_response_job_serialization(
        self, mock_db_session, sample_batch_with_jobs
    ):
        """Test that jobs are properly serialized in BatchWithJobsResponse."""
        with patch(
            "src.api.routers.batches.BatchCRUD.get_batch", return_value=sample_batch_with_jobs
        ):
            result = await get_batch(1, mock_db_session)

            assert len(result.jobs) == 2

            # Check job fields are properly serialized
            for job in result.jobs:
                assert hasattr(job, "id")
                assert hasattr(job, "url")
                assert hasattr(job, "domain")
                assert hasattr(job, "status")
                assert hasattr(job, "batch_id")

    @pytest.mark.asyncio
    async def test_list_batches_default_parameters(self, mock_db_session):
        """Test list_batches with default parameters."""
        with patch(
            "src.api.routers.batches.BatchCRUD.get_batches", return_value=([], 0)
        ) as mock_get_batches:
            result = await list_batches(mock_db_session, page=1, page_size=50)

            # Should use default values
            assert result.page == 1
            assert result.page_size == 50

            # Check default skip calculation
            mock_get_batches.assert_called_once_with(
                mock_db_session,
                skip=0,  # (1-1) * 50 = 0
                limit=50,
            )

    @pytest.mark.asyncio
    async def test_list_batches_large_page_numbers(self, mock_db_session):
        """Test list_batches with large page numbers."""
        with patch(
            "src.api.routers.batches.BatchCRUD.get_batches", return_value=([], 1000)
        ) as mock_get_batches:
            result = await list_batches(mock_db_session, page=50, page_size=20)

            # skip should be (50-1) * 20 = 980
            mock_get_batches.assert_called_once_with(mock_db_session, skip=980, limit=20)

            assert result.total_pages == 50  # 1000/20 = 50

    @pytest.mark.asyncio
    async def test_batch_model_validation_error_handling(self, mock_db_session, sample_batch):
        """Test handling of model validation during response creation."""
        # Create batch with potentially problematic data
        from datetime import datetime, timezone

        batch_with_none_values = Batch(
            id=1,
            name="Test Batch",
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            max_concurrent=10,
            continue_on_error=True,
            output_base_directory="test_output",
            create_archives=False,
            cleanup_after_archive=False,
            total_jobs=1,
            completed_jobs=0,
            failed_jobs=0,
            skipped_jobs=0,
            # Some fields might be None
            description=None,
            batch_config=None,
        )

        with patch(
            "src.api.routers.batches.BatchCRUD.create_batch", return_value=batch_with_none_values
        ):
            result = await create_batch(
                BatchCreate(name="Test", urls=["https://test.com"]), mock_db_session
            )

            # Should handle None values gracefully
            assert isinstance(result, BatchResponse)
            assert result.description is None

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_types_handling(self, mock_db_session, batch_create_data):
        """Test handling of different SQLAlchemy error types."""
        from sqlalchemy.exc import (
            DatabaseError,
            DisconnectionError,
            IntegrityError,
            InvalidRequestError,
            OperationalError,
        )

        error_types = [
            IntegrityError("statement", {}, "integrity violation"),
            OperationalError("statement", {}, "operational error"),
            DatabaseError("statement", {}, "database error"),
            DisconnectionError("disconnection error"),
            InvalidRequestError("invalid request"),
        ]

        for error in error_types:
            with patch("src.api.routers.batches.BatchCRUD.create_batch") as mock_create:
                mock_create.side_effect = error

                with pytest.raises(HTTPException) as exc_info:
                    await create_batch(batch_create_data, mock_db_session)

                assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert "Failed to create batch" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_batch_crud_method_calls_exact_parameters(self, mock_db_session, sample_batch):
        """Test that router calls CRUD methods with exact expected parameters."""
        batch_data = BatchCreate(name="Parameter Test", urls=["https://example.com/test"])

        with patch(
            "src.api.routers.batches.BatchCRUD.create_batch", return_value=sample_batch
        ) as mock_create:
            await create_batch(batch_data, mock_db_session)

            # Verify exact call
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0]

            assert call_args[0] == mock_db_session
            assert call_args[1] == batch_data

        with patch(
            "src.api.routers.batches.BatchCRUD.get_batch", return_value=sample_batch
        ) as mock_get:
            await get_batch(42, mock_db_session)

            mock_get.assert_called_once_with(mock_db_session, 42)

        with patch(
            "src.api.routers.batches.BatchCRUD.get_batches", return_value=([], 0)
        ) as mock_get_batches:
            await list_batches(mock_db_session, page=5, page_size=30)

            mock_get_batches.assert_called_once_with(
                mock_db_session,
                skip=120,  # (5-1) * 30
                limit=30,
            )
