"""Tests for enhanced batch processor with concurrent execution."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.batch.enhanced_processor import (
    BatchConfig,
    BatchProcessor,
    BatchResults,
    Priority,
    ProcessingResult,
)
from src.core.exceptions import BatchProcessingError
from src.database.models import JobStatus
from src.database.service import DatabaseService


@pytest.fixture
def mock_database_service():
    """Create mock database service."""
    service = MagicMock(spec=DatabaseService)
    service.get_session.return_value.__enter__ = Mock(return_value=MagicMock())
    service.get_session.return_value.__exit__ = Mock(return_value=None)

    # Mock database operations
    service.create_batch = Mock(return_value=Mock(id=1))
    service.create_job = Mock(return_value=Mock(id=1))
    service.update_job_status = Mock()
    service.update_batch_progress = Mock()
    service.get_batch = Mock()

    return service


@pytest.fixture
def mock_converter():
    """Create mock converter."""
    converter = AsyncMock()
    converter.process_url = AsyncMock(return_value={"status": "success", "content": "test"})
    return converter


@pytest.fixture
def batch_config():
    """Create batch configuration."""
    return BatchConfig(
        max_concurrent=3,
        timeout_seconds=10,
        retry_attempts=2,
        retry_delay=0.1,  # Short delay for tests
        output_directory=Path("test_output"),
        rate_limit_per_second=10,
    )


@pytest.fixture
def batch_processor(batch_config, mock_database_service, mock_converter):
    """Create batch processor instance."""
    return BatchProcessor(
        config=batch_config, database_service=mock_database_service, converter=mock_converter
    )


class TestPriority:
    """Test Priority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert Priority.URGENT.value == 1
        assert Priority.HIGH.value == 2
        assert Priority.NORMAL.value == 3
        assert Priority.LOW.value == 4
        assert Priority.DEFERRED.value == 5

    def test_priority_ordering(self):
        """Test that lower numeric values represent higher priority."""
        assert Priority.URGENT.value < Priority.HIGH.value
        assert Priority.HIGH.value < Priority.NORMAL.value
        assert Priority.NORMAL.value < Priority.LOW.value
        assert Priority.LOW.value < Priority.DEFERRED.value


class TestProcessingResult:
    """Test ProcessingResult data class."""

    def test_processing_result_creation(self):
        """Test creating processing result."""
        result = ProcessingResult(
            success=True,
            url="https://example.com/test",
            data={"content": "test"},
            error=None,
            retries=1,
            duration=2.5,
        )

        assert result.success is True
        assert result.url == "https://example.com/test"
        assert result.data == {"content": "test"}
        assert result.error is None
        assert result.retries == 1
        assert result.duration == 2.5

    def test_processing_result_failure(self):
        """Test creating failed processing result."""
        result = ProcessingResult(
            success=False, url="https://example.com/failed", error="Connection timeout", retries=3
        )

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.retries == 3
        assert result.data is None
        assert result.duration is None


class TestBatchResults:
    """Test BatchResults data class."""

    def test_batch_results_creation(self):
        """Test creating batch results."""
        results = BatchResults(
            successful=["url1", "url2"],
            failed=["url3"],
            total=3,
            duration=120.5,
            statistics={"rate": "95%"},
        )

        assert len(results.successful) == 2
        assert len(results.failed) == 1
        assert results.total == 3
        assert results.duration == 120.5
        assert results.statistics == {"rate": "95%"}

    def test_batch_results_defaults(self):
        """Test batch results with default values."""
        results = BatchResults()

        assert len(results.successful) == 0
        assert len(results.failed) == 0
        assert results.total == 0
        assert results.duration is None
        assert results.statistics is None


