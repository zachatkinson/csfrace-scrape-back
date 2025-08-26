"""Unit tests for batch processor."""

from pathlib import Path

import pytest

from src.batch.processor import BatchConfig, BatchProcessor


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

        assert summary["status"] == "no_jobs"
        assert summary["results"] == []

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
