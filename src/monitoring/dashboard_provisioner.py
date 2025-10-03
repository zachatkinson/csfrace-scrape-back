"""Grafana dashboard provisioning and deployment system.

This module handles the automated creation, validation, and deployment
of Grafana dashboards following industry best practices.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

from .grafana import GrafanaConfig, GrafanaDashboardManager

logger = get_monitoring_logger()


class GrafanaDashboardProvisioner:
    """Handles dashboard provisioning and deployment to Grafana.

    This class implements the complete dashboard lifecycle:
    1. Generation of dashboard JSON configurations
    2. Validation of dashboard structures
    3. Provisioning file creation
    4. Docker Compose integration
    """

    def __init__(self, config: GrafanaConfig | None = None):
        """Initialize dashboard provisioner.

        Args:
            config: Grafana configuration settings
        """
        self.config = config or GrafanaConfig()
        self._validate_config()
        self.dashboard_manager = GrafanaDashboardManager(self.config)

    def _validate_config(self) -> None:
        """Validate configuration settings."""
        if not self.config.prometheus_url:
            raise ValueError("Prometheus URL is required for dashboard provisioning")

        if not self.config.dashboards_dir or not self.config.provisioning_dir:
            raise ValueError("Dashboard and provisioning directories must be configured")

    def provision_all_dashboards(self) -> None:
        """Generate and provision all standard dashboards.

        Creates the complete suite of monitoring dashboards:
        - System Overview (USE methodology)
        - Application Metrics (RED methodology)
        - Database Performance
        - Custom business metrics
        """
        logger.info(
            "Starting dashboard provisioning", dashboards_dir=str(self.config.dashboards_dir)
        )

        # Generate all dashboard configurations
        dashboards = {
            "system-overview.json": self.dashboard_manager.generate_system_overview_dashboard(),
            "application-metrics.json": self.dashboard_manager.generate_application_metrics_dashboard(),
            "database-performance.json": self.dashboard_manager.generate_database_dashboard(),
        }

        # Write dashboard files
        for filename, dashboard_config in dashboards.items():
            _write_dashboard_file_safe(self, filename, dashboard_config)

        # Create provisioning configuration
        _create_provisioning_files_safe(self)

        # Create Prometheus configuration
        self.create_prometheus_config()

        # Generate Docker Compose integration
        self._update_docker_compose()

        logger.info(
            "Dashboard provisioning completed successfully", dashboard_count=len(dashboards)
        )

    def _write_dashboard_file(self, filename: str, dashboard_config: dict[str, Any]) -> None:
        """Write dashboard configuration to JSON file.

        Args:
            filename: Name of the dashboard file
            dashboard_config: Dashboard configuration dictionary
        """
        _write_dashboard_file_safe(self, filename, dashboard_config)

    def _create_provisioning_files(self) -> None:
        """Create Grafana provisioning configuration files."""
        _create_provisioning_files_safe(self)

    def _update_docker_compose(self) -> None:
        """Update Docker Compose configuration to include Grafana service."""
        docker_compose_path = Path("docker-compose.yml")

        if not docker_compose_path.exists():
            logger.warning("Docker Compose file not found, creating new one")
            self._create_docker_compose()
        else:
            self._add_grafana_to_existing_compose()

    def _create_docker_compose(self) -> None:
        """Create new Docker Compose configuration with Grafana."""
        compose_config = {
            "version": "3.8",
            "services": {
                "grafana": self._get_grafana_service_config(),
                "prometheus": self._get_prometheus_service_config(),
            },
            "volumes": {
                "grafana_data": None,
                "prometheus_data": None,
            },
            "networks": {"monitoring": {"driver": "bridge"}},
        }

        with open("docker-compose.yml", "w", encoding="utf-8") as f:
            yaml.dump(compose_config, f, default_flow_style=False)

        logger.info("Docker Compose configuration created")

    def _add_grafana_to_existing_compose(self) -> None:
        """Add Grafana service to existing Docker Compose configuration."""
        _add_grafana_to_existing_compose_safe(self)

    def _get_grafana_service_config(self) -> dict[str, Any]:
        """Get Grafana service configuration for Docker Compose.

        Returns:
            Grafana service configuration
        """
        return {
            "image": "grafana/grafana:latest",
            "container_name": "csfrace-grafana",
            "restart": "unless-stopped",
            "ports": [f"{self.config.port}:3000"],
            "environment": {
                "GF_SECURITY_ADMIN_USER": self.config.admin_user,
                "GF_SECURITY_ADMIN_PASSWORD": self.config.admin_password,
                "GF_USERS_ALLOW_SIGN_UP": "false",
                "GF_INSTALL_PLUGINS": "grafana-piechart-panel,grafana-worldmap-panel",
            },
            "volumes": [
                "grafana_data:/var/lib/grafana",
                f"{self.config.provisioning_dir}:/etc/grafana/provisioning",
                f"{self.config.dashboards_dir}:/etc/grafana/provisioning/dashboards",
            ],
            "networks": ["monitoring"],
            "depends_on": ["prometheus"],
            "healthcheck": {
                "test": ["CMD-SHELL", "curl -f http://localhost:3000/api/health || exit 1"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "30s",
            },
        }

    def _get_prometheus_service_config(self) -> dict[str, Any]:
        """Get Prometheus service configuration for Docker Compose.

        Returns:
            Prometheus service configuration
        """
        return {
            "image": "prom/prometheus:latest",
            "container_name": "csfrace-prometheus",
            "restart": "unless-stopped",
            "command": [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.path=/prometheus",
                "--web.console.libraries=/etc/prometheus/console_libraries",
                "--web.console.templates=/etc/prometheus/consoles",
                "--storage.tsdb.retention.time=15d",
                "--web.enable-lifecycle",
            ],
            "ports": ["9090:9090"],
            "volumes": [
                "./prometheus.yml:/etc/prometheus/prometheus.yml",
                "prometheus_data:/prometheus",
            ],
            "networks": ["monitoring"],
            "healthcheck": {
                "test": [
                    "CMD-SHELL",
                    "wget --no-verbose --tries=1 --spider http://localhost:9090/ || exit 1",
                ],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "30s",
            },
        }

    def create_prometheus_config(self) -> None:
        """Create Prometheus configuration file."""
        prometheus_config = {
            "global": {
                "scrape_interval": "15s",
                "evaluation_interval": "15s",
            },
            "scrape_configs": [
                {
                    "job_name": "csfrace-scraper",
                    "static_configs": [{"targets": ["host.docker.internal:9090"]}],
                    "scrape_interval": "5s",
                    "metrics_path": "/health/prometheus",
                }
            ],
        }

        with open("prometheus.yml", "w", encoding="utf-8") as f:
            yaml.dump(prometheus_config, f, default_flow_style=False)

        logger.info("Prometheus configuration created")

    def validate_dashboards(self) -> bool:
        """Validate all dashboard configurations.

        Returns:
            True if all dashboards are valid, False otherwise
        """
        dashboard_files = list(self.config.dashboards_dir.glob("*.json"))

        if not dashboard_files:
            logger.warning("No dashboard files found for validation")
            return False

        all_valid = True
        for dashboard_file in dashboard_files:
            if not self._validate_single_dashboard(dashboard_file):
                all_valid = False

        if all_valid:
            logger.info(
                "All dashboards validated successfully", dashboard_count=len(dashboard_files)
            )
        else:
            logger.error("Some dashboards failed validation")

        return all_valid

    def _validate_single_dashboard(self, dashboard_path: Path) -> bool:
        """Validate a single dashboard configuration file.

        Args:
            dashboard_path: Path to dashboard JSON file

        Returns:
            True if dashboard is valid, False otherwise
        """
        result = _validate_single_dashboard_safe(self, dashboard_path)
        return result if result is not None else False

    def _validate_panel(self, panel: dict[str, Any], dashboard_path: Path) -> bool:
        """Validate a single panel configuration.

        Args:
            panel: Panel configuration dictionary
            dashboard_path: Path to dashboard file (for logging)

        Returns:
            True if panel is valid, False otherwise
        """
        required_fields = ["id", "title", "type"]

        for field in required_fields:
            if field not in panel:
                logger.error(
                    f"Invalid panel: missing '{field}' field",
                    file=str(dashboard_path),
                    panel_id=panel.get("id", "unknown"),
                )
                return False

        # Validate targets for query panels
        if "targets" in panel and panel["targets"]:
            for target in panel["targets"]:
                if "expr" not in target:
                    logger.error(
                        "Panel target missing 'expr' field",
                        file=str(dashboard_path),
                        panel_id=panel.get("id"),
                    )
                    return False

        return True


@monitoring_error_handler("write dashboard file")
def _write_dashboard_file_safe(
    provisioner: GrafanaDashboardProvisioner, filename: str, dashboard_config: dict[str, Any]
) -> None:
    """Safely write dashboard configuration to JSON file."""
    dashboard_path = provisioner.config.dashboards_dir / filename

    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(dashboard_config, f, indent=2, ensure_ascii=False)

    logger.debug(
        "Dashboard file written",
        file=str(dashboard_path),
        title=dashboard_config.get("dashboard", {}).get("title", "Unknown"),
    )


@monitoring_error_handler("create provisioning files")
def _create_provisioning_files_safe(provisioner: GrafanaDashboardProvisioner) -> None:
    """Safely create Grafana provisioning configuration files."""
    # Dashboard provisioning configuration
    dashboard_provisioning = provisioner.dashboard_manager.create_provisioning_config()
    provisioning_file = provisioner.config.provisioning_dir / "dashboards" / "dashboards.yaml"

    with open(provisioning_file, "w", encoding="utf-8") as f:
        yaml.dump(dashboard_provisioning, f, default_flow_style=False)

    # Datasource provisioning configuration
    datasource_config = provisioner.dashboard_manager.create_datasource_config()
    datasource_file = provisioner.config.provisioning_dir / "datasources" / "datasources.yaml"

    with open(datasource_file, "w", encoding="utf-8") as f:
        yaml.dump(datasource_config, f, default_flow_style=False)

    logger.info(
        "Provisioning configuration files created",
        dashboard_config=str(provisioning_file),
        datasource_config=str(datasource_file),
    )


@monitoring_error_handler("add Grafana to existing Docker Compose")
def _add_grafana_to_existing_compose_safe(provisioner: GrafanaDashboardProvisioner) -> None:
    """Safely add Grafana service to existing Docker Compose configuration."""
    with open("docker-compose.yml", encoding="utf-8") as f:
        compose_config = yaml.safe_load(f)

    # Add Grafana service if not present
    if "grafana" not in compose_config.get("services", {}):
        compose_config.setdefault("services", {})["grafana"] = (
            provisioner._get_grafana_service_config()
        )

    # Add Prometheus service if not present
    if "prometheus" not in compose_config.get("services", {}):
        compose_config.setdefault("services", {})["prometheus"] = (
            provisioner._get_prometheus_service_config()
        )

    # Add volumes
    compose_config.setdefault("volumes", {}).update(
        {
            "grafana_data": None,
            "prometheus_data": None,
        }
    )

    # Add monitoring network
    compose_config.setdefault("networks", {}).setdefault("monitoring", {"driver": "bridge"})

    # Update existing services to use monitoring network
    for service_name, service_config in compose_config["services"].items():
        if "networks" not in service_config:
            service_config["networks"] = ["monitoring"]

    with open("docker-compose.yml", "w", encoding="utf-8") as f:
        yaml.dump(compose_config, f, default_flow_style=False)

    logger.info("Grafana service added to existing Docker Compose")


@monitoring_error_handler("validate single dashboard")
def _validate_single_dashboard_safe(
    provisioner: GrafanaDashboardProvisioner, dashboard_path: Path
) -> bool:
    """Safely validate a single dashboard configuration file."""
    with open(dashboard_path, encoding="utf-8") as f:
        dashboard_config = json.load(f)

    # Basic structure validation
    if "dashboard" not in dashboard_config:
        logger.error(
            "Invalid dashboard structure: missing 'dashboard' key", file=str(dashboard_path)
        )
        return False

    dashboard = dashboard_config["dashboard"]
    required_fields = ["title", "panels"]

    for field in required_fields:
        if field not in dashboard:
            logger.error(f"Invalid dashboard: missing '{field}' field", file=str(dashboard_path))
            return False

    # Validate panels
    panels = dashboard.get("panels", [])
    if not panels:
        logger.warning("Dashboard has no panels", file=str(dashboard_path))
        return True

    for panel in panels:
        if not provisioner._validate_panel(panel, dashboard_path):
            return False

    logger.debug("Dashboard validated successfully", file=str(dashboard_path))
    return True
