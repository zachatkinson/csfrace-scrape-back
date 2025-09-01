"""Central observability manager orchestrating all monitoring components."""

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog

from .alerts import AlertConfig, alert_manager
from .health import HealthConfig, health_checker
from .metrics import MetricsConfig, metrics_collector
from .performance import PerformanceConfig, performance_monitor

logger = structlog.get_logger(__name__)


@dataclass
class ObservabilityConfig:
    """Central configuration for all observability components."""

    enabled: bool = True

    # Component configurations
    metrics_config: MetricsConfig | None = None
    health_config: HealthConfig | None = None
    alerts_config: AlertConfig | None = None
    performance_config: PerformanceConfig | None = None

    # Global settings
    startup_health_check: bool = True
    graceful_shutdown_timeout: float = 30.0

    # Correlation settings
    enable_correlation_ids: bool = True
    correlation_header_name: str = "X-Correlation-ID"


class ObservabilityManager:
    """Central manager for all observability components."""

    def __init__(self, config: ObservabilityConfig | None = None):
        """Initialize observability manager.

        Args:
            config: Observability configuration
        """
        self.config = config or ObservabilityConfig()

        # Initialize components with their respective configs
        self.metrics_collector = metrics_collector
        if self.config.metrics_config:
            self.metrics_collector.config = self.config.metrics_config

        self.health_checker = health_checker
        if self.config.health_config:
            self.health_checker.config = self.config.health_config

        self.alert_manager = alert_manager
        if self.config.alerts_config:
            self.alert_manager.config = self.config.alerts_config

        self.performance_monitor = performance_monitor
        if self.config.performance_config:
            self.performance_monitor.config = self.config.performance_config

        self._initialized = False
        self._shutdown_event = asyncio.Event()

        logger.info("Observability manager initialized", enabled=self.config.enabled)

    async def initialize(self) -> None:
        """Initialize all observability components."""
        if not self.config.enabled or self._initialized:
            return

        logger.info("Initializing observability system")

        try:
            # Initialize components in order
            if self.metrics_collector.config.enabled:
                await self.metrics_collector.start_collection()
                logger.debug("Metrics collector started")

            if self.health_checker.config.enabled:
                await self.health_checker.start_monitoring()
                logger.debug("Health checker started")

            if self.alert_manager.config.enabled:
                await self.alert_manager.start_evaluation()
                logger.debug("Alert manager started")

            # Performance monitor doesn't need explicit initialization
            logger.debug("Performance monitor ready")

            # Run startup health check if enabled
            if self.config.startup_health_check:
                await self._run_startup_health_check()

            self._initialized = True
            logger.info("Observability system initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize observability system", error=str(e))
            # Attempt cleanup on failure
            await self.shutdown()
            raise

    async def _run_startup_health_check(self) -> None:
        """Run comprehensive health check on startup."""
        logger.info("Running startup health check")

        try:
            # Run all health checks
            results = await self.health_checker.run_all_checks()

            # Analyze results
            overall_status = self.health_checker.get_overall_status()

            if overall_status.value == "healthy":
                logger.info("Startup health check passed", checks_passed=len(results))
            elif overall_status.value == "degraded":
                logger.warning(
                    "Startup health check shows degraded status",
                    status=overall_status.value,
                    total_checks=len(results),
                )
            else:
                logger.error(
                    "Startup health check failed",
                    status=overall_status.value,
                    total_checks=len(results),
                )

                # Log individual failures
                for name, result in results.items():
                    if result.status.value in ["unhealthy", "unknown"]:
                        logger.error(
                            "Health check failed",
                            check=name,
                            status=result.status.value,
                            message=result.message,
                        )

        except Exception as e:
            logger.error("Startup health check failed", error=str(e))

    async def shutdown(self) -> None:
        """Gracefully shutdown all observability components."""
        if not self._initialized:
            return

        logger.info("Shutting down observability system")

        # Set shutdown event
        self._shutdown_event.set()

        try:
            # Shutdown components in reverse order with timeout
            shutdown_tasks = []

            if self.alert_manager.config.enabled:
                shutdown_tasks.append(self.alert_manager.shutdown())

            if self.health_checker.config.enabled:
                shutdown_tasks.append(self.health_checker.shutdown())

            if self.metrics_collector.config.enabled:
                shutdown_tasks.append(self.metrics_collector.shutdown())

            if self.performance_monitor.config.enabled:
                shutdown_tasks.append(self.performance_monitor.shutdown())

            # Wait for all shutdowns to complete with timeout
            if shutdown_tasks:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=self.config.graceful_shutdown_timeout,
                )

            self._initialized = False
            logger.info("Observability system shutdown complete")

        except TimeoutError:
            logger.warning(
                "Observability shutdown timed out", timeout=self.config.graceful_shutdown_timeout
            )
            self._initialized = False
        except Exception as e:
            logger.error("Error during observability shutdown", error=str(e))
            self._initialized = False

    def get_system_overview(self) -> dict[str, Any]:
        """Get comprehensive system overview.

        Returns:
            System overview including all monitoring data
        """
        overview = {
            "timestamp": self.metrics_collector.get_metrics_snapshot()["timestamp"],
            "system_status": "unknown",
            "observability_status": {
                "initialized": self._initialized,
                "metrics_enabled": self.metrics_collector.config.enabled,
                "health_enabled": self.health_checker.config.enabled,
                "alerts_enabled": self.alert_manager.config.enabled,
                "performance_enabled": self.performance_monitor.config.enabled,
            },
        }

        try:
            # Get health summary
            if self._initialized and self.health_checker.config.enabled:
                health_summary = self.health_checker.get_health_summary()
                overview["health"] = health_summary
                overview["system_status"] = health_summary["status"]

            # Get metrics snapshot
            if self._initialized and self.metrics_collector.config.enabled:
                overview["metrics"] = self.metrics_collector.get_metrics_snapshot()

            # Get alert summary
            if self._initialized and self.alert_manager.config.enabled:
                overview["alerts"] = self.alert_manager.get_alert_summary()

            # Get performance summary
            if self._initialized and self.performance_monitor.config.enabled:
                overview["performance"] = self.performance_monitor.get_performance_summary()

        except Exception as e:
            logger.error("Failed to generate system overview", error=str(e))
            overview["error"] = str(e)

        return overview

    def get_component_status(self) -> dict[str, dict[str, Any]]:
        """Get detailed status of all observability components.

        Returns:
            Component status dictionary
        """
        return {
            "metrics_collector": {
                "enabled": self.metrics_collector.config.enabled,
                "collecting": self.metrics_collector._collecting,
                "prometheus_available": hasattr(self.metrics_collector, "registry")
                and self.metrics_collector.registry is not None,
                "active_traces": len(getattr(self.metrics_collector, "active_traces", {})),
            },
            "health_checker": {
                "enabled": self.health_checker.config.enabled,
                "monitoring": self.health_checker._checking,
                "registered_checks": len(self.health_checker._checks),
                "last_results": len(self.health_checker._results),
            },
            "alert_manager": {
                "enabled": self.alert_manager.config.enabled,
                "evaluating": self.alert_manager._evaluating,
                "total_rules": len(self.alert_manager.rules),
                "enabled_rules": sum(1 for r in self.alert_manager.rules.values() if r.enabled),
                "active_alerts": len(self.alert_manager.active_alerts),
            },
            "performance_monitor": {
                "enabled": self.performance_monitor.config.enabled,
                "tracing_enabled": self.performance_monitor.config.trace_requests,
                "active_traces": len(self.performance_monitor.active_traces),
                "completed_traces": len(self.performance_monitor.completed_traces),
                "slow_requests": len(self.performance_monitor.slow_requests),
            },
        }

    async def run_diagnostic(self) -> dict[str, Any]:
        """Run comprehensive diagnostic check of the observability system.

        Returns:
            Diagnostic results
        """
        diagnostic = {
            "timestamp": self.metrics_collector.get_metrics_snapshot()["timestamp"],
            "overall_status": "unknown",
            "components": {},
            "recommendations": [],
            "issues": [],
        }

        try:
            # Check each component

            # Metrics collector diagnostic
            metrics_ok = (
                self.metrics_collector.config.enabled
                and hasattr(self.metrics_collector, "_collecting")
                and self.metrics_collector._collecting
            )

            diagnostic["components"]["metrics_collector"] = {
                "status": "healthy" if metrics_ok else "degraded",
                "details": self.get_component_status()["metrics_collector"],
            }

            if not metrics_ok and self.metrics_collector.config.enabled:
                diagnostic["issues"].append("Metrics collection not running")

            # Health checker diagnostic
            if self.health_checker.config.enabled:
                health_results = await self.health_checker.run_all_checks()
                overall_health = self.health_checker.get_overall_status()

                diagnostic["components"]["health_checker"] = {
                    "status": overall_health.value,
                    "details": {
                        "total_checks": len(health_results),
                        "unhealthy_checks": [
                            name
                            for name, result in health_results.items()
                            if result.status.value in ["unhealthy", "unknown"]
                        ],
                    },
                }

                if overall_health.value in ["unhealthy", "unknown"]:
                    diagnostic["issues"].extend(
                        [
                            f"Health check failed: {name}"
                            for name, result in health_results.items()
                            if result.status.value in ["unhealthy", "unknown"]
                        ]
                    )

            # Alert manager diagnostic
            alert_status = "healthy"
            if self.alert_manager.config.enabled:
                if not self.alert_manager._evaluating:
                    alert_status = "degraded"
                    diagnostic["issues"].append("Alert evaluation not running")

                if self.alert_manager.active_alerts:
                    alert_status = "warning"
                    diagnostic["issues"].append(
                        f"{len(self.alert_manager.active_alerts)} active alerts"
                    )

            diagnostic["components"]["alert_manager"] = {
                "status": alert_status,
                "details": self.get_component_status()["alert_manager"],
            }

            # Performance monitor diagnostic
            perf_status = "healthy"
            if (
                self.performance_monitor.config.enabled
                and len(self.performance_monitor.slow_requests) > 10
            ):
                perf_status = "warning"
                diagnostic["issues"].append("High number of slow requests detected")

            diagnostic["components"]["performance_monitor"] = {
                "status": perf_status,
                "details": self.get_component_status()["performance_monitor"],
            }

            # Determine overall status
            component_statuses = [comp["status"] for comp in diagnostic["components"].values()]

            if any(status == "unhealthy" for status in component_statuses):
                diagnostic["overall_status"] = "unhealthy"
            elif any(status in ["degraded", "warning"] for status in component_statuses):
                diagnostic["overall_status"] = "degraded"
            else:
                diagnostic["overall_status"] = "healthy"

            # Generate recommendations
            if diagnostic["issues"]:
                diagnostic["recommendations"].append("Review and resolve identified issues")

            if not self._initialized:
                diagnostic["recommendations"].append("Initialize observability system")

        except Exception as e:
            logger.error("Diagnostic check failed", error=str(e))
            diagnostic["overall_status"] = "error"
            diagnostic["error"] = str(e)

        return diagnostic

    def export_metrics(self) -> bytes:
        """Export all metrics in Prometheus format.

        Returns:
            Prometheus metrics data
        """
        if not self.metrics_collector.config.enabled:
            return b"# Metrics collection disabled\n"

        return self.metrics_collector.export_prometheus_metrics()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()


# Global observability manager instance
observability_manager = ObservabilityManager()
