"""Batch recovery and resume functionality for Phase 4B."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import structlog
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.batch.enhanced_processor import BatchProcessor, BatchResults
from src.core.exceptions import BatchProcessingError
from src.database.models import Batch, JobStatus, ScrapingJob
from src.database.service import DatabaseService

logger = structlog.get_logger(__name__)


class CheckpointManager:
    """Manages checkpoint creation and recovery for batch operations."""

    def __init__(
        self, database_service: DatabaseService, checkpoint_directory: Path = Path("checkpoints")
    ):
        """Initialize checkpoint manager.

        Args:
            database_service: Database service for persistence
            checkpoint_directory: Directory to store checkpoint files
        """
        self.database_service = database_service
        self.checkpoint_directory = checkpoint_directory
        self.checkpoint_directory.mkdir(parents=True, exist_ok=True)

        logger.info("Initialized checkpoint manager", directory=str(checkpoint_directory))

    def create_checkpoint(self, batch_id: int, current_state: dict[str, Any]) -> Path:
        """Create a checkpoint file for the current batch state.

        Args:
            batch_id: ID of the batch being checkpointed
            current_state: Current processing state

        Returns:
            Path to the created checkpoint file
        """
        checkpoint_data = {
            "batch_id": batch_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "state": current_state,
        }

        checkpoint_file = self.checkpoint_directory / f"batch_{batch_id}_checkpoint.json"

        # Write checkpoint atomically using temporary file
        temp_file = checkpoint_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)

            # Atomic move to final location
            temp_file.replace(checkpoint_file)

            logger.info("Created checkpoint", batch_id=batch_id, file=str(checkpoint_file))

            return checkpoint_file

        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()

            logger.error("Failed to create checkpoint", batch_id=batch_id, error=str(e))
            raise BatchProcessingError(f"Checkpoint creation failed: {e}")

    def load_checkpoint(self, batch_id: int) -> Optional[dict[str, Any]]:
        """Load checkpoint data for a batch.

        Args:
            batch_id: ID of the batch to load checkpoint for

        Returns:
            Checkpoint data if found, None otherwise
        """
        checkpoint_file = self.checkpoint_directory / f"batch_{batch_id}_checkpoint.json"

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file) as f:
                checkpoint_data = json.load(f)

            logger.info("Loaded checkpoint", batch_id=batch_id, file=str(checkpoint_file))

            return checkpoint_data

        except Exception as e:
            logger.error("Failed to load checkpoint", batch_id=batch_id, error=str(e))
            return None

    def list_checkpoints(self) -> list[tuple[int, datetime, Path]]:
        """List all available checkpoints.

        Returns:
            List of tuples (batch_id, timestamp, file_path)
        """
        checkpoints = []

        for checkpoint_file in self.checkpoint_directory.glob("batch_*_checkpoint.json"):
            try:
                with open(checkpoint_file) as f:
                    data = json.load(f)

                batch_id = data["batch_id"]
                timestamp = datetime.fromisoformat(data["timestamp"])
                checkpoints.append((batch_id, timestamp, checkpoint_file))

            except Exception as e:
                logger.warning("Invalid checkpoint file", file=str(checkpoint_file), error=str(e))

        # Sort by timestamp, newest first
        checkpoints.sort(key=lambda x: x[1], reverse=True)
        return checkpoints

    def cleanup_old_checkpoints(self, max_age_days: int = 30):
        """Clean up old checkpoint files.

        Args:
            max_age_days: Maximum age of checkpoints to keep
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        cleaned = 0

        for batch_id, timestamp, file_path in self.list_checkpoints():
            if timestamp < cutoff_date:
                try:
                    file_path.unlink()
                    cleaned += 1
                    logger.info(
                        "Cleaned old checkpoint",
                        batch_id=batch_id,
                        age_days=(datetime.now(timezone.utc) - timestamp).days,
                    )
                except Exception as e:
                    logger.warning("Failed to clean checkpoint", file=str(file_path), error=str(e))

        if cleaned > 0:
            logger.info("Checkpoint cleanup complete", files_cleaned=cleaned)


