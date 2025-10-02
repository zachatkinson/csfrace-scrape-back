"""Statistics and analytics service following Single Responsibility Principle.

This module handles all statistics-related database operations including:
- Job performance metrics
- Success/failure rates
- Processing time analytics
- Domain-specific statistics
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import DatabaseLoggingMixin, get_database_logger

from ...common.status import JobStatus
from ..models import ScrapingJob

logger = get_database_logger()


class StatisticsService(DatabaseLoggingMixin):
    """Service for job statistics and analytics."""

    def __init__(self, session: Session):
        """Initialize with provided database session.

        Args:
            session: SQLAlchemy session to use for database operations
        """
        self.session = session

    @database_error_handler("calculate statistics")
    def get_job_statistics(self, days: int = 7) -> dict[str, Any]:
        """Get comprehensive job statistics for a time period.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dictionary with various statistics including:
            - Total jobs and status breakdown
            - Success/failure rates
            - Average processing times
            - Top domains
            - Hourly distribution
        """
        logger.info("Calculating job statistics", days=days)

        # Calculate date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        # Base query for the time period
        base_query = self.session.query(ScrapingJob).filter(ScrapingJob.created_at >= start_date)

        # Total jobs
        total_jobs = base_query.count()

        # Status breakdown
        status_counts = {}
        for status in JobStatus:
            count = base_query.filter(ScrapingJob.status == status.value).count()
            status_counts[status.name] = count

        # Success rate calculation
        completed = status_counts.get("COMPLETED", 0)
        # Calculate success rate based on total jobs (not just finished ones)
        success_rate = (completed / total_jobs * 100) if total_jobs > 0 else 0

        # Average processing time for completed jobs
        avg_time_result = (
            self.session.query(func.avg(ScrapingJob.processing_time_ms))
            .filter(
                and_(
                    ScrapingJob.created_at >= start_date,
                    ScrapingJob.status == JobStatus.COMPLETED.value,
                    ScrapingJob.processing_time_ms.isnot(None),
                )
            )
            .scalar()
        )

        avg_processing_time_ms = float(avg_time_result) if avg_time_result else 0

        # Top domains by job count
        domain_stats = (
            self.session.query(ScrapingJob.domain, func.count(ScrapingJob.id).label("count"))
            .filter(ScrapingJob.created_at >= start_date)
            .group_by(ScrapingJob.domain)
            .order_by(func.count(ScrapingJob.id).desc())
            .limit(10)
            .all()
        )

        top_domains = [{"domain": domain, "count": count} for domain, count in domain_stats]

        # Hourly distribution
        hourly_distribution = self._calculate_hourly_distribution(
            self.session, start_date, end_date
        )

        # Retry statistics
        retry_stats = self._calculate_retry_statistics(self.session, start_date)

        # Calculate content and download sizes
        size_stats = self._calculate_size_statistics(self.session, start_date)

        statistics = {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_jobs": total_jobs,
            "status_breakdown": status_counts,
            "success_rate": round(success_rate, 2),
            "average_processing_time_ms": round(avg_processing_time_ms, 2),
            "total_content_size_bytes": size_stats.get("total_output_size", 0),
            "total_download_size_bytes": size_stats.get("total_download_size", 0),
            "top_domains": top_domains,
            "hourly_distribution": hourly_distribution,
            "retry_statistics": retry_stats,
        }

        self.logger.info(
            "Job statistics calculated",
            days=days,
            total_jobs=total_jobs,
            success_rate=success_rate,
        )

        return statistics

    def _calculate_hourly_distribution(
        self, session: Any, start_date: datetime, end_date: datetime
    ) -> dict[str, int]:
        """Calculate job distribution by hour of day.

        Args:
            session: Database session
            start_date: Start of period
            end_date: End of period

        Returns:
            Dictionary with hourly job counts
        """
        self.logger.debug("Calculating hourly distribution")

        # Use database-specific hour extraction
        from sqlalchemy import extract

        hourly_stats = (
            session.query(
                extract("hour", ScrapingJob.created_at).label("hour"),
                func.count(ScrapingJob.id).label("count"),
            )
            .filter(and_(ScrapingJob.created_at >= start_date, ScrapingJob.created_at <= end_date))
            .group_by("hour")
            .all()
        )

        # Create full 24-hour distribution
        distribution = {str(h).zfill(2): 0 for h in range(24)}
        for hour, count in hourly_stats:
            if hour is not None:
                distribution[str(int(hour)).zfill(2)] = count

        self.logger.debug("Hourly distribution calculated", total_hours=len(distribution))
        return distribution

    def _calculate_retry_statistics(self, session: Any, start_date: datetime) -> dict[str, Any]:
        """Calculate retry-related statistics.

        Args:
            session: Database session
            start_date: Start of analysis period

        Returns:
            Dictionary with retry statistics
        """
        self.logger.debug("Calculating retry statistics")

        # Jobs with retries
        jobs_with_retries = (
            session.query(func.count(ScrapingJob.id))
            .filter(and_(ScrapingJob.created_at >= start_date, ScrapingJob.retry_count > 0))
            .scalar()
            or 0
        )

        # Average retry count
        avg_retries_result = (
            session.query(func.avg(ScrapingJob.retry_count))
            .filter(and_(ScrapingJob.created_at >= start_date, ScrapingJob.retry_count > 0))
            .scalar()
        )

        avg_retries = float(avg_retries_result) if avg_retries_result else 0

        # Max retries used
        max_retries_result = (
            session.query(func.max(ScrapingJob.retry_count))
            .filter(ScrapingJob.created_at >= start_date)
            .scalar()
        )

        max_retries = int(max_retries_result) if max_retries_result else 0

        retry_stats = {
            "jobs_with_retries": jobs_with_retries,
            "average_retry_count": round(avg_retries, 2),
            "max_retry_count": max_retries,
        }

        self.logger.debug("Retry statistics calculated", stats=retry_stats)
        return retry_stats

    @database_error_handler("calculate performance metrics")
    def get_performance_metrics(self, domain: str | None = None, days: int = 30) -> dict[str, Any]:
        """Get performance metrics for optimization.

        Args:
            domain: Optional domain to filter by
            days: Number of days to analyze

        Returns:
            Dictionary with performance metrics
        """
        self.logger.info("Calculating performance metrics", domain=domain, days=days)

        # Calculate date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        # Base query
        query = self.session.query(ScrapingJob).filter(
            and_(
                ScrapingJob.created_at >= start_date,
                ScrapingJob.status == JobStatus.COMPLETED.value,
                ScrapingJob.processing_time_ms.isnot(None),
            )
        )

        if domain:
            query = query.filter(ScrapingJob.domain == domain)

        # Performance statistics
        perf_stats = self.session.query(
            func.min(ScrapingJob.processing_time_ms).label("min_time"),
            func.max(ScrapingJob.processing_time_ms).label("max_time"),
            func.avg(ScrapingJob.processing_time_ms).label("avg_time"),
            func.stddev(ScrapingJob.processing_time_ms).label("stddev_time"),
            func.count(ScrapingJob.id).label("sample_size"),
        ).filter(
            and_(
                ScrapingJob.created_at >= start_date,
                ScrapingJob.status == JobStatus.COMPLETED.value,
                ScrapingJob.processing_time_ms.isnot(None),
            )
        )

        if domain:
            perf_stats = perf_stats.filter(ScrapingJob.domain == domain)

        result = perf_stats.first()

        metrics = {
            "domain": domain or "all",
            "period_days": days,
            "min_processing_time_ms": float(result.min_time) if result.min_time else 0,
            "max_processing_time_ms": float(result.max_time) if result.max_time else 0,
            "avg_processing_time_ms": float(result.avg_time) if result.avg_time else 0,
            "stddev_processing_time_ms": float(result.stddev_time) if result.stddev_time else 0,
            "sample_size": int(result.sample_size or 0),
        }

        # Calculate percentiles if we have enough data
        sample_size = metrics["sample_size"]
        assert isinstance(sample_size, int), f"Expected int, got {type(sample_size)}"
        if sample_size >= 10:
            percentiles = self._calculate_percentiles(self.session, start_date, domain)
            metrics["percentiles"] = percentiles

        self.logger.info(
            "Performance metrics calculated",
            domain=domain or "all",
            sample_size=sample_size,
        )

        return metrics

    def _calculate_percentiles(
        self, session: Any, start_date: datetime, domain: str | None = None
    ) -> dict[str, float]:
        """Calculate processing time percentiles.

        Args:
            session: Database session
            start_date: Start of analysis period
            domain: Optional domain filter

        Returns:
            Dictionary with percentile values (p50, p75, p90, p95, p99)
        """
        self.logger.debug("Calculating percentiles", domain=domain)

        # Get all processing times for percentile calculation
        query = self.session.query(ScrapingJob.processing_time_ms).filter(
            and_(
                ScrapingJob.created_at >= start_date,
                ScrapingJob.status == JobStatus.COMPLETED.value,
                ScrapingJob.processing_time_ms.isnot(None),
            )
        )

        if domain:
            query = query.filter(ScrapingJob.domain == domain)

        times = [t[0] for t in query.all()]

        if not times:
            return {}

        # Calculate percentiles
        times_sorted = sorted(times)

        def percentile(data: list[float], p: int) -> float:
            n = len(data)
            i = int(n * p / 100)
            return data[min(i, n - 1)]

        percentiles = {
            "p50": percentile(times_sorted, 50),
            "p75": percentile(times_sorted, 75),
            "p90": percentile(times_sorted, 90),
            "p95": percentile(times_sorted, 95),
            "p99": percentile(times_sorted, 99),
        }

        self.logger.debug("Percentiles calculated", percentiles=percentiles)
        return percentiles

    def _calculate_size_statistics(self, session: Any, start_date: datetime) -> dict[str, int]:
        """Calculate size-related statistics.

        Args:
            session: Database session
            start_date: Start of analysis period

        Returns:
            Dictionary with size statistics
        """
        self.logger.debug("Calculating size statistics")

        # Calculate total sizes from job records
        size_stats_result = (
            self.session.query(
                func.sum(ScrapingJob.output_size_bytes).label("total_output"),
                func.sum(ScrapingJob.download_size_bytes).label("total_download"),
            )
            .filter(
                and_(
                    ScrapingJob.created_at >= start_date,
                    ScrapingJob.status == JobStatus.COMPLETED.value,
                )
            )
            .first()
        )

        total_output_size = int(size_stats_result.total_output or 0) if size_stats_result else 0
        total_download_size = int(size_stats_result.total_download or 0) if size_stats_result else 0

        size_stats = {
            "total_output_size": total_output_size,
            "total_download_size": total_download_size,
        }

        self.logger.debug("Size statistics calculated", stats=size_stats)
        return size_stats
