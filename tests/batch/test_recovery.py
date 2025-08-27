"""Tests for batch recovery and resume functionality."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.batch.enhanced_processor import BatchProcessor, BatchResults
from src.batch.recovery import BatchRecoveryManager, CheckpointManager
from src.core.exceptions import BatchProcessingError
from src.database.models import Batch, JobStatus, ScrapingJob
from src.database.service import DatabaseService


@pytest.fixture
def mock_database_service():
    """Create mock database service."""
    service = MagicMock(spec=DatabaseService)
    service.get_session.return_value.__enter__ = Mock(return_value=MagicMock())
    service.get_session.return_value.__exit__ = Mock(return_value=None)
    return service


@pytest.fixture
def checkpoint_manager(mock_database_service, tmp_path):
    """Create checkpoint manager instance."""
    return CheckpointManager(
        database_service=mock_database_service, checkpoint_directory=tmp_path / "checkpoints"
    )


@pytest.fixture
def recovery_manager(mock_database_service, checkpoint_manager):
    """Create batch recovery manager instance."""
    return BatchRecoveryManager(
        database_service=mock_database_service, checkpoint_manager=checkpoint_manager
    )


@pytest.fixture
def sample_batch():
    """Create sample batch mock."""
    batch = Mock(spec=Batch)
    batch.id = 1
    batch.name = "test_batch"
    batch.status = JobStatus.RUNNING
    batch.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    batch.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    batch.completed_at = None
    batch.max_concurrent = 5
    batch.output_base_directory = "/test/output"
    batch.total_jobs = 10
    batch.completed_jobs = 7
    batch.failed_jobs = 3
    return batch


@pytest.fixture
def sample_jobs():
    """Create sample job mocks."""
    jobs = []
    statuses = [JobStatus.COMPLETED] * 7 + [JobStatus.FAILED] * 2 + [JobStatus.PENDING] * 1

    for i, status in enumerate(statuses):
        job = Mock(spec=ScrapingJob)
        job.id = i + 1
        job.url = f"https://example.com/page{i + 1}"
        job.status = status
        job.batch_id = 1
        job.domain = "example.com"
        job.duration_seconds = 2.0 if status == JobStatus.COMPLETED else None
        job.error_type = "timeout" if status == JobStatus.FAILED else None
        job.error_message = "Request timeout" if status == JobStatus.FAILED else None
        job.created_at = datetime.now(timezone.utc) - timedelta(minutes=60 - i * 5)
        job.completed_at = (
            datetime.now(timezone.utc) - timedelta(minutes=30 - i * 2)
            if status == JobStatus.COMPLETED
            else None
        )
        job.retry_count = 0
        jobs.append(job)

    return jobs


class TestCheckpointManager:
    """Test CheckpointManager functionality."""

    def test_initialization(self, mock_database_service, tmp_path):
        """Test checkpoint manager initialization."""
        checkpoint_dir = tmp_path / "test_checkpoints"
        manager = CheckpointManager(
            database_service=mock_database_service, checkpoint_directory=checkpoint_dir
        )

        assert manager.database_service is mock_database_service
        assert manager.checkpoint_directory == checkpoint_dir
        assert checkpoint_dir.exists()  # Should be created

    def test_create_checkpoint_success(self, checkpoint_manager):
        """Test successful checkpoint creation."""
        batch_id = 123
        state = {"processed": 5, "failed": 1, "current_url": "https://example.com/current"}

        checkpoint_file = checkpoint_manager.create_checkpoint(batch_id, state)

        assert checkpoint_file.exists()
        assert checkpoint_file.name == "batch_123_checkpoint.json"

        # Verify checkpoint content
        with open(checkpoint_file) as f:
            data = json.load(f)

        assert data["batch_id"] == batch_id
        assert data["version"] == "1.0"
        assert data["state"] == state
        assert "timestamp" in data

    def test_create_checkpoint_atomic_write(self, checkpoint_manager):
        """Test that checkpoint creation is atomic."""
        batch_id = 456
        state = {"test": "data"}

        # Mock file operations to test atomic write behavior
        checkpoint_file = checkpoint_manager.create_checkpoint(batch_id, state)

        # File should exist and be complete (not .tmp)
        assert checkpoint_file.exists()
        assert not checkpoint_file.with_suffix(".tmp").exists()

    def test_create_checkpoint_write_error(self, checkpoint_manager):
        """Test checkpoint creation with write error."""
        batch_id = 789
        state = {"test": "data"}

        # Mock the open function to raise an exception
        with patch("builtins.open", side_effect=PermissionError("Write permission denied")):
            with pytest.raises(BatchProcessingError):
                checkpoint_manager.create_checkpoint(batch_id, state)

    def test_load_checkpoint_success(self, checkpoint_manager):
        """Test successful checkpoint loading."""
        batch_id = 111
        state = {"loaded": True, "count": 42}

        # Create checkpoint first
        checkpoint_manager.create_checkpoint(batch_id, state)

        # Load it back
        loaded_data = checkpoint_manager.load_checkpoint(batch_id)

        assert loaded_data is not None
        assert loaded_data["batch_id"] == batch_id
        assert loaded_data["state"] == state
        assert "timestamp" in loaded_data

    def test_load_checkpoint_not_found(self, checkpoint_manager):
        """Test loading non-existent checkpoint."""
        result = checkpoint_manager.load_checkpoint(999)
        assert result is None

    def test_load_checkpoint_invalid_json(self, checkpoint_manager, tmp_path):
        """Test loading checkpoint with invalid JSON."""
        # Create invalid checkpoint file
        checkpoint_file = checkpoint_manager.checkpoint_directory / "batch_222_checkpoint.json"
        checkpoint_file.write_text("invalid json content")

        result = checkpoint_manager.load_checkpoint(222)
        assert result is None

    def test_list_checkpoints(self, checkpoint_manager):
        """Test listing all checkpoints."""
        # Create multiple checkpoints
        states = [{"count": i} for i in range(3)]
        batch_ids = [100, 200, 300]

        for batch_id, state in zip(batch_ids, states):
            checkpoint_manager.create_checkpoint(batch_id, state)

        checkpoints = checkpoint_manager.list_checkpoints()

        assert len(checkpoints) == 3

        # Verify structure: (batch_id, timestamp, file_path)
        for batch_id, timestamp, file_path in checkpoints:
            assert batch_id in batch_ids
            assert isinstance(timestamp, datetime)
            assert file_path.exists()

        # Should be sorted by timestamp (newest first)
        timestamps = [checkpoint[1] for checkpoint in checkpoints]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_checkpoints_invalid_file(self, checkpoint_manager):
        """Test listing checkpoints with invalid files."""
        # Create valid checkpoint
        checkpoint_manager.create_checkpoint(123, {"valid": True})

        # Create invalid checkpoint file
        invalid_file = checkpoint_manager.checkpoint_directory / "batch_456_checkpoint.json"
        invalid_file.write_text("invalid json")

        checkpoints = checkpoint_manager.list_checkpoints()

        # Should only return valid checkpoint
        assert len(checkpoints) == 1
        assert checkpoints[0][0] == 123

    def test_cleanup_old_checkpoints(self, checkpoint_manager):
        """Test cleaning up old checkpoint files."""
        # Create old checkpoint
        old_state = {"old": True}
        checkpoint_manager.create_checkpoint(111, old_state)
        old_checkpoint = checkpoint_manager.checkpoint_directory / "batch_111_checkpoint.json"

        # Manually modify timestamp to make it old
        old_data = json.loads(old_checkpoint.read_text())
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        old_data["timestamp"] = old_timestamp.isoformat()
        old_checkpoint.write_text(json.dumps(old_data))

        # Create recent checkpoint
        checkpoint_manager.create_checkpoint(222, {"recent": True})

        # Cleanup old checkpoints (max_age_days=30)
        checkpoint_manager.cleanup_old_checkpoints(max_age_days=30)

        # Old checkpoint should be removed
        assert not old_checkpoint.exists()

        # Recent checkpoint should remain
        recent_checkpoint = checkpoint_manager.checkpoint_directory / "batch_222_checkpoint.json"
        assert recent_checkpoint.exists()

    def test_cleanup_old_checkpoints_no_old_files(self, checkpoint_manager):
        """Test cleanup when no old files exist."""
        # Create recent checkpoint
        checkpoint_manager.create_checkpoint(123, {"recent": True})

        # Should not raise error and file should remain
        checkpoint_manager.cleanup_old_checkpoints(max_age_days=1)

        checkpoint_file = checkpoint_manager.checkpoint_directory / "batch_123_checkpoint.json"
        assert checkpoint_file.exists()


class TestBatchRecoveryManager:
    """Test BatchRecoveryManager functionality."""

    def test_initialization(self, mock_database_service, checkpoint_manager):
        """Test recovery manager initialization."""
        manager = BatchRecoveryManager(
            database_service=mock_database_service, checkpoint_manager=checkpoint_manager
        )

        assert manager.database_service is mock_database_service
        assert manager.checkpoint_manager is checkpoint_manager

    def test_find_interrupted_batches(self, recovery_manager, sample_batch):
        """Test finding interrupted batches."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )

        # Mock running batches
        mock_session.query.return_value.filter.return_value.all.return_value = [sample_batch]

        # Mock no running jobs, some pending jobs
        mock_session.query.return_value.filter.return_value.count.side_effect = [
            0,
            3,
        ]  # 0 running, 3 pending

        # Mock checkpoint loading
        recovery_manager.checkpoint_manager.load_checkpoint = Mock(return_value=None)

        interrupted = recovery_manager.find_interrupted_batches()

        assert len(interrupted) == 1
        batch_info = interrupted[0]
        assert batch_info["batch_id"] == 1
        assert batch_info["name"] == "test_batch"
        assert batch_info["pending_jobs"] == 3
        assert batch_info["has_checkpoint"] is False

    def test_find_interrupted_batches_with_checkpoint(self, recovery_manager, sample_batch):
        """Test finding interrupted batches with checkpoints."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.all.return_value = [sample_batch]
        mock_session.query.return_value.filter.return_value.count.side_effect = [
            0,
            0,
        ]  # No running or pending

        # Mock checkpoint exists
        checkpoint_data = {"timestamp": datetime.now(timezone.utc).isoformat()}
        recovery_manager.checkpoint_manager.load_checkpoint = Mock(return_value=checkpoint_data)

        interrupted = recovery_manager.find_interrupted_batches()

        assert len(interrupted) == 1
        assert interrupted[0]["has_checkpoint"] is True
        assert interrupted[0]["checkpoint_timestamp"] is not None

    def test_find_interrupted_batches_none_found(self, recovery_manager):
        """Test finding interrupted batches when none exist."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.all.return_value = []

        interrupted = recovery_manager.find_interrupted_batches()
        assert len(interrupted) == 0

    def test_analyze_batch_failure(self, recovery_manager, sample_batch, sample_jobs):
        """Test analyzing batch failure."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch
        mock_session.query.return_value.filter.return_value.all.return_value = sample_jobs

        # Mock checkpoint with proper structure
        recovery_manager.checkpoint_manager.load_checkpoint = Mock(
            return_value={"test": "checkpoint", "timestamp": "2025-01-01T00:00:00+00:00"}
        )

        analysis = recovery_manager.analyze_batch_failure(1)

        # Verify analysis structure
        assert "batch_info" in analysis
        assert "job_analysis" in analysis
        assert "failure_analysis" in analysis
        assert "recovery_options" in analysis

        # Verify batch info
        batch_info = analysis["batch_info"]
        assert batch_info["id"] == 1
        assert batch_info["name"] == "test_batch"

        # Verify job analysis
        job_analysis = analysis["job_analysis"]
        assert job_analysis["total_jobs"] == 10
        assert job_analysis["status_counts"]["completed"] == 7
        assert job_analysis["status_counts"]["failed"] == 2
        assert job_analysis["status_counts"]["pending"] == 1
        assert job_analysis["completion_rate"] == 70.0

        # Verify failure analysis
        failure_analysis = analysis["failure_analysis"]
        assert "timeout" in failure_analysis["error_patterns"]
        assert failure_analysis["error_patterns"]["timeout"] == 2
        assert failure_analysis["failure_rate"] == 20.0

        # Verify checkpoint info
        assert analysis["checkpoint_available"] is True

    def test_analyze_batch_failure_not_found(self, recovery_manager):
        """Test analyzing non-existent batch."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Batch 999 not found"):
            recovery_manager.analyze_batch_failure(999)

    @pytest.mark.asyncio
    async def test_recover_batch_not_found(self, recovery_manager):
        """Test recovering non-existent batch."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Batch 999 not found"):
            await recovery_manager.recover_batch(999)

    @pytest.mark.asyncio
    async def test_recover_batch_no_jobs_to_recover(self, recovery_manager, sample_batch):
        """Test recovering batch with no jobs to recover."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch

        # Mock no jobs need recovery
        recovery_manager._get_jobs_for_recovery = Mock(return_value=[])

        result = await recovery_manager.recover_batch(1)

        assert result.total == 0
        assert len(result.successful) == 0
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_recover_batch_with_processor(self, recovery_manager, sample_batch, sample_jobs):
        """Test batch recovery with processor."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch

        # Mock failed jobs for recovery
        failed_jobs = [job for job in sample_jobs if job.status == JobStatus.FAILED]
        recovery_manager._get_jobs_for_recovery = Mock(return_value=failed_jobs)

        # Mock processor
        mock_processor = Mock(spec=BatchProcessor)
        mock_processor.process_batch = AsyncMock(
            return_value=BatchResults(successful=["url1"], failed=["url2"], total=2)
        )

        result = await recovery_manager.recover_batch(
            1, recovery_strategy="retry_failed", processor=mock_processor
        )

        assert result.total == 2
        assert len(result.successful) == 1
        assert len(result.failed) == 1

        # Verify job statuses were reset
        for job in failed_jobs:
            assert job.status == JobStatus.PENDING
            assert job.error_message is None
            assert job.retry_count == 1

    @pytest.mark.asyncio
    async def test_recover_batch_without_processor(
        self, recovery_manager, sample_batch, sample_jobs
    ):
        """Test batch recovery without processor (plan only)."""
        mock_session = (
            recovery_manager.database_service.get_session.return_value.__enter__.return_value
        )
        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch

        pending_jobs = [job for job in sample_jobs if job.status == JobStatus.PENDING]
        recovery_manager._get_jobs_for_recovery = Mock(return_value=pending_jobs)

        result = await recovery_manager.recover_batch(1, "resume_pending")

        # Should return info about what would be recovered
        assert result.total == 1  # 1 pending job
        assert len(result.successful) == 0  # Not actually processed
        assert len(result.failed) == 0

    def test_create_recovery_plan(self, recovery_manager):
        """Test creating detailed recovery plan."""
        # Mock analyze_batch_failure
        mock_analysis = {
            "batch_info": {"id": 1, "name": "test_batch"},
            "job_analysis": {
                "status_counts": {"pending": 5, "failed": 3, "completed": 7, "running": 0},
                "completion_rate": 46.7,
            },
            "failure_analysis": {
                "error_patterns": {"timeout": 2},
                "failure_rate": 20.0,
            },
            "recovery_options": {"recommended_strategy": "retry_failed"},
            "checkpoint_available": True,
        }

        recovery_manager.analyze_batch_failure = Mock(return_value=mock_analysis)

        plan = recovery_manager.create_recovery_plan(1)

        # Verify plan structure
        assert "batch_id" in plan
        assert "analysis" in plan
        assert "recovery_steps" in plan
        assert "estimated_total_time" in plan
        assert "success_probability" in plan
        assert "risks" in plan

        # Verify steps
        assert len(plan["recovery_steps"]) == 3
        steps = plan["recovery_steps"]
        assert steps[0]["action"] == "cleanup_state"
        assert steps[1]["action"] == "apply_recovery_strategy"
        assert steps[2]["action"] == "resume_processing"

    def test_determine_recovery_strategy_high_completion(self, recovery_manager):
        """Test strategy determination with high completion rate."""
        batch = Mock(spec=Batch)
        jobs = [Mock(spec=ScrapingJob) for _ in range(10)]

        status_counts = {"completed": 9, "failed": 1, "pending": 0}
        error_patterns = {"timeout": 1}

        strategy = recovery_manager._determine_recovery_strategy(
            batch, jobs, status_counts, error_patterns
        )

        assert strategy["recommended_strategy"] == "retry_failed"
        assert "Completion: 90.0%" in strategy["recommendation_reason"]

    def test_determine_recovery_strategy_high_failure(self, recovery_manager):
        """Test strategy determination with high failure rate."""
        batch = Mock(spec=Batch)
        jobs = [Mock(spec=ScrapingJob) for _ in range(10)]

        status_counts = {"completed": 3, "failed": 6, "pending": 1}
        error_patterns = {"connection_error": 4, "timeout": 2}

        strategy = recovery_manager._determine_recovery_strategy(
            batch, jobs, status_counts, error_patterns
        )

        assert strategy["recommended_strategy"] == "investigate_errors"
        assert "Failure: 60.0%" in strategy["recommendation_reason"]

    def test_determine_recovery_strategy_pending_jobs(self, recovery_manager):
        """Test strategy determination with pending jobs."""
        batch = Mock(spec=Batch)
        jobs = [Mock(spec=ScrapingJob) for _ in range(10)]

        status_counts = {"completed": 5, "failed": 2, "pending": 3}
        error_patterns = {"timeout": 2}

        strategy = recovery_manager._determine_recovery_strategy(
            batch, jobs, status_counts, error_patterns
        )

        assert strategy["recommended_strategy"] == "resume_pending"

    def test_get_jobs_for_recovery_resume_pending(self, recovery_manager):
        """Test getting jobs for resume_pending strategy."""
        mock_session = Mock()

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = ["pending_job"]
        mock_session.query.return_value.filter.return_value = mock_query

        jobs = recovery_manager._get_jobs_for_recovery(mock_session, 1, "resume_pending")

        assert jobs == ["pending_job"]

    def test_get_jobs_for_recovery_retry_failed(self, recovery_manager):
        """Test getting jobs for retry_failed strategy."""
        mock_session = Mock()

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = ["failed_job"]
        mock_session.query.return_value.filter.return_value = mock_query

        jobs = recovery_manager._get_jobs_for_recovery(mock_session, 1, "retry_failed")

        assert jobs == ["failed_job"]

    def test_get_jobs_for_recovery_full_retry(self, recovery_manager):
        """Test getting jobs for full_retry strategy."""
        mock_session = Mock()

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = ["pending_job", "failed_job"]
        mock_session.query.return_value.filter.return_value = mock_query

        jobs = recovery_manager._get_jobs_for_recovery(mock_session, 1, "full_retry")

        assert jobs == ["pending_job", "failed_job"]

    def test_estimate_success_probability(self, recovery_manager):
        """Test success probability estimation."""
        # High completion, low failure
        analysis = {
            "job_analysis": {"completion_rate": 85.0},
            "failure_analysis": {"failure_rate": 5.0},
        }

        prob = recovery_manager._estimate_success_probability(analysis)
        assert 0.8 <= prob <= 1.0  # Should be high probability

        # Low completion, high failure
        analysis = {
            "job_analysis": {"completion_rate": 15.0},
            "failure_analysis": {"failure_rate": 60.0},
        }

        prob = recovery_manager._estimate_success_probability(analysis)
        assert 0.1 <= prob <= 0.5  # Should be lower probability

    def test_identify_recovery_risks(self, recovery_manager):
        """Test recovery risk identification."""
        # High failure rate with timeout errors
        analysis = {
            "failure_analysis": {
                "failure_rate": 35.0,
                "error_patterns": {"timeout": 5, "connection": 3},
            },
            "checkpoint_available": False,
        }

        risks = recovery_manager._identify_recovery_risks(analysis)

        assert "High failure rate may indicate systemic issues" in risks
        assert "Timeout errors may indicate network issues" in risks
        assert "Connection errors may require infrastructure fixes" in risks
        assert "No checkpoint available - limited recovery state" in risks

    def test_identify_recovery_risks_low_risk(self, recovery_manager):
        """Test risk identification for low-risk scenarios."""
        analysis = {
            "failure_analysis": {"failure_rate": 5.0, "error_patterns": {}},
            "checkpoint_available": True,
        }

        risks = recovery_manager._identify_recovery_risks(analysis)
        assert "Low risk recovery operation" in risks


@pytest.mark.integration
def test_recovery_integration(mock_database_service, tmp_path):
    """Integration test for recovery components."""
    checkpoint_manager = CheckpointManager(
        database_service=mock_database_service, checkpoint_directory=tmp_path / "checkpoints"
    )

    recovery_manager = BatchRecoveryManager(
        database_service=mock_database_service, checkpoint_manager=checkpoint_manager
    )

    # Test checkpoint creation and loading
    batch_id = 123
    state = {"processed": 10, "failed": 2}

    checkpoint_file = checkpoint_manager.create_checkpoint(batch_id, state)
    assert checkpoint_file.exists()

    loaded_state = checkpoint_manager.load_checkpoint(batch_id)
    assert loaded_state["state"] == state

    # Test recovery planning
    mock_session = recovery_manager.database_service.get_session.return_value.__enter__.return_value

    # Mock batch and jobs
    batch = Mock(spec=Batch, id=batch_id, name="integration_test", status=JobStatus.RUNNING)
    jobs = [Mock(spec=ScrapingJob, status=JobStatus.FAILED) for _ in range(3)]

    mock_session.query.return_value.filter.return_value.first.return_value = batch
    mock_session.query.return_value.filter.return_value.all.return_value = jobs

    analysis = recovery_manager.analyze_batch_failure(batch_id)
    assert analysis["checkpoint_available"] is True

    plan = recovery_manager.create_recovery_plan(batch_id)
    assert plan["batch_id"] == batch_id
    assert len(plan["recovery_steps"]) == 3
