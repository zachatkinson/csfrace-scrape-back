"""Unit tests for API CRUD operations."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.crud import BatchCRUD, ContentResultCRUD, JobCRUD
from src.api.schemas import BatchCreate, JobCreate, JobUpdate
from src.database.models import Batch, ContentResult, JobPriority, JobStatus, ScrapingJob


class TestJobCRUD:
    """Test JobCRUD operations."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def job_create_data(self):
        """Sample job creation data."""
        return JobCreate(
            url="https://example.com/test-page",
            priority=JobPriority.HIGH,
            custom_slug="test-page-slug",
            max_retries=5,
            timeout_seconds=60,
            skip_existing=True,
            converter_config={"preserve_images": True},
            processing_options={"clean_html": True},
        )

    @pytest.fixture
    def job_update_data(self):
        """Sample job update data."""
        return JobUpdate(
            priority=JobPriority.LOW,
            max_retries=2,
            timeout_seconds=45,
            converter_config={"new_setting": True},
        )

    @pytest.fixture
    def sample_job(self):
        """Sample ScrapingJob instance."""
        return ScrapingJob(
            id=1,
            url="https://example.com/existing-page",
            domain="example.com",
            slug="existing-page",
            priority=JobPriority.NORMAL,
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            retry_count=1,
            max_retries=3,
            timeout_seconds=30,
            output_directory="converted_content/example.com_existing-page",
            skip_existing=False,
            success=False,
            images_downloaded=0,
        )

    @pytest.mark.asyncio
    async def test_create_job_basic(self, mock_db_session, job_create_data):
        """Test basic job creation."""
        # Setup mock
        mock_db_session.flush = AsyncMock()

        result = await JobCRUD.create_job(mock_db_session, job_create_data)

        assert isinstance(result, ScrapingJob)
        assert result.url == str(job_create_data.url)
        assert result.domain == "example.com"
        assert result.slug == "test-page"
        assert result.priority == JobPriority.HIGH
        assert result.custom_slug == "test-page-slug"
        assert result.max_retries == 5
        assert result.timeout_seconds == 60
        assert result.skip_existing is True
        assert result.converter_config == {"preserve_images": True}
        assert result.processing_options == {"clean_html": True}

        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_with_auto_generated_directory(self, mock_db_session):
        """Test job creation with auto-generated output directory."""
        job_data = JobCreate(url="https://test.com/path/page")

        result = await JobCRUD.create_job(mock_db_session, job_data)

        assert result.output_directory == "converted_content/test.com_page"
        assert result.domain == "test.com"
        assert result.slug == "page"

    @pytest.mark.asyncio
    async def test_create_job_with_custom_directory(self, mock_db_session):
        """Test job creation with custom output directory."""
        job_data = JobCreate(url="https://example.com/test", output_directory="/custom/output/path")

        result = await JobCRUD.create_job(mock_db_session, job_data)

        assert result.output_directory == "/custom/output/path"

    @pytest.mark.asyncio
    async def test_create_job_url_parsing_edge_cases(self, mock_db_session):
        """Test job creation with various URL formats."""
        test_cases = [
            ("https://example.com/", "example.com", "index"),
            ("https://subdomain.example.com/deep/path/page", "subdomain.example.com", "page"),
            ("https://example.com/path/", "example.com", "path"),
            ("https://example.com/single", "example.com", "single"),
        ]

        for url, expected_domain, expected_slug in test_cases:
            job_data = JobCreate(url=url)
            result = await JobCRUD.create_job(mock_db_session, job_data)

            assert result.domain == expected_domain
            assert result.slug == expected_slug

    @pytest.mark.asyncio
    async def test_get_job_exists(self, mock_db_session, sample_job):
        """Test getting an existing job."""
        # Setup mock result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        result = await JobCRUD.get_job(mock_db_session, 1)

        assert result == sample_job
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, mock_db_session):
        """Test getting a non-existent job."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await JobCRUD.get_job(mock_db_session, 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_jobs_no_filters(self, mock_db_session):
        """Test getting jobs without filters."""
        # Mock jobs result
        jobs = [ScrapingJob(id=1, url="https://test.com", domain="test.com", slug="test")]
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = jobs

        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs_list, total = await JobCRUD.get_jobs(mock_db_session, skip=0, limit=10)

        assert len(jobs_list) == 1
        assert total == 1
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_jobs_with_status_filter(self, mock_db_session):
        """Test getting jobs with status filter."""
        jobs = [
            ScrapingJob(
                id=1,
                url="https://test.com",
                domain="test.com",
                slug="test",
                status=JobStatus.RUNNING,
            )
        ]
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = jobs
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs_list, total = await JobCRUD.get_jobs(mock_db_session, status=JobStatus.RUNNING)

        assert len(jobs_list) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_jobs_with_domain_filter(self, mock_db_session):
        """Test getting jobs with domain filter."""
        jobs = [
            ScrapingJob(id=1, url="https://example.com/test", domain="example.com", slug="test")
        ]
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = jobs
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs_list, total = await JobCRUD.get_jobs(mock_db_session, domain="example.com")

        assert len(jobs_list) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_jobs_with_pagination(self, mock_db_session):
        """Test getting jobs with pagination."""
        jobs = [
            ScrapingJob(id=i, url=f"https://test.com/page{i}", domain="test.com", slug=f"page{i}")
            for i in range(5)
        ]
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = jobs[:2]  # First 2
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs_list, total = await JobCRUD.get_jobs(mock_db_session, skip=0, limit=2)

        assert len(jobs_list) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_jobs_empty_result(self, mock_db_session):
        """Test getting jobs when no jobs exist."""
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs_list, total = await JobCRUD.get_jobs(mock_db_session)

        assert jobs_list == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_job_success(self, mock_db_session, sample_job, job_update_data):
        """Test successful job update."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job) as mock_get:
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job(mock_db_session, 1, job_update_data)

            assert result == sample_job
            assert sample_job.priority == JobPriority.LOW
            assert sample_job.max_retries == 2
            assert sample_job.timeout_seconds == 45
            assert sample_job.converter_config == {"new_setting": True}

            mock_get.assert_called_once_with(mock_db_session, 1)
            mock_db_session.flush.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_update_job_not_found(self, mock_db_session, job_update_data):
        """Test updating non-existent job."""
        with patch.object(JobCRUD, "get_job", return_value=None):
            result = await JobCRUD.update_job(mock_db_session, 999, job_update_data)
            assert result is None

    @pytest.mark.asyncio
    async def test_update_job_partial_update(self, mock_db_session, sample_job):
        """Test partial job update (only some fields)."""
        partial_update = JobUpdate(priority=JobPriority.HIGH)

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job(mock_db_session, 1, partial_update)

            assert result == sample_job
            assert sample_job.priority == JobPriority.HIGH
            # Other fields should remain unchanged

    @pytest.mark.asyncio
    async def test_delete_job_success(self, mock_db_session, sample_job):
        """Test successful job deletion."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.delete = AsyncMock()

            result = await JobCRUD.delete_job(mock_db_session, 1)

            assert result is True
            mock_db_session.delete.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, mock_db_session):
        """Test deleting non-existent job."""
        with patch.object(JobCRUD, "get_job", return_value=None):
            result = await JobCRUD.delete_job(mock_db_session, 999)
            assert result is False

    @pytest.mark.asyncio
    async def test_update_job_status_to_running(self, mock_db_session, sample_job):
        """Test updating job status to running."""
        sample_job.started_at = None  # Ensure it's None initially

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job_status(mock_db_session, 1, JobStatus.RUNNING)

            assert result == sample_job
            assert sample_job.status == JobStatus.RUNNING
            assert sample_job.started_at is not None
            assert isinstance(sample_job.started_at, datetime)

    @pytest.mark.asyncio
    async def test_update_job_status_to_completed(self, mock_db_session, sample_job):
        """Test updating job status to completed."""
        sample_job.completed_at = None
        sample_job.success = False

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job_status(mock_db_session, 1, JobStatus.COMPLETED)

            assert result == sample_job
            assert sample_job.status == JobStatus.COMPLETED
            assert sample_job.completed_at is not None
            assert sample_job.success is True

    @pytest.mark.asyncio
    async def test_update_job_status_to_failed(self, mock_db_session, sample_job):
        """Test updating job status to failed with error details."""
        sample_job.completed_at = None

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job_status(
                mock_db_session,
                1,
                JobStatus.FAILED,
                error_message="Test error",
                error_type="TestException",
            )

            assert result == sample_job
            assert sample_job.status == JobStatus.FAILED
            assert sample_job.error_message == "Test error"
            assert sample_job.error_type == "TestException"
            assert sample_job.completed_at is not None
            assert sample_job.success is False

    @pytest.mark.asyncio
    async def test_update_job_status_not_found(self, mock_db_session):
        """Test updating status of non-existent job."""
        with patch.object(JobCRUD, "get_job", return_value=None):
            result = await JobCRUD.update_job_status(mock_db_session, 999, JobStatus.RUNNING)
            assert result is None

    @pytest.mark.asyncio
    async def test_update_job_status_running_with_existing_started_at(
        self, mock_db_session, sample_job
    ):
        """Test updating to running when started_at already exists."""
        existing_time = datetime.now(UTC)
        sample_job.started_at = existing_time

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job_status(mock_db_session, 1, JobStatus.RUNNING)

            # Should not overwrite existing started_at
            assert result.started_at == existing_time

    @pytest.mark.asyncio
    async def test_update_job_status_cancelled(self, mock_db_session, sample_job):
        """Test updating job status to cancelled."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job_status(mock_db_session, 1, JobStatus.CANCELLED)

            assert result.status == JobStatus.CANCELLED
            assert result.completed_at is not None
            assert result.success is False


