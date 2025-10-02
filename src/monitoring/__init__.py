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

from typing import Any


def _safe_import(module_path: str, *names: str) -> dict[str, Any]:
    """Centralized safe import handler to eliminate try/except duplication.

    Args:
        module_path: Module path to import from
        *names: Names to import from the module

    Returns:
        Dictionary mapping names to imported objects or None
    """
    try:
        module = __import__(f"{__name__}.{module_path}", fromlist=list(names))
        return {name: getattr(module, name, None) for name in names}
    except ImportError:
        return dict.fromkeys(names)


# Centralized safe imports using DRY principle
_alerts_imports = _safe_import("alerts", "AlertConfig", "AlertManager", "alert_manager")
AlertConfig = _alerts_imports["AlertConfig"]
AlertManager = _alerts_imports["AlertManager"]
alert_manager = _alerts_imports["alert_manager"]

_dashboard_imports = _safe_import("dashboard_provisioner", "GrafanaDashboardProvisioner")
GrafanaDashboardProvisioner = _dashboard_imports["GrafanaDashboardProvisioner"]

_grafana_imports = _safe_import("grafana", "GrafanaConfig", "GrafanaDashboardManager")
GrafanaConfig = _grafana_imports["GrafanaConfig"]
GrafanaDashboardManager = _grafana_imports["GrafanaDashboardManager"]

_health_imports = _safe_import("health", "HealthChecker", "HealthConfig", "health_checker")
HealthChecker = _health_imports["HealthChecker"]
HealthConfig = _health_imports["HealthConfig"]
health_checker = _health_imports["health_checker"]

_health_checks_imports = _safe_import(
    "health_checks", "HealthCheck", "HealthCheckResult", "HealthStatus", "health_registry"
)
_setup_imports = _safe_import("setup", "get_health_check_summary", "setup_default_health_checks")
HealthCheck = _health_checks_imports["HealthCheck"]
HealthCheckResult = _health_checks_imports["HealthCheckResult"]
HealthStatus = _health_checks_imports["HealthStatus"]
health_registry = _health_checks_imports["health_registry"]
get_health_check_summary = _setup_imports["get_health_check_summary"]
setup_default_health_checks = _setup_imports["setup_default_health_checks"]

_metrics_imports = _safe_import("metrics", "MetricsCollector", "MetricsConfig", "metrics_collector")
MetricsCollector = _metrics_imports["MetricsCollector"]
MetricsConfig = _metrics_imports["MetricsConfig"]
metrics_collector = _metrics_imports["metrics_collector"]

_observability_imports = _safe_import(
    "observability", "ObservabilityConfig", "ObservabilityManager", "observability_manager"
)
ObservabilityConfig = _observability_imports["ObservabilityConfig"]
ObservabilityManager = _observability_imports["ObservabilityManager"]
observability_manager = _observability_imports["observability_manager"]

_performance_imports = _safe_import(
    "performance", "PerformanceConfig", "PerformanceMonitor", "performance_monitor"
)
PerformanceConfig = _performance_imports["PerformanceConfig"]
PerformanceMonitor = _performance_imports["PerformanceMonitor"]
performance_monitor = _performance_imports["performance_monitor"]

_tracing_imports = _safe_import(
    "tracing", "DistributedTracer", "TracingConfig", "distributed_tracer"
)
DistributedTracer = _tracing_imports["DistributedTracer"]
TracingConfig = _tracing_imports["TracingConfig"]
distributed_tracer = _tracing_imports["distributed_tracer"]

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
