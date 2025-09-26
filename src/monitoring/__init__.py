"""Advanced monitoring and observability system for Phase 4F.

This module provides comprehensive monitoring capabilities including:
- System and application metrics collection with Prometheus export
- Health check system with dependency validation
- Performance monitoring with request tracing
- OpenTelemetry distributed tracing for enhanced observability
- Alerting system with configurable thresholds
- Grafana dashboard provisioning and management
- Structured logging with correlation tracking
"""

# Conditional imports to avoid dependency issues

try:
    from .alerts import AlertConfig, AlertManager, alert_manager
except ImportError:
    AlertConfig = AlertManager = alert_manager = None  # type: ignore[misc,assignment]

try:
    from .dashboard_provisioner import GrafanaDashboardProvisioner
except ImportError:
    GrafanaDashboardProvisioner = None  # type: ignore[misc,assignment]

try:
    from .grafana import GrafanaConfig, GrafanaDashboardManager
except ImportError:
    GrafanaConfig = GrafanaDashboardManager = None  # type: ignore[misc,assignment]

try:
    from .health import HealthChecker, HealthConfig, health_checker
except ImportError:
    HealthChecker = HealthConfig = health_checker = None  # type: ignore[misc,assignment]

try:
    from .health_checks import HealthCheck, HealthCheckResult, HealthStatus, health_registry
    from .setup import get_health_check_summary, setup_default_health_checks
except ImportError:
    HealthCheck = HealthCheckResult = HealthStatus = health_registry = None  # type: ignore
    get_health_check_summary = setup_default_health_checks = None  # type: ignore

try:
    from .metrics import MetricsCollector, MetricsConfig, metrics_collector
except ImportError:
    MetricsCollector = MetricsConfig = metrics_collector = None  # type: ignore[misc,assignment]

try:
    from .observability import ObservabilityConfig, ObservabilityManager, observability_manager
except ImportError:
    ObservabilityConfig = ObservabilityManager = observability_manager = None  # type: ignore[misc,assignment]

try:
    from .performance import PerformanceConfig, PerformanceMonitor, performance_monitor
except ImportError:
    PerformanceConfig = PerformanceMonitor = performance_monitor = None  # type: ignore[misc,assignment]

try:
    from .tracing import DistributedTracer, TracingConfig, distributed_tracer
except ImportError:
    DistributedTracer = TracingConfig = distributed_tracer = None  # type: ignore[misc,assignment]

__all__ = [
    "MetricsCollector",
    "MetricsConfig",
    "metrics_collector",
    "HealthChecker",
    "HealthConfig",
    "health_checker",
    "HealthCheck",
    "HealthCheckResult",
    "HealthStatus",
    "health_registry",
    "setup_default_health_checks",
    "get_health_check_summary",
    "AlertManager",
    "AlertConfig",
    "alert_manager",
    "PerformanceMonitor",
    "PerformanceConfig",
    "performance_monitor",
    "ObservabilityManager",
    "ObservabilityConfig",
    "observability_manager",
    "GrafanaDashboardManager",
    "GrafanaDashboardProvisioner",
    "GrafanaConfig",
    "DistributedTracer",
    "TracingConfig",
    "distributed_tracer",
]
