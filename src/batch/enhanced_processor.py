"""Enhanced batch processor with advanced features for Phase 4B."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import asyncio
import structlog
from sqlalchemy import select

from src.core.exceptions import BatchProcessingError
from src.database.models import JobStatus, ScrapingJob
from src.database.service import DatabaseService, JobCreateRequest

logger = structlog.get_logger(__name__)


class Priority(Enum):
    """Job priority levels for queue management."""

    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    DEFERRED = 5


@dataclass
class ProcessingResult:
    """Result of processing a single URL."""

    success: bool
    url: str
    data: dict[str, Any] | None = None
    error: str | None = None
    retries: int = 0
    duration: float | None = None


@dataclass
class ProcessingState:
    """Tracks current processing state."""

    active_tasks: set[asyncio.Task] = field(default_factory=set)
    completed_count: int = 0
    failed_count: int = 0
    cancelled: bool = False

    def reset(self) -> None:
        """Reset processing counters."""
        self.completed_count = 0
        self.failed_count = 0
        self.cancelled = False


@dataclass
class BatchResults:
    """Results of batch processing."""

    successful: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    total: int = 0
    duration: float | None = None
    statistics: dict[str, Any] | None = None


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrency and rate limiting."""

    max_concurrent: int = 5
    timeout_seconds: int = 30
    rate_limit_per_second: int | None = None


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    retry_attempts: int = 2
    retry_delay: float = 1.0
    continue_on_error: bool = True


@dataclass
class ProcessingConfig:
    """Configuration for processing behavior."""

    priority_queue: bool = True
    save_checkpoints: bool = True
    checkpoint_interval: int = 10  # Save progress every N jobs


@dataclass
class OutputConfig:
    """Configuration for output handling."""

    output_directory: Path = Path("batch_output")
    create_archives: bool = False
    cleanup_after_archive: bool = False


@dataclass
class BatchConfig:
    """Enhanced configuration for batch processing."""

    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    def __init__(self, **kwargs):
        """Initialize batch configuration with backward compatibility.

        Args:
            **kwargs: Configuration parameters including:
                - concurrency: ConcurrencyConfig instance
                - retry: RetryConfig instance
                - processing: ProcessingConfig instance
                - output: OutputConfig instance
                - max_concurrent: Maximum concurrent operations (backward compatibility)
                - rate_limit_per_second: Rate limit per second (backward compatibility)
                - retry_attempts: Number of retry attempts (backward compatibility)
                - timeout_seconds: Timeout in seconds (backward compatibility)
                - continue_on_error: Whether to continue on error (backward compatibility)
                - output_directory: Output directory path (backward compatibility)
        """
        # Use provided nested configs or create from kwargs/defaults
        self.concurrency = kwargs.get("concurrency") or ConcurrencyConfig(
            max_concurrent=kwargs.get("max_concurrent", 5),
            rate_limit_per_second=kwargs.get("rate_limit_per_second"),
            timeout_seconds=kwargs.get("timeout_seconds", 30),
        )

        self.retry = kwargs.get("retry") or RetryConfig(
            retry_attempts=kwargs.get("retry_attempts", 2),
            retry_delay=kwargs.get("retry_delay", 1.0),
            continue_on_error=kwargs.get("continue_on_error", True),
        )

        self.processing = kwargs.get("processing") or ProcessingConfig()

        self.output = kwargs.get("output")
        if not self.output:
            output_directory = kwargs.get("output_directory")
            if output_directory:
                self.output = OutputConfig(output_directory=Path(output_directory))
            else:
                self.output = OutputConfig()

    def validate(self) -> bool:
        """Validate configuration settings."""
        if self.concurrency.max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive")
        if self.concurrency.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry.retry_attempts < 0:
            raise ValueError("retry_attempts cannot be negative")
        if self.retry.retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")
        return True


class ConcurrencyManager:
    """Manages concurrency controls for batch processing."""

    def __init__(self, config: ConcurrencyConfig):
        """Initialize concurrency manager."""
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.rate_limiter = self._create_rate_limiter()

    def get_semaphore(self) -> asyncio.Semaphore:
        """Get the concurrency semaphore for controlling concurrent operations."""
        return self.semaphore

    def get_rate_limiter(self) -> asyncio.Semaphore | None:
        """Get the rate limiter semaphore if configured."""
        return self.rate_limiter

    def _create_rate_limiter(self) -> asyncio.Semaphore | None:
        """Create rate limiter if configured."""
        if self.config.rate_limit_per_second:
            return asyncio.Semaphore(self.config.rate_limit_per_second)
        return None


