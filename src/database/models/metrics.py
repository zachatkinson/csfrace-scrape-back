"""System metrics and monitoring database models.

This module contains models for system-wide metrics, performance data,
and monitoring information. Follows Single Responsibility Principle by
focusing only on metrics domain.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.core.logging_hierarchy import get_database_logger

from .base import Base

logger = get_database_logger()


class SystemMetrics(Base):
    """Model for system-wide metrics and performance data.

    Stores aggregated metrics for monitoring system health,
    performance trends, and capacity planning.
    """

    __tablename__ = "system_metrics"

    # Primary identification
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Metric values
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    numeric_value: Mapped[float | None] = mapped_column()
    string_value: Mapped[str | None] = mapped_column(String(500))
    json_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Categorization
    component: Mapped[str | None] = mapped_column(String(100), index=True)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)

    # Tags for flexible querying (JSON array)
    tags: Mapped[dict[str, str] | None] = mapped_column(JSON)

    def __repr__(self) -> str:
        """String representation of the metrics entry."""
        return (
            f"<SystemMetrics(id={self.id}, type='{self.metric_type}', name='{self.metric_name}')>"
        )
