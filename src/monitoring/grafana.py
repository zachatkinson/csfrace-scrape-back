"""Grafana dashboard provisioning and configuration management.

This module provides comprehensive Grafana integration following industry best practices
for metrics visualization and dashboard management.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import structlog

from ..constants import CONSTANTS

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GrafanaConfig:
    """Configuration for Grafana integration."""

    enabled: bool = True
    host: str = "localhost"
    port: int = 3000
    protocol: str = "http"
    admin_user: str = "admin"
    admin_password: str = "admin"
    dashboards_dir: Path = Path(CONSTANTS.DEFAULT_OUTPUT_DIR) / "grafana" / "dashboards"
    provisioning_dir: Path = Path(CONSTANTS.DEFAULT_OUTPUT_DIR) / "grafana" / "provisioning"
    prometheus_url: str = "http://prometheus:9090"
    refresh_interval: str = "30s"
    time_range: str = "1h"
    custom_labels: dict[str, str] = field(default_factory=dict)


class GrafanaDashboardManager:
    """Manages Grafana dashboard creation and provisioning.

    Follows Grafana best practices for dashboard organization, naming,
    and performance optimization.
    """

    def __init__(self, config: Optional[GrafanaConfig] = None):
        """Initialize Grafana dashboard manager.

        Args:
            config: Grafana configuration settings
        """
        self.config = config or GrafanaConfig()
        self._ensure_directories()
        self._dashboard_templates = {}

    def _ensure_directories(self) -> None:
        """Create necessary directories for Grafana provisioning."""
        self.config.dashboards_dir.mkdir(parents=True, exist_ok=True)
        self.config.provisioning_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for organized provisioning
        (self.config.provisioning_dir / "dashboards").mkdir(exist_ok=True)
        (self.config.provisioning_dir / "datasources").mkdir(exist_ok=True)

    def generate_system_overview_dashboard(self) -> dict[str, Any]:
        """Generate system overview dashboard following USE methodology.

        USE methodology focuses on:
        - Utilization: How busy is the resource?
        - Saturation: How much extra work is queued?
        - Errors: What is the error rate?

        Returns:
            Dashboard configuration dictionary
        """
        return {
            "dashboard": {
                "id": None,
                "title": "CSFrace Scraper - System Overview",
                "tags": ["csfrace", "system", "overview"],
                "timezone": "browser",
                "refresh": self.config.refresh_interval,
                "time": {"from": f"now-{self.config.time_range}", "to": "now"},
                "panels": [
                    self._create_cpu_utilization_panel(),
                    self._create_memory_utilization_panel(),
                    self._create_disk_utilization_panel(),
                    self._create_network_io_panel(),
                    self._create_system_load_panel(),
                    self._create_error_rate_panel(),
                ],
            }
        }

    def generate_application_metrics_dashboard(self) -> dict[str, Any]:
        """Generate application metrics dashboard following RED methodology.

        RED methodology focuses on:
        - Rate: How many requests per second?
        - Errors: How many of those requests are failing?
        - Duration: How long do those requests take?

        Returns:
            Dashboard configuration dictionary
        """
        return {
            "dashboard": {
                "id": None,
                "title": "CSFrace Scraper - Application Metrics",
                "tags": ["csfrace", "application", "performance"],
                "timezone": "browser",
                "refresh": self.config.refresh_interval,
                "time": {"from": f"now-{self.config.time_range}", "to": "now"},
                "panels": [
                    self._create_request_rate_panel(),
                    self._create_request_duration_panel(),
                    self._create_error_rate_panel(),
                    self._create_active_requests_panel(),
                    self._create_batch_jobs_panel(),
                    self._create_cache_metrics_panel(),
                ],
            }
        }

    def generate_database_dashboard(self) -> dict[str, Any]:
        """Generate database performance dashboard.

        Returns:
            Dashboard configuration dictionary
        """
        return {
            "dashboard": {
                "id": None,
                "title": "CSFrace Scraper - Database Performance",
                "tags": ["csfrace", "database", "postgresql"],
                "timezone": "browser",
                "refresh": self.config.refresh_interval,
                "time": {"from": f"now-{self.config.time_range}", "to": "now"},
                "panels": [
                    self._create_db_connections_panel(),
                    self._create_db_query_duration_panel(),
                    self._create_db_queries_panel(),
                    self._create_job_status_panel(),
                ],
            }
        }

    def _create_cpu_utilization_panel(self) -> dict[str, Any]:
        """Create CPU utilization panel following Grafana best practices."""
        return {
            "id": 1,
            "title": "CPU Utilization",
            "type": "stat",
            "targets": [{"expr": "system_cpu_percent", "legendFormat": "CPU %", "refId": "A"}],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 70},
                            {"color": "red", "value": 90},
                        ]
                    },
                }
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        }

    def _create_memory_utilization_panel(self) -> dict[str, Any]:
        """Create memory utilization panel with proper thresholds."""
        return {
            "id": 2,
            "title": "Memory Utilization",
            "type": "stat",
            "targets": [
                {"expr": "system_memory_percent", "legendFormat": "Memory %", "refId": "A"}
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 80},
                            {"color": "red", "value": 95},
                        ]
                    },
                }
            },
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        }

    def _create_disk_utilization_panel(self) -> dict[str, Any]:
        """Create disk utilization panel."""
        return {
            "id": 3,
            "title": "Disk Utilization",
            "type": "stat",
            "targets": [{"expr": "system_disk_percent", "legendFormat": "Disk %", "refId": "A"}],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 85},
                            {"color": "red", "value": 95},
                        ]
                    },
                }
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        }

    def _create_network_io_panel(self) -> dict[str, Any]:
        """Create network I/O panel."""
        return {
            "id": 4,
            "title": "Network I/O",
            "type": "timeseries",
            "targets": [
                {
                    "expr": "rate(system_network_bytes_sent[5m])",
                    "legendFormat": "Bytes Sent/sec",
                    "refId": "A",
                },
                {
                    "expr": "rate(system_network_bytes_recv[5m])",
                    "legendFormat": "Bytes Received/sec",
                    "refId": "B",
                },
            ],
            "fieldConfig": {"defaults": {"unit": "binBps"}},
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        }

    def _create_system_load_panel(self) -> dict[str, Any]:
        """Create system load average panel."""
        return {
            "id": 5,
            "title": "System Load Average",
            "type": "timeseries",
            "targets": [
                {"expr": "system_load_average", "legendFormat": "Load Average", "refId": "A"}
            ],
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
        }

    def _create_error_rate_panel(self) -> dict[str, Any]:
        """Create error rate panel following RED methodology."""
        return {
            "id": 6,
            "title": "Error Rate",
            "type": "stat",
            "targets": [
                {
                    "expr": 'rate(scraper_requests_total{status="error"}[5m]) / rate(scraper_requests_total[5m]) * 100',
                    "legendFormat": "Error Rate %",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 1},
                            {"color": "red", "value": 5},
                        ]
                    },
                }
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
        }

    def _create_request_rate_panel(self) -> dict[str, Any]:
        """Create request rate panel following RED methodology."""
        return {
            "id": 10,
            "title": "Request Rate",
            "type": "timeseries",
            "targets": [
                {
                    "expr": "rate(scraper_requests_total[5m])",
                    "legendFormat": "Requests/sec",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "reqps"}},
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        }

    def _create_request_duration_panel(self) -> dict[str, Any]:
        """Create request duration panel."""
        return {
            "id": 11,
            "title": "Request Duration",
            "type": "timeseries",
            "targets": [
                {
                    "expr": "histogram_quantile(0.95, rate(scraper_request_duration_seconds_bucket[5m]))",
                    "legendFormat": "95th percentile",
                    "refId": "A",
                },
                {
                    "expr": "histogram_quantile(0.50, rate(scraper_request_duration_seconds_bucket[5m]))",
                    "legendFormat": "50th percentile",
                    "refId": "B",
                },
            ],
            "fieldConfig": {"defaults": {"unit": "s"}},
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        }

    def _create_active_requests_panel(self) -> dict[str, Any]:
        """Create active requests panel."""
        return {
            "id": 12,
            "title": "Active Requests",
            "type": "stat",
            "targets": [
                {"expr": "scraper_active_requests", "legendFormat": "Active", "refId": "A"}
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        }

    def _create_batch_jobs_panel(self) -> dict[str, Any]:
        """Create batch jobs status panel."""
        return {
            "id": 13,
            "title": "Batch Jobs Status",
            "type": "piechart",
            "targets": [
                {
                    "expr": 'scraper_batch_jobs{status="completed"}',
                    "legendFormat": "Completed",
                    "refId": "A",
                },
                {
                    "expr": 'scraper_batch_jobs{status="pending"}',
                    "legendFormat": "Pending",
                    "refId": "B",
                },
                {
                    "expr": 'scraper_batch_jobs{status="running"}',
                    "legendFormat": "Running",
                    "refId": "C",
                },
                {
                    "expr": 'scraper_batch_jobs{status="failed"}',
                    "legendFormat": "Failed",
                    "refId": "D",
                },
            ],
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        }

    def _create_cache_metrics_panel(self) -> dict[str, Any]:
        """Create cache performance panel."""
        return {
            "id": 14,
            "title": "Cache Hit Rate",
            "type": "stat",
            "targets": [
                {
                    "expr": "cache_hits / (cache_hits + cache_misses) * 100",
                    "legendFormat": "Hit Rate %",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {
                        "steps": [
                            {"color": "red", "value": None},
                            {"color": "yellow", "value": 80},
                            {"color": "green", "value": 95},
                        ]
                    },
                }
            },
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
        }

    def _create_db_connections_panel(self) -> dict[str, Any]:
        """Create database connections panel."""
        return {
            "id": 20,
            "title": "Database Connections",
            "type": "timeseries",
            "targets": [
                {
                    "expr": "database_connections_active",
                    "legendFormat": "Active Connections",
                    "refId": "A",
                }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        }

    def _create_db_query_duration_panel(self) -> dict[str, Any]:
        """Create database query duration panel."""
        return {
            "id": 21,
            "title": "Query Duration",
            "type": "timeseries",
            "targets": [
                {
                    "expr": "histogram_quantile(0.95, rate(database_query_duration_seconds_bucket[5m]))",
                    "legendFormat": "95th percentile",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "s"}},
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        }

    def _create_db_queries_panel(self) -> dict[str, Any]:
        """Create database queries per second panel."""
        return {
            "id": 22,
            "title": "Queries per Second",
            "type": "timeseries",
            "targets": [
                {
                    "expr": "rate(database_queries_total[5m])",
                    "legendFormat": "Queries/sec",
                    "refId": "A",
                }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        }

    def _create_job_status_panel(self) -> dict[str, Any]:
        """Create job status distribution panel."""
        return {
            "id": 23,
            "title": "Job Status Distribution",
            "type": "piechart",
            "targets": [
                {
                    "expr": 'jobs_status{status="completed"}',
                    "legendFormat": "Completed",
                    "refId": "A",
                },
                {"expr": 'jobs_status{status="pending"}', "legendFormat": "Pending", "refId": "B"},
                {"expr": 'jobs_status{status="running"}', "legendFormat": "Running", "refId": "C"},
                {"expr": 'jobs_status{status="failed"}', "legendFormat": "Failed", "refId": "D"},
            ],
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        }

    def create_provisioning_config(self) -> dict[str, Any]:
        """Create Grafana provisioning configuration.

        Returns:
            Provisioning configuration for dashboards
        """
        return {
            "apiVersion": 1,
            "providers": [
                {
                    "name": "csfrace-dashboards",
                    "orgId": 1,
                    "folder": "",
                    "type": "file",
                    "disableDeletion": False,
                    "updateIntervalSeconds": 10,
                    "allowUiUpdates": True,
                    "options": {"path": "/etc/grafana/provisioning/dashboards"},
                }
            ],
        }

    def create_datasource_config(self) -> dict[str, Any]:
        """Create Grafana datasource configuration for Prometheus.

        Returns:
            Datasource configuration
        """
        return {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "Prometheus",
                    "type": "prometheus",
                    "access": "proxy",
                    "url": self.config.prometheus_url,
                    "isDefault": True,
                    "editable": True,
                }
            ],
        }