class TestBatchCRUD:
    """Test BatchCRUD operations."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def batch_create_data(self):
        """Sample batch creation data."""
        return BatchCreate(
            name="Test Batch",
            description="A test batch",
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
        return Batch(
            id=1,
            name="Existing Batch",
            description="An existing batch",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            max_concurrent=10,
            continue_on_error=True,
            output_base_directory="test_output",
            create_archives=False,
            cleanup_after_archive=False,
            total_jobs=3,
            completed_jobs=0,
            failed_jobs=0,
            skipped_jobs=0,
        )

    @pytest.mark.asyncio
    async def test_create_batch_basic(self, mock_db_session, batch_create_data):
        """Test basic batch creation."""
        with patch.object(JobCRUD, "create_job") as mock_create_job:
            # Setup mocks
            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            # Mock created jobs
            mock_job1 = ScrapingJob(id=1, url="https://example.com/page1")
            mock_job2 = ScrapingJob(id=2, url="https://example.com/page2")
            mock_create_job.side_effect = [mock_job1, mock_job2]

            result = await BatchCRUD.create_batch(mock_db_session, batch_create_data)

            assert isinstance(result, Batch)
            assert result.name == "Test Batch"
            assert result.description == "A test batch"
            assert result.max_concurrent == 5
            assert result.continue_on_error is True
            assert result.create_archives is False
            assert result.cleanup_after_archive is False
            assert result.batch_config == {"retry_failed": True}
            assert result.total_jobs == 2

            # Should create jobs for each URL
            assert mock_create_job.call_count == 2
            mock_db_session.add.assert_called_once()
            assert mock_db_session.flush.call_count == 2  # Once for batch, once for jobs

    @pytest.mark.asyncio
    async def test_create_batch_with_custom_output_directory(self, mock_db_session):
        """Test batch creation with custom output directory."""
        batch_data = BatchCreate(
            name="Custom Dir Batch",
            urls=["https://test.com/page"],
            output_base_directory="/custom/output",
        )

        with patch.object(JobCRUD, "create_job"):
            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await BatchCRUD.create_batch(mock_db_session, batch_data)

            assert result.output_base_directory == "/custom/output"

    @pytest.mark.asyncio
    async def test_create_batch_auto_generated_directory(self, mock_db_session):
        """Test batch creation with auto-generated output directory."""
        batch_data = BatchCreate(
            name="Auto Dir Batch",
            urls=["https://test.com/page"],
            # No output_base_directory specified
        )

        with patch.object(JobCRUD, "create_job"):
            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await BatchCRUD.create_batch(mock_db_session, batch_data)

            assert result.output_base_directory == "batch_output/Auto Dir Batch"

    @pytest.mark.asyncio
    async def test_create_batch_empty_urls(self, mock_db_session):
        """Test batch creation with empty URL list."""
        batch_data = BatchCreate(name="Empty Batch", urls=[])

        with patch.object(JobCRUD, "create_job") as mock_create_job:
            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await BatchCRUD.create_batch(mock_db_session, batch_data)

            assert result.total_jobs == 0
            mock_create_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_batch_exists(self, mock_db_session, sample_batch):
        """Test getting an existing batch."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_batch
        mock_db_session.execute.return_value = mock_result

        result = await BatchCRUD.get_batch(mock_db_session, 1)

        assert result == sample_batch
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_batch_not_found(self, mock_db_session):
        """Test getting a non-existent batch."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await BatchCRUD.get_batch(mock_db_session, 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_batches(self, mock_db_session):
        """Test getting paginated batches."""
        batches = [
            Batch(id=1, name="Batch 1", total_jobs=2),
            Batch(id=2, name="Batch 2", total_jobs=3),
        ]

        # Mock batches result
        mock_batches_result = MagicMock()
        mock_batches_result.scalars.return_value.all.return_value = batches

        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_db_session.execute.side_effect = [mock_batches_result, mock_count_result]

        batches_list, total = await BatchCRUD.get_batches(mock_db_session, skip=0, limit=10)

        assert len(batches_list) == 2
        assert total == 2
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_batches_with_pagination(self, mock_db_session):
        """Test getting batches with pagination."""
        batches = [Batch(id=1, name="Batch 1", total_jobs=1)]

        mock_batches_result = MagicMock()
        mock_batches_result.scalars.return_value.all.return_value = batches
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_db_session.execute.side_effect = [mock_batches_result, mock_count_result]

        batches_list, total = await BatchCRUD.get_batches(mock_db_session, skip=10, limit=5)

        assert len(batches_list) == 1
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_batches_empty_result(self, mock_db_session):
        """Test getting batches when none exist."""
        mock_batches_result = MagicMock()
        mock_batches_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db_session.execute.side_effect = [mock_batches_result, mock_count_result]

        batches_list, total = await BatchCRUD.get_batches(mock_db_session)

        assert batches_list == []
        assert total == 0


class TestContentResultCRUD:
    """Test ContentResultCRUD operations."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def sample_content_result(self):
        """Sample ContentResult instance."""
        return ContentResult(
            id=1,
            job_id=1,
            title="Test Content",
            meta_description="Test description",
            word_count=500,
            image_count=3,
            link_count=10,
            processing_time_seconds=2.5,
        )

    @pytest.mark.asyncio
    async def test_get_content_result_exists(self, mock_db_session, sample_content_result):
        """Test getting an existing content result."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_content_result
        mock_db_session.execute.return_value = mock_result

        result = await ContentResultCRUD.get_content_result(mock_db_session, 1)

        assert result == sample_content_result
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_content_result_not_found(self, mock_db_session):
        """Test getting a non-existent content result."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await ContentResultCRUD.get_content_result(mock_db_session, 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_content_results_by_job(self, mock_db_session, sample_content_result):
        """Test getting content results for a specific job."""
        content_results = [
            sample_content_result,
            ContentResult(id=2, job_id=1, title="Second Content"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = content_results
        mock_db_session.execute.return_value = mock_result

        result = await ContentResultCRUD.get_content_results_by_job(mock_db_session, 1)

        assert len(result) == 2
        assert result[0] == sample_content_result
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_content_results_by_job_empty(self, mock_db_session):
        """Test getting content results for job with no results."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await ContentResultCRUD.get_content_results_by_job(mock_db_session, 999)

        assert result == []
        mock_db_session.execute.assert_called_once()


class TestCRUDIntegration:
    """Integration tests for CRUD operations."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_job_batch_relationship(self, mock_db_session):
        """Test creating jobs within a batch context."""
        batch_data = BatchCreate(
            name="Integration Batch",
            urls=["https://example.com/page1", "https://example.com/page2"],
        )

        with patch.object(JobCRUD, "create_job") as mock_create_job:
            mock_job1 = ScrapingJob(id=1)
            mock_job2 = ScrapingJob(id=2)
            mock_create_job.side_effect = [mock_job1, mock_job2]

            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            batch = await BatchCRUD.create_batch(mock_db_session, batch_data)

            # Verify batch-job relationship is established
            assert mock_job1.batch_id == batch.id
            assert mock_job2.batch_id == batch.id

    @pytest.mark.asyncio
    async def test_job_output_directory_generation_in_batch(self, mock_db_session):
        """Test job output directory generation within batch."""
        batch_data = BatchCreate(
            name="Dir Test Batch", urls=["https://example.com/page1", "https://example.com/page2"]
        )

        with patch.object(JobCRUD, "create_job") as mock_create_job:
            # Create realistic job instances
            def create_job_side_effect(db, job_data):
                from datetime import datetime

                job = ScrapingJob(
                    url=str(job_data.url),
                    domain="example.com",
                    slug=str(job_data.url).split("/")[-1],
                    output_directory=job_data.output_directory,
                    created_at=datetime.now(UTC),
                    retry_count=0,
                    max_retries=3,
                    timeout_seconds=30,
                    skip_existing=False,
                    success=False,
                    images_downloaded=0,
                )
                return job

            mock_create_job.side_effect = create_job_side_effect

            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            batch = await BatchCRUD.create_batch(mock_db_session, batch_data)

            # Verify job creation calls had correct output directories
            create_calls = mock_create_job.call_args_list
            assert len(create_calls) == 2

            # Check first job
            first_job_data = create_calls[0][0][1]
            assert first_job_data.output_directory == f"{batch.output_base_directory}/job_1"

            # Check second job
            second_job_data = create_calls[1][0][1]
            assert second_job_data.output_directory == f"{batch.output_base_directory}/job_2"

    @pytest.mark.asyncio
    async def test_update_job_model_dump_handling(self, mock_db_session):
        """Test that update_job handles model_dump correctly."""
        sample_job = ScrapingJob(
            id=1,
            url="https://example.com/test",
            domain="example.com",
            slug="test",
            priority=JobPriority.NORMAL,
        )

        update_data = JobUpdate(priority=JobPriority.HIGH, max_retries=5)

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await JobCRUD.update_job(mock_db_session, 1, update_data)

            # Verify only provided fields were updated
            assert result.priority == JobPriority.HIGH
            assert result.max_retries == 5
            # Other fields should remain unchanged

    @pytest.mark.asyncio
    async def test_batch_total_jobs_calculation(self, mock_db_session):
        """Test that batch total_jobs is calculated correctly."""
        urls = [f"https://example.com/page{i}" for i in range(10)]
        batch_data = BatchCreate(name="Large Batch", urls=urls)

        with patch.object(JobCRUD, "create_job"):
            mock_db_session.add = MagicMock()
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await BatchCRUD.create_batch(mock_db_session, batch_data)

            assert result.total_jobs == len(urls)
            assert result.total_jobs == 10

    @pytest.mark.asyncio
    async def test_get_jobs_count_handling(self, mock_db_session):
        """Test count handling when scalar returns None."""
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None  # Test None case

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs_list, total = await JobCRUD.get_jobs(mock_db_session)

        assert jobs_list == []
        assert total == 0  # Should default to 0 when scalar returns None

    @pytest.mark.asyncio
    async def test_get_batches_count_handling(self, mock_db_session):
        """Test batch count handling when scalar returns None."""
        mock_batches_result = MagicMock()
        mock_batches_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None

        mock_db_session.execute.side_effect = [mock_batches_result, mock_count_result]

        batches_list, total = await BatchCRUD.get_batches(mock_db_session)

        assert batches_list == []
        assert total == 0
