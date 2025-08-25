"""Tests for batch processing functionality."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import pytest

from src.batch.processor import BatchConfig, BatchJob, BatchJobStatus, BatchProcessor


class TestBatchConfig:
    """Test BatchConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
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

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BatchConfig(
            max_concurrent=5,
            output_base_dir=Path("/custom/path"),
            create_archives=True,
            cleanup_after_archive=True,
        )

        assert config.max_concurrent == 5
        assert config.output_base_dir == Path("/custom/path")
        assert config.create_archives is True
        assert config.cleanup_after_archive is True


class TestBatchJob:
    """Test BatchJob dataclass."""

    def test_job_creation(self):
        """Test job creation with required fields."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("test_output"))

        assert job.url == "https://example.com/test"
        assert job.output_dir == Path("test_output")
        assert job.status == BatchJobStatus.PENDING
        assert job.error is None
        assert job.start_time is None
        assert job.end_time is None
        assert job.duration is None

    def test_job_duration_calculation(self):
        """Test duration calculation."""
        job = BatchJob(url="https://example.com/test", output_dir=Path("test_output"))

        # No duration when times not set
        assert job.duration is None

        # Duration calculation
        job.start_time = 1000.0
        job.end_time = 1005.5
        assert job.duration == 5.5

        # Incomplete timing
        job.end_time = None
        assert job.duration is None


class TestBatchProcessor:
    """Test BatchProcessor functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Provide temporary directory for tests."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def batch_config(self, temp_dir):
        """Provide test batch configuration."""
        return BatchConfig(
            max_concurrent=2,
            output_base_dir=temp_dir / "batch_output",
            create_summary=True,
            continue_on_error=True,
        )

    @pytest.fixture
    def processor(self, batch_config):
        """Provide BatchProcessor instance."""
        return BatchProcessor(batch_config)

    def test_processor_initialization(self, processor, batch_config):
        """Test processor initialization."""
        assert processor.config == batch_config
        assert processor.jobs == []
        assert processor.semaphore._value == batch_config.max_concurrent

    def test_add_job_basic(self, processor):
        """Test adding a basic job."""
        job = processor.add_job("https://example.com/test")

        assert len(processor.jobs) == 1
        assert job.url == "https://example.com/test"
        assert job.status == BatchJobStatus.PENDING
        assert "example-com_test" in str(job.output_dir)

    def test_add_job_with_custom_slug(self, processor):
        """Test adding job with custom slug."""
        job = processor.add_job("https://example.com/long-post-title", custom_slug="short-title")

        assert "example-com_short-title" in str(job.output_dir)

    def test_add_job_with_custom_output_dir(self, processor):
        """Test adding job with custom output directory."""
        custom_dir = Path("custom/output")
        job = processor.add_job("https://example.com/test", output_dir=custom_dir)

        assert job.output_dir == custom_dir

    def test_generate_output_directory(self, processor):
        """Test output directory generation logic."""
        # Test with slug in URL
        job1 = processor.add_job("https://csfrace.com/blog/my-awesome-post")
        assert "csfrace-com_my-awesome-post" in str(job1.output_dir)

        # Test with custom slug
        job2 = processor.add_job("https://example.com/long-url-path", custom_slug="custom")
        assert "example-com_custom" in str(job2.output_dir)

        # Test collision handling
        job3 = processor.add_job("https://csfrace.com/blog/my-awesome-post")
        assert str(job1.output_dir) != str(job3.output_dir)
        assert "my-awesome-post-2" in str(job3.output_dir)

    def test_add_jobs_from_text_file(self, processor, temp_dir):
        """Test adding jobs from text file."""
        # Create test file
        urls_file = temp_dir / "test_urls.txt"
        urls_content = """
        https://example.com/post1
        https://example.com/post2
        # This is a comment
        https://example.com/post3

        https://example.com/post4
        """

        with open(urls_file, "w") as f:
            f.write(urls_content)

        count = processor.add_jobs_from_file(urls_file)

        assert count == 4
        assert len(processor.jobs) == 4
        assert processor.jobs[0].url == "https://example.com/post1"
        assert processor.jobs[1].url == "https://example.com/post2"
        assert processor.jobs[2].url == "https://example.com/post3"
        assert processor.jobs[3].url == "https://example.com/post4"

    def test_add_jobs_from_csv_structured(self, processor, temp_dir):
        """Test adding jobs from structured CSV file."""
        csv_file = temp_dir / "test_jobs.csv"
        csv_content = """url,slug,output_dir,priority
https://example.com/post1,custom-slug-1,custom/dir1,1
https://example.com/post2,custom-slug-2,,2
https://example.com/post3,,,3
"""

        with open(csv_file, "w") as f:
            f.write(csv_content)

        count = processor.add_jobs_from_file(csv_file)

        assert count == 3
        assert len(processor.jobs) == 3

        # Check first job with all custom fields (custom output_dir overrides slug)
        job1 = processor.jobs[0]
        assert job1.url == "https://example.com/post1"
        assert str(job1.output_dir) == "custom/dir1"

        # Check second job with partial custom fields
        job2 = processor.jobs[1]
        assert job2.url == "https://example.com/post2"
        assert "custom-slug-2" in str(job2.output_dir)

        # Check third job with defaults
        job3 = processor.jobs[2]
        assert job3.url == "https://example.com/post3"
        assert "post3" in str(job3.output_dir)

    def test_add_jobs_from_csv_simple(self, processor, temp_dir):
        """Test adding jobs from simple CSV (URL list)."""
        csv_file = temp_dir / "simple_urls.csv"
        csv_content = """https://example.com/post1
https://example.com/post2
https://example.com/post3"""

        with open(csv_file, "w") as f:
            f.write(csv_content)

        count = processor.add_jobs_from_file(csv_file)

        assert count == 3
        assert len(processor.jobs) == 3

        for i, job in enumerate(processor.jobs, 1):
            assert job.url == f"https://example.com/post{i}"

    def test_add_jobs_from_nonexistent_file(self, processor):
        """Test error handling for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            processor.add_jobs_from_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_process_single_job_success(self, processor):
        """Test successful processing of a single job."""
        from rich.progress import Progress

        # Mock the converter
        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter:
            mock_instance = AsyncMock()
            mock_converter.return_value = mock_instance
            mock_instance.convert.return_value = None

            job = processor.add_job("https://example.com/test")
            progress = Progress()

            # Process the job
            result_job = await processor._process_single_job(job, progress)

            assert result_job.status == BatchJobStatus.COMPLETED
            assert result_job.error is None
            assert result_job.start_time is not None
            assert result_job.end_time is not None
            assert result_job.duration is not None
            mock_instance.convert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_job_failure(self, processor):
        """Test failed processing of a single job."""
        from rich.progress import Progress

        # Mock the converter to raise an exception
        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter:
            mock_instance = AsyncMock()
            mock_converter.return_value = mock_instance
            mock_instance.convert.side_effect = Exception("Test error")

            job = processor.add_job("https://example.com/test")
            progress = Progress()

            # Process the job
            result_job = await processor._process_single_job(job, progress)

            assert result_job.status == BatchJobStatus.FAILED
            assert result_job.error == "Test error"
            assert result_job.start_time is not None
            assert result_job.end_time is not None

    @pytest.mark.asyncio
    async def test_process_single_job_timeout(self, processor):
        """Test job timeout handling."""
        from rich.progress import Progress

        # Configure short timeout
        processor.config.timeout_per_job = 0.1

        # Mock converter with slow operation
        with patch("src.batch.processor.AsyncWordPressConverter") as mock_converter:
            mock_instance = AsyncMock()
            mock_converter.return_value = mock_instance

            async def slow_convert(*args, **kwargs):
                await asyncio.sleep(0.2)  # Longer than timeout

            mock_instance.convert = slow_convert

            job = processor.add_job("https://example.com/test")
            progress = Progress()

            # Process the job
            result_job = await processor._process_single_job(job, progress)

            assert result_job.status == BatchJobStatus.FAILED
            assert "Timeout" in result_job.error

    @pytest.mark.asyncio
    async def test_create_archive(self, processor, temp_dir):
        """Test archive creation functionality."""
        import zipfile

        # Create job with output directory and some test files
        job = BatchJob(url="https://example.com/test", output_dir=temp_dir / "test_output")
        job.output_dir.mkdir(parents=True)

        # Create test files
        (job.output_dir / "content.html").write_text("<html>Test</html>")
        (job.output_dir / "metadata.txt").write_text("title: Test")
        images_dir = job.output_dir / "images"
        images_dir.mkdir()
        (images_dir / "test.jpg").write_bytes(b"fake image data")

        # Set up batch config for archives
        processor.config.output_base_dir = temp_dir

        # Create archive
        archive_path = await processor._create_archive(job)

        assert archive_path.exists()
        assert archive_path.suffix == ".zip"

        # Verify archive contents
        with zipfile.ZipFile(archive_path, "r") as zip_file:
            files = zip_file.namelist()
            assert "content.html" in files
            assert "metadata.txt" in files
            assert "images/test.jpg" in files

            # Check content
            content = zip_file.read("content.html").decode()
            assert content == "<html>Test</html>"

    def test_compile_results(self, processor):
        """Test results compilation."""
        # Add some jobs with different statuses
        job1 = processor.add_job("https://example.com/post1")
        job2 = processor.add_job("https://example.com/post2")
        job3 = processor.add_job("https://example.com/post3")

        # Set different statuses
        job1.status = BatchJobStatus.COMPLETED
        job1.start_time = 1000.0
        job1.end_time = 1005.0

        job2.status = BatchJobStatus.FAILED
        job2.error = "Test error"

        job3.status = BatchJobStatus.COMPLETED
        job3.start_time = 2000.0
        job3.end_time = 2003.0

        # Compile results
        summary = processor._compile_results([job1, job2, job3])

        assert summary["total"] == 3
        assert summary["successful"] == 2
        assert summary["failed"] == 1
        assert summary["skipped"] == 0
        assert summary["total_duration"] == 8.0  # 5.0 + 3.0
        assert summary["average_duration"] == 4.0  # 8.0 / 2

        # Check job details
        job_data = summary["jobs"]
        assert len(job_data) == 3
        assert job_data[0]["status"] == "completed"
        assert job_data[1]["status"] == "failed"
        assert job_data[1]["error"] == "Test error"

    @pytest.mark.asyncio
    async def test_create_summary_report(self, processor, temp_dir, capsys):
        """Test summary report creation."""
        processor.config.output_base_dir = temp_dir

        # Create test summary data
        summary = {
            "total": 3,
            "successful": 2,
            "failed": 1,
            "skipped": 0,
            "total_duration": 10.5,
            "average_duration": 5.25,
            "jobs": [
                {
                    "url": "https://example.com/post1",
                    "status": "completed",
                    "duration": 5.0,
                    "output_dir": str(temp_dir / "post1"),
                },
                {
                    "url": "https://example.com/post2",
                    "status": "failed",
                    "duration": None,
                    "output_dir": str(temp_dir / "post2"),
                },
            ],
        }

        # Create summary report
        await processor._create_summary_report(summary)

        # Check that summary file was created
        summary_file = temp_dir / "batch_summary.json"
        assert summary_file.exists()

        # Verify summary file content
        with open(summary_file) as f:
            saved_summary = json.load(f)

        assert saved_summary["total"] == 3
        assert saved_summary["successful"] == 2
        assert saved_summary["failed"] == 1
        assert len(saved_summary["jobs"]) == 2
