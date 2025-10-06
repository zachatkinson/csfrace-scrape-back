"""Setup and configuration for monitoring system including health checks."""

from typing import Any

from src.core.logging_hierarchy import get_monitoring_logger

from .health_checks import (
    APIHealthCheck,
    CacheHealthCheck,
    DatabaseHealthCheck,
    DatabaseTableHealthCheck,
    DependencyHealthCheck,
    health_registry,
)

logger = get_monitoring_logger()


def setup_default_health_checks() -> None:
    """Register default health checks for the application."""
    try:
        # Register core system health checks
        health_registry.register(APIHealthCheck(), tags=["core", "api"])

        health_registry.register(DependencyHealthCheck(), tags=["core", "dependencies"])

        # Register database health checks
        health_registry.register(DatabaseHealthCheck(), tags=["database", "critical"])

        # Register specific table health checks
        critical_tables = ["users", "scraping_jobs", "job_logs"]
        for table in critical_tables:
            health_registry.register(
                DatabaseTableHealthCheck(table), tags=["database", "tables", "critical"]
            )

        # Register cache health check (non-critical)
        health_registry.register(CacheHealthCheck(), tags=["cache", "performance"])

        logger.info(
            f"Registered {len(health_registry.list_checks())} health checks",
            checks=health_registry.list_checks(),
            tags=health_registry.list_tags(),
        )

    except Exception as e:
        logger.error(f"Failed to setup default health checks: {e}")
        raise


def get_health_check_summary() -> dict[str, Any]:
    """Get a summary of all registered health checks."""
    return {
        "total_checks": len(health_registry.list_checks()),
        "checks": health_registry.list_checks(),
        "tags": health_registry.list_tags(),
        "checks_by_tag": {
            tag: [check.name for check in health_registry.get_checks_by_tag(tag)]
            for tag in health_registry.list_tags()
        },
    }
