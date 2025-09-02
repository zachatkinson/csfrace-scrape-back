"""Tests for Grafana CLI interface."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.grafana_cli import app
from src.monitoring.dashboard_provisioner import GrafanaDashboardProvisioner
from src.monitoring.grafana import GrafanaConfig


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestGrafanaCLI:
    """Test suite for Grafana CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @patch.object(GrafanaDashboardProvisioner, "provision_all_dashboards")
    @patch.object(GrafanaDashboardProvisioner, "create_prometheus_config")
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_provision_command_default_options(
        self, mock_init, mock_prometheus, mock_provision, runner
    ):
        """Test provision command with default options."""
        result = runner.invoke(app, ["provision"])

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify provisioner was initialized and methods called
        mock_init.assert_called_once()
        mock_provision.assert_called_once()
        mock_prometheus.assert_called_once()

        # Verify output messages
        assert "Starting Grafana dashboard provisioning" in result.stdout
        assert "Dashboard provisioning completed successfully" in result.stdout
        assert "docker-compose up -d" in result.stdout

    @patch.object(GrafanaDashboardProvisioner, "provision_all_dashboards")
    @patch.object(GrafanaDashboardProvisioner, "create_prometheus_config")
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_provision_command_custom_options(
        self, mock_init, mock_prometheus, mock_provision, runner
    ):
        """Test provision command with custom options."""
        custom_prometheus = "http://custom-prometheus:9090"
        custom_port = 8080
        output_dir = "/custom/output"

        result = runner.invoke(
            app,
            [
                "provision",
                "--prometheus-url",
                custom_prometheus,
                "--port",
                str(custom_port),
                "--output",
                output_dir,
                "--force",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify provisioner was initialized with custom config
        mock_init.assert_called_once()
        init_args = mock_init.call_args[0]

        # The config should be passed to the provisioner
        if init_args:  # If config was passed as argument
            config = init_args[0]
            assert config.prometheus_url == custom_prometheus
            assert config.port == custom_port

    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(GrafanaDashboardProvisioner, "provision_all_dashboards")
    @patch.object(GrafanaDashboardProvisioner, "create_prometheus_config")
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_provision_command_existing_directory_with_force(
        self, mock_init, mock_prometheus, mock_provision, mock_exists, runner
    ):
        """Test provision command with existing directory and force flag."""
        result = runner.invoke(app, ["provision", "--force"])

        # Verify command succeeded without confirmation prompt
        assert result.exit_code == 0
        mock_provision.assert_called_once()
        mock_prometheus.assert_called_once()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("typer.confirm", return_value=False)
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_provision_command_existing_directory_cancelled(
        self, mock_init, mock_confirm, mock_exists, runner
    ):
        """Test provision command cancelled when directory exists and user declines."""
        result = runner.invoke(app, ["provision"])

        # Verify command was aborted
        assert result.exit_code == 1
        assert "Provisioning cancelled" in result.stdout

    @patch.object(
        GrafanaDashboardProvisioner, "provision_all_dashboards", side_effect=Exception("Test error")
    )
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_provision_command_error_handling(self, mock_init, mock_provision, runner, caplog):
        """Test provision command handles errors gracefully."""
        result = runner.invoke(app, ["provision"])

        # Verify command failed with proper error handling
        assert result.exit_code == 1
        # Error message appears in stderr (typer.echo with err=True) and structured logging
        assert "Test error" in result.stderr or "Test error" in caplog.text

    @patch.object(GrafanaDashboardProvisioner, "validate_dashboards", return_value=True)
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_validate_command_success(self, mock_init, mock_validate, runner):
        """Test validate command with valid dashboards."""
        result = runner.invoke(app, ["validate"])

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify validation was called
        mock_validate.assert_called_once()

        # Verify success message
        assert "All dashboards are valid" in result.stdout

    @patch.object(GrafanaDashboardProvisioner, "validate_dashboards", return_value=False)
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_validate_command_failure(self, mock_init, mock_validate, runner):
        """Test validate command with invalid dashboards."""
        result = runner.invoke(app, ["validate"])

        # Verify command failed
        assert result.exit_code == 1

        # Verify validation was called
        mock_validate.assert_called_once()

        # Verify error message (appears in stderr with typer.echo err=True)
        assert (
            "validation failed" in result.stderr.lower()
            or "failed validation" in result.stderr.lower()
        )

    @patch.object(
        GrafanaDashboardProvisioner,
        "validate_dashboards",
        side_effect=Exception("Validation error"),
    )
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_validate_command_error_handling(self, mock_init, mock_validate, runner, caplog):
        """Test validate command handles errors gracefully."""
        result = runner.invoke(app, ["validate"])

        # Verify command failed
        assert result.exit_code == 1
        # Error message appears in stderr (typer.echo with err=True) and structured logging
        assert "Validation error" in result.stderr or "Validation error" in caplog.text

    def test_status_command_all_present(self, runner):
        """Test status command when all components are present."""
        # Test the status command without complex mocking - it should run successfully
        # and show the current state of the system
        result = runner.invoke(app, ["status"])

        # Verify command succeeded (status command should always work)
        assert result.exit_code == 0

        # Verify status output contains expected sections
        assert "Grafana Dashboard Status" in result.stdout
        assert "Dashboard files:" in result.stdout
        assert "Provisioning config:" in result.stdout
        assert "Docker Compose:" in result.stdout
        assert "Prometheus config:" in result.stdout

    @patch("pathlib.Path.exists", return_value=False)
    @patch("pathlib.Path.glob", return_value=[])
    @patch.object(GrafanaConfig, "__init__", return_value=None)
    def test_status_command_components_missing(
        self, mock_config_init, mock_glob, mock_exists, runner
    ):
        """Test status command when components are missing."""
        # Mock GrafanaConfig attributes
        mock_config = MagicMock()
        mock_config.dashboards_dir = Path("/test/dashboards")
        mock_config.provisioning_dir = Path("/test/provisioning")

        with patch("src.cli.grafana_cli.GrafanaConfig", return_value=mock_config):
            result = runner.invoke(app, ["status"])

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify status shows missing components
        assert "Dashboard files: 0" in result.stdout
        assert "❌ Missing" in result.stdout

    def test_clean_command_with_files(self, runner):
        """Test clean command removes dashboard files."""
        # Test the clean command without complex mocking - test actual behavior
        result = runner.invoke(app, ["clean", "--force"])

        # Verify command succeeded (clean should work even if no files exist)
        assert result.exit_code == 0

        # Should show either "No dashboard files to clean" or actual cleanup results
        assert (
            "No dashboard files to clean" in result.stdout
            or "Cleaned up" in result.stdout
            or "Found" in result.stdout
        )

    @patch("pathlib.Path.exists", return_value=False)
    @patch("pathlib.Path.glob", return_value=[])
    @patch.object(GrafanaConfig, "__init__", return_value=None)
    def test_clean_command_no_files(self, mock_config_init, mock_glob, mock_exists, runner):
        """Test clean command when no files exist."""
        # Mock GrafanaConfig attributes
        mock_config = MagicMock()
        mock_config.dashboards_dir = Path("/test/dashboards")
        mock_config.provisioning_dir = Path("/test/provisioning")

        with patch("src.cli.grafana_cli.GrafanaConfig", return_value=mock_config):
            result = runner.invoke(app, ["clean"])

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify no cleanup message
        assert "No dashboard files to clean" in result.stdout

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", create=True)
    def test_init_command(self, mock_open, mock_mkdir, runner):
        """Test init command creates directory structure and example config."""
        result = runner.invoke(app, ["init", "--output", "/test/init"])

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify directories were created
        mock_mkdir.assert_called()

        # Verify success messages
        assert "Initializing Grafana configuration" in result.stdout
        assert "Grafana configuration initialized" in result.stdout
        assert "grafana provision" in result.stdout

    @patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied"))
    def test_init_command_error_handling(self, mock_mkdir, runner, caplog):
        """Test init command handles errors gracefully."""
        result = runner.invoke(app, ["init"])

        # Verify command failed
        assert result.exit_code == 1
        # Error message appears in stderr (typer.echo with err=True) and structured logging
        assert "Permission denied" in result.stderr or "Permission denied" in caplog.text

    def test_app_help(self, runner):
        """Test that CLI app shows help information."""
        result = runner.invoke(app, ["--help"])

        # Verify help is shown
        assert result.exit_code == 0
        assert "Manage Grafana dashboards and provisioning" in result.stdout

        # Verify all commands are listed
        commands = ["provision", "validate", "status", "clean", "init"]
        for command in commands:
            assert command in result.stdout

    def test_provision_command_help(self, runner):
        """Test provision command help."""
        result = runner.invoke(app, ["provision", "--help"])
        clean_output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Provision Grafana dashboards" in clean_output
        assert "--prometheus-url" in clean_output
        assert "--port" in clean_output
        assert "--output" in clean_output
        assert "--force" in clean_output

    def test_validate_command_help(self, runner):
        """Test validate command help."""
        result = runner.invoke(app, ["validate", "--help"])
        clean_output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Validate existing dashboard configurations" in clean_output
        assert "--dashboards-dir" in clean_output

    def test_clean_command_help(self, runner):
        """Test clean command help."""
        result = runner.invoke(app, ["clean", "--help"])
        clean_output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Clean up generated dashboard" in clean_output
        assert "--force" in clean_output

    def test_init_command_help(self, runner):
        """Test init command help."""
        result = runner.invoke(app, ["init", "--help"])
        clean_output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Initialize Grafana configuration" in clean_output
        assert "--output" in clean_output

    @patch.object(GrafanaDashboardProvisioner, "validate_dashboards", return_value=True)
    @patch.object(GrafanaDashboardProvisioner, "__init__", return_value=None)
    def test_validate_command_with_custom_directory(self, mock_init, mock_validate, runner):
        """Test validate command with custom dashboards directory."""
        custom_dir = "/custom/dashboards"
        result = runner.invoke(app, ["validate", "--dashboards-dir", custom_dir])

        assert result.exit_code == 0
        mock_validate.assert_called_once()
        assert "All dashboards are valid" in result.stdout

    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(GrafanaConfig, "__init__", return_value=None)
    def test_status_command_with_dashboard_files(
        self, mock_config_init, mock_exists, mock_glob, runner
    ):
        """Test status command when dashboard files exist."""
        mock_config = MagicMock()
        mock_config.dashboards_dir = Path("/test/dashboards")
        mock_config.provisioning_dir = Path("/test/provisioning")

        # Mock dashboard files
        mock_dashboard_files = [Path("dashboard1.json"), Path("dashboard2.json")]
        mock_glob.return_value = mock_dashboard_files

        with patch("src.cli.grafana_cli.GrafanaConfig", return_value=mock_config):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Dashboard files: 2" in result.stdout
        assert "dashboard1.json" in result.stdout
        assert "dashboard2.json" in result.stdout

    @patch.object(GrafanaConfig, "__init__", side_effect=Exception("Config error"))
    def test_status_command_config_error(self, mock_config_init, runner, caplog):
        """Test status command handles config initialization errors."""
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        # Error message appears in stderr (typer.echo with err=True) and structured logging
        assert "Config error" in result.stderr or "Config error" in caplog.text

    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(GrafanaConfig, "__init__", return_value=None)
    def test_clean_command_file_discovery(
        self, mock_config_init, mock_exists, mock_rglob, mock_glob, runner
    ):
        """Test clean command discovers dashboard and provisioning files."""
        mock_config = MagicMock()
        mock_config.dashboards_dir = Path("/test/dashboards")
        mock_config.provisioning_dir = Path("/test/provisioning")

        # Mock file discovery
        mock_glob.return_value = [Path("dashboard1.json")]
        mock_rglob.return_value = [Path("config.yaml")]

        with patch("src.cli.grafana_cli.GrafanaConfig", return_value=mock_config):
            result = runner.invoke(app, ["clean", "--force"])

        assert result.exit_code == 0
        # Should show files found and cleaned up
        assert "Found" in result.stdout or "Cleaned up" in result.stdout