class TestBatchConfig:
    """Test BatchConfig validation and functionality."""

    def test_batch_config_creation(self):
        """Test creating batch configuration."""
        config = BatchConfig(
            max_concurrent=5, timeout_seconds=30, retry_attempts=3, output_directory=Path("output")
        )

        assert config.max_concurrent == 5
        assert config.timeout_seconds == 30
        assert config.retry_attempts == 3
        assert config.output_directory == Path("output")

    def test_batch_config_defaults(self):
        """Test batch configuration defaults."""
        config = BatchConfig()

        assert config.max_concurrent == 5
        assert config.timeout_seconds == 30
        assert config.retry_attempts == 2
        assert config.retry_delay == 1.0
        assert config.continue_on_error is True
        assert config.output_directory == Path("batch_output")
        assert config.create_archives is False
        assert config.priority_queue is True
        assert config.save_checkpoints is True
        assert config.checkpoint_interval == 10

    def test_batch_config_validation_success(self):
        """Test successful batch configuration validation."""
        config = BatchConfig(max_concurrent=3, timeout_seconds=20, retry_attempts=1)
        assert config.validate() is True

    def test_batch_config_validation_invalid_max_concurrent(self):
        """Test validation with invalid max_concurrent."""
        config = BatchConfig(max_concurrent=0)

        with pytest.raises(ValueError, match="max_concurrent must be positive"):
            config.validate()

    def test_batch_config_validation_invalid_timeout(self):
        """Test validation with invalid timeout."""
        config = BatchConfig(timeout_seconds=-1)

        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            config.validate()

    def test_batch_config_validation_invalid_retry_attempts(self):
        """Test validation with invalid retry attempts."""
        config = BatchConfig(retry_attempts=-1)

        with pytest.raises(ValueError, match="retry_attempts cannot be negative"):
            config.validate()

    def test_batch_config_validation_invalid_retry_delay(self):
        """Test validation with invalid retry delay."""
        config = BatchConfig(retry_delay=-1.0)

        with pytest.raises(ValueError, match="retry_delay cannot be negative"):
            config.validate()


