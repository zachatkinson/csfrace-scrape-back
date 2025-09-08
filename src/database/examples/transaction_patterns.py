"""Examples demonstrating improved database transaction patterns.

This shows the before/after patterns for eliminating DRY violations
and improving data integrity across database operations.
"""

import logging
from datetime import datetime

from fastapi import HTTPException

from ..models import Batch, Job, JobStatus
from ..transactions import TransactionError, batch_transaction, database_transaction

logger = logging.getLogger(__name__)

# ===== BEFORE: Repeated transaction pattern (DRY VIOLATION) =====


async def old_create_batch_pattern(db, batch_data):
    """❌ OLD PATTERN: Repeated transaction handling with inconsistent error recovery."""
    try:
        batch = Batch(**batch_data)
        db.add(batch)
        await db.commit()
        return batch
    except Exception:
        # Inconsistent error handling - sometimes rollback, sometimes not
        batch.status = JobStatus.FAILED
        await db.commit()  # Another commit after error
        raise


async def old_update_jobs_pattern(db, batch_id, job_updates):
    """❌ OLD PATTERN: Another variation of the same transaction pattern."""
    try:
        for job_id, update_data in job_updates.items():
            job = await db.get(Job, job_id)
            if job:
                job.status = update_data.status
                job.result = update_data.result

        batch = await db.get(Batch, batch_id)
        batch.updated_at = datetime.now()
        await db.commit()

    except Exception as e:
        # Different error handling pattern
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===== AFTER: Centralized transaction pattern (SOLUTION) =====


async def new_create_batch_pattern(batch_data):
    """✅ NEW PATTERN: Centralized transaction handling with consistent error recovery."""

    async def _create_batch_operation(db):
        batch = Batch(**batch_data)
        db.add(batch)
        return batch

    try:
        # Centralized transaction handling with automatic rollback/commit
        async with database_transaction() as db:
            return await _create_batch_operation(db)
    except TransactionError as e:
        # Consistent error handling across all operations
        logger.error("Batch creation failed", error=str(e.original_error))
        raise HTTPException(status_code=500, detail="Failed to create batch")


async def new_update_jobs_pattern(batch_id, job_updates):
    """✅ NEW PATTERN: Centralized transaction with automatic error handling."""

    async def _update_jobs_operation(db):
        results = []
        for job_id, update_data in job_updates.items():
            job = await db.get(Job, job_id)
            if job:
                job.status = update_data.status
                job.result = update_data.result
                results.append(job)

        # Update batch timestamp
        batch = await db.get(Batch, batch_id)
        if batch:
            batch.updated_at = datetime.now()
            results.append(batch)

        return results

    try:
        async with database_transaction() as db:
            return await _update_jobs_operation(db)
    except TransactionError as e:
        logger.error("Job updates failed", batch_id=batch_id, error=str(e.original_error))
        raise HTTPException(status_code=500, detail="Failed to update jobs")


async def new_batch_processing_pattern(job_data_list):
    """✅ NEW PATTERN: Batch processing with periodic commits for large datasets."""

    async def _process_batch_operation(db):
        processed_jobs = []
        for i, job_data in enumerate(job_data_list):
            job = Job(**job_data)
            db.add(job)
            processed_jobs.append(job)

            # Commit every 100 items for large batches
            if (i + 1) % 100 == 0:
                await db.commit()
                logger.debug(f"Committed batch of {i + 1} jobs")

        return processed_jobs

    try:
        async with batch_transaction(batch_size=100) as db:
            return await _process_batch_operation(db)
    except TransactionError as e:
        logger.error(
            "Batch processing failed", count=len(job_data_list), error=str(e.original_error)
        )
        raise HTTPException(status_code=500, detail="Failed to process batch")


# ===== ADVANCED PATTERNS =====


async def retry_pattern_example(batch_data):
    """✅ ADVANCED: Automatic retry for transient database errors."""
    from ..transactions import transaction_manager

    async def _create_batch_with_retry(db):
        # This operation will be retried automatically on database errors
        batch = Batch(**batch_data)
        db.add(batch)
        return batch

    try:
        return await transaction_manager.execute_with_retry(
            _create_batch_with_retry, max_retries=3, backoff_factor=2.0
        )
    except TransactionError as e:
        logger.error("Batch creation failed after retries", error=str(e.original_error))
        raise HTTPException(status_code=500, detail="Failed to create batch after retries")


async def parallel_operations_example(batch_operations):
    """✅ ADVANCED: Parallel database operations with separate transactions."""
    from ..transactions import transaction_manager

    try:
        results = await transaction_manager.execute_in_parallel(batch_operations, max_concurrent=5)
        return results
    except TransactionError as e:
        logger.error("Parallel operations failed", error=str(e.original_error))
        raise HTTPException(status_code=500, detail="Failed to execute parallel operations")


# ===== BENEFITS OF NEW PATTERN =====

"""
✅ BENEFITS OF CENTRALIZED TRANSACTION PATTERN:

1. **Eliminates DRY Violations**:
   - Single transaction pattern used everywhere
   - No more repeated try/catch/commit/rollback code

2. **Consistent Error Handling**:
   - All database errors handled the same way
   - Proper logging and error context
   - Consistent rollback behavior

3. **Improved Data Integrity**:
   - Automatic transaction boundaries
   - Proper isolation levels when needed
   - Deadlock detection and retry logic

4. **Better Observability**:
   - Transaction timing and logging
   - Error tracking with context
   - Performance monitoring built-in

5. **Reduced Security Risk**:
   - No partial commits on errors
   - Consistent error responses (no data leakage)
   - Proper cleanup on failures

6. **Testing Benefits**:
   - Easy to mock transaction behavior
   - Consistent test patterns
   - Better error simulation

7. **Performance Improvements**:
   - Batch processing for large operations
   - Connection pooling optimization
   - Reduced transaction overhead
"""
