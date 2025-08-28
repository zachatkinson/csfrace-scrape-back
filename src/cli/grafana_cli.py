"""Command-line interface for Grafana dashboard management.

This module provides CLI commands for provisioning, validating, and managing
Grafana dashboards following CLAUDE.md standards.
"""

from pathlib import Path
from typing import Optional

import structlog
import typer

from ..monitoring import GrafanaConfig, GrafanaDashboardProvisioner

logger = structlog.get_logger(__name__)

app = typer.Typer(
    name="grafana", help="Manage Grafana dashboards and provisioning", no_args_is_help=True
)


@app.command()
def provision(
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to Grafana configuration file"
    ),
    prometheus_url: Optional[str] = typer.Option(
        "http://prometheus:9090", "--prometheus-url", "-p", help="Prometheus server URL"
    ),
    grafana_port: int = typer.Option(3000, "--port", help="Grafana server port"),
    output_dir: Optional[Path] = typer.Option(
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
    try:
        # Load configuration
        if config_file and config_file.exists():
            typer.echo(f"Loading configuration from {config_file}")
            # TODO: Implement config file loading
            config = GrafanaConfig()
        else:
            config = GrafanaConfig(prometheus_url=prometheus_url, port=grafana_port)

        if output_dir:
            config.dashboards_dir = output_dir / "dashboards"
            config.provisioning_dir = output_dir / "provisioning"

        # Check for existing files if not forcing
        if (
            not force
            and config.dashboards_dir.exists()
            and not typer.confirm(
                f"Dashboard directory {config.dashboards_dir} already exists. Continue?"
            )
        ):
            typer.echo("Provisioning cancelled.")
            raise typer.Abort()

        # Initialize provisioner
        provisioner = GrafanaDashboardProvisioner(config)

        typer.echo("🚀 Starting Grafana dashboard provisioning...")

        # Provision all dashboards
        provisioner.provision_all_dashboards()

        # Create Prometheus configuration
        provisioner.create_prometheus_config()

        typer.echo("✅ Dashboard provisioning completed successfully!")
        typer.echo(f"📁 Dashboards: {config.dashboards_dir}")
        typer.echo(f"⚙️  Provisioning: {config.provisioning_dir}")
        typer.echo("🐳 Docker Compose updated")
        typer.echo("\n🎯 Next steps:")
        typer.echo("   1. Run: docker-compose up -d")
        typer.echo(f"   2. Access Grafana: http://localhost:{config.port}")
        typer.echo(
            f"   3. Login: {config.admin_user}/<password from GRAFANA_ADMIN_PASSWORD env var>"
        )

    except Exception as e:
        logger.error("Dashboard provisioning failed", error=str(e))
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def validate(
    dashboards_dir: Optional[Path] = typer.Option(
        None, "--dashboards-dir", "-d", help="Directory containing dashboard JSON files"
    ),
) -> None:
    """Validate existing dashboard configurations.

    Performs comprehensive validation of dashboard JSON files including:
    - Structure validation
    - Panel configuration checks
    - Query syntax validation
    """
    try:
        config = GrafanaConfig()
        if dashboards_dir:
            config.dashboards_dir = dashboards_dir

        provisioner = GrafanaDashboardProvisioner(config)

        typer.echo(f"🔍 Validating dashboards in {config.dashboards_dir}")

        if provisioner.validate_dashboards():
            typer.echo("✅ All dashboards are valid!")
        else:
            typer.echo("❌ Some dashboards failed validation", err=True)
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Dashboard validation failed", error=str(e))
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show status of Grafana dashboards and services."""
    try:
        config = GrafanaConfig()

        typer.echo("📊 Grafana Dashboard Status")
        typer.echo("=" * 40)

        # Check dashboard files
        dashboard_files = (
            list(config.dashboards_dir.glob("*.json")) if config.dashboards_dir.exists() else []
        )
        typer.echo(f"📁 Dashboard files: {len(dashboard_files)}")

        if dashboard_files:
            for dashboard_file in dashboard_files:
                typer.echo(f"   - {dashboard_file.name}")

        # Check provisioning files
        provisioning_exists = config.provisioning_dir.exists()
        typer.echo(
            f"⚙️  Provisioning config: {'✅ Present' if provisioning_exists else '❌ Missing'}"
        )

        # Check Docker Compose
        docker_compose_exists = Path("docker-compose.yml").exists()
        typer.echo(f"🐳 Docker Compose: {'✅ Present' if docker_compose_exists else '❌ Missing'}")

        # Check Prometheus config
        prometheus_config_exists = Path("prometheus.yml").exists()
        typer.echo(
            f"📈 Prometheus config: {'✅ Present' if prometheus_config_exists else '❌ Missing'}"
        )

        # Service connectivity status (if services are running)
        typer.echo("\n🔗 Service Connectivity:")
        typer.echo("   (Run 'docker-compose ps' to check running services)")

    except Exception as e:
        logger.error("Status check failed", error=str(e))
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def clean(
    force: bool = typer.Option(False, "--force", "-f", help="Remove files without confirmation"),
) -> None:
    """Clean up generated dashboard and provisioning files."""
    try:
        config = GrafanaConfig()

        files_to_remove = []

        # Collect dashboard files
        if config.dashboards_dir.exists():
            dashboard_files = list(config.dashboards_dir.glob("*.json"))
            files_to_remove.extend(dashboard_files)

        # Collect provisioning files
        if config.provisioning_dir.exists():
            provisioning_files = list(config.provisioning_dir.rglob("*.yaml"))
            files_to_remove.extend(provisioning_files)

        # Include Docker and Prometheus configs
        for config_file in ["prometheus.yml"]:
            if Path(config_file).exists():
                files_to_remove.append(Path(config_file))

        if not files_to_remove:
            typer.echo("✅ No dashboard files to clean")
            return

        typer.echo(f"🗑️  Found {len(files_to_remove)} files to remove:")
        for file_path in files_to_remove:
            typer.echo(f"   - {file_path}")

        if not force and not typer.confirm("Proceed with cleanup?"):
            typer.echo("Cleanup cancelled.")
            return

        # Remove files
        removed_count = 0
        for file_path in files_to_remove:
            try:
                file_path.unlink()
                removed_count += 1
            except Exception as e:
                typer.echo(f"⚠️  Failed to remove {file_path}: {e}")

        # Remove empty directories
        for directory in [config.dashboards_dir, config.provisioning_dir]:
            try:
                if directory.exists() and not any(directory.iterdir()):
                    directory.rmdir()
            except Exception:
                pass  # Directory not empty or other issue

        typer.echo(f"✅ Cleaned up {removed_count} files")

    except Exception as e:
        logger.error("Cleanup failed", error=str(e))
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def init(
    output_dir: Path = typer.Option(
        Path("grafana"), "--output", "-o", help="Output directory for initialization"
    ),
) -> None:
    """Initialize Grafana configuration with example files."""
    try:
        typer.echo("🏗️  Initializing Grafana configuration...")

        # Create directory structure
        dashboards_dir = output_dir / "dashboards"
        provisioning_dir = output_dir / "provisioning"

        dashboards_dir.mkdir(parents=True, exist_ok=True)
        provisioning_dir.mkdir(parents=True, exist_ok=True)

        # Create example configuration file
        config_file = output_dir / "grafana-config.yaml"
        example_config = """# Grafana Configuration
enabled: true
host: localhost
port: 3000
protocol: http
prometheus_url: http://prometheus:9090
refresh_interval: 30s
time_range: 1h

# Security Note: Set these environment variables instead of hardcoding
# export GRAFANA_ADMIN_USER=admin
# export GRAFANA_ADMIN_PASSWORD=your-secure-password
"""

        with open(config_file, "w") as f:
            f.write(example_config)

        typer.echo(f"✅ Grafana configuration initialized in {output_dir}")
        typer.echo(f"📝 Edit {config_file} to customize settings")
        typer.echo(f"\n🎯 Next step: Run 'grafana provision -o {output_dir}'")

    except Exception as e:
        logger.error("Initialization failed", error=str(e))
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
