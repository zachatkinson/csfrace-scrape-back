"""Tests for Grafana dashboard management functionality."""
# pylint: disable=protected-access,use-implicit-booleaness-not-comparison,line-too-long

from pathlib import Path
from unittest.mock import patch

import pytest

from src.constants import CONSTANTS
from src.monitoring.grafana import GrafanaConfig, GrafanaDashboardManager


class TestGrafanaConfig:
    """Test suite for GrafanaConfig dataclass."""

    def test_grafana_config_defaults(self):
        """Test GrafanaConfig creates with proper defaults."""
        config = GrafanaConfig()

        assert config.enabled is True
        assert config.host == "localhost"
        assert config.port == 3000
        assert config.protocol == "http"
        assert config.admin_user == "admin"
        assert config.admin_password == "CHANGE_ME_IN_PRODUCTION"  # Security-conscious default
        assert config.prometheus_url == "http://prometheus:9090"
        assert config.refresh_interval == "30s"
        assert config.time_range == "1h"
        assert config.custom_labels == {}

        # Check path defaults
        expected_base = Path(CONSTANTS.DEFAULT_OUTPUT_DIR) / "grafana"
        assert config.dashboards_dir == expected_base / "dashboards"
        assert config.provisioning_dir == expected_base / "provisioning"

    def test_grafana_config_custom_values(self):
        """Test GrafanaConfig with custom values."""
        custom_dashboards = Path("/custom/dashboards")
        custom_provisioning = Path("/custom/provisioning")
        custom_labels = {"env": "production", "team": "platform"}

        config = GrafanaConfig(
            enabled=False,
            host="grafana.example.com",
            port=8080,
            protocol="https",
            admin_user="admin123",
            admin_password="secure_password",
            dashboards_dir=custom_dashboards,
            provisioning_dir=custom_provisioning,
            prometheus_url="http://prometheus.internal:9090",
            refresh_interval="15s",
            time_range="6h",
            custom_labels=custom_labels,
        )

        assert config.enabled is False
        assert config.host == "grafana.example.com"
        assert config.port == 8080
        assert config.protocol == "https"
        assert config.admin_user == "admin123"
        assert config.admin_password == "secure_password"
        assert config.dashboards_dir == custom_dashboards
        assert config.provisioning_dir == custom_provisioning
        assert config.prometheus_url == "http://prometheus.internal:9090"
        assert config.refresh_interval == "15s"
        assert config.time_range == "6h"
        assert config.custom_labels == custom_labels

    def test_grafana_config_mutable(self):
        """Test GrafanaConfig is mutable (Pydantic BaseSettings design)."""
        config = GrafanaConfig()

        # Pydantic BaseSettings are mutable by design for configuration flexibility
        original_enabled = config.enabled
        original_port = config.port

        config.enabled = False
        config.port = 8080

        assert config.enabled is False
        assert config.port == 8080

        # Restore for other tests
        config.enabled = original_enabled
        config.port = original_port


