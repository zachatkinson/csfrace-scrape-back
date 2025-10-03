"""Monitoring interface protocols following Interface Segregation Principle.

This module defines focused, segregated interfaces for different monitoring concerns,
following SOLID principles to ensure clean separation of responsibilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol

from src.core.logging_hierarchy import get_monitoring_logger

logger = get_monitoring_logger()


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Available alert notification channels."""

    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class HealthCheckProvider(Protocol):
    """Protocol for health checking functionality following Interface Segregation.

    This protocol defines the interface for health monitoring systems,
    allowing different implementations while maintaining consistency.
    """

    async def check_health(self, check_name: str) -> dict[str, Any]:
        """Perform a specific health check.

        Args:
            check_name: Name of the health check to perform

        Returns:
            Dictionary containing health check results
        """
        ...

    async def get_overall_health(self) -> dict[str, Any]:
        """Get overall system health status.

        Returns:
            Dictionary containing overall health status and summary
        """
        ...

    async def register_check(self, name: str, check_func: Any) -> bool:
        """Register a new health check.

        Args:
            name: Name of the health check
            check_func: Function to perform the health check

        Returns:
            True if registration successful
        """
        ...

    async def unregister_check(self, name: str) -> bool:
        """Unregister a health check.

        Args:
            name: Name of the health check to remove

        Returns:
            True if unregistration successful
        """
        ...

    async def get_check_history(self, check_name: str) -> list[dict[str, Any]]:
        """Get history of a specific health check.

        Args:
            check_name: Name of the health check

        Returns:
            List of historical health check results
        """
        ...


class MetricsProvider(Protocol):
    """Protocol for metrics collection functionality following Interface Segregation.

    This protocol defines the interface for metrics collection systems,
    allowing different implementations (Prometheus, custom, etc.).
    """

    async def record_metric(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> bool:
        """Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels for the metric

        Returns:
            True if recording successful
        """
        ...

    async def increment_counter(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> bool:
        """Increment a counter metric.

        Args:
            name: Counter name
            value: Value to increment by (default 1.0)
            labels: Optional labels for the metric

        Returns:
            True if increment successful
        """
        ...

    async def record_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> bool:
        """Record a histogram value.

        Args:
            name: Histogram name
            value: Value to record
            labels: Optional labels for the metric

        Returns:
            True if recording successful
        """
        ...

    async def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> bool:
        """Set a gauge metric value.

        Args:
            name: Gauge name
            value: Value to set
            labels: Optional labels for the metric

        Returns:
            True if setting successful
        """
        ...

    async def get_metrics(self, format_type: str = "prometheus") -> str:
        """Export metrics in specified format.

        Args:
            format_type: Format for metrics export (e.g., "prometheus", "json")

        Returns:
            Metrics data in requested format
        """
        ...

    async def get_metric_value(
        self, name: str, labels: dict[str, str] | None = None
    ) -> float | None:
        """Get current value of a metric.

        Args:
            name: Metric name
            labels: Optional labels to filter by

        Returns:
            Current metric value or None if not found
        """
        ...


class AlertingProvider(Protocol):
    """Protocol for alerting functionality following Interface Segregation.

    This protocol defines the interface for alerting systems,
    allowing different notification channels and alert management.
    """

    async def create_alert(
        self,
        name: str,
        message: str,
        severity: AlertSeverity,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new alert.

        Args:
            name: Alert name/identifier
            message: Alert message
            severity: Alert severity level
            metadata: Optional additional metadata

        Returns:
            Alert ID
        """
        ...

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert.

        Args:
            alert_id: ID of the alert to resolve

        Returns:
            True if resolution successful
        """
        ...

    async def send_notification(
        self,
        message: str,
        channels: list[AlertChannel],
        severity: AlertSeverity = AlertSeverity.INFO,
    ) -> bool:
        """Send notification through specified channels.

        Args:
            message: Notification message
            channels: List of channels to send notification to
            severity: Severity level of the notification

        Returns:
            True if notification sent successfully
        """
        ...

    async def add_alert_rule(
        self,
        name: str,
        condition: str,
        threshold: float,
        severity: AlertSeverity,
        channels: list[AlertChannel],
    ) -> bool:
        """Add a new alert rule.

        Args:
            name: Rule name
            condition: Condition that triggers the alert
            threshold: Threshold value for the condition
            severity: Alert severity when triggered
            channels: Channels to notify when triggered

        Returns:
            True if rule added successfully
        """
        ...

    async def remove_alert_rule(self, name: str) -> bool:
        """Remove an alert rule.

        Args:
            name: Name of the rule to remove

        Returns:
            True if rule removed successfully
        """
        ...

    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get list of currently active alerts.

        Returns:
            List of active alert dictionaries
        """
        ...


class MonitoringProvider(Protocol):
    """Unified monitoring protocol that combines all monitoring concerns.

    This protocol provides a unified interface for systems that need
    access to all monitoring capabilities in one place.
    """

    @property
    def health(self) -> HealthCheckProvider:
        """Get health checking provider."""
        ...

    @property
    def metrics(self) -> MetricsProvider:
        """Get metrics collection provider."""
        ...

    @property
    def alerts(self) -> AlertingProvider:
        """Get alerting provider."""
        ...

    async def initialize(self) -> bool:
        """Initialize all monitoring subsystems.

        Returns:
            True if initialization successful
        """
        ...

    async def shutdown(self) -> bool:
        """Shutdown all monitoring subsystems.

        Returns:
            True if shutdown successful
        """
        ...


class BaseMonitoringService(ABC):
    """Abstract base class for monitoring service implementations.

    Provides common functionality while allowing concrete implementations
    to focus on their specific monitoring concerns.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize monitoring service.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = get_monitoring_logger()
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the monitoring service.

        Returns:
            True if initialization successful
        """
        pass

    @abstractmethod
    async def shutdown(self) -> bool:
        """Shutdown the monitoring service.

        Returns:
            True if shutdown successful
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized

    def _mark_initialized(self) -> None:
        """Mark service as initialized."""
        self._initialized = True
        self.logger.info(f"{self.__class__.__name__} initialized successfully")

    def _mark_shutdown(self) -> None:
        """Mark service as shutdown."""
        self._initialized = False
        self.logger.info(f"{self.__class__.__name__} shutdown completed")