class TestBatchProcessor:
    """Test BatchProcessor functionality."""

    def test_batch_processor_initialization(
        self, batch_config, mock_database_service, mock_converter
    ):
        """Test batch processor initialization."""
        processor = BatchProcessor(
            config=batch_config, database_service=mock_database_service, converter=mock_converter
        )

        assert processor.config == batch_config
        assert processor.database_service == mock_database_service
        assert processor.converter == mock_converter
        assert processor.completed_count == 0
        assert processor.failed_count == 0
        assert processor.cancelled is False
        assert processor.semaphore._value == batch_config.max_concurrent
        assert processor.rate_limiter is not None  # Rate limiter configured

    def test_batch_processor_initialization_no_rate_limit(
        self, mock_database_service, mock_converter
    ):
        """Test batch processor initialization without rate limiting."""
        config = BatchConfig(rate_limit_per_second=None)
        processor = BatchProcessor(
            config=config, database_service=mock_database_service, converter=mock_converter
        )

        assert processor.rate_limiter is None

    @pytest.mark.asyncio
    async def test_process_single_url_success(self, batch_processor, mock_converter):
        """Test successful single URL processing."""
        url = "https://example.com/test"
        expected_data = {"content": "test data"}
        mock_converter.process_url.return_value = expected_data

        result = await batch_processor.process_single_url(url, Priority.NORMAL)

        assert result.success is True
        assert result.url == url
        assert result.data == expected_data
        assert result.retries == 0
        assert result.error is None

        mock_converter.process_url.assert_called_once_with(url)

    @pytest.mark.asyncio
    async def test_process_single_url_timeout(self, batch_processor, mock_converter):
        """Test single URL processing with timeout."""
        url = "https://example.com/timeout"
        mock_converter.process_url.side_effect = TimeoutError()

        result = await batch_processor.process_single_url(url, Priority.NORMAL)

        assert result.success is False
        assert result.url == url
        assert "Timeout after" in result.error
        assert result.retries == batch_processor.config.retry_attempts

    @pytest.mark.asyncio
    async def test_process_single_url_exception(self, batch_processor, mock_converter):
        """Test single URL processing with exception."""
        url = "https://example.com/error"
        mock_converter.process_url.side_effect = Exception("Processing error")

        result = await batch_processor.process_single_url(url, Priority.NORMAL)

        assert result.success is False
        assert result.url == url
        assert result.error == "Processing error"
        assert result.retries == batch_processor.config.retry_attempts

    @pytest.mark.asyncio
    async def test_process_single_url_retry_success(self, batch_processor, mock_converter):
        """Test single URL processing with retry success."""
        url = "https://example.com/retry"

        # First call fails, second succeeds
        mock_converter.process_url.side_effect = [
            Exception("First attempt fails"),
            {"content": "success on retry"},
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
            result = await batch_processor.process_single_url(url, Priority.NORMAL)

        assert result.success is True
        assert result.url == url
        assert result.data == {"content": "success on retry"}
        assert result.retries == 1
        assert mock_converter.process_url.call_count == 2

    @pytest.mark.asyncio
    async def test_process_single_url_with_rate_limiting(self, batch_processor):
        """Test single URL processing with rate limiting."""
        url = "https://example.com/rate_limited"

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await batch_processor.process_single_url(url, Priority.NORMAL)

        # Should have called sleep for rate limiting
        mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_process_batch_empty_urls(self, batch_processor):
        """Test processing empty URL list."""
        result = await batch_processor.process_batch("empty_batch", [])

        assert result.total == 0
        assert len(result.successful) == 0
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_process_batch_success(self, batch_processor, mock_converter):
        """Test successful batch processing."""
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

        mock_converter.process_url.return_value = {"status": "ok"}

        result = await batch_processor.process_batch("test_batch", urls)

        assert result.total == 3
        assert len(result.successful) == 3
        assert len(result.failed) == 0
        assert result.duration is not None
        assert result.statistics is not None

        # Verify database calls
        batch_processor.database_service.create_batch.assert_called_once()
        # update_batch_progress is called once per job + once at end, so 4 times total for 3 URLs
        assert batch_processor.database_service.update_batch_progress.call_count == 4

    @pytest.mark.asyncio
    async def test_process_batch_with_priorities(self, batch_processor, mock_converter):
        """Test batch processing with URL priorities."""
        urls = ["url1", "url2", "url3"]
        priorities = {"url1": Priority.LOW, "url2": Priority.HIGH, "url3": Priority.NORMAL}

        mock_converter.process_url.return_value = {"status": "ok"}

        result = await batch_processor.process_batch("priority_batch", urls, priorities)

        assert result.total == 3
        assert len(result.successful) == 3

    @pytest.mark.asyncio
    async def test_process_batch_partial_failure(self, batch_processor, mock_converter):
        """Test batch processing with some failures."""
        urls = ["success_url", "fail_url", "success_url2"]

        def mock_process_url(url):
            if "fail" in url:
                raise Exception("Processing failed")
            return {"status": "ok"}

        mock_converter.process_url.side_effect = mock_process_url

        result = await batch_processor.process_batch("mixed_batch", urls)

        assert result.total == 3
        assert len(result.successful) == 2
        assert len(result.failed) == 1
        assert "fail_url" in result.failed

    @pytest.mark.asyncio
    async def test_process_batch_continue_on_error_false(self, batch_processor, mock_converter):
        """Test batch processing with continue_on_error=False."""
        batch_processor.config.continue_on_error = False
        urls = ["url1", "fail_url", "url3"]

        def mock_process_url(url):
            if "fail" in url:
                raise Exception("Processing failed")
            return {"status": "ok"}

        mock_converter.process_url.side_effect = mock_process_url

        with pytest.raises(BatchProcessingError):
            await batch_processor.process_batch("error_batch", urls)

    @pytest.mark.asyncio
    async def test_process_with_tracking(self, batch_processor, mock_converter):
        """Test _process_with_tracking method."""
        url = "https://example.com/track"
        batch_id = 1
        priority = Priority.NORMAL

        # Mock job creation
        mock_job = Mock(id=123)
        batch_processor.database_service.create_job.return_value = mock_job

        mock_converter.process_url.return_value = {"data": "test"}

        result = await batch_processor._process_with_tracking(url, batch_id, priority)

        assert result.success is True
        assert result.url == url
        assert batch_processor.completed_count == 1
        assert batch_processor.failed_count == 0

        # Verify database interactions
        batch_processor.database_service.create_job.assert_called_once()
        batch_processor.database_service.update_job_status.assert_called()
        batch_processor.database_service.update_batch_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_with_tracking_failure(self, batch_processor, mock_converter):
        """Test _process_with_tracking with processing failure."""
        url = "https://example.com/fail"
        batch_id = 1
        priority = Priority.NORMAL

        mock_job = Mock(id=123)
        batch_processor.database_service.create_job.return_value = mock_job

        mock_converter.process_url.side_effect = Exception("Processing error")

        result = await batch_processor._process_with_tracking(url, batch_id, priority)

        assert result.success is False
        assert batch_processor.completed_count == 0
        assert batch_processor.failed_count == 1

        # Verify failed job was updated with error
        update_calls = batch_processor.database_service.update_job_status.call_args_list
        assert any(JobStatus.FAILED.value in str(call) for call in update_calls)

    @pytest.mark.asyncio
    async def test_process_with_tracking_checkpoint_saving(self, batch_processor, mock_converter):
        """Test checkpoint saving during processing."""
        batch_processor.config.save_checkpoints = True
        batch_processor.config.checkpoint_interval = 1  # Save every job

        url = "https://example.com/checkpoint"
        batch_id = 1

        mock_job = Mock(id=123)
        batch_processor.database_service.create_job.return_value = mock_job
        mock_converter.process_url.return_value = {"data": "test"}

        with patch.object(batch_processor, "_save_checkpoint", new_callable=AsyncMock) as mock_save:
            await batch_processor._process_with_tracking(url, batch_id, Priority.NORMAL)
            mock_save.assert_called_once_with(batch_id)

    @pytest.mark.asyncio
    async def test_resume_batch(self, batch_processor):
        """Test resuming an interrupted batch."""
        batch_id = 1

        # Mock batch
        mock_batch = Mock()
        mock_batch.id = batch_id
        mock_batch.name = "resume_test"
        mock_batch.total_jobs = 5

        # Mock jobs for SQLAlchemy query
        mock_pending_job = Mock(url="pending_url1")
        mock_failed_job = Mock(url="failed_url")

        # Mock SQLAlchemy session and query
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_pending_job, mock_failed_job]
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        batch_processor.database_service.get_batch.return_value = mock_batch
        batch_processor.database_service.get_session.return_value = mock_session

        # Mock process_batch to avoid actual processing
        with patch.object(batch_processor, "process_batch", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = BatchResults(
                total=2, successful=["pending_url1"], failed=["failed_url"]
            )

            result = await batch_processor.resume_batch(batch_id)

            assert result.total == 5  # Original total
            mock_process.assert_called_once()

            # Should process pending and failed URLs
            processed_urls = mock_process.call_args[0][1]
            assert "pending_url1" in processed_urls
            assert "failed_url" in processed_urls
            assert len(processed_urls) == 2

    @pytest.mark.asyncio
    async def test_resume_batch_not_found(self, batch_processor):
        """Test resuming non-existent batch."""
        batch_processor.database_service.get_batch.return_value = None

        with pytest.raises(ValueError, match="Batch 999 not found"):
            await batch_processor.resume_batch(999)

    @pytest.mark.asyncio
    async def test_save_checkpoint(self, batch_processor, tmp_path):
        """Test saving processing checkpoint."""
        batch_processor.config.output_directory = tmp_path
        batch_processor.completed_count = 5
        batch_processor.failed_count = 2

        await batch_processor._save_checkpoint(123)

        checkpoint_file = tmp_path / "checkpoint_123.json"
        assert checkpoint_file.exists()

        import json

        with open(checkpoint_file) as f:
            data = json.load(f)

        assert data["batch_id"] == 123
        assert data["completed"] == 5
        assert data["failed"] == 2
        assert "timestamp" in data

    def test_cancel(self, batch_processor):
        """Test cancelling batch processing."""
        # Add mock active tasks
        mock_task1 = Mock()
        mock_task2 = Mock()
        batch_processor.active_tasks.update([mock_task1, mock_task2])

        batch_processor.cancel()

        assert batch_processor.cancelled is True
        mock_task1.cancel.assert_called_once()
        mock_task2.cancel.assert_called_once()

    def test_get_statistics(self, batch_processor):
        """Test getting processing statistics."""
        batch_processor.completed_count = 8
        batch_processor.failed_count = 2

        stats = batch_processor.get_statistics()

        assert stats["total_processed"] == 10
        assert stats["successful"] == 8
        assert stats["failed"] == 2
        assert stats["success_rate"] == 80.0  # 8/10 * 100
        assert "average_time_per_url" in stats
        assert "total_time_seconds" in stats
        assert "urls_per_second" in stats

    def test_get_statistics_no_processed(self, batch_processor):
        """Test statistics with no processed jobs."""
        stats = batch_processor.get_statistics()

        assert stats["total_processed"] == 0
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_processing_limit(
        self, batch_config, mock_database_service, mock_converter
    ):
        """Test that concurrent processing respects semaphore limits."""
        # Set very low concurrency limit
        batch_config.max_concurrent = 1
        processor = BatchProcessor(batch_config, mock_database_service, mock_converter)

        # Mock slow processing
        async def slow_process(url):
            await asyncio.sleep(0.1)
            return {"data": "processed"}

        mock_converter.process_url.side_effect = slow_process

        urls = ["url1", "url2", "url3"]

        start_time = asyncio.get_event_loop().time()
        await processor.process_batch("concurrent_test", urls)
        end_time = asyncio.get_event_loop().time()

        # With max_concurrent=1, processing should be sequential
        # Total time should be at least 0.3 seconds (3 * 0.1)
        assert end_time - start_time >= 0.25  # Allow some margin


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_processor_integration(tmp_path):
    """Integration test for complete batch processing workflow."""
    # Setup
    config = BatchConfig(
        max_concurrent=2,
        timeout_seconds=5,
        retry_attempts=1,
        output_directory=tmp_path,
        save_checkpoints=True,
    )

    mock_db = MagicMock(spec=DatabaseService)
    mock_db.create_batch.return_value = Mock(id=1)
    mock_db.create_job.return_value = Mock(id=1)
    mock_db.update_batch_status = Mock()
    mock_db.update_job_status = Mock()
    mock_db.update_batch_progress = Mock()

    mock_converter = AsyncMock()

    processor = BatchProcessor(config, mock_db, mock_converter)

    # Test data
    urls = [
        "https://example.com/success1",
        "https://example.com/success2",
        "https://example.com/fail",
        "https://example.com/success3",
    ]

    # Mock converter behavior
    def mock_process(url):
        if "fail" in url:
            raise Exception("Simulated failure")
        return {"url": url, "content": f"Content for {url}"}

    mock_converter.process_url.side_effect = mock_process

    # Execute
    result = await processor.process_batch("integration_test", urls)

    # Verify results
    assert result.total == 4
    assert len(result.successful) == 3
    assert len(result.failed) == 1
    assert "https://example.com/fail" in result.failed
    assert result.duration is not None

    # Verify statistics
    stats = processor.get_statistics()
    assert stats["total_processed"] == 4
    assert stats["successful"] == 3
    assert stats["failed"] == 1