class BatchRecoveryManager:
    """Manages recovery of interrupted or failed batch operations."""

    def __init__(self, database_service: DatabaseService, checkpoint_manager: CheckpointManager):
        """Initialize recovery manager.

        Args:
            database_service: Database service for data access
            checkpoint_manager: Checkpoint manager for state persistence
        """
        self.database_service = database_service
        self.checkpoint_manager = checkpoint_manager

        logger.info("Initialized batch recovery manager")

    def find_interrupted_batches(self) -> list[dict[str, Any]]:
        """Find batches that were interrupted during processing.

        Returns:
            List of interrupted batch information
        """
        with self.database_service.get_session() as session:
            # Find batches that are in RUNNING state but have no active jobs
            interrupted_batches = (
                session.query(Batch).filter(Batch.status == JobStatus.RUNNING).all()
            )

            recovery_candidates = []

            for batch in interrupted_batches:
                # Check if batch has any running jobs
                running_jobs = (
                    session.query(ScrapingJob)
                    .filter(
                        and_(
                            ScrapingJob.batch_id == batch.id,
                            ScrapingJob.status == JobStatus.RUNNING,
                        )
                    )
                    .count()
                )

                # Check for pending jobs
                pending_jobs = (
                    session.query(ScrapingJob)
                    .filter(
                        and_(
                            ScrapingJob.batch_id == batch.id,
                            ScrapingJob.status == JobStatus.PENDING,
                        )
                    )
                    .count()
                )

                # Check if there's a checkpoint
                checkpoint = self.checkpoint_manager.load_checkpoint(batch.id)

                if running_jobs == 0 and (pending_jobs > 0 or checkpoint):
                    recovery_candidates.append(
                        {
                            "batch_id": batch.id,
                            "name": batch.name,
                            "created_at": batch.created_at,
                            "started_at": batch.started_at,
                            "pending_jobs": pending_jobs,
                            "has_checkpoint": checkpoint is not None,
                            "checkpoint_timestamp": (
                                datetime.fromisoformat(checkpoint["timestamp"])
                                if checkpoint
                                else None
                            ),
                        }
                    )

            logger.info("Found interrupted batches", count=len(recovery_candidates))

            return recovery_candidates

    def analyze_batch_failure(self, batch_id: int) -> dict[str, Any]:
        """Analyze why a batch failed and determine recovery options.

        Args:
            batch_id: ID of the batch to analyze

        Returns:
            Analysis results and recovery recommendations
        """
        with self.database_service.get_session() as session:
            batch = session.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")

            # Get all jobs for this batch
            jobs = session.query(ScrapingJob).filter(ScrapingJob.batch_id == batch_id).all()

            # Analyze job statuses
            status_counts = {}
            for status in JobStatus:
                status_counts[status.value] = len([j for j in jobs if j.status == status])

            # Analyze failure patterns
            failed_jobs = [j for j in jobs if j.status == JobStatus.FAILED]
            error_patterns = {}
            for job in failed_jobs:
                error_type = job.error_type or "unknown"
                error_patterns[error_type] = error_patterns.get(error_type, 0) + 1

            # Determine recovery strategy
            recovery_strategy = self._determine_recovery_strategy(
                batch, jobs, status_counts, error_patterns
            )

            # Load checkpoint if available
            checkpoint = self.checkpoint_manager.load_checkpoint(batch_id)

            analysis = {
                "batch_info": {
                    "id": batch.id,
                    "name": batch.name,
                    "status": batch.status.value,
                    "created_at": batch.created_at.isoformat(),
                    "started_at": batch.started_at.isoformat() if batch.started_at else None,
                },
                "job_analysis": {
                    "total_jobs": len(jobs),
                    "status_counts": status_counts,
                    "completion_rate": (
                        status_counts.get("completed", 0) / len(jobs) * 100 if jobs else 0
                    ),
                },
                "failure_analysis": {
                    "error_patterns": error_patterns,
                    "most_common_error": (
                        max(error_patterns.items(), key=lambda x: x[1]) if error_patterns else None
                    ),
                    "failure_rate": (
                        status_counts.get("failed", 0) / len(jobs) * 100 if jobs else 0
                    ),
                },
                "recovery_options": recovery_strategy,
                "checkpoint_available": checkpoint is not None,
                "checkpoint_timestamp": (checkpoint["timestamp"] if checkpoint else None),
            }

            logger.info(
                "Analyzed batch failure",
                batch_id=batch_id,
                completion_rate=analysis["job_analysis"]["completion_rate"],
                failure_rate=analysis["failure_analysis"]["failure_rate"],
            )

            return analysis

    async def recover_batch(
        self,
        batch_id: int,
        recovery_strategy: str = "resume_pending",
        processor: Optional[BatchProcessor] = None,
    ) -> BatchResults:
        """Recover a failed or interrupted batch.

        Args:
            batch_id: ID of the batch to recover
            recovery_strategy: Recovery strategy to use
            processor: Batch processor to use for recovery

        Returns:
            Results from the recovery operation
        """
        logger.info("Starting batch recovery", batch_id=batch_id, strategy=recovery_strategy)

        with self.database_service.get_session() as session:
            batch = session.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")

            # Load checkpoint if available
            self.checkpoint_manager.load_checkpoint(batch_id)

            # Get jobs to recover based on strategy
            jobs_to_recover = self._get_jobs_for_recovery(session, batch_id, recovery_strategy)

            if not jobs_to_recover:
                logger.info("No jobs to recover", batch_id=batch_id)
                return BatchResults(total=0)

            # Reset job statuses to PENDING for retry
            urls_to_retry = []
            for job in jobs_to_recover:
                if job.status == JobStatus.FAILED:
                    job.status = JobStatus.PENDING
                    job.error_message = None
                    job.error_type = None
                    job.retry_count += 1

                urls_to_retry.append(job.url)

            session.commit()

            # Update batch status
            batch.status = JobStatus.RUNNING
            session.commit()

            logger.info(
                "Prepared batch for recovery", batch_id=batch_id, urls_to_retry=len(urls_to_retry)
            )

        # Process the recovered URLs if processor is provided
        if processor:
            results = await processor.process_batch(f"{batch.name}_recovery", urls_to_retry)

            logger.info(
                "Batch recovery complete",
                batch_id=batch_id,
                successful=len(results.successful),
                failed=len(results.failed),
            )

            return results
        else:
            # Return info about what would be recovered
            return BatchResults(
                total=len(urls_to_retry),
                successful=[],  # Not actually processed yet
                failed=[],
            )

    def create_recovery_plan(self, batch_id: int) -> dict[str, Any]:
        """Create a detailed recovery plan for a failed batch.

        Args:
            batch_id: ID of the batch to create plan for

        Returns:
            Detailed recovery plan
        """
        analysis = self.analyze_batch_failure(batch_id)

        plan_steps = []

        # Step 1: Clean up any corrupted state
        plan_steps.append(
            {
                "step": 1,
                "action": "cleanup_state",
                "description": "Reset failed jobs and clean up temporary files",
                "estimated_duration": "1-2 minutes",
            }
        )

        # Step 2: Apply recovery strategy
        strategy = analysis["recovery_options"]["recommended_strategy"]
        plan_steps.append(
            {
                "step": 2,
                "action": "apply_recovery_strategy",
                "description": f"Apply {strategy} recovery strategy",
                "estimated_duration": "Variable based on remaining jobs",
            }
        )

        # Step 3: Resume processing
        remaining_jobs = analysis["job_analysis"]["status_counts"].get("pending", 0)
        failed_jobs = analysis["job_analysis"]["status_counts"].get("failed", 0)

        jobs_to_process = remaining_jobs + (failed_jobs if strategy == "retry_failed" else 0)

        plan_steps.append(
            {
                "step": 3,
                "action": "resume_processing",
                "description": f"Process {jobs_to_process} remaining jobs",
                "estimated_duration": f"~{jobs_to_process * 2} seconds",
            }
        )

        recovery_plan = {
            "batch_id": batch_id,
            "analysis": analysis,
            "recovery_steps": plan_steps,
            "estimated_total_time": f"{2 + (jobs_to_process * 2 // 60)} minutes",
            "success_probability": self._estimate_success_probability(analysis),
            "risks": self._identify_recovery_risks(analysis),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return recovery_plan

    def _determine_recovery_strategy(
        self,
        batch: Batch,
        jobs: list[ScrapingJob],
        status_counts: dict[str, int],
        error_patterns: dict[str, int],
    ) -> dict[str, Any]:
        """Determine the best recovery strategy for a batch."""
        total_jobs = len(jobs)
        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        pending = status_counts.get("pending", 0)

        completion_rate = completed / total_jobs if total_jobs > 0 else 0
        failure_rate = failed / total_jobs if total_jobs > 0 else 0

        # Determine strategy based on completion and failure rates
        if completion_rate > 0.8:
            # High completion rate - just retry failures
            recommended = "retry_failed"
        elif failure_rate > 0.5:
            # High failure rate - investigate errors first
            recommended = "investigate_errors"
        elif pending > 0:
            # Resume pending jobs
            recommended = "resume_pending"
        else:
            # Full retry
            recommended = "full_retry"

        return {
            "recommended_strategy": recommended,
            "available_strategies": [
                "resume_pending",
                "retry_failed",
                "full_retry",
                "partial_recovery",
                "investigate_errors",
            ],
            "strategy_descriptions": {
                "resume_pending": "Continue processing pending jobs only",
                "retry_failed": "Retry only failed jobs",
                "full_retry": "Retry all non-completed jobs",
                "partial_recovery": "Recover specific job subsets",
                "investigate_errors": "Analyze errors before recovery",
            },
            "recommendation_reason": f"Completion: {completion_rate:.1%}, Failure: {failure_rate:.1%}",
        }

    def _get_jobs_for_recovery(
        self, session: Session, batch_id: int, strategy: str
    ) -> list[ScrapingJob]:
        """Get jobs that need to be recovered based on strategy."""
        base_query = session.query(ScrapingJob).filter(ScrapingJob.batch_id == batch_id)

        if strategy == "resume_pending":
            return base_query.filter(ScrapingJob.status == JobStatus.PENDING).all()
        elif strategy == "retry_failed":
            return base_query.filter(ScrapingJob.status == JobStatus.FAILED).all()
        elif strategy == "full_retry":
            return base_query.filter(
                or_(ScrapingJob.status == JobStatus.PENDING, ScrapingJob.status == JobStatus.FAILED)
            ).all()
        else:
            # Default to pending jobs
            return base_query.filter(ScrapingJob.status == JobStatus.PENDING).all()

    def _estimate_success_probability(self, analysis: dict[str, Any]) -> float:
        """Estimate probability of successful recovery."""
        completion_rate = analysis["job_analysis"]["completion_rate"]
        failure_rate = analysis["failure_analysis"]["failure_rate"]

        # Simple heuristic based on previous performance
        base_probability = 0.7  # Base 70% success chance

        # Adjust based on completion rate
        if completion_rate > 50:
            base_probability += 0.2
        elif completion_rate < 20:
            base_probability -= 0.2

        # Adjust based on failure rate
        if failure_rate > 50:
            base_probability -= 0.3
        elif failure_rate < 10:
            base_probability += 0.1

        return max(0.1, min(0.95, base_probability))

    def _identify_recovery_risks(self, analysis: dict[str, Any]) -> list[str]:
        """Identify potential risks for recovery operation."""
        risks = []

        failure_rate = analysis["failure_analysis"]["failure_rate"]
        error_patterns = analysis["failure_analysis"]["error_patterns"]

        if failure_rate > 30:
            risks.append("High failure rate may indicate systemic issues")

        if "timeout" in str(error_patterns).lower():
            risks.append("Timeout errors may indicate network issues")

        if "connection" in str(error_patterns).lower():
            risks.append("Connection errors may require infrastructure fixes")

        if not analysis["checkpoint_available"]:
            risks.append("No checkpoint available - limited recovery state")

        if not risks:
            risks.append("Low risk recovery operation")

        return risks
