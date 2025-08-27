"""Enhanced batch processor with advanced features for Phase 4B."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import structlog

from src.core.exceptions import BatchProcessingError
from src.database.models import JobStatus
from src.database.service import DatabaseService

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
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    retries: int = 0
    duration: Optional[float] = None


@dataclass
class BatchResults:
    """Results of batch processing."""

    successful: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    total: int = 0
    duration: Optional[float] = None
    statistics: Optional[dict[str, Any]] = None


@dataclass
class BatchConfig:
    """Enhanced configuration for batch processing."""

    max_concurrent: int = 5
    timeout_seconds: int = 30
    retry_attempts: int = 2
    retry_delay: float = 1.0
    continue_on_error: bool = True
    output_directory: Path = Path("batch_output")
    create_archives: bool = False
    cleanup_after_archive: bool = False
    rate_limit_per_second: Optional[int] = None
    priority_queue: bool = True
    save_checkpoints: bool = True
    checkpoint_interval: int = 10  # Save progress every N jobs

    def validate(self) -> bool:
        """Validate configuration settings."""
        if self.max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_attempts < 0:
            raise ValueError("retry_attempts cannot be negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")
        return True


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
        self.active_tasks: set[asyncio.Task] = set()
        self.completed_count = 0
        self.failed_count = 0
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.rate_limiter: Optional[asyncio.Semaphore] = None
        self.cancelled = False

        if config.rate_limit_per_second:
            self.rate_limiter = asyncio.Semaphore(config.rate_limit_per_second)

        logger.info(
            "Initialized enhanced batch processor",
            max_concurrent=config.max_concurrent,
            timeout=config.timeout_seconds,
            retry_attempts=config.retry_attempts,
        )

    async def process_single_url(
        self, url: str, priority: Priority = Priority.NORMAL
    ) -> ProcessingResult:
        """Process a single URL with retry logic.

        Args:
            url: URL to process
            priority: Processing priority

        Returns:
            ProcessingResult with success status and data
        """
        retries = 0
        last_error = None

        while retries <= self.config.retry_attempts:
            try:
                # Apply rate limiting if configured
                if self.rate_limiter:
                    async with self.rate_limiter:
                        await asyncio.sleep(1.0 / self.config.rate_limit_per_second)

                # Process the URL with timeout
                async with self.semaphore:
                    result = await asyncio.wait_for(
                        self.converter.process_url(url), timeout=self.config.timeout_seconds
                    )

                return ProcessingResult(success=True, url=url, data=result, retries=retries)

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.config.timeout_seconds} seconds"
                logger.warning("URL processing timeout", url=url, attempt=retries + 1)

            except Exception as e:
                last_error = str(e)
                logger.warning("URL processing error", url=url, error=str(e), attempt=retries + 1)

            retries += 1
            if retries <= self.config.retry_attempts:
                await asyncio.sleep(self.config.retry_delay * retries)

        return ProcessingResult(success=False, url=url, error=last_error, retries=retries - 1)

    async def process_batch(
        self, batch_name: str, urls: list[str], priorities: Optional[dict[str, Priority]] = None
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
            max_concurrent=self.config.max_concurrent,
            output_base_directory=str(self.config.output_directory),
        )

        # Reset counters
        self.completed_count = 0
        self.failed_count = 0
        self.cancelled = False

        results = BatchResults(total=len(urls))
        start_time = datetime.now(timezone.utc)

        # Sort URLs by priority if provided
        if priorities:
            sorted_urls = sorted(urls, key=lambda u: priorities.get(u, Priority.NORMAL).value)
        else:
            sorted_urls = urls

        # Process URLs concurrently
        tasks = []
        for url in sorted_urls:
            if self.cancelled:
                break

            priority = priorities.get(url, Priority.NORMAL) if priorities else Priority.NORMAL
            task = asyncio.create_task(self._process_with_tracking(url, batch.id, priority))
            tasks.append(task)
            self.active_tasks.add(task)
            task.add_done_callback(self.active_tasks.discard)

        # Wait for all tasks to complete
        processed = await asyncio.gather(*tasks, return_exceptions=True)

        # Compile results
        for i, result in enumerate(processed):
            if isinstance(result, Exception):
                results.failed.append(sorted_urls[i])
                if not self.config.continue_on_error:
                    raise BatchProcessingError(f"Batch processing failed: {result}")
            elif isinstance(result, ProcessingResult):
                if result.success:
                    results.successful.append(result.url)
                else:
                    results.failed.append(result.url)
                    if not self.config.continue_on_error:
                        raise BatchProcessingError(f"Batch processing failed: {result.error}")

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        results.duration = (end_time - start_time).total_seconds()

        # Update batch status
        self.database_service.update_batch_status(
            batch.id,
            JobStatus.COMPLETED if not results.failed else JobStatus.PARTIAL,
            completed_jobs=len(results.successful),
            failed_jobs=len(results.failed),
        )

        # Generate statistics
        results.statistics = self.get_statistics()

        logger.info(
            "Batch processing complete",
            batch_name=batch_name,
            total=results.total,
            successful=len(results.successful),
            failed=len(results.failed),
            duration=results.duration,
        )

        return results

    async def _process_with_tracking(
        self, url: str, batch_id: int, priority: Priority
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
        job = self.database_service.create_job(url=url, batch_id=batch_id, priority=priority.value)

        # Update job status to running
        self.database_service.update_job_status(job.id, JobStatus.RUNNING)

        # Process the URL
        result = await self.process_single_url(url, priority)

        # Update job status based on result
        if result.success:
            self.completed_count += 1
            self.database_service.update_job_status(
                job.id, JobStatus.COMPLETED, result_data=result.data
            )
        else:
            self.failed_count += 1
            self.database_service.update_job_status(
                job.id, JobStatus.FAILED, error_message=result.error
            )

        # Update batch progress
        self.database_service.update_batch_progress(
            batch_id, self.completed_count, self.failed_count
        )

        # Save checkpoint if configured
        if self.config.save_checkpoints and (self.completed_count + self.failed_count) % self.config.checkpoint_interval == 0:
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

        # Get pending and failed jobs
        jobs = self.database_service.get_batch_jobs(batch_id)
        pending_urls = [
            job.url for job in jobs if job.status in [JobStatus.PENDING, JobStatus.FAILED]
        ]

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

    async def _save_checkpoint(self, batch_id: int):
        """Save processing checkpoint for recovery.

        Args:
            batch_id: Batch ID to checkpoint
        """
        checkpoint_data = {
            "batch_id": batch_id,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        checkpoint_file = self.config.output_directory / f"checkpoint_{batch_id}.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.debug("Saved checkpoint", batch_id=batch_id, file=str(checkpoint_file))

    def cancel(self):
        """Cancel ongoing batch processing."""
        self.cancelled = True

        # Cancel all active tasks
        for task in self.active_tasks:
            task.cancel()

        logger.info("Batch processing cancelled")

    def get_statistics(self) -> dict[str, Any]:
        """Get current processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        total_processed = self.completed_count + self.failed_count
        success_rate = (self.completed_count / total_processed * 100) if total_processed > 0 else 0

        stats = {
            "total_processed": total_processed,
            "successful": self.completed_count,
            "failed": self.failed_count,
            "success_rate": success_rate,
            "average_time_per_url": 0,  # Would need timing tracking
            "total_time_seconds": 0,  # Would need timing tracking
            "urls_per_second": 0,  # Would need timing tracking
        }

        return stats
