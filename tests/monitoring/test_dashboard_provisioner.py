"""Tests for Grafana dashboard provisioning system."""

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.monitoring.dashboard_provisioner import GrafanaDashboardProvisioner
from src.monitoring.grafana import GrafanaConfig, GrafanaDashboardManager


class TestGrafanaDashboardProvisioner:
    """Test suite for GrafanaDashboardProvisioner."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return GrafanaConfig(
            dashboards_dir=Path("/test/dashboards"),
            provisioning_dir=Path("/test/provisioning"),
            prometheus_url="http://test-prometheus:9090",
            port=3000,
            admin_user="test_admin",
            admin_password="test_password",
        )

    @pytest.fixture
    def provisioner(self, config):
        """Create provisioner with test configuration."""
        with (
            patch.object(Path, "mkdir"),
            patch.object(GrafanaDashboardProvisioner, "_validate_config"),
        ):
            return GrafanaDashboardProvisioner(config)

    def test_provisioner_initialization_with_config(self, config):
        """Test provisioner initializes with provided config."""
        with (
            patch.object(Path, "mkdir"),
            patch.object(GrafanaDashboardProvisioner, "_validate_config") as mock_validate,
        ):
            provisioner = GrafanaDashboardProvisioner(config)

            assert provisioner.config == config
            assert isinstance(provisioner.dashboard_manager, GrafanaDashboardManager)
            mock_validate.assert_called_once()

    def test_provisioner_initialization_default_config(self):
        """Test provisioner initializes with default config when none provided."""
        with (
            patch.object(Path, "mkdir"),
            patch.object(GrafanaDashboardProvisioner, "_validate_config"),
        ):
            provisioner = GrafanaDashboardProvisioner()

            assert isinstance(provisioner.config, GrafanaConfig)
            assert provisioner.config.enabled is True

    def test_validate_config_success(self, config):
        """Test configuration validation passes with valid config."""
        with patch.object(Path, "mkdir"):
            # Should not raise any exceptions
            provisioner = GrafanaDashboardProvisioner(config)
            provisioner._validate_config()

    def test_validate_config_missing_prometheus_url(self):
        """Test configuration validation fails without Prometheus URL."""
        config = GrafanaConfig(prometheus_url="")

        with (
            patch.object(Path, "mkdir"),
            pytest.raises(ValueError, match="Prometheus URL is required"),
        ):
            GrafanaDashboardProvisioner(config)

    def test_validate_config_missing_directories(self):
        """Test configuration validation fails without required directories."""
        config = GrafanaConfig(dashboards_dir=None, provisioning_dir=Path("/test/provisioning"))

        with (
            patch.object(Path, "mkdir"),
            pytest.raises(
                ValueError, match="Dashboard and provisioning directories must be configured"
            ),
        ):
            GrafanaDashboardProvisioner(config)

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_write_dashboard_file(self, mock_json_dump, mock_file, provisioner):
        """Test dashboard file writing with proper JSON formatting."""
        dashboard_config = {"dashboard": {"title": "Test Dashboard", "panels": []}}

        provisioner._write_dashboard_file("test-dashboard.json", dashboard_config)

        # Verify file was opened correctly
        expected_path = provisioner.config.dashboards_dir / "test-dashboard.json"
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")

        # Verify JSON dump was called with proper formatting
        mock_json_dump.assert_called_once_with(
            dashboard_config,
            mock_file.return_value.__enter__.return_value,
            indent=2,
            ensure_ascii=False,
        )

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_write_dashboard_file_error_handling(self, mock_file, provisioner):
        """Test dashboard file writing handles errors properly."""
        dashboard_config = {"dashboard": {"title": "Test"}}

        with pytest.raises(OSError):
            provisioner._write_dashboard_file("test.json", dashboard_config)

    @patch.object(GrafanaDashboardProvisioner, "_write_dashboard_file")
    @patch.object(GrafanaDashboardProvisioner, "_create_provisioning_files")
    @patch.object(GrafanaDashboardProvisioner, "_update_docker_compose")
    def test_provision_all_dashboards(
        self, mock_docker, mock_provisioning, mock_write, provisioner
    ):
        """Test complete dashboard provisioning workflow."""
        # Mock dashboard manager methods
        provisioner.dashboard_manager.generate_system_overview_dashboard = Mock(
            return_value={"test": "system"}
        )
        provisioner.dashboard_manager.generate_application_metrics_dashboard = Mock(
            return_value={"test": "app"}
        )
        provisioner.dashboard_manager.generate_database_dashboard = Mock(
            return_value={"test": "db"}
        )

        provisioner.provision_all_dashboards()

        # Verify all dashboard generation methods were called
        provisioner.dashboard_manager.generate_system_overview_dashboard.assert_called_once()
        provisioner.dashboard_manager.generate_application_metrics_dashboard.assert_called_once()
        provisioner.dashboard_manager.generate_database_dashboard.assert_called_once()

        # Verify all dashboard files were written
        expected_calls = [
            ("system-overview.json", {"test": "system"}),
            ("application-metrics.json", {"test": "app"}),
            ("database-performance.json", {"test": "db"}),
        ]
        for filename, config in expected_calls:
            mock_write.assert_any_call(filename, config)

        # Verify provisioning and docker steps were called
        mock_provisioning.assert_called_once()
        mock_docker.assert_called_once()

    @patch.object(
        GrafanaDashboardProvisioner, "_write_dashboard_file", side_effect=Exception("Write error")
    )
    def test_provision_all_dashboards_error_handling(self, mock_write, provisioner):
        """Test dashboard provisioning handles errors gracefully."""
        # Mock dashboard manager methods
        provisioner.dashboard_manager.generate_system_overview_dashboard = Mock(
            return_value={"test": "system"}
        )

        with pytest.raises(Exception, match="Write error"):
            provisioner.provision_all_dashboards()

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    def test_create_provisioning_files(self, mock_yaml_dump, mock_file, provisioner):
        """Test provisioning configuration files creation."""
        # Mock dashboard manager methods
        provisioner.dashboard_manager.create_provisioning_config = Mock(
            return_value={"test": "provisioning"}
        )
        provisioner.dashboard_manager.create_datasource_config = Mock(
            return_value={"test": "datasource"}
        )

        provisioner._create_provisioning_files()

        # Verify both configuration methods were called
        provisioner.dashboard_manager.create_provisioning_config.assert_called_once()
        provisioner.dashboard_manager.create_datasource_config.assert_called_once()

        # Verify both files were opened
        expected_dashboard_path = (
            provisioner.config.provisioning_dir / "dashboards" / "dashboards.yaml"
        )
        expected_datasource_path = (
            provisioner.config.provisioning_dir / "datasources" / "datasources.yaml"
        )

        mock_file.assert_any_call(expected_dashboard_path, "w", encoding="utf-8")
        mock_file.assert_any_call(expected_datasource_path, "w", encoding="utf-8")

        # Verify YAML dump was called twice
        assert mock_yaml_dump.call_count == 2

    @patch("pathlib.Path.exists", return_value=False)
    @patch.object(GrafanaDashboardProvisioner, "_create_docker_compose")
    def test_update_docker_compose_new_file(self, mock_create, mock_exists, provisioner):
        """Test Docker Compose update creates new file when none exists."""
        provisioner._update_docker_compose()

        mock_create.assert_called_once()

    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(GrafanaDashboardProvisioner, "_add_grafana_to_existing_compose")
    def test_update_docker_compose_existing_file(self, mock_add, mock_exists, provisioner):
        """Test Docker Compose update modifies existing file."""
        provisioner._update_docker_compose()

        mock_add.assert_called_once()

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    def test_create_docker_compose(self, mock_yaml_dump, mock_file, provisioner):
        """Test new Docker Compose file creation."""
        provisioner._create_docker_compose()

        # Verify file was created
        mock_file.assert_called_once_with("docker-compose.yml", "w", encoding="utf-8")

        # Verify YAML was written
        mock_yaml_dump.assert_called_once()

        # Get the actual configuration that was written
        written_config = mock_yaml_dump.call_args[0][0]

        # Verify structure
        assert written_config["version"] == "3.8"
        assert "grafana" in written_config["services"]
        assert "prometheus" in written_config["services"]
        assert "grafana_data" in written_config["volumes"]
        assert "prometheus_data" in written_config["volumes"]
        assert "monitoring" in written_config["networks"]

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='version: "3.8"\nservices:\n  app:\n    image: nginx',
    )
    @patch("yaml.safe_load")
    @patch("yaml.dump")
    def test_add_grafana_to_existing_compose(
        self, mock_yaml_dump, mock_yaml_load, mock_file, provisioner
    ):
        """Test adding Grafana to existing Docker Compose file."""
        # Mock existing compose config
        existing_config = {"version": "3.8", "services": {"app": {"image": "nginx"}}}
        mock_yaml_load.return_value = existing_config

        provisioner._add_grafana_to_existing_compose()

        # Verify file was read and written
        assert mock_file.call_count == 2  # One read, one write
        mock_yaml_load.assert_called_once()
        mock_yaml_dump.assert_called_once()

        # Get the updated configuration
        updated_config = mock_yaml_dump.call_args[0][0]

        # Verify Grafana and Prometheus were added
        assert "grafana" in updated_config["services"]
        assert "prometheus" in updated_config["services"]
        assert "app" in updated_config["services"]  # Original service preserved

        # Verify volumes and networks were added
        assert "grafana_data" in updated_config["volumes"]
        assert "prometheus_data" in updated_config["volumes"]
        assert "monitoring" in updated_config["networks"]

        # Verify existing services got monitoring network
        assert "monitoring" in updated_config["services"]["app"]["networks"]

    def test_get_grafana_service_config(self, provisioner):
        """Test Grafana service configuration generation."""
        service_config = provisioner._get_grafana_service_config()

        # Verify basic service configuration
        assert service_config["image"] == "grafana/grafana:latest"
        assert service_config["container_name"] == "csfrace-grafana"
        assert service_config["restart"] == "unless-stopped"

        # Verify port mapping
        expected_port = f"{provisioner.config.port}:3000"
        assert expected_port in service_config["ports"]

        # Verify environment variables
        env = service_config["environment"]
        assert env["GF_SECURITY_ADMIN_USER"] == provisioner.config.admin_user
        assert env["GF_SECURITY_ADMIN_PASSWORD"] == provisioner.config.admin_password
        assert env["GF_USERS_ALLOW_SIGN_UP"] == "false"

        # Verify volumes
        volumes = service_config["volumes"]
        assert "grafana_data:/var/lib/grafana" in volumes
        assert f"{provisioner.config.provisioning_dir}:/etc/grafana/provisioning" in volumes

        # Verify networking and dependencies
        assert "monitoring" in service_config["networks"]
        assert "prometheus" in service_config["depends_on"]

        # Verify health check
        assert "healthcheck" in service_config
        health_check = service_config["healthcheck"]
        assert "curl -f http://localhost:3000/api/health" in health_check["test"][1]

    def test_get_prometheus_service_config(self, provisioner):
        """Test Prometheus service configuration generation."""
        service_config = provisioner._get_prometheus_service_config()

        # Verify basic configuration
        assert service_config["image"] == "prom/prometheus:latest"
        assert service_config["container_name"] == "csfrace-prometheus"
        assert service_config["restart"] == "unless-stopped"

        # Verify command line arguments
        command = service_config["command"]
        assert "--config.file=/etc/prometheus/prometheus.yml" in command
        assert "--storage.tsdb.path=/prometheus" in command
        assert "--storage.tsdb.retention.time=15d" in command
        assert "--web.enable-lifecycle" in command

        # Verify port mapping
        assert "9090:9090" in service_config["ports"]

        # Verify volumes
        volumes = service_config["volumes"]
        assert "./prometheus.yml:/etc/prometheus/prometheus.yml" in volumes
        assert "prometheus_data:/prometheus" in volumes

        # Verify health check
        health_check = service_config["healthcheck"]
        assert (
            "wget --no-verbose --tries=1 --spider http://localhost:9090/" in health_check["test"][1]
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    def test_create_prometheus_config(self, mock_yaml_dump, mock_file, provisioner):
        """Test Prometheus configuration file creation."""
        provisioner.create_prometheus_config()

        # Verify file was created
        mock_file.assert_called_once_with("prometheus.yml", "w", encoding="utf-8")

        # Verify YAML was written
        mock_yaml_dump.assert_called_once()

        # Get the actual configuration
        prometheus_config = mock_yaml_dump.call_args[0][0]

        # Verify global configuration
        assert prometheus_config["global"]["scrape_interval"] == "15s"
        assert prometheus_config["global"]["evaluation_interval"] == "15s"

        # Verify scrape configuration
        scrape_configs = prometheus_config["scrape_configs"]
        assert len(scrape_configs) == 1

        scraper_config = scrape_configs[0]
        assert scraper_config["job_name"] == "csfrace-scraper"
        assert scraper_config["scrape_interval"] == "5s"
        assert scraper_config["metrics_path"] == "/health/prometheus"

        # Verify target configuration
        static_configs = scraper_config["static_configs"]
        assert len(static_configs) == 1
        assert "host.docker.internal:9090" in static_configs[0]["targets"]

    @patch("pathlib.Path.glob")
    @patch.object(GrafanaDashboardProvisioner, "_validate_single_dashboard")
    def test_validate_dashboards_success(self, mock_validate_single, mock_glob, provisioner):
        """Test dashboard validation with all valid dashboards."""
        # Mock dashboard files
        mock_dashboard_files = [
            Path("/test/dashboards/dashboard1.json"),
            Path("/test/dashboards/dashboard2.json"),
        ]
        mock_glob.return_value = mock_dashboard_files
        mock_validate_single.return_value = True

        result = provisioner.validate_dashboards()

        # Verify validation was called for each file
        assert mock_validate_single.call_count == 2
        for dashboard_file in mock_dashboard_files:
            mock_validate_single.assert_any_call(dashboard_file)

        # Verify success result
        assert result is True

    @patch("pathlib.Path.glob")
    @patch.object(GrafanaDashboardProvisioner, "_validate_single_dashboard")
    def test_validate_dashboards_failure(self, mock_validate_single, mock_glob, provisioner):
        """Test dashboard validation with some invalid dashboards."""
        mock_dashboard_files = [
            Path("/test/dashboards/valid.json"),
            Path("/test/dashboards/invalid.json"),
        ]
        mock_glob.return_value = mock_dashboard_files
        # First validation succeeds, second fails
        mock_validate_single.side_effect = [True, False]

        result = provisioner.validate_dashboards()

        # Verify validation was called for each file
        assert mock_validate_single.call_count == 2

        # Verify failure result
        assert result is False

    @patch("pathlib.Path.glob", return_value=[])
    def test_validate_dashboards_no_files(self, mock_glob, provisioner):
        """Test dashboard validation with no dashboard files."""
        result = provisioner.validate_dashboards()

        assert result is False

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"dashboard": {"title": "Test", "panels": []}}',
    )
    @patch("json.load")
    def test_validate_single_dashboard_success(self, mock_json_load, mock_file, provisioner):
        """Test single dashboard validation success."""
        dashboard_config = {
            "dashboard": {
                "title": "Test Dashboard",
                "panels": [{"id": 1, "title": "Panel 1", "type": "stat"}],
            }
        }
        mock_json_load.return_value = dashboard_config

        result = provisioner._validate_single_dashboard(Path("/test/dashboard.json"))

        assert result is True
        mock_file.assert_called_once()
        mock_json_load.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data='{"invalid": "json"}')
    @patch("json.load")
    def test_validate_single_dashboard_missing_dashboard_key(
        self, mock_json_load, mock_file, provisioner
    ):
        """Test single dashboard validation fails with missing dashboard key."""
        mock_json_load.return_value = {"invalid": "structure"}

        result = provisioner._validate_single_dashboard(Path("/test/dashboard.json"))

        assert result is False

    @patch("builtins.open", new_callable=mock_open, read_data='{"dashboard": {}}')
    @patch("json.load")
    def test_validate_single_dashboard_missing_required_fields(
        self, mock_json_load, mock_file, provisioner
    ):
        """Test single dashboard validation fails with missing required fields."""
        mock_json_load.return_value = {"dashboard": {}}

        result = provisioner._validate_single_dashboard(Path("/test/dashboard.json"))

        assert result is False

    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_validate_single_dashboard_invalid_json(self, mock_file, provisioner):
        """Test single dashboard validation handles invalid JSON."""
        result = provisioner._validate_single_dashboard(Path("/test/dashboard.json"))

        assert result is False
