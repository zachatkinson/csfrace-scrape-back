"""Command-line interface for Grafana dashboard management.

This module provides CLI commands for provisioning, validating, and managing
Grafana dashboards following CLAUDE.md standards.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
import yaml

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_general_logger

from ..constants import DEFAULT_GRAFANA_PORT, DEFAULT_OUTPUT_DIR, DEFAULT_PROMETHEUS_URL
from ..monitoring import GrafanaConfig, GrafanaDashboardProvisioner

logger = get_general_logger()

app = typer.Typer(
    name="grafana", help="Manage Grafana dashboards and provisioning", no_args_is_help=True
)


@app.command()
def provision(
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Path to Grafana configuration file"
    ),
    prometheus_url: str = typer.Option(
        DEFAULT_PROMETHEUS_URL, "--prometheus-url", "-p", help="Prometheus server URL"
    ),
    grafana_port: int = typer.Option(DEFAULT_GRAFANA_PORT, "--port", help="Grafana server port"),
    output_dir: Path | None = typer.Option(
        None, "--output", "-o", help="Output directory for dashboards and provisioning files"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing files without confirmation"
    ),
) -> None:
    """Provision Grafana dashboards and configuration files.

    Generates complete dashboard suite including:
    - System overview (USE methodology)
    - Application metrics (RED methodology)
    - Database performance monitoring
    - Docker Compose integration
    """
    _execute_cli_command_safe(
        "provision",
        _provision_dashboards,
        config_file,
        prometheus_url,
        grafana_port,
        output_dir,
        force,
    )


@app.command()
def validate(
    dashboards_dir: Path | None = typer.Option(
        None, "--dashboards-dir", "-d", help="Directory containing dashboard JSON files"
    ),
) -> None:
    """Validate existing dashboard configurations.

    Performs comprehensive validation of dashboard JSON files including:
    - Structure validation
    - Panel configuration checks
    - Query syntax validation
    """
    _execute_cli_command_safe("validate", _validate_dashboards, dashboards_dir)


@app.command()
def status() -> None:
    """Show status of Grafana dashboards and services."""
    _execute_cli_command_safe("status", _show_status)


@app.command()
def clean(
    force: bool = typer.Option(False, "--force", "-f", help="Remove files without confirmation"),
) -> None:
    """Clean up generated dashboard and provisioning files."""
    _execute_cli_command_safe("clean", _clean_files, force)


@app.command()
def init(
    output_dir: Path = typer.Option(
        Path("grafana"), "--output", "-o", help="Output directory for initialization"
    ),
) -> None:
    """Initialize Grafana configuration with example files."""
    _execute_cli_command_safe("init", _initialize_config, output_dir)


def _load_config_from_file(
    config_file: Path, prometheus_url: str, grafana_port: int
) -> GrafanaConfig:
    """Load Grafana configuration from file.

    Args:
        config_file: Path to configuration file (YAML or JSON)
        prometheus_url: Default Prometheus URL
        grafana_port: Default Grafana port

    Returns:
        GrafanaConfig instance with loaded settings

    Raises:
        typer.Exit: If configuration file is invalid
    """
    return _load_config_safe(config_file, prometheus_url, grafana_port)


@database_error_handler("execute CLI command")
def _execute_cli_command_safe(operation: str, func: Callable[..., Any], *args: Any) -> None:
    """Execute CLI command with error handling."""
    try:
        func(*args)
        logger.logger.info(f"{operation} completed successfully")
    except Exception as e:
        logger.logger.error(f"{operation} failed", error=str(e))
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@database_error_handler("provision dashboards")
def _provision_dashboards(
    config_file: Path | None,
    prometheus_url: str,
    grafana_port: int,
    output_dir: Path | None,
    force: bool,
) -> None:
    """Provision dashboards with error handling."""
    config = (
        _load_config_from_file(config_file, prometheus_url, grafana_port)
        if config_file
        else GrafanaConfig(
            prometheus_url=prometheus_url,
            port=grafana_port,
            output_dir=output_dir or DEFAULT_OUTPUT_DIR,
        )
    )

    provisioner = GrafanaDashboardProvisioner(config)
    provisioner.provision_all(force=force)


@database_error_handler("validate dashboards")
def _validate_dashboards(dashboards_dir: Path | None) -> None:
    """Validate dashboards with error handling."""
    config = GrafanaConfig()
    if dashboards_dir:
        config.dashboards_dir = dashboards_dir

    provisioner = GrafanaDashboardProvisioner(config)
    is_valid = provisioner.validate_dashboards()
    if not is_valid:
        raise ValueError("Dashboard validation failed")


@database_error_handler("show status")
def _show_status() -> None:
    """Show status with error handling."""
    config = GrafanaConfig()
    provisioner = GrafanaDashboardProvisioner(config)
    status = provisioner.get_status()

    typer.echo("\n📊 Grafana Dashboard Status:")
    for key, value in status.items():
        typer.echo(f"  {key}: {value}")


@database_error_handler("clean files")
def _clean_files(force: bool) -> None:
    """Clean files with error handling."""
    config = GrafanaConfig()

    if not force:
        confirm = typer.confirm("Are you sure you want to remove all generated files?")
        if not confirm:
            typer.echo("❌ Operation cancelled")
            return

    provisioner = GrafanaDashboardProvisioner(config)
    removed_count = provisioner.clean_generated_files()
    typer.echo(f"✅ Removed {removed_count} generated files")


@database_error_handler("initialize config")
def _initialize_config(output_dir: Path) -> None:
    """Initialize config with error handling."""
    config = GrafanaConfig(output_dir=output_dir)
    provisioner = GrafanaDashboardProvisioner(config)
    provisioner.initialize_config_structure()

    typer.echo(f"✅ Initialized Grafana configuration in {output_dir}")


@database_error_handler("load config from file")
def _load_config_safe(config_file: Path, prometheus_url: str, grafana_port: int) -> GrafanaConfig:
    """Load config from file with error handling."""
    if config_file.suffix.lower() == ".json":
        with open(config_file, encoding="utf-8") as f:
            config_data = json.load(f)
    elif config_file.suffix.lower() in [".yml", ".yaml"]:
        with open(config_file, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported config file format: {config_file.suffix}")

    # Override with CLI parameters
    config_data.update({"prometheus_url": prometheus_url, "port": grafana_port})

    return GrafanaConfig(**config_data)


if __name__ == "__main__":
    app()
