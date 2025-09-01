"""Tests for alerting system."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.monitoring.alerts import (
    Alert,
    AlertChannel,
    AlertConfig,
    AlertManager,
    AlertRule,
    AlertSeverity,
)


class TestAlertSeverity:
    """Test alert severity enumeration."""

    def test_severity_values(self):
        """Test all severity values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestAlertChannel:
    """Test alert channel enumeration."""

    def test_channel_values(self):
        """Test all channel values."""
        assert AlertChannel.LOG.value == "log"
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.WEBHOOK.value == "webhook"
        assert AlertChannel.CONSOLE.value == "console"


class TestAlertRule:
    """Test alert rule configuration."""

    def test_rule_creation(self):
        """Test creating alert rule."""
        rule = AlertRule(
            name="test_rule",
            description="Test rule description",
            metric_name="cpu_percent",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            cooldown_minutes=10,
            max_alerts_per_hour=2,
            enabled=True,
        )

        assert rule.name == "test_rule"
        assert rule.description == "Test rule description"
        assert rule.metric_name == "cpu_percent"
        assert rule.threshold == 80.0
        assert rule.operator == ">"
        assert rule.severity == AlertSeverity.WARNING
        assert AlertChannel.LOG in rule.channels
        assert AlertChannel.EMAIL in rule.channels
        assert rule.cooldown_minutes == 10
        assert rule.max_alerts_per_hour == 2
        assert rule.enabled is True


class TestAlert:
    """Test alert data structure."""

    def test_alert_creation(self):
        """Test creating alert."""
        timestamp = datetime.now(UTC)
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.ERROR,
            message="Test alert message",
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            timestamp=timestamp,
        )

        assert alert.rule_name == "test_rule"
        assert alert.severity == AlertSeverity.ERROR
        assert alert.message == "Test alert message"
        assert alert.metric_name == "cpu_percent"
        assert alert.metric_value == 85.0
        assert alert.threshold == 80.0
        assert alert.timestamp == timestamp
        assert alert.resolved is False
        assert alert.resolved_at is None


