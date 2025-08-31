"""Comprehensive monitoring and reporting system for batch processing operations."""

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import structlog
from sqlalchemy import case, func

from src.batch.enhanced_processor import BatchResults
from src.database.models import Batch, JobStatus, ScrapingJob, SystemMetrics
from src.database.service import DatabaseService

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Collects and aggregates batch processing metrics."""

    def __init__(self, database_service: DatabaseService):
        """Initialize metrics collector.

        Args:
            database_service: Database service for persistence
        """
        self.database_service = database_service
        self.start_time = datetime.now(timezone.utc)

        # Runtime metrics
        self.urls_processed = 0
        self.urls_failed = 0
        self.bytes_processed = 0
        self.processing_times: list[float] = []

        logger.info("Initialized metrics collector")

    def record_processing_result(
        self,
        url: str,
        duration: float,
        success: bool,
        bytes_processed: Optional[int] = None,
        error_type: Optional[str] = None,
    ):
        """Record the result of processing a single URL.

        Args:
            url: URL that was processed
            duration: Processing duration in seconds
            success: Whether processing succeeded
            bytes_processed: Number of bytes processed
            error_type: Type of error if failed
        """
        self.processing_times.append(duration)

        if success:
            self.urls_processed += 1
            if bytes_processed:
                self.bytes_processed += bytes_processed
        else:
            self.urls_failed += 1

            # Record error metrics
            self._record_system_metric(
                metric_type="error",
                metric_name="processing_error",
                string_value=error_type or "unknown",
                component="batch_processor",
            )

        # Record performance metrics
        self._record_system_metric(
            metric_type="performance",
            metric_name="processing_duration",
            numeric_value=duration,
            component="batch_processor",
        )

    def record_batch_metrics(self, batch_results: BatchResults):
        """Record metrics for a completed batch.

        Args:
            batch_results: Results from batch processing
        """
        success_rate = (
            len(batch_results.successful) / batch_results.total * 100
            if batch_results.total > 0
            else 0
        )

        # Record batch-level metrics
        metrics_data = {
            "total_urls": batch_results.total,
            "successful_urls": len(batch_results.successful),
            "failed_urls": len(batch_results.failed),
            "success_rate_percent": success_rate,
            "duration_seconds": batch_results.duration,
            "urls_per_second": (
                batch_results.total / batch_results.duration
                if batch_results.duration and batch_results.duration > 0
                else 0
            ),
        }

        self._record_system_metric(
            metric_type="batch",
            metric_name="batch_completion",
            json_value=metrics_data,
            component="batch_processor",
        )

        logger.info("Recorded batch metrics", **metrics_data)

    def get_current_metrics(self) -> dict[str, Any]:
        """Get current runtime metrics.

        Returns:
            Dictionary with current metrics
        """
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        metrics = {
            "uptime_seconds": uptime,
            "urls_processed": self.urls_processed,
            "urls_failed": self.urls_failed,
            "total_urls": self.urls_processed + self.urls_failed,
            "success_rate_percent": (
                (self.urls_processed / (self.urls_processed + self.urls_failed) * 100)
                if (self.urls_processed + self.urls_failed) > 0
                else 0
            ),
            "bytes_processed": self.bytes_processed,
            "throughput": {
                "urls_per_second": self.urls_processed / uptime if uptime > 0 else 0,
                "bytes_per_second": self.bytes_processed / uptime if uptime > 0 else 0,
            },
        }

        # Add timing statistics if we have processing times
        if self.processing_times:
            metrics["processing_times"] = {
                "average_seconds": statistics.mean(self.processing_times),
                "median_seconds": statistics.median(self.processing_times),
                "min_seconds": min(self.processing_times),
                "max_seconds": max(self.processing_times),
                "std_dev_seconds": (
                    statistics.stdev(self.processing_times) if len(self.processing_times) > 1 else 0
                ),
            }

        return metrics

    def _record_system_metric(
        self,
        metric_type: str,
        metric_name: str,
        numeric_value: Optional[float] = None,
        string_value: Optional[str] = None,
        json_value: Optional[dict[str, Any]] = None,
        component: str = "batch_processing",
    ):
        """Record a system metric in the database.

        Args:
            metric_type: Type of metric (performance, error, batch, etc.)
            metric_name: Name of the metric
            numeric_value: Numeric value if applicable
            string_value: String value if applicable
            json_value: JSON value if applicable
            component: Component name
        """
        try:
            with self.database_service.get_session() as session:
                metric = SystemMetrics(
                    timestamp=datetime.now(timezone.utc),
                    metric_type=metric_type,
                    metric_name=metric_name,
                    numeric_value=numeric_value,
                    string_value=string_value,
                    json_value=json_value,
                    component=component,
                )
                session.add(metric)
                session.commit()
        except Exception as e:
            logger.error("Failed to record system metric", error=str(e))


class BatchMonitor:
    """Monitors batch processing operations and provides real-time status."""

    def __init__(self, database_service: DatabaseService):
        """Initialize batch monitor.

        Args:
            database_service: Database service for data access
        """
        self.database_service = database_service
        self.metrics_collector = MetricsCollector(database_service)

        logger.info("Initialized batch monitor")

    def get_active_batches(self) -> list[dict[str, Any]]:
        """Get information about currently active batches.

        Returns:
            List of active batch information
        """
        with self.database_service.get_session() as session:
            active_batches = (
                session.query(Batch)
                .filter(Batch.status.in_([JobStatus.PENDING, JobStatus.RUNNING]))
                .all()
            )

            batch_info = []
            for batch in active_batches:
                # Get job statistics for this batch
                job_stats = (
                    session.query(
                        func.count(ScrapingJob.id).label("total"),
                        func.sum(
                            case((ScrapingJob.status == JobStatus.COMPLETED, 1), else_=0)
                        ).label("completed"),
                        func.sum(case((ScrapingJob.status == JobStatus.RUNNING, 1), else_=0)).label(
                            "running"
                        ),
                        func.sum(case((ScrapingJob.status == JobStatus.FAILED, 1), else_=0)).label(
                            "failed"
                        ),
                    )
                    .filter(ScrapingJob.batch_id == batch.id)
                    .first()
                )

                batch_info.append(
                    {
                        "id": batch.id,
                        "name": batch.name,
                        "status": batch.status.value,
                        "created_at": batch.created_at.isoformat(),
                        "started_at": batch.started_at.isoformat() if batch.started_at else None,
                        "total_jobs": job_stats.total or 0,
                        "completed_jobs": job_stats.completed or 0,
                        "running_jobs": job_stats.running or 0,
                        "failed_jobs": job_stats.failed or 0,
                        "progress_percent": (
                            (job_stats.completed or 0) / (job_stats.total or 1) * 100
                            if job_stats.total
                            else 0
                        ),
                        "max_concurrent": batch.max_concurrent,
                        "output_directory": batch.output_base_directory,
                    }
                )

            return batch_info

    def get_batch_details(self, batch_id: int) -> Optional[dict[str, Any]]:
        """Get detailed information about a specific batch.

        Args:
            batch_id: ID of the batch to get details for

        Returns:
            Detailed batch information or None if not found
        """
        with self.database_service.get_session() as session:
            batch = session.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                return None

            # Get all jobs for this batch
            jobs = session.query(ScrapingJob).filter(ScrapingJob.batch_id == batch_id).all()

            # Calculate statistics
            job_stats = {
                "total": len(jobs),
                "pending": len([j for j in jobs if j.status == JobStatus.PENDING]),
                "running": len([j for j in jobs if j.status == JobStatus.RUNNING]),
                "completed": len([j for j in jobs if j.status == JobStatus.COMPLETED]),
                "failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
                "skipped": len([j for j in jobs if j.status == JobStatus.SKIPPED]),
            }

            # Calculate timing statistics
            completed_jobs = [j for j in jobs if j.duration_seconds is not None]
            timing_stats = None
            if completed_jobs:
                durations = [j.duration_seconds for j in completed_jobs]
                timing_stats = {
                    "average_duration": statistics.mean(durations),
                    "median_duration": statistics.median(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                    "total_processing_time": sum(durations),
                }

            # Recent job activity
            recent_jobs = sorted(
                [j for j in jobs if j.completed_at], key=lambda x: x.completed_at, reverse=True
            )[:10]

            recent_activity = [
                {
                    "url": job.url,
                    "status": job.status.value,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "duration": job.duration_seconds,
                    "error": job.error_message,
                }
                for job in recent_jobs
            ]

            return {
                "batch": {
                    "id": batch.id,
                    "name": batch.name,
                    "description": batch.description,
                    "status": batch.status.value,
                    "created_at": batch.created_at.isoformat(),
                    "started_at": batch.started_at.isoformat() if batch.started_at else None,
                    "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
                    "max_concurrent": batch.max_concurrent,
                    "output_directory": batch.output_base_directory,
                },
                "job_statistics": job_stats,
                "timing_statistics": timing_stats,
                "recent_activity": recent_activity,
            }

    def get_system_health(self) -> dict[str, Any]:
        """Get overall system health metrics.

        Returns:
            System health information
        """
        with self.database_service.get_session() as session:
            # Get counts by status
            job_counts = (
                session.query(ScrapingJob.status, func.count(ScrapingJob.id))
                .group_by(ScrapingJob.status)
                .all()
            )

            status_counts = {status.value: 0 for status in JobStatus}
            for status, count in job_counts:
                status_counts[status.value] = count

            # Get recent error rate (last hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_jobs = (
                session.query(ScrapingJob).filter(ScrapingJob.created_at >= one_hour_ago).all()
            )

            recent_error_rate = 0.0
            if recent_jobs:
                failed_recent = len([j for j in recent_jobs if j.status == JobStatus.FAILED])
                recent_error_rate = failed_recent / len(recent_jobs) * 100

            # Database connection pool status
            engine_stats = {
                "pool_size": self.database_service.engine.pool.size(),
                "checked_in": self.database_service.engine.pool.checkedin(),
                "checked_out": self.database_service.engine.pool.checkedout(),
                "overflow": self.database_service.engine.pool.overflow(),
                "invalid": self.database_service.engine.pool.invalid(),
            }

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_status_counts": status_counts,
                "total_jobs": sum(status_counts.values()),
                "recent_error_rate_percent": recent_error_rate,
                "database": {
                    "connection_pool": engine_stats,
                    "healthy": self._check_database_health_sync(),
                },
                "runtime_metrics": self.metrics_collector.get_current_metrics(),
            }

    def _check_database_health_sync(self) -> bool:
        """Check if database connection is healthy (synchronous version).

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with self.database_service.get_session() as session:
                # Try a simple query
                from sqlalchemy import text

                result = session.execute(text("SELECT 1"))
                return result is not None
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False

    async def _check_database_health(self) -> bool:
        """Check if database connection is healthy (async version).

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with self.database_service.get_session() as session:
                # Try a simple query
                from sqlalchemy import text

                result = session.execute(text("SELECT 1"))
                return result is not None
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False

    async def generate_report(
        self, start_date: datetime, end_date: datetime, output_file: Optional[Path] = None
    ) -> dict[str, Any]:
        """Generate a comprehensive batch processing report.

        Args:
            start_date: Start date for the report
            end_date: End date for the report
            output_file: Optional file to save the report to

        Returns:
            Report data as dictionary
        """
        with self.database_service.get_session() as session:
            # Get batches in date range
            batches = (
                session.query(Batch)
                .filter(Batch.created_at >= start_date, Batch.created_at <= end_date)
                .all()
            )

            # Get jobs in date range
            jobs = (
                session.query(ScrapingJob)
                .filter(ScrapingJob.created_at >= start_date, ScrapingJob.created_at <= end_date)
                .all()
            )

            # Calculate summary statistics
            total_jobs = len(jobs)
            successful_jobs = len([j for j in jobs if j.status == JobStatus.COMPLETED])
            failed_jobs = len([j for j in jobs if j.status == JobStatus.FAILED])

            # Processing time statistics
            completed_with_duration = [j for j in jobs if j.duration_seconds is not None]
            duration_stats = None
            if completed_with_duration:
                durations = [j.duration_seconds for j in completed_with_duration]
                duration_stats = {
                    "average": statistics.mean(durations),
                    "median": statistics.median(durations),
                    "min": min(durations),
                    "max": max(durations),
                    "total": sum(durations),
                }

            # Top domains by processing count
            domain_counts: dict[str, int] = {}
            for job in jobs:
                domain = job.domain
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

            top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            # Error analysis
            error_types: dict[str, int] = {}
            for job in jobs:
                if job.status == JobStatus.FAILED and job.error_type:
                    error_types[job.error_type] = error_types.get(job.error_type, 0) + 1

            # Build report
            report = {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "duration_days": (end_date - start_date).days,
                },
                "summary": {
                    "total_batches": len(batches),
                    "total_jobs": total_jobs,
                    "successful_jobs": successful_jobs,
                    "failed_jobs": failed_jobs,
                    "success_rate_percent": (
                        successful_jobs / total_jobs * 100 if total_jobs > 0 else 0
                    ),
                },
                "processing_statistics": {
                    "duration_statistics": duration_stats,
                    "total_processing_time_hours": (
                        duration_stats["total"] / 3600 if duration_stats else 0
                    ),
                },
                "top_domains": top_domains,
                "error_analysis": {
                    "error_types": error_types,
                    "most_common_error": (
                        max(error_types.items(), key=lambda x: x[1]) if error_types else None
                    ),
                },
                "batch_details": [
                    {
                        "name": batch.name,
                        "status": batch.status.value,
                        "created_at": batch.created_at.isoformat(),
                        "total_jobs": batch.total_jobs,
                        "completed_jobs": batch.completed_jobs,
                        "failed_jobs": batch.failed_jobs,
                        "success_rate": batch.success_rate,
                    }
                    for batch in batches
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            # Save report to file if requested
            if output_file:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w") as f:
                    json.dump(report, f, indent=2)

                logger.info("Generated batch processing report", file=str(output_file))

            return report


class AlertManager:
    """Manages alerts and notifications for batch processing issues."""

    def __init__(self, database_service: DatabaseService):
        """Initialize alert manager.

        Args:
            database_service: Database service for data access
        """
        self.database_service = database_service
        self.alert_thresholds = {
            "error_rate_percent": 10.0,  # Alert if error rate > 10%
            "queue_size": 1000,  # Alert if queue > 1000 items
            "processing_delay_minutes": 30,  # Alert if jobs delayed > 30 min
            "disk_usage_percent": 85.0,  # Alert if disk > 85% full
            "memory_usage_percent": 90.0,  # Alert if memory > 90% full
        }

        logger.info("Initialized alert manager", thresholds=self.alert_thresholds)

    async def check_error_rate_alert(self) -> Optional[dict[str, Any]]:
        """Check for high error rate and return alert if needed.

        Returns:
            Alert dictionary if threshold exceeded, None otherwise
        """
        with self.database_service.get_session() as session:
            # Check error rate in last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

            recent_jobs = (
                session.query(ScrapingJob).filter(ScrapingJob.created_at >= one_hour_ago).all()
            )

            if not recent_jobs:
                return None

            failed_count = len([j for j in recent_jobs if j.status == JobStatus.FAILED])
            error_rate = failed_count / len(recent_jobs) * 100

            if error_rate > self.alert_thresholds["error_rate_percent"]:
                return {
                    "type": "high_error_rate",
                    "severity": "warning" if error_rate < 25 else "critical",
                    "message": f"Error rate is {error_rate:.1f}% (threshold: {self.alert_thresholds['error_rate_percent']}%)",
                    "details": {
                        "error_rate_percent": error_rate,
                        "failed_jobs": failed_count,
                        "total_jobs": len(recent_jobs),
                        "time_period": "last_hour",
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return None

    async def check_stalled_jobs_alert(self) -> Optional[dict[str, Any]]:
        """Check for jobs that have been running too long.

        Returns:
            Alert dictionary if stalled jobs found, None otherwise
        """
        with self.database_service.get_session() as session:
            threshold_time = datetime.now(timezone.utc) - timedelta(
                minutes=self.alert_thresholds["processing_delay_minutes"]
            )

            stalled_jobs = (
                session.query(ScrapingJob)
                .filter(
                    ScrapingJob.status == JobStatus.RUNNING, ScrapingJob.started_at < threshold_time
                )
                .all()
            )

            if stalled_jobs:
                return {
                    "type": "stalled_jobs",
                    "severity": "warning",
                    "message": f"Found {len(stalled_jobs)} jobs running longer than {self.alert_thresholds['processing_delay_minutes']} minutes",
                    "details": {
                        "stalled_count": len(stalled_jobs),
                        "threshold_minutes": self.alert_thresholds["processing_delay_minutes"],
                        "oldest_job_url": stalled_jobs[0].url if stalled_jobs else None,
                        "oldest_started_at": (
                            stalled_jobs[0].started_at.isoformat()
                            if stalled_jobs and stalled_jobs[0].started_at
                            else None
                        ),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return None

    async def get_all_alerts(self) -> list[dict[str, Any]]:
        """Get all current alerts.

        Returns:
            List of active alerts
        """
        alerts = []

        # Check all alert types
        alert_checks = [self.check_error_rate_alert(), self.check_stalled_jobs_alert()]

        for check in alert_checks:
            result = await check
            if result:
                alerts.append(result)

        return alerts