class TestGrafanaDashboardManager:
    """Test suite for GrafanaDashboardManager."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return GrafanaConfig(
            dashboards_dir=Path("/test/dashboards"),
            provisioning_dir=Path("/test/provisioning"),
            prometheus_url="http://test-prometheus:9090",
        )

    @pytest.fixture
    def manager(self, config):
        """Create dashboard manager with test configuration."""
        with patch.object(Path, "mkdir"):
            return GrafanaDashboardManager(config)

    def test_dashboard_manager_initialization(self, config):
        """Test dashboard manager initializes correctly."""
        with patch.object(Path, "mkdir") as mock_mkdir:
            manager = GrafanaDashboardManager(config)

            assert manager.config == config
            assert manager._dashboard_templates == {}

            # Verify directories are created
            mock_mkdir.assert_any_call(parents=True, exist_ok=True)

    def test_dashboard_manager_default_config(self):
        """Test dashboard manager with default configuration."""
        with patch.object(Path, "mkdir"):
            manager = GrafanaDashboardManager()

            assert isinstance(manager.config, GrafanaConfig)
            assert manager.config.enabled is True

    def test_ensure_directories_called(self, config):
        """Test that directories are properly created."""
        with patch.object(Path, "mkdir") as mock_mkdir:
            GrafanaDashboardManager(config)

            # Verify directories were created
            mkdir_calls = mock_mkdir.call_args_list
            assert (
                len(mkdir_calls) == 4
            )  # dashboards, provisioning, dashboards subdir, datasources subdir

            # First two calls should be main directories with parents=True
            main_dir_calls = mkdir_calls[:2]
            for call in main_dir_calls:
                assert call.kwargs.get("parents") is True
                assert call.kwargs.get("exist_ok") is True

            # Last two calls should be subdirectories with only exist_ok=True
            subdir_calls = mkdir_calls[2:]
            for call in subdir_calls:
                assert call.kwargs.get("exist_ok") is True
                assert "parents" not in call.kwargs or call.kwargs.get("parents") is None

    def test_generate_system_overview_dashboard(self, manager):
        """Test system overview dashboard generation following USE methodology."""
        dashboard = manager.generate_system_overview_dashboard()

        # Verify overall structure
        assert "dashboard" in dashboard
        dash_config = dashboard["dashboard"]

        # Verify basic properties
        assert dash_config["title"] == "CSFrace Scraper - System Overview"
        assert "csfrace" in dash_config["tags"]
        assert "system" in dash_config["tags"]
        assert "overview" in dash_config["tags"]
        assert dash_config["timezone"] == "browser"
        assert dash_config["refresh"] == manager.config.refresh_interval

        # Verify time configuration
        time_config = dash_config["time"]
        assert time_config["from"] == f"now-{manager.config.time_range}"
        assert time_config["to"] == "now"

        # Verify panels exist (USE methodology)
        panels = dash_config["panels"]
        assert len(panels) == 6  # CPU, Memory, Disk, Network, Load, Errors

        # Verify each panel has required fields
        for panel in panels:
            assert "id" in panel
            assert "title" in panel
            assert "type" in panel
            assert "gridPos" in panel

        # Verify specific USE methodology panels
        panel_titles = [panel["title"] for panel in panels]
        assert "CPU Utilization" in panel_titles  # Utilization
        assert "Memory Utilization" in panel_titles  # Utilization
        assert "System Load Average" in panel_titles  # Saturation
        assert "Error Rate" in panel_titles  # Errors

    def test_generate_application_metrics_dashboard(self, manager):
        """Test application metrics dashboard generation following RED methodology."""
        dashboard = manager.generate_application_metrics_dashboard()

        # Verify overall structure
        assert "dashboard" in dashboard
        dash_config = dashboard["dashboard"]

        # Verify basic properties
        assert dash_config["title"] == "CSFrace Scraper - Application Metrics"
        assert "csfrace" in dash_config["tags"]
        assert "application" in dash_config["tags"]
        assert "performance" in dash_config["tags"]

        # Verify panels exist (RED methodology)
        panels = dash_config["panels"]
        assert len(panels) == 6  # Rate, Duration, Errors, Active, Batch, Cache

        # Verify specific RED methodology panels
        panel_titles = [panel["title"] for panel in panels]
        assert "Request Rate" in panel_titles  # Rate
        assert "Request Duration" in panel_titles  # Duration
        assert "Error Rate" in panel_titles  # Errors
        assert "Active Requests" in panel_titles

    def test_generate_database_dashboard(self, manager):
        """Test database performance dashboard generation."""
        dashboard = manager.generate_database_dashboard()

        # Verify overall structure
        assert "dashboard" in dashboard
        dash_config = dashboard["dashboard"]

        # Verify basic properties
        assert dash_config["title"] == "CSFrace Scraper - Database Performance"
        assert "csfrace" in dash_config["tags"]
        assert "database" in dash_config["tags"]
        assert "postgresql" in dash_config["tags"]

        # Verify panels exist
        panels = dash_config["panels"]
        assert len(panels) == 4  # Connections, Duration, Queries, Jobs

        # Verify database-specific panels
        panel_titles = [panel["title"] for panel in panels]
        assert "Database Connections" in panel_titles
        assert "Query Duration" in panel_titles
        assert "Queries per Second" in panel_titles
        assert "Job Status Distribution" in panel_titles

    def test_cpu_utilization_panel_structure(self, manager):
        """Test CPU utilization panel follows Grafana best practices."""
        panel = manager._create_cpu_utilization_panel()

        # Verify basic panel structure
        assert panel["id"] == 1
        assert panel["title"] == "CPU Utilization"
        assert panel["type"] == "stat"

        # Verify targets
        targets = panel["targets"]
        assert len(targets) == 1
        assert targets[0]["expr"] == "system_cpu_percent"
        assert targets[0]["legendFormat"] == "CPU %"
        assert targets[0]["refId"] == "A"

        # Verify field configuration
        field_config = panel["fieldConfig"]["defaults"]
        assert field_config["unit"] == "percent"

        # Verify thresholds
        thresholds = field_config["thresholds"]["steps"]
        assert len(thresholds) == 3
        assert thresholds[0] == {"color": "green", "value": None}
        assert thresholds[1] == {"color": "yellow", "value": 70}
        assert thresholds[2] == {"color": "red", "value": 90}

        # Verify grid position
        grid_pos = panel["gridPos"]
        assert grid_pos["h"] == 8
        assert grid_pos["w"] == 12
        assert grid_pos["x"] == 0
        assert grid_pos["y"] == 0

    def test_request_rate_panel_red_methodology(self, manager):
        """Test request rate panel implements RED methodology correctly."""
        panel = manager._create_request_rate_panel()

        # Verify RED methodology implementation
        assert panel["id"] == 10
        assert panel["title"] == "Request Rate"
        assert panel["type"] == "timeseries"

        # Verify Prometheus query for rate calculation
        targets = panel["targets"]
        assert targets[0]["expr"] == "rate(scraper_requests_total[5m])"
        assert targets[0]["legendFormat"] == "Requests/sec"

        # Verify appropriate units
        field_config = panel["fieldConfig"]["defaults"]
        assert field_config["unit"] == "reqps"

    def test_create_provisioning_config(self, manager):
        """Test provisioning configuration creation."""
        config = manager.create_provisioning_config()

        # Verify structure
        assert config["apiVersion"] == 1
        assert "providers" in config

        providers = config["providers"]
        assert len(providers) == 1

        provider = providers[0]
        assert provider["name"] == "csfrace-dashboards"
        assert provider["orgId"] == 1
        assert provider["type"] == "file"
        assert provider["disableDeletion"] is False
        assert provider["allowUiUpdates"] is True
        assert provider["updateIntervalSeconds"] == 10
        assert provider["options"]["path"] == "/etc/grafana/provisioning/dashboards"

    def test_create_datasource_config(self, manager):
        """Test datasource configuration creation."""
        config = manager.create_datasource_config()

        # Verify structure
        assert config["apiVersion"] == 1
        assert "datasources" in config

        datasources = config["datasources"]
        assert len(datasources) == 1

        datasource = datasources[0]
        assert datasource["name"] == "Prometheus"
        assert datasource["type"] == "prometheus"
        assert datasource["access"] == "proxy"
        assert datasource["url"] == manager.config.prometheus_url
        assert datasource["isDefault"] is True
        assert datasource["editable"] is True

    def test_error_rate_panel_calculation(self, manager):
        """Test error rate panel uses proper Prometheus calculation."""
        panel = manager._create_error_rate_panel()

        # Verify error rate calculation formula
        targets = panel["targets"]
        expected_expr = 'rate(scraper_requests_total{status="error"}[5m]) / rate(scraper_requests_total[5m]) * 100'
        assert targets[0]["expr"] == expected_expr

        # Verify thresholds are appropriate for error rates
        thresholds = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert thresholds[0]["color"] == "green"
        assert thresholds[1]["value"] == 1  # 1% warning
        assert thresholds[2]["value"] == 5  # 5% critical

    def test_cache_metrics_panel_thresholds(self, manager):
        """Test cache hit rate panel has inverted threshold colors."""
        panel = manager._create_cache_metrics_panel()

        # Cache hit rate should have inverted thresholds (higher is better)
        thresholds = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert thresholds[0]["color"] == "red"  # Low hit rate is bad
        assert thresholds[1]["color"] == "yellow"  # Medium hit rate
        assert thresholds[2]["color"] == "green"  # High hit rate is good
        assert thresholds[1]["value"] == 80
        assert thresholds[2]["value"] == 95