class BatchProcessor:
    """Enhanced batch processor with concurrent execution and recovery."""

    def __init__(
        self,
        config: BatchConfig,
        database_service: DatabaseService,
        converter: Any,  # AsyncWordPressConverter
    ):
        """Initialize the enhanced batch processor.

        Args:
            config: Batch processing configuration
            database_service: Database service for persistence
            converter: Converter for processing URLs
        """
        self.config = config
        self.database_service = database_service
        self.converter = converter
        self.state = ProcessingState()
        self.concurrency = ConcurrencyManager(config.concurrency)

        logger.info(
            "Initialized enhanced batch processor",
            max_concurrent=config.concurrency.max_concurrent,
            timeout=config.concurrency.timeout_seconds,
            retry_attempts=config.retry.retry_attempts,
        )

    async def process_single_url(
        self, url: str, _priority: Priority = Priority.NORMAL
    ) -> ProcessingResult:
        """Process a single URL with retry logic.

        Args:
            url: URL to process
            _priority: Processing priority (unused but kept for API compatibility)

        Returns:
            ProcessingResult with success status and data
        """
        retries = 0
        last_error = None

        while retries <= self.config.retry.retry_attempts:
            try:
                # Apply rate limiting if configured
                if self.concurrency.rate_limiter and self.config.concurrency.rate_limit_per_second:
                    async with self.concurrency.rate_limiter:
                        await asyncio.sleep(1.0 / self.config.concurrency.rate_limit_per_second)

                # Process the URL with timeout
                async with self.concurrency.get_semaphore():
                    result = await asyncio.wait_for(
                        self.converter.process_url(url),
                        timeout=self.config.concurrency.timeout_seconds,
                    )

                return ProcessingResult(success=True, url=url, data=result, retries=retries)

            except TimeoutError as e:
                last_error = f"Timeout after {self.config.concurrency.timeout_seconds} seconds"
                logger.warning("URL processing timeout", url=url, attempt=retries + 1, error=str(e))

            except (ConnectionError, OSError) as e:
                last_error = f"Connection error: {e}"
                logger.warning("URL connection error", url=url, error=str(e), attempt=retries + 1)

            except (ValueError, TypeError, AttributeError) as e:
                last_error = f"Processing error: {e}"
                logger.warning("URL processing error", url=url, error=str(e), attempt=retries + 1)

            except Exception as e:  # pylint: disable=broad-exception-caught
                last_error = f"Processing error: {e}"
                logger.warning("URL processing error", url=url, error=str(e), attempt=retries + 1)

            retries += 1
            if retries <= self.config.retry.retry_attempts:
                await asyncio.sleep(self.config.retry.retry_delay * retries)

        return ProcessingResult(success=False, url=url, error=last_error, retries=retries - 1)

    async def process_batch(
        self, batch_name: str, urls: list[str], priorities: dict[str, Priority] | None = None
    ) -> BatchResults:
        """Process a batch of URLs concurrently.

        Args:
            batch_name: Name for the batch
            urls: List of URLs to process
            priorities: Optional priority mapping for URLs

        Returns:
            BatchResults with success/failure lists
        """
        if not urls:
            return BatchResults(total=0)

        # Create batch in database
        batch = self.database_service.create_batch(
            name=batch_name,
            total_jobs=len(urls),
            max_concurrent=self.config.concurrency.max_concurrent,
            output_base_directory=str(self.config.output.output_directory),
        )

        # Execute batch processing workflow
        self._reset_state()
        results = BatchResults(total=len(urls))
        start_time = datetime.now(UTC)

        # Process URLs and compile results
        sorted_urls = self._sort_urls_by_priority(urls, priorities)
        tasks = self._create_processing_tasks(sorted_urls, batch.id, priorities)
        processed = await asyncio.gather(*tasks, return_exceptions=True)
        self._compile_results(processed, sorted_urls, results)

        # Finalize results
        results = self._finalize_batch_results(results, start_time, batch)

        # Check continue_on_error setting
        if not self.config.retry.continue_on_error and results.failed:
            raise BatchProcessingError(
                f"Batch processing failed with {len(results.failed)} failed URLs",
                batch_id=batch.id,
            )

        logger.info(
            "Batch processing complete",
            batch_name=batch_name,
            total=results.total,
            successful=len(results.successful),
            failed=len(results.failed),
            duration=results.duration,
        )

        return results

    def _reset_state(self) -> None:
        """Reset processing counters."""
        self.state.reset()

    def _sort_urls_by_priority(
        self, urls: list[str], priorities: dict[str, Priority] | None
    ) -> list[str]:
        """Sort URLs by priority if provided."""
        if priorities:
            return sorted(urls, key=lambda u: priorities.get(u, Priority.NORMAL).value)
        return urls

    def _create_processing_tasks(
        self, urls: list[str], batch_id: str, priorities: dict[str, Priority] | None
    ) -> list[asyncio.Task]:
        """Create processing tasks for URLs."""
        tasks = []
        for url in urls:
            if self.state.cancelled:
                break
            priority = priorities.get(url, Priority.NORMAL) if priorities else Priority.NORMAL
            task = asyncio.create_task(self._process_with_tracking(url, batch_id, priority))
            tasks.append(task)
            self.state.active_tasks.add(task)
            task.add_done_callback(self.state.active_tasks.discard)
        return tasks

    def _compile_results(
        self, processed: list, sorted_urls: list[str], results: BatchResults
    ) -> None:
        """Compile processing results."""
        for i, result in enumerate(processed):
            if isinstance(result, Exception):
                results.failed.append(sorted_urls[i])
                if not self.config.retry.continue_on_error:
                    raise BatchProcessingError(f"Batch processing failed: {result}") from result
            elif isinstance(result, ProcessingResult):
                if result.success:
                    results.successful.append(result.url)
                else:
                    results.failed.append(result.url)
                    if not self.config.retry.continue_on_error:
                        raise BatchProcessingError(f"Batch processing failed: {result.error}")

    def _finalize_batch_results(
        self, results: BatchResults, start_time: datetime, batch
    ) -> BatchResults:
        """Finalize batch results with timing and statistics."""
        end_time = datetime.now(UTC)
        results.duration = (end_time - start_time).total_seconds()

        # Update batch progress
        self.database_service.update_batch_progress(batch.id)

        # Generate statistics
        results.statistics = self.get_statistics()

        return results

    async def _process_with_tracking(
        self, url: str, batch_id: str, priority: Priority
    ) -> ProcessingResult:
        """Process a URL with progress tracking.

        Args:
            url: URL to process
            batch_id: Batch ID for tracking
            priority: Processing priority

        Returns:
            ProcessingResult
        """
        # Create job in database
        request = JobCreateRequest(
            url=url,
            output_directory=str(self.config.output.output_directory),
            batch_id=batch_id,
            priority=priority.name.lower(),
        )
        job = self.database_service.create_job(request)

        # Update job status to running
        self.database_service.update_job_status(job.id, JobStatus.RUNNING.value)

        # Process the URL
        result = await self.process_single_url(url, priority)

        # Update job status based on result
        if result.success:
            self.state.completed_count += 1
            self.database_service.update_job_status(
                job.id, JobStatus.COMPLETED.value, duration=result.duration
            )
        else:
            self.state.failed_count += 1
            self.database_service.update_job_status(
                job.id, JobStatus.FAILED.value, error_message=result.error
            )

        # Update batch progress
        self.database_service.update_batch_progress(batch_id)

        # Save checkpoint if configured
        if (
            self.config.processing.save_checkpoints
            and (self.state.completed_count + self.state.failed_count)
            % self.config.processing.checkpoint_interval
            == 0
        ):
            await self._save_checkpoint(batch_id)

        return result

    async def resume_batch(self, batch_id: int) -> BatchResults:
        """Resume an interrupted batch.

        Args:
            batch_id: ID of the batch to resume

        Returns:
            BatchResults for the resumed processing
        """
        batch = self.database_service.get_batch(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        # Get pending and failed jobs for this batch
        with self.database_service.get_session() as session:
            stmt = select(ScrapingJob).where(
                ScrapingJob.batch_id == batch_id,
                ScrapingJob.status.in_([JobStatus.PENDING, JobStatus.FAILED]),
            )
            jobs = session.execute(stmt).scalars().all()
            pending_urls = [job.url for job in jobs]

        logger.info(
            "Resuming batch",
            batch_id=batch_id,
            pending_jobs=len(pending_urls),
            total_jobs=batch.total_jobs,
        )

        # Process remaining URLs
        results = await self.process_batch(batch.name + "_resumed", pending_urls)

        # Adjust totals to include previously completed jobs
        results.total = batch.total_jobs

        return results

    async def _save_checkpoint(self, batch_id: str):
        """Save processing checkpoint for recovery.

        Args:
            batch_id: Batch ID to checkpoint
        """
        checkpoint_data = {
            "batch_id": batch_id,
            "completed": self.state.completed_count,
            "failed": self.state.failed_count,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        checkpoint_file = self.config.output.output_directory / f"checkpoint_{batch_id}.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.debug("Saved checkpoint", batch_id=batch_id, file=str(checkpoint_file))

    def cancel(self):
        """Cancel ongoing batch processing."""
        self.state.cancelled = True

        # Cancel all active tasks
        for task in self.state.active_tasks:
            task.cancel()

        logger.info("Batch processing cancelled")

    def get_statistics(self) -> dict[str, Any]:
        """Get current processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        total_processed = self.state.completed_count + self.state.failed_count
        success_rate = (
            (self.state.completed_count / total_processed * 100) if total_processed > 0 else 0
        )

        stats = {
            "total_processed": total_processed,
            "successful": self.state.completed_count,
            "failed": self.state.failed_count,
            "success_rate": success_rate,
            "average_time_per_url": 0,  # Would need timing tracking
            "total_time_seconds": 0,  # Would need timing tracking
            "urls_per_second": 0,  # Would need timing tracking
        }

        return stats
