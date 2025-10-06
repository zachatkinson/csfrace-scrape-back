"""Central observability manager orchestrating all monitoring components."""

from dataclasses import dataclass

import asyncio

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

from .alerts import AlertConfig, AlertManager, alert_manager
from .health import HealthChecker, HealthConfig, health_checker
from .metrics import MetricsCollector, MetricsConfig, metrics_collector
from .performance import PerformanceConfig, performance_monitor
from .tracing import DistributedTracer, TracingConfig, distributed_tracer

logger = get_monitoring_logger()


@dataclass
class ObservabilityConfig:
    """Central configuration for all observability components."""

    enabled: bool = True

    # Component configurations
    metrics_config: MetricsConfig | None = None
    health_config: HealthConfig | None = None
    alerts_config: AlertConfig | None = None
    performance_config: PerformanceConfig | None = None
    tracing_config: TracingConfig | None = None

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

        self.distributed_tracer = distributed_tracer
        if self.config.tracing_config:
            self.distributed_tracer.config = self.config.tracing_config

        self._initialized = False
        self._shutdown_event = asyncio.Event()

        logger.info("Observability manager initialized", enabled=self.config.enabled)

    async def initialize(self) -> None:
        """Initialize all observability components."""
        if not self.config.enabled or self._initialized:
            return

        logger.info("Initializing observability system")

        # Initialize components in order
        if self.metrics_collector.config.enabled:
            await _start_metrics_collector_safe(self.metrics_collector)
            logger.debug("Metrics collector started")

        if self.health_checker.config.enabled:
            await _start_health_checker_safe(self.health_checker)
            logger.debug("Health checker started")

        if self.alert_manager.config.enabled:
            await _start_alert_manager_safe(self.alert_manager)
            logger.debug("Alert manager started")

        # Initialize distributed tracing
        if self.distributed_tracer.config.enabled:
            await _initialize_tracer_safe(self.distributed_tracer)
            logger.debug("Distributed tracer initialized")

        # Performance monitor doesn't need explicit initialization
        logger.debug("Performance monitor ready")

        # Run startup health check if enabled
        if self.config.startup_health_check:
            await self._run_startup_health_check()

        self._initialized = True
        logger.info("Observability system initialized successfully")

    @monitoring_error_handler("run startup health check")
    async def _run_startup_health_check(self) -> None:
        """Run comprehensive health check on startup."""
        logger.info("Running startup health check")

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

    async def shutdown(self) -> None:
        """Gracefully shutdown all observability components."""
        if not hasattr(self, "_initialized") or not self._initialized:
            return

        logger.info("Shutting down observability system")

        # Set shutdown event if exists
        if hasattr(self, "_shutdown_event"):
            self._shutdown_event.set()

        # Shutdown components
        try:
            await self.metrics_collector.stop_collection()
        except Exception as e:
            logger.warning(f"Error stopping metrics collector: {e}")

        try:
            await self.health_checker.stop_monitoring()
        except Exception as e:
            logger.warning(f"Error stopping health checker: {e}")

        try:
            await self.alert_manager.stop_evaluation()
        except Exception as e:
            logger.warning(f"Error stopping alert manager: {e}")

        self._initialized = False
        logger.info("Observability system shutdown completed")


@monitoring_error_handler("start metrics collector")
async def _start_metrics_collector_safe(metrics_collector: MetricsCollector) -> None:
    """Safely start metrics collector."""
    await metrics_collector.start_collection()


@monitoring_error_handler("start health checker")
async def _start_health_checker_safe(health_checker: HealthChecker) -> None:
    """Safely start health checker."""
    await health_checker.start_monitoring()


@monitoring_error_handler("start alert manager")
async def _start_alert_manager_safe(alert_manager: AlertManager) -> None:
    """Safely start alert manager."""
    await alert_manager.start_evaluation()


@monitoring_error_handler("initialize tracer")
async def _initialize_tracer_safe(tracer: DistributedTracer) -> None:
    """Safely initialize distributed tracer."""
    tracer.initialize()


# Global observability manager instance
observability_manager = ObservabilityManager()
