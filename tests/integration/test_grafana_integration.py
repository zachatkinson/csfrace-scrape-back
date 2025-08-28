"""Integration tests for Grafana dashboard system."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.monitoring.dashboard_provisioner import GrafanaDashboardProvisioner
from src.monitoring.grafana import GrafanaConfig, GrafanaDashboardManager


class TestGrafanaIntegration:
    """Integration tests for complete Grafana dashboard workflow."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary configuration for integration tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config = GrafanaConfig(
                dashboards_dir=temp_path / "dashboards",
                provisioning_dir=temp_path / "provisioning",
                prometheus_url="http://test-prometheus:9090",
                port=3000,
                admin_user="test_admin",
                admin_password="test_password",
            )
            yield config

    def test_complete_dashboard_provisioning_workflow(self, temp_config):
        """Test complete workflow from configuration to dashboard files."""
        # Initialize provisioner
        provisioner = GrafanaDashboardProvisioner(temp_config)

        # Provision all dashboards
        with patch.object(provisioner, "_update_docker_compose"):  # Skip Docker Compose changes
            provisioner.provision_all_dashboards()

        # Verify dashboard files were created
        dashboard_files = list(temp_config.dashboards_dir.glob("*.json"))
        assert len(dashboard_files) == 3

        expected_files = [
            "system-overview.json",
            "application-metrics.json",
            "database-performance.json",
        ]

        actual_filenames = [f.name for f in dashboard_files]
        for expected_file in expected_files:
            assert expected_file in actual_filenames

        # Verify provisioning files were created
        dashboard_provisioning = temp_config.provisioning_dir / "dashboards" / "dashboards.yaml"
        datasource_provisioning = temp_config.provisioning_dir / "datasources" / "datasources.yaml"

        assert dashboard_provisioning.exists()
        assert datasource_provisioning.exists()

        # Verify Prometheus config was created
        prometheus_config = Path("prometheus.yml")
        assert prometheus_config.exists()

        # Cleanup
        prometheus_config.unlink()

    def test_dashboard_json_structure_validation(self, temp_config):
        """Test that generated dashboard JSON has valid structure."""
        manager = GrafanaDashboardManager(temp_config)

        # Generate all dashboard types
        dashboards = {
            "system": manager.generate_system_overview_dashboard(),
            "application": manager.generate_application_metrics_dashboard(),
            "database": manager.generate_database_dashboard(),
        }

        for dashboard_name, dashboard_config in dashboards.items():
            # Verify top-level structure
            assert "dashboard" in dashboard_config, f"{dashboard_name} missing dashboard key"

            dashboard = dashboard_config["dashboard"]

            # Verify required dashboard fields
            required_fields = ["title", "tags", "timezone", "refresh", "time", "panels"]
            for field in required_fields:
                assert field in dashboard, f"{dashboard_name} missing {field}"

            # Verify panels structure
            panels = dashboard["panels"]
            assert isinstance(panels, list), f"{dashboard_name} panels should be list"
            assert len(panels) > 0, f"{dashboard_name} should have panels"

            # Verify each panel structure
            for i, panel in enumerate(panels):
                panel_required = ["id", "title", "type", "gridPos"]
                for field in panel_required:
                    assert field in panel, f"{dashboard_name} panel {i} missing {field}"

                # Verify grid position
                grid_pos = panel["gridPos"]
                grid_required = ["h", "w", "x", "y"]
                for field in grid_required:
                    assert field in grid_pos, f"{dashboard_name} panel {i} gridPos missing {field}"
                    assert isinstance(grid_pos[field], int), (
                        f"{dashboard_name} panel {i} {field} should be int"
                    )

    def test_prometheus_query_validation(self, temp_config):
        """Test that Prometheus queries in dashboards are properly formatted."""
        manager = GrafanaDashboardManager(temp_config)

        # Generate dashboards
        dashboards = [
            manager.generate_system_overview_dashboard(),
            manager.generate_application_metrics_dashboard(),
            manager.generate_database_dashboard(),
        ]

        for dashboard_config in dashboards:
            panels = dashboard_config["dashboard"]["panels"]

            for panel in panels:
                if "targets" in panel:
                    targets = panel["targets"]
                    assert isinstance(targets, list), "Panel targets should be list"

                    for target in targets:
                        if "expr" in target:
                            # Verify basic Prometheus query structure
                            expr = target["expr"]
                            assert isinstance(expr, str), "Prometheus expression should be string"
                            assert len(expr.strip()) > 0, (
                                "Prometheus expression should not be empty"
                            )

                            # Verify required target fields
                            assert "refId" in target, "Target should have refId"
                            assert isinstance(target["refId"], str), "RefId should be string"

    def test_provisioning_config_structure(self, temp_config):
        """Test provisioning configuration files have correct structure."""
        manager = GrafanaDashboardManager(temp_config)

        # Test dashboard provisioning config
        dashboard_config = manager.create_provisioning_config()

        assert dashboard_config["apiVersion"] == 1
        assert "providers" in dashboard_config
        assert isinstance(dashboard_config["providers"], list)
        assert len(dashboard_config["providers"]) == 1

        provider = dashboard_config["providers"][0]
        required_provider_fields = ["name", "orgId", "type", "options"]
        for field in required_provider_fields:
            assert field in provider

        # Test datasource provisioning config
        datasource_config = manager.create_datasource_config()

        assert datasource_config["apiVersion"] == 1
        assert "datasources" in datasource_config
        assert isinstance(datasource_config["datasources"], list)
        assert len(datasource_config["datasources"]) == 1

        datasource = datasource_config["datasources"][0]
        required_datasource_fields = ["name", "type", "access", "url", "isDefault"]
        for field in required_datasource_fields:
            assert field in datasource

    def test_dashboard_validation_workflow(self, temp_config):
        """Test complete dashboard validation workflow."""
        provisioner = GrafanaDashboardProvisioner(temp_config)

        # First provision dashboards
        with patch.object(provisioner, "_update_docker_compose"):
            provisioner.provision_all_dashboards()

        # Then validate them
        validation_result = provisioner.validate_dashboards()
        assert validation_result is True

        # Verify each individual dashboard validates
        dashboard_files = list(temp_config.dashboards_dir.glob("*.json"))
        for dashboard_file in dashboard_files:
            individual_result = provisioner._validate_single_dashboard(dashboard_file)
            assert individual_result is True, f"Dashboard {dashboard_file.name} failed validation"

    def test_docker_compose_integration(self, temp_config):
        """Test Docker Compose service configuration generation."""
        provisioner = GrafanaDashboardProvisioner(temp_config)

        # Test Grafana service configuration
        grafana_config = provisioner._get_grafana_service_config()

        # Verify essential Docker service fields
        essential_fields = [
            "image",
            "container_name",
            "restart",
            "ports",
            "environment",
            "volumes",
            "networks",
        ]
        for field in essential_fields:
            assert field in grafana_config, f"Grafana service missing {field}"

        # Verify environment variables
        env = grafana_config["environment"]
        assert env["GF_SECURITY_ADMIN_USER"] == temp_config.admin_user
        assert env["GF_SECURITY_ADMIN_PASSWORD"] == temp_config.admin_password

        # Test Prometheus service configuration
        prometheus_config = provisioner._get_prometheus_service_config()

        for field in essential_fields:
            if field != "environment":  # Prometheus doesn't need custom environment
                assert field in prometheus_config, f"Prometheus service missing {field}"

        # Verify Prometheus command configuration
        assert "command" in prometheus_config
        command = prometheus_config["command"]
        assert "--config.file=/etc/prometheus/prometheus.yml" in command
        assert "--storage.tsdb.path=/prometheus" in command

    def test_prometheus_config_integration(self, temp_config):
        """Test Prometheus configuration file generation and structure."""
        provisioner = GrafanaDashboardProvisioner(temp_config)

        # Generate Prometheus config
        provisioner.create_prometheus_config()

        # Verify file was created
        prometheus_file = Path("prometheus.yml")
        assert prometheus_file.exists()

        # Load and verify structure
        with open(prometheus_file) as f:
            prometheus_config = yaml.safe_load(f)

        # Verify global configuration
        assert "global" in prometheus_config
        global_config = prometheus_config["global"]
        assert "scrape_interval" in global_config
        assert "evaluation_interval" in global_config

        # Verify scrape configuration
        assert "scrape_configs" in prometheus_config
        scrape_configs = prometheus_config["scrape_configs"]
        assert isinstance(scrape_configs, list)
        assert len(scrape_configs) >= 1

        # Verify CSFrace scraper job
        csfrace_job = next(
            (job for job in scrape_configs if job["job_name"] == "csfrace-scraper"), None
        )
        assert csfrace_job is not None, "CSFrace scraper job not found"

        assert "static_configs" in csfrace_job
        assert "scrape_interval" in csfrace_job
        assert "metrics_path" in csfrace_job

        # Cleanup
        prometheus_file.unlink()

    def test_error_recovery_integration(self, temp_config):
        """Test error recovery in complete workflow."""
        provisioner = GrafanaDashboardProvisioner(temp_config)

        # Test with invalid dashboard generation
        with patch.object(
            provisioner.dashboard_manager,
            "generate_system_overview_dashboard",
            side_effect=Exception("Dashboard generation failed"),
        ):
            with pytest.raises(Exception, match="Dashboard generation failed"):
                provisioner.provision_all_dashboards()

        # Verify system can recover and work with valid configuration
        with patch.object(provisioner, "_update_docker_compose"):
            provisioner.provision_all_dashboards()

        # Verify files were still created (for successful dashboards)
        dashboard_files = list(temp_config.dashboards_dir.glob("*.json"))
        # Should have 2 files since system overview failed but others succeeded
        assert len(dashboard_files) >= 1

    def test_concurrent_dashboard_generation(self, temp_config):
        """Test concurrent dashboard generation doesn't cause conflicts."""
        import threading

        results = []
        errors = []

        def generate_dashboard(dashboard_type):
            try:
                manager = GrafanaDashboardManager(temp_config)
                if dashboard_type == "system":
                    result = manager.generate_system_overview_dashboard()
                elif dashboard_type == "application":
                    result = manager.generate_application_metrics_dashboard()
                else:
                    result = manager.generate_database_dashboard()

                results.append((dashboard_type, result))
            except Exception as e:
                errors.append((dashboard_type, str(e)))

        # Create threads for concurrent generation
        threads = []
        dashboard_types = ["system", "application", "database"]

        for dashboard_type in dashboard_types:
            thread = threading.Thread(target=generate_dashboard, args=(dashboard_type,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent generation errors: {errors}"

        # Verify all dashboards were generated
        assert len(results) == 3

        # Verify each result is valid
        for dashboard_type, dashboard_config in results:
            assert "dashboard" in dashboard_config
            assert dashboard_config["dashboard"]["title"]
            assert len(dashboard_config["dashboard"]["panels"]) > 0

    def test_configuration_persistence(self, temp_config):
        """Test that configuration changes persist through workflow."""
        # Create provisioner with custom config
        custom_config = GrafanaConfig(
            dashboards_dir=temp_config.dashboards_dir,
            provisioning_dir=temp_config.provisioning_dir,
            prometheus_url="http://custom-prometheus:9999",
            port=8080,
            admin_user="custom_admin",
            admin_password="custom_password",
            refresh_interval="15s",
            time_range="2h",
        )

        provisioner = GrafanaDashboardProvisioner(custom_config)

        # Verify custom configuration is used in dashboard generation
        dashboard = provisioner.dashboard_manager.generate_system_overview_dashboard()
        dashboard_config = dashboard["dashboard"]

        assert dashboard_config["refresh"] == "15s"
        assert dashboard_config["time"]["from"] == "now-2h"

        # Verify custom configuration is used in Docker service
        grafana_service = provisioner._get_grafana_service_config()
        assert "8080:3000" in grafana_service["ports"]
        assert grafana_service["environment"]["GF_SECURITY_ADMIN_USER"] == "custom_admin"
        assert grafana_service["environment"]["GF_SECURITY_ADMIN_PASSWORD"] == "custom_password"

        # Verify custom configuration is used in datasource
        datasource_config = provisioner.dashboard_manager.create_datasource_config()
        datasource = datasource_config["datasources"][0]
        assert datasource["url"] == "http://custom-prometheus:9999"
