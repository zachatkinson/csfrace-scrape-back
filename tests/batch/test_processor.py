"""Unit tests for batch processor."""
# pylint: disable=protected-access

import asyncio
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.batch.processor import BatchConfig, BatchJob, BatchJobStatus, BatchProcessor
from src.core.exceptions import ConversionError
from src.utils.path_utils import get_directory_name


class TestBatchProcessor:
    """Test batch processing functionality."""

    @pytest.fixture
    def batch_processor(self):
        """Create test batch processor."""
        config = BatchConfig(max_concurrent=5)
        return BatchProcessor(batch_config=config)

    def test_batch_processor_initialization(self, batch_processor):
        """Test batch processor initialization."""
        assert batch_processor.config.max_concurrent == 5
        assert isinstance(batch_processor.jobs, list)
        assert len(batch_processor.jobs) == 0

    def test_add_job(self, batch_processor):
        """Test adding a job to the batch processor."""
        job = batch_processor.add_job("https://example.com/post1")

        assert len(batch_processor.jobs) == 1
        assert job.url == "https://example.com/post1"
        assert job.status.value == "pending"
        assert job.output_dir is not None

    def test_add_multiple_jobs(self, batch_processor):
        """Test adding multiple jobs."""
        urls = [
            "https://example.com/post1",
            "https://example.com/post2",
            "https://example.com/post3",
        ]

        for url in urls:
            batch_processor.add_job(url)

        assert len(batch_processor.jobs) == 3
        assert all(job.status.value == "pending" for job in batch_processor.jobs)
        assert all(job.url in urls for job in batch_processor.jobs)

    def test_add_job_with_custom_slug(self, batch_processor):
        """Test adding job with custom slug."""
        job = batch_processor.add_job("https://example.com/post1", custom_slug="my-custom-post")

        assert "my-custom-post" in str(job.output_dir)

    def test_unique_output_directories(self, batch_processor):
        """Test that duplicate URLs get unique output directories."""
        job1 = batch_processor.add_job("https://example.com/post1")
        job2 = batch_processor.add_job("https://example.com/post1")

        assert len(batch_processor.jobs) == 2
        assert job1.output_dir != job2.output_dir  # Should be unique

    @pytest.mark.asyncio
    async def test_process_all_no_jobs(self, batch_processor):
        """Test processing with no jobs."""
        summary = await batch_processor.process_all()

        assert summary["total"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 0
        assert summary["jobs"] == []

    def test_batch_config_defaults(self):
        """Test batch configuration defaults."""
        config = BatchConfig()

        assert config.max_concurrent == 3
        assert config.continue_on_error is True
        assert config.output_base_dir == Path("batch_output")
        assert config.timeout_per_job == 300

    def test_custom_batch_config(self):
        """Test custom batch configuration."""
        custom_dir = Path("custom_output")
        config = BatchConfig(
            max_concurrent=10,
            continue_on_error=False,
            output_base_dir=custom_dir,
            timeout_per_job=600,
        )

        processor = BatchProcessor(batch_config=config)

        assert processor.config.max_concurrent == 10
        assert processor.config.continue_on_error is False
        assert processor.config.output_base_dir == custom_dir
        assert processor.config.timeout_per_job == 600


class TestBatchJob:
    """Test batch job functionality."""

    def test_batch_job_creation(self):
        """Test BatchJob creation with default values."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("/tmp/test"))

        assert job.url == "https://example.com/test"
        assert job.output_dir == Path("/tmp/test")
        assert job.status == BatchJobStatus.PENDING
        assert job.error is None
        assert job.start_time is None
        assert job.end_time is None
        assert job.progress_task is None
        assert job.archive_path is None

    def test_batch_job_duration_calculation(self):
        """Test duration calculation for completed jobs."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("/tmp/test"))

        # No duration when times are not set
        assert job.duration is None

        # Duration calculation when both times are set
        job.start_time = 100.0
        job.end_time = 105.5
        assert job.duration == 5.5

        # No duration when only start time is set
        job.end_time = None
        assert job.duration is None

    def test_batch_job_status_enum(self):
        """Test BatchJobStatus enum values."""
        assert BatchJobStatus.PENDING.value == "pending"
        assert BatchJobStatus.RUNNING.value == "running"
        assert BatchJobStatus.COMPLETED.value == "completed"
        assert BatchJobStatus.FAILED.value == "failed"
        assert BatchJobStatus.SKIPPED.value == "skipped"


class TestBatchConfig:
    """Test batch configuration."""

    def test_batch_config_all_defaults(self):
        """Test all default configuration values."""
        config = BatchConfig()

        assert config.max_concurrent == 3
        assert config.continue_on_error is True
        assert config.output_base_dir == Path("batch_output")
        assert config.create_summary is True
        assert config.skip_existing is False
        assert config.timeout_per_job == 300
        assert config.retry_failed is True
        assert config.max_retries == 2
        assert config.create_archives is False
        assert config.archive_format == "zip"
        assert config.cleanup_after_archive is False

    def test_batch_config_custom_values(self):
        """Test configuration with all custom values."""
        config = BatchConfig(
            max_concurrent=8,
            continue_on_error=False,
            output_base_dir=Path("/custom/output"),
            create_summary=False,
            skip_existing=True,
            timeout_per_job=600,
            retry_failed=False,
            max_retries=5,
            create_archives=True,
            archive_format="tar.gz",
            cleanup_after_archive=True,
        )

        assert config.max_concurrent == 8
        assert config.continue_on_error is False
        assert config.output_base_dir == Path("/custom/output")
        assert config.create_summary is False
        assert config.skip_existing is True
        assert config.timeout_per_job == 600
        assert config.retry_failed is False
        assert config.max_retries == 5
        assert config.create_archives is True
        assert config.archive_format == "tar.gz"
        assert config.cleanup_after_archive is True


class TestBatchProcessorURLParsing:
    """Test URL parsing and directory generation."""

    @pytest.fixture
    def processor(self):
        """Create processor for URL parsing tests."""
        config = BatchConfig(output_base_dir=Path("/tmp/batch_test"))
        return BatchProcessor(batch_config=config)

    def test_generate_output_directory_basic_url(self, processor):
        """Test directory generation from basic URL."""
        url = "https://example.com/my-blog-post"
        output_dir = processor._generate_output_directory(url)

        assert output_dir == Path("/tmp/batch_test/example-com_my-blog-post")

    def test_generate_output_directory_www_removal(self, processor):
        """Test www prefix removal in domain."""
        url = "https://www.example.com/test-post"
        output_dir = processor._generate_output_directory(url)

        assert output_dir == Path("/tmp/batch_test/example-com_test-post")

    def test_generate_output_directory_custom_slug(self, processor):
        """Test directory generation with custom slug."""
        url = "https://example.com/ignored-path"
        output_dir = processor._generate_output_directory(url, custom_slug="my-custom-slug")

        assert output_dir == Path("/tmp/batch_test/example-com_my-custom-slug")

    def test_generate_output_directory_nested_path(self, processor):
        """Test directory generation from nested URL path."""
        url = "https://example.com/category/subcategory/final-post"
        output_dir = processor._generate_output_directory(url)

        assert output_dir == Path("/tmp/batch_test/example-com_final-post")

    def test_generate_output_directory_html_extension_removal(self, processor):
        """Test removal of .html extensions from slugs."""
        url = "https://example.com/my-post.html"
        output_dir = processor._generate_output_directory(url)

        assert output_dir == Path("/tmp/batch_test/example-com_my-post")

    def test_generate_output_directory_php_extension_removal(self, processor):
        """Test removal of .php extensions from slugs."""
        url = "https://example.com/index.php"
        output_dir = processor._generate_output_directory(url)

        assert output_dir == Path("/tmp/batch_test/example-com_homepage")

    def test_generate_output_directory_root_path(self, processor):
        """Test directory generation for root path URLs."""
        url = "https://example.com/"
        output_dir = processor._generate_output_directory(url)

        assert output_dir == Path("/tmp/batch_test/example-com_homepage")

    def test_generate_output_directory_special_characters_cleanup(self, processor):
        """Test cleanup of special characters in slugs."""
        url = "https://example.com/my-post!@#$%^&*()_+{}[]|\\\\;':,./<>?"
        output_dir = processor._generate_output_directory(url)

        # Should clean up special characters
        assert "example-com" in str(output_dir)
        assert "my-post" in str(output_dir)

    def test_generate_output_directory_length_limit(self, processor):
        """Test slug length limiting."""
        long_slug = "a" * 100  # Very long slug
        url = f"https://example.com/{long_slug}"
        output_dir = processor._generate_output_directory(url)

        # Should limit slug to 50 characters
        dir_name = get_directory_name(output_dir)  # Get the actual directory name
        slug_part = dir_name.split("_", 1)[1] if "_" in dir_name else dir_name
        assert len(slug_part) <= 50

    def test_generate_output_directory_invalid_url_fallback(self, processor):
        """Test fallback for invalid URLs."""
        invalid_url = "not-a-valid-url"
        output_dir = processor._generate_output_directory(invalid_url)

        # Should fallback to hash-based naming
        assert "post_" in str(output_dir)
        assert len(str(output_dir).split("post_")[1]) == 8  # 8-character hash

    def test_ensure_unique_directory_no_conflict(self, processor):
        """Test unique directory generation without conflicts."""
        base_dir = Path("/tmp/test/unique")
        unique_dir = processor._ensure_unique_directory(base_dir)

        assert unique_dir == base_dir

    def test_ensure_unique_directory_with_conflict(self, processor):
        """Test unique directory generation with conflicts."""
        # Add a job to create conflict
        processor.add_job("https://example.com/test")
        existing_dir = processor.jobs[0].output_dir

        # Try to add same directory
        unique_dir = processor._ensure_unique_directory(existing_dir)

        # Should get numbered version
        expected_dir = Path(str(existing_dir) + "-2")
        assert unique_dir == expected_dir

    def test_ensure_unique_directory_multiple_conflicts(self, processor):
        """Test unique directory generation with multiple conflicts."""
        # Add multiple jobs with same base path
        base_url = "https://example.com/test"
        processor.add_job(base_url)
        processor.add_job(base_url)
        processor.add_job(base_url)

        assert len(processor.jobs) == 3
        # All should have unique output directories
        output_dirs = [job.output_dir for job in processor.jobs]
        assert len(set(output_dirs)) == 3  # All unique


class TestBatchProcessorFileLoading:
    """Test file-based job loading functionality."""

    @pytest.fixture
    def processor(self):
        """Create processor for file loading tests."""
        return BatchProcessor()

    @pytest.fixture
    def temp_txt_file(self):
        """Create temporary text file with URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://example.com/post1\n")
            f.write("https://example.com/post2\n")
            f.write("# This is a comment\n")
            f.write("https://example.com/post3\n")
            f.write("\n")  # Empty line
            f.write("https://example.com/post4")
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    @pytest.fixture
    def temp_csv_structured_file(self):
        """Create temporary structured CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("url,slug,output_dir,priority\n")
            f.write("https://example.com/post1,custom-slug-1,,high\n")
            f.write("https://example.com/post2,,,normal\n")
            f.write("# https://example.com/comment,,, \n")
            f.write("https://example.com/post3,special-post,/custom/path,low\n")
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    @pytest.fixture
    def temp_csv_simple_file(self):
        """Create temporary simple CSV file (just URLs)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("https://example.com/post1\n")
            f.write("https://example.com/post2\n")
            f.write("https://example.com/post3\n")
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    def test_add_jobs_from_txt_file(self, processor, temp_txt_file):
        """Test loading jobs from text file."""
        added = processor.add_jobs_from_file(temp_txt_file)

        assert added == 4  # 4 valid URLs, skipped comment and empty line
        assert len(processor.jobs) == 4

        urls = [job.url for job in processor.jobs]
        expected_urls = [
            "https://example.com/post1",
            "https://example.com/post2",
            "https://example.com/post3",
            "https://example.com/post4",
        ]
        assert urls == expected_urls

    def test_add_jobs_from_structured_csv(self, processor, temp_csv_structured_file):
        """Test loading jobs from structured CSV file."""
        added = processor.add_jobs_from_file(temp_csv_structured_file)

        assert added == 3  # 3 valid rows, skipped comment
        assert len(processor.jobs) == 3

        # Check first job with custom slug
        job1 = processor.jobs[0]
        assert job1.url == "https://example.com/post1"
        assert "custom-slug-1" in str(job1.output_dir)

        # Check third job with custom output dir
        job3 = processor.jobs[2]
        assert job3.url == "https://example.com/post3"
        assert job3.output_dir == Path("/custom/path")

    def test_add_jobs_from_simple_csv(self, processor, temp_csv_simple_file):
        """Test loading jobs from simple CSV file."""
        added = processor.add_jobs_from_file(temp_csv_simple_file)

        # Simple CSV has 3 line-separated URLs
        assert added == 3
        assert len(processor.jobs) == 3

        # Should load the three URLs from the fixture
        urls = [job.url for job in processor.jobs]
        expected_urls = [
            "https://example.com/post1",
            "https://example.com/post2",
            "https://example.com/post3",
        ]
        assert urls == expected_urls

    def test_add_jobs_from_nonexistent_file(self, processor):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            processor.add_jobs_from_file("/nonexistent/file.txt")

    def test_add_jobs_from_invalid_csv(self, processor):
        """Test handling of invalid CSV format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("url,slug\n")
            f.write("invalid-url-line-with-wrong-format\n")
            temp_path = Path(f.name)

        try:
            # Should handle gracefully and skip invalid lines
            added = processor.add_jobs_from_file(temp_path)
            assert added == 0  # No valid URLs added
        finally:
            temp_path.unlink()


class TestBatchProcessorAsyncProcessing:
    """Test async batch processing functionality."""

    @pytest.fixture
    def processor(self):
        """Create processor with test configuration."""
        config = BatchConfig(max_concurrent=2, timeout_per_job=10)
        return BatchProcessor(batch_config=config)

    @pytest.mark.asyncio
    async def test_process_single_job_success(self, processor):
        """Test successful single job processing."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("/tmp/test"))

        # Mock Progress and AsyncWordPressConverter
        mock_progress = MagicMock()

        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
            mock_converter = AsyncMock()
            mock_converter_class.return_value = mock_converter
            mock_converter.convert = AsyncMock()

            result = await processor._process_single_job(job, mock_progress)

            assert result.status == BatchJobStatus.COMPLETED
            assert result.start_time is not None
            assert result.end_time is not None
            assert result.duration is not None
            mock_converter.convert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_job_timeout(self, processor):
        """Test job timeout handling."""
        processor.config.timeout_per_job = 0.1  # Very short timeout
        job = BatchJob(url="https://example.com/test", output_dir=Path("/tmp/test"))
        mock_progress = MagicMock()

        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
            mock_converter = AsyncMock()
            mock_converter_class.return_value = mock_converter

            # Create a proper async function that takes time
            async def slow_convert(**_kwargs):
                await asyncio.sleep(1)  # Longer than timeout

            mock_converter.convert = slow_convert

            result = await processor._process_single_job(job, mock_progress)

            assert result.status == BatchJobStatus.FAILED
            assert "Timeout after" in result.error

    @pytest.mark.asyncio
    async def test_process_single_job_conversion_error(self, processor):
        """Test job error handling."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("/tmp/test"))
        mock_progress = MagicMock()

        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
            mock_converter = AsyncMock()
            mock_converter_class.return_value = mock_converter
            mock_converter.convert = AsyncMock(side_effect=ConversionError("Test error"))

            result = await processor._process_single_job(job, mock_progress)

            assert result.status == BatchJobStatus.FAILED
            assert result.error == "Test error"

    @pytest.mark.asyncio
    async def test_process_single_job_skip_existing(self, processor, tmp_path):
        """Test skipping jobs when output already exists."""
        processor.config.skip_existing = True

        # Create existing output file
        job_dir = tmp_path / "test_job"
        job_dir.mkdir()
        (job_dir / "converted_content.html").write_text("existing content")

        job = BatchJob(url="https://example.com/test", output_dir=job_dir)
        mock_progress = MagicMock()

        result = await processor._process_single_job(job, mock_progress)

        assert result.status == BatchJobStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_process_all_complete_workflow(self, processor):
        """Test complete processing workflow."""
        # Add test jobs
        processor.add_job("https://example.com/post1")
        processor.add_job("https://example.com/post2")

        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
            mock_converter = AsyncMock()
            mock_converter_class.return_value = mock_converter
            mock_converter.convert = AsyncMock()

            with patch.object(processor, "_create_summary_report", new=AsyncMock()) as mock_summary:
                summary = await processor.process_all()

                assert summary["total"] == 2
                assert summary["successful"] == 2
                assert summary["failed"] == 0
                mock_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_compile_results_statistics(self, processor):
        """Test result compilation and statistics."""
        # Create jobs with different statuses
        job1 = BatchJob(url="https://example.com/post1", output_dir=Path("/tmp/job1"))
        job1.status = BatchJobStatus.COMPLETED
        job1.start_time = 100.0
        job1.end_time = 103.0

        job2 = BatchJob(url="https://example.com/post2", output_dir=Path("/tmp/job2"))
        job2.status = BatchJobStatus.FAILED
        job2.error = "Test error"

        job3 = BatchJob(url="https://example.com/post3", output_dir=Path("/tmp/job3"))
        job3.status = BatchJobStatus.SKIPPED

        processor.jobs = [job1, job2, job3]

        summary = processor._compile_results([job1, job2, job3])

        assert summary["total"] == 3
        assert summary["successful"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["total_duration"] == 3.0
        assert summary["average_duration"] == 3.0
        assert len(summary["jobs"]) == 3


class TestBatchProcessorArchiving:
    """Test archive creation functionality."""

    @pytest.fixture
    def processor(self):
        """Create processor with archive configuration."""
        config = BatchConfig(create_archives=True, output_base_dir=Path("/tmp/batch_test"))
        return BatchProcessor(batch_config=config)

    @pytest.mark.asyncio
    async def test_create_archive_success(self, processor, tmp_path):
        """Test successful archive creation."""
        # Create test job output directory with files
        job_dir = tmp_path / "test_job"
        job_dir.mkdir()
        (job_dir / "converted_content.html").write_text("test content")
        (job_dir / "metadata.txt").write_text("test metadata")

        images_dir = job_dir / "images"
        images_dir.mkdir()
        (images_dir / "test.jpg").write_bytes(b"fake image data")

        job = BatchJob(url="https://example.com/test", output_dir=job_dir)

        # Mock the config to use tmp_path
        processor.config.output_base_dir = tmp_path

        archive_path = await processor._create_archive(job)

        # Verify archive was created
        assert archive_path.exists()
        assert archive_path.suffix == ".zip"

        # Verify archive contents
        with zipfile.ZipFile(archive_path, "r") as zip_file:
            file_list = zip_file.namelist()
            assert "converted_content.html" in file_list
            assert "metadata.txt" in file_list
            assert "images/test.jpg" in file_list

    @pytest.mark.asyncio
    async def test_create_archive_nonexistent_directory(self, processor):
        """Test archive creation with non-existent directory."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("/nonexistent/dir"))

        with pytest.raises(ValueError, match="Output directory does not exist"):
            await processor._create_archive(job)

    @pytest.mark.asyncio
    async def test_create_archive_with_cleanup(self, processor, tmp_path):
        """Test archive creation with directory cleanup."""
        processor.config.cleanup_after_archive = True
        processor.config.output_base_dir = tmp_path

        # Create test job output directory
        job_dir = tmp_path / "test_job"
        job_dir.mkdir()
        (job_dir / "test.txt").write_text("test")

        job = BatchJob(url="https://example.com/test", output_dir=job_dir)

        # Directory should exist before archiving
        assert job_dir.exists()

        await processor._create_archive(job)

        # Directory should be removed after archiving
        assert not job_dir.exists()


class TestBatchProcessorSummaryReporting:
    """Test summary reporting functionality."""

    @pytest.fixture
    def processor(self):
        """Create processor with summary configuration."""
        config = BatchConfig(create_summary=True)
        return BatchProcessor(batch_config=config)

    @pytest.mark.asyncio
    async def test_create_summary_report(self, processor, tmp_path):
        """Test summary report creation."""
        processor.config.output_base_dir = tmp_path

        # Create test summary data
        summary = {
            "total": 3,
            "successful": 2,
            "failed": 1,
            "skipped": 0,
            "average_duration": 2.5,
            "jobs": [
                {
                    "url": "https://example.com/post1",
                    "status": "completed",
                    "duration": 2.0,
                    "output_dir": str(tmp_path / "job1"),
                },
                {
                    "url": "https://example.com/post2",
                    "status": "completed",
                    "duration": 3.0,
                    "output_dir": str(tmp_path / "job2"),
                },
                {
                    "url": "https://example.com/post3",
                    "status": "failed",
                    "duration": None,
                    "output_dir": str(tmp_path / "job3"),
                },
            ],
        }

        await processor._create_summary_report(summary)

        # Verify summary file was created
        summary_file = tmp_path / "batch_summary.json"
        assert summary_file.exists()

        # Verify summary file contents
        with open(summary_file, encoding="utf-8") as f:
            saved_summary = json.load(f)
            assert saved_summary["total"] == 3
            assert saved_summary["successful"] == 2
            assert saved_summary["failed"] == 1


class TestBatchProcessorEdgeCases:
    """Test edge cases and error scenarios."""

    def test_initialization_with_none_config(self):
        """Test initialization with None config uses defaults."""
        processor = BatchProcessor(batch_config=None)

        assert processor.config is not None
        assert processor.config.max_concurrent == 3  # Default value

    def test_add_job_with_none_output_dir(self):
        """Test adding job with None output directory."""
        processor = BatchProcessor()
        job = processor.add_job("https://example.com/test", output_dir=None)

        assert job.output_dir is not None
        assert "example-com_test" in str(job.output_dir)

    def test_add_job_with_custom_output_dir(self):
        """Test adding job with custom output directory."""
        processor = BatchProcessor()
        custom_dir = Path("/custom/output/path")
        job = processor.add_job("https://example.com/test", output_dir=custom_dir)

        assert job.output_dir == custom_dir

    @pytest.mark.asyncio
    async def test_process_all_with_continue_on_error_false(self):
        """Test processing with continue_on_error=False."""
        config = BatchConfig(continue_on_error=False)
        processor = BatchProcessor(batch_config=config)
        processor.add_job("https://example.com/test")

        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
            mock_converter = AsyncMock()
            mock_converter_class.return_value = mock_converter
            mock_converter.convert = AsyncMock(side_effect=ConversionError("Test error"))

            # The exception gets caught in _process_single_job and doesn't bubble up to process_all
            # Instead, check that the summary shows failure when continue_on_error=False
            summary = await processor.process_all()
            assert summary["failed"] == 1
            assert summary["successful"] == 0

    def test_url_parsing_edge_cases(self):
        """Test URL parsing with various edge cases."""
        processor = BatchProcessor()

        # Test with ports
        job1 = processor.add_job("https://example.com:8080/test")
        assert "example-com" in str(job1.output_dir)

        # Test with query parameters
        job2 = processor.add_job("https://example.com/test?param=value")
        assert "test" in str(job2.output_dir)

        # Test with fragments
        job3 = processor.add_job("https://example.com/test#section")
        assert "test" in str(job3.output_dir)

    def test_batch_job_equality_and_uniqueness(self):
        """Test that batch jobs are properly handled for uniqueness."""
        processor = BatchProcessor()

        # Add same URL multiple times
        job1 = processor.add_job("https://example.com/test")
        job2 = processor.add_job("https://example.com/test")
        job3 = processor.add_job("https://example.com/test")

        # Should have unique output directories
        dirs = {str(job.output_dir) for job in [job1, job2, job3]}
        assert len(dirs) == 3  # All unique

        # Should have numbered suffixes
        dir_list = sorted(dirs)
        assert dir_list[1].endswith("-2")
        assert dir_list[2].endswith("-3")

    @pytest.mark.asyncio
    async def test_process_single_job_with_archive_creation(self):
        """Test job processing with archive creation enabled."""
        config = BatchConfig(create_archives=True)
        processor = BatchProcessor(batch_config=config)

        # Create a temporary directory structure for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            job_dir = Path(temp_dir) / "test_job"
            job_dir.mkdir()
            (job_dir / "test.txt").write_text("test content")

            job = BatchJob(url="https://example.com/test", output_dir=job_dir)
            mock_progress = MagicMock()

            with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
                mock_converter = AsyncMock()
                mock_converter_class.return_value = mock_converter
                mock_converter.convert = AsyncMock()

                with patch.object(processor, "_create_archive", new=AsyncMock()) as mock_archive:
                    mock_archive.return_value = Path("/tmp/test.zip")

                    result = await processor._process_single_job(job, mock_progress)

                    assert result.status == BatchJobStatus.COMPLETED
                    mock_archive.assert_called_once_with(job)
                    assert result.archive_path == Path("/tmp/test.zip")

    @pytest.mark.asyncio
    async def test_process_single_job_archive_creation_failure(self):
        """Test job processing when archive creation fails."""
        config = BatchConfig(create_archives=True)
        processor = BatchProcessor(batch_config=config)

        job = BatchJob(url="https://example.com/test", output_dir=Path("/tmp/test"))
        mock_progress = MagicMock()

        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter_class:
            mock_converter = AsyncMock()
            mock_converter_class.return_value = mock_converter
            mock_converter.convert = AsyncMock()

            with patch.object(processor, "_create_archive", new=AsyncMock()) as mock_archive:
                mock_archive.side_effect = Exception("Archive creation failed")

                # Job should still complete successfully even if archive fails
                result = await processor._process_single_job(job, mock_progress)

                assert result.status == BatchJobStatus.COMPLETED
                assert result.archive_path is None  # Archive creation failed