class TestAlertConfig:
    """Test alert configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AlertConfig()

        assert config.enabled is True
        assert config.evaluation_interval == 60.0
        assert config.email_enabled is False
        assert config.smtp_host == "localhost"
        assert config.smtp_port == 587
        assert config.webhook_enabled is False
        assert len(config.default_rules) > 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = AlertConfig(
            enabled=False,
            evaluation_interval=30.0,
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=465,
            webhook_enabled=True,
            webhook_url="https://hooks.slack.com/webhook",
        )

        assert config.enabled is False
        assert config.evaluation_interval == 30.0
        assert config.email_enabled is True
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.webhook_enabled is True
        assert config.webhook_url == "https://hooks.slack.com/webhook"


class TestAlertManager:
    """Test alert manager functionality."""

    @pytest.fixture
    def alert_manager(self):
        """Create alert manager for testing."""
        config = AlertConfig(
            enabled=True,
            evaluation_interval=0.1,  # Fast for testing
            default_rules=[],  # No default rules for clean testing
        )
        return AlertManager(config)

    def test_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert alert_manager.config.enabled is True
        assert alert_manager.rules == {}
        assert alert_manager.active_alerts == {}
        assert alert_manager.alert_history == []
        assert alert_manager._evaluating is False

    def test_add_rule(self, alert_manager):
        """Test adding alert rule."""
        rule = AlertRule(
            name="cpu_high",
            description="High CPU usage",
            metric_name="cpu_percent",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
        )

        alert_manager.add_rule(rule)
        assert "cpu_high" in alert_manager.rules
        assert alert_manager.rules["cpu_high"] == rule

    def test_remove_rule(self, alert_manager):
        """Test removing alert rule."""
        rule = AlertRule(
            name="cpu_high",
            description="High CPU usage",
            metric_name="cpu_percent",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
        )

        alert_manager.add_rule(rule)
        assert "cpu_high" in alert_manager.rules

        success = alert_manager.remove_rule("cpu_high")
        assert success is True
        assert "cpu_high" not in alert_manager.rules

    def test_remove_nonexistent_rule(self, alert_manager):
        """Test removing non-existent rule."""
        success = alert_manager.remove_rule("nonexistent")
        assert success is False

    def test_enable_disable_rule(self, alert_manager):
        """Test enabling and disabling rules."""
        rule = AlertRule(
            name="test_rule",
            description="Test",
            metric_name="metric",
            threshold=50.0,
            operator=">",
            severity=AlertSeverity.INFO,
            channels=[AlertChannel.LOG],
            enabled=True,
        )

        alert_manager.add_rule(rule)

        # Disable rule
        success = alert_manager.disable_rule("test_rule")
        assert success is True
        assert alert_manager.rules["test_rule"].enabled is False

        # Enable rule
        success = alert_manager.enable_rule("test_rule")
        assert success is True
        assert alert_manager.rules["test_rule"].enabled is True

    def test_enable_disable_nonexistent_rule(self, alert_manager):
        """Test enabling/disabling non-existent rule."""
        assert alert_manager.enable_rule("nonexistent") is False
        assert alert_manager.disable_rule("nonexistent") is False

    @pytest.mark.asyncio
    async def test_start_stop_evaluation(self, alert_manager):
        """Test starting and stopping alert evaluation."""
        assert not alert_manager._evaluating

        await alert_manager.start_evaluation()
        assert alert_manager._evaluating is True
        assert alert_manager._evaluation_task is not None

        await asyncio.sleep(0.2)  # Let it run briefly

        await alert_manager.stop_evaluation()
        assert alert_manager._evaluating is False

    @pytest.mark.asyncio
    async def test_evaluation_disabled(self):
        """Test that evaluation doesn't start when disabled."""
        config = AlertConfig(enabled=False)
        alert_manager = AlertManager(config)

        await alert_manager.start_evaluation()
        assert not alert_manager._evaluating

    @pytest.mark.asyncio
    async def test_get_current_metrics(self, alert_manager):
        """Test getting current metrics for evaluation."""
        with patch("src.monitoring.metrics.metrics_collector") as mock_metrics:
            mock_metrics.get_metrics_snapshot.return_value = {
                "system_metrics": {
                    "cpu_percent": 75.0,
                    "memory_percent": 60.0,
                    "disk_used": 50 * 1024**3,
                    "disk_total": 100 * 1024**3,
                }
            }

            with patch("src.monitoring.health.health_checker") as mock_health:
                mock_result = MagicMock()
                mock_result.status.value = "healthy"
                mock_health._results = {"database": mock_result}

                metrics = await alert_manager._get_current_metrics()

                assert metrics["cpu_percent"] == 75.0
                assert metrics["memory_percent"] == 60.0
                assert metrics["disk_free_percent"] == 50.0  # Calculated
                assert metrics["database_healthy"] == 1.0

    def test_evaluate_condition(self, alert_manager):
        """Test condition evaluation."""
        assert alert_manager._evaluate_condition(85.0, ">", 80.0) is True
        assert alert_manager._evaluate_condition(75.0, ">", 80.0) is False
        assert alert_manager._evaluate_condition(20.0, "<", 25.0) is True
        assert alert_manager._evaluate_condition(30.0, "<", 25.0) is False
        assert alert_manager._evaluate_condition(50.0, ">=", 50.0) is True
        assert alert_manager._evaluate_condition(49.0, ">=", 50.0) is False
        assert alert_manager._evaluate_condition(25.0, "<=", 25.0) is True
        assert alert_manager._evaluate_condition(26.0, "<=", 25.0) is False
        assert alert_manager._evaluate_condition(100.0, "==", 100.0) is True
        assert alert_manager._evaluate_condition(99.0, "==", 100.0) is False
        assert alert_manager._evaluate_condition(50.0, "!=", 100.0) is True
        assert alert_manager._evaluate_condition(100.0, "!=", 100.0) is False

    def test_evaluate_condition_unknown_operator(self, alert_manager):
        """Test condition evaluation with unknown operator."""
        result = alert_manager._evaluate_condition(50.0, "unknown", 25.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_alert_triggered(self, alert_manager):
        """Test handling alert triggered."""
        rule = AlertRule(
            name="test_rule",
            description="Test alert",
            metric_name="cpu_percent",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
            cooldown_minutes=5,
            max_alerts_per_hour=2,
        )

        alert_manager.add_rule(rule)

        with patch.object(alert_manager, "_send_alert_notifications", new_callable=AsyncMock):
            await alert_manager._handle_alert_triggered(rule, 85.0)

            # Should have created active alert
            assert "test_rule" in alert_manager.active_alerts
            alert = alert_manager.active_alerts["test_rule"]
            assert alert.metric_value == 85.0
            assert alert.severity == AlertSeverity.WARNING

            # Should have added to history
            assert len(alert_manager.alert_history) == 1

    @pytest.mark.asyncio
    async def test_handle_alert_resolved(self, alert_manager):
        """Test handling alert resolved."""
        # First trigger an alert
        rule = AlertRule(
            name="test_rule",
            description="Test alert",
            metric_name="cpu_percent",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
        )

        alert_manager.add_rule(rule)

        with patch.object(alert_manager, "_send_alert_notifications", new_callable=AsyncMock):
            await alert_manager._handle_alert_triggered(rule, 85.0)
            assert "test_rule" in alert_manager.active_alerts

            # Now resolve it
            await alert_manager._handle_alert_resolved(rule, 75.0)
            assert "test_rule" not in alert_manager.active_alerts

            # Check history
            assert len(alert_manager.alert_history) == 1
            assert alert_manager.alert_history[0].resolved is True

    def test_is_rule_in_cooldown(self, alert_manager):
        """Test cooldown period checking."""
        rule = AlertRule(
            name="test_rule",
            description="Test",
            metric_name="metric",
            threshold=50.0,
            operator=">",
            severity=AlertSeverity.INFO,
            channels=[AlertChannel.LOG],
            cooldown_minutes=10,
        )

        alert_manager.add_rule(rule)

        # No cooldown initially
        assert alert_manager._is_rule_in_cooldown("test_rule") is False

        # Set cooldown
        alert_manager.rule_cooldowns["test_rule"] = datetime.now(UTC)
        assert alert_manager._is_rule_in_cooldown("test_rule") is True

        # Set old cooldown
        alert_manager.rule_cooldowns["test_rule"] = datetime.now(UTC) - timedelta(minutes=15)
        assert alert_manager._is_rule_in_cooldown("test_rule") is False

    def test_is_rule_rate_limited(self, alert_manager):
        """Test rate limiting checking."""
        rule = AlertRule(
            name="test_rule",
            description="Test",
            metric_name="metric",
            threshold=50.0,
            operator=">",
            severity=AlertSeverity.INFO,
            channels=[AlertChannel.LOG],
            max_alerts_per_hour=2,
        )

        alert_manager.add_rule(rule)

        # No rate limiting initially
        assert alert_manager._is_rule_rate_limited("test_rule") is False

        # Add some recent alerts
        now = datetime.now(UTC)
        alert_manager.rule_alert_counts["test_rule"] = [
            now - timedelta(minutes=10),
            now - timedelta(minutes=5),
        ]

        # Should be rate limited
        assert alert_manager._is_rule_rate_limited("test_rule") is True

        # Add old alerts (should be cleaned up)
        alert_manager.rule_alert_counts["test_rule"] = [
            now - timedelta(hours=2),
            now - timedelta(minutes=10),
        ]

        # Should not be rate limited (old alert cleaned up)
        assert alert_manager._is_rule_rate_limited("test_rule") is False

    @pytest.mark.asyncio
    async def test_send_log_notification(self, alert_manager):
        """Test sending log notification."""
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.WARNING,
            message="Test alert message",
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )

        # Should not raise exception
        await alert_manager._send_log_notification(alert)

    @pytest.mark.asyncio
    async def test_send_console_notification(self, alert_manager, capsys):
        """Test sending console notification."""
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.ERROR,
            message="Test alert message",
            metric_name="cpu_percent",
            metric_value=95.0,
            threshold=90.0,
            timestamp=datetime.now(UTC),
        )

        await alert_manager._send_console_notification(alert)

        # Check console output
        captured = capsys.readouterr()
        assert "ALERT [ERROR]" in captured.out
        assert "test_rule" in captured.out

    @pytest.mark.asyncio
    async def test_send_email_notification_disabled(self, alert_manager):
        """Test email notification when disabled."""
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.WARNING,
            message="Test alert",
            metric_name="metric",
            metric_value=85.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )

        # Should not raise exception when disabled
        await alert_manager._send_email_notification(alert)

    @pytest.mark.asyncio
    async def test_send_webhook_notification_disabled(self, alert_manager):
        """Test webhook notification when disabled."""
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.WARNING,
            message="Test alert",
            metric_name="metric",
            metric_value=85.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )

        # Should not raise exception when disabled
        await alert_manager._send_webhook_notification(alert)

    @pytest.mark.asyncio
    async def test_send_webhook_notification_enabled(self, alert_manager):
        """Test webhook notification when enabled."""
        alert_manager.config.webhook_enabled = True
        alert_manager.config.webhook_url = "https://hooks.example.com/webhook"

        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.WARNING,
            message="Test alert",
            metric_name="metric",
            metric_value=85.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post.return_value.__aenter__ = AsyncMock(
                return_value=mock_response
            )
            mock_session.return_value.post.return_value.__aexit__ = AsyncMock(return_value=None)

            await alert_manager._send_webhook_notification(alert)

            # Should have made POST request
            mock_session.return_value.post.assert_called_once()

    def test_get_alert_summary(self, alert_manager):
        """Test getting alert summary."""
        # Add some test data
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.WARNING,
            message="Test alert",
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )

        alert_manager.active_alerts["test_rule"] = alert
        alert_manager.alert_history.append(alert)

        rule = AlertRule(
            name="test_rule",
            description="Test",
            metric_name="cpu_percent",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
            enabled=True,
        )
        alert_manager.rules["test_rule"] = rule

        summary = alert_manager.get_alert_summary()

        assert summary["active_alerts"] == 1
        assert summary["total_rules"] == 1
        assert summary["enabled_rules"] == 1
        assert "test_rule" in summary["active_alert_details"]
        assert summary["active_alert_details"]["test_rule"]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_evaluate_rules_no_metrics(self, alert_manager):
        """Test rule evaluation when metrics are not available."""
        rule = AlertRule(
            name="test_rule",
            description="Test",
            metric_name="nonexistent_metric",
            threshold=50.0,
            operator=">",
            severity=AlertSeverity.INFO,
            channels=[AlertChannel.LOG],
        )

        alert_manager.add_rule(rule)

        with patch.object(alert_manager, "_get_current_metrics", return_value={}):
            # Should not raise exception
            await alert_manager.evaluate_rules()

    @pytest.mark.asyncio
    async def test_evaluation_loop_error_handling(self, alert_manager):
        """Test evaluation loop handles errors gracefully."""
        with patch.object(
            alert_manager, "evaluate_rules", side_effect=Exception("Evaluation error")
        ):
            await alert_manager.start_evaluation()

            # Let it run briefly to hit the error
            await asyncio.sleep(0.2)

            # Should still be evaluating despite errors
            assert alert_manager._evaluating is True

            await alert_manager.stop_evaluation()

    @pytest.mark.asyncio
    async def test_shutdown(self, alert_manager):
        """Test alert manager shutdown."""
        await alert_manager.start_evaluation()
        assert alert_manager._evaluating is True

        await alert_manager.shutdown()
        assert alert_manager._evaluating is False

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self, alert_manager):
        """Test multiple start/stop cycles work correctly."""
        # First cycle
        await alert_manager.start_evaluation()
        assert alert_manager._evaluating is True
        await alert_manager.stop_evaluation()
        assert alert_manager._evaluating is False

        # Second cycle
        await alert_manager.start_evaluation()
        assert alert_manager._evaluating is True
        await alert_manager.stop_evaluation()
        assert alert_manager._evaluating is False
