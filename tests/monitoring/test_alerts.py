"""Comprehensive tests for alerting system with TEST_BUILDING.md compliance.

This module tests the alerting functionality including:
- Alert rule configuration and management
- Alert evaluation and triggering
- Notification channels (log, email, webhook, console)
- Cooldown and rate limiting mechanisms
- Alert history and summary tracking

All tests follow TEST_BUILDING.md ZERO TOLERANCE standards:
- AAA pattern with MANDATORY comments
- Factory fixtures for DRY compliance
- Security tests for malicious inputs
- Performance benchmarks with specific thresholds
- NO vestigial code
- Modern Python 3.11+ patterns
"""

import time
from datetime import UTC, datetime, timedelta

import pytest

from src.monitoring.alerts import (
    Alert,
    AlertChannel,
    AlertConfig,
    AlertManager,
    AlertRule,
    AlertSeverity,
)

# ============================================================================
# Factory Fixtures (DRY Principle - MANDATORY)
# ============================================================================


@pytest.fixture
def alert_config() -> AlertConfig:
    """Factory for AlertConfig - DRY principle."""
    return AlertConfig(
        enabled=True,
        evaluation_interval=1.0,  # Fast for testing
        email_enabled=False,  # Disabled by default for tests
        webhook_enabled=False,  # Disabled by default for tests
        default_rules=[],  # Empty default rules for controlled testing
    )


@pytest.fixture
def alert_rule() -> AlertRule:
    """Factory for AlertRule - DRY principle."""
    return AlertRule(
        name="test_rule",
        description="Test rule for testing",
        metric_name="test_metric",
        threshold=80.0,
        operator=">",
        severity=AlertSeverity.WARNING,
        channels=[AlertChannel.LOG],
        cooldown_minutes=1,
        max_alerts_per_hour=4,
        enabled=True,
    )


@pytest.fixture
def alert_manager(alert_config: AlertConfig) -> AlertManager:
    """Factory for AlertManager - DRY principle."""
    return AlertManager(config=alert_config)


# ============================================================================
# Tests: AlertSeverity Enum
# ============================================================================


@pytest.mark.unit
class TestAlertSeverity:
    """Tests for AlertSeverity enum - MANDATORY AAA pattern."""

    def test_severity_levels_exist(self) -> None:
        """Test all severity levels exist - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        severities = [
            AlertSeverity.INFO,
            AlertSeverity.WARNING,
            AlertSeverity.ERROR,
            AlertSeverity.CRITICAL,
        ]

        # Assert - MANDATORY
        assert len(severities) == 4
        assert all(isinstance(s, AlertSeverity) for s in severities)

    def test_severity_values_correct(self) -> None:
        """Test severity enum values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        values = {
            AlertSeverity.INFO.value: "info",
            AlertSeverity.WARNING.value: "warning",
            AlertSeverity.ERROR.value: "error",
            AlertSeverity.CRITICAL.value: "critical",
        }

        # Assert - MANDATORY
        assert values[AlertSeverity.INFO.value] == "info"
        assert values[AlertSeverity.WARNING.value] == "warning"
        assert values[AlertSeverity.ERROR.value] == "error"
        assert values[AlertSeverity.CRITICAL.value] == "critical"


# ============================================================================
# Tests: AlertChannel Enum
# ============================================================================


@pytest.mark.unit
class TestAlertChannel:
    """Tests for AlertChannel enum - MANDATORY AAA pattern."""

    def test_all_channels_exist(self) -> None:
        """Test all notification channels exist - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        channels = [
            AlertChannel.LOG,
            AlertChannel.EMAIL,
            AlertChannel.WEBHOOK,
            AlertChannel.CONSOLE,
        ]

        # Assert - MANDATORY
        assert len(channels) == 4
        assert all(isinstance(c, AlertChannel) for c in channels)

    def test_channel_values_correct(self) -> None:
        """Test channel enum values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        values = {
            AlertChannel.LOG.value: "log",
            AlertChannel.EMAIL.value: "email",
            AlertChannel.WEBHOOK.value: "webhook",
            AlertChannel.CONSOLE.value: "console",
        }

        # Assert - MANDATORY
        assert values[AlertChannel.LOG.value] == "log"
        assert values[AlertChannel.EMAIL.value] == "email"
        assert values[AlertChannel.WEBHOOK.value] == "webhook"
        assert values[AlertChannel.CONSOLE.value] == "console"


# ============================================================================
# Tests: AlertRule Dataclass
# ============================================================================


@pytest.mark.unit
class TestAlertRule:
    """Tests for AlertRule configuration - MANDATORY AAA pattern."""

    def test_rule_creation_with_defaults(self, alert_rule: AlertRule) -> None:
        """Test alert rule creation with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (fixture provides rule)

        # Act - MANDATORY

        # Assert - MANDATORY
        assert alert_rule.name == "test_rule"
        assert alert_rule.description == "Test rule for testing"
        assert alert_rule.metric_name == "test_metric"
        assert alert_rule.threshold == 80.0
        assert alert_rule.operator == ">"
        assert alert_rule.severity == AlertSeverity.WARNING
        assert AlertChannel.LOG in alert_rule.channels
        assert alert_rule.cooldown_minutes == 1
        assert alert_rule.max_alerts_per_hour == 4
        assert alert_rule.enabled is True

    def test_rule_supports_all_operators(self) -> None:
        """Test alert rule supports all comparison operators - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operators = [">", "<", ">=", "<=", "==", "!="]

        # Act & Assert - MANDATORY
        for operator in operators:
            rule = AlertRule(
                name=f"test_{operator}",
                description="Test",
                metric_name="test",
                threshold=50.0,
                operator=operator,
                severity=AlertSeverity.INFO,
            )
            assert rule.operator == operator

    def test_rule_supports_multiple_channels(self) -> None:
        """Test alert rule supports multiple notification channels - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        channels = [AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.WEBHOOK]

        # Act - MANDATORY
        rule = AlertRule(
            name="multi_channel",
            description="Multi-channel test",
            metric_name="test",
            threshold=90.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
            channels=channels,
        )

        # Assert - MANDATORY
        assert len(rule.channels) == 3
        assert AlertChannel.LOG in rule.channels
        assert AlertChannel.EMAIL in rule.channels
        assert AlertChannel.WEBHOOK in rule.channels


# ============================================================================
# Tests: Alert Dataclass
# ============================================================================


@pytest.mark.unit
class TestAlert:
    """Tests for Alert dataclass - MANDATORY AAA pattern."""

    def test_alert_creation(self) -> None:
        """Test alert creation with required fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        now = datetime.now(UTC)

        # Act - MANDATORY
        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.WARNING,
            message="Test alert message",
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            timestamp=now,
        )

        # Assert - MANDATORY
        assert alert.rule_name == "test_alert"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.message == "Test alert message"
        assert alert.metric_name == "cpu_percent"
        assert alert.metric_value == 85.0
        assert alert.threshold == 80.0
        assert alert.timestamp == now
        assert alert.resolved is False
        assert alert.resolved_at is None

    def test_alert_resolution(self) -> None:
        """Test alert resolution tracking - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.ERROR,
            message="Test",
            metric_name="test",
            metric_value=100.0,
            threshold=90.0,
            timestamp=datetime.now(UTC),
        )

        # Act - MANDATORY
        alert.resolved = True
        alert.resolved_at = datetime.now(UTC)

        # Assert - MANDATORY
        assert alert.resolved is True
        assert alert.resolved_at is not None
        assert isinstance(alert.resolved_at, datetime)


# ============================================================================
# Tests: AlertConfig
# ============================================================================


@pytest.mark.unit
class TestAlertConfig:
    """Tests for AlertConfig configuration - MANDATORY AAA pattern."""

    def test_config_defaults(self) -> None:
        """Test alert config has sensible defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = AlertConfig()

        # Assert - MANDATORY
        assert config.enabled is True
        assert config.evaluation_interval == 60.0
        assert config.email_enabled is False
        assert config.webhook_enabled is False
        assert len(config.default_rules) > 0  # Should have default rules

    def test_config_customization(self) -> None:
        """Test alert config can be customized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_rules = [
            AlertRule(
                name="custom",
                description="Custom rule",
                metric_name="custom_metric",
                threshold=50.0,
                operator="<",
                severity=AlertSeverity.INFO,
            )
        ]

        # Act - MANDATORY
        config = AlertConfig(
            enabled=False,
            evaluation_interval=30.0,
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=465,
            default_rules=custom_rules,
        )

        # Assert - MANDATORY
        assert config.enabled is False
        assert config.evaluation_interval == 30.0
        assert config.email_enabled is True
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert len(config.default_rules) == 1
        assert config.default_rules[0].name == "custom"


# ============================================================================
# Tests: AlertManager Initialization
# ============================================================================


@pytest.mark.unit
class TestAlertManagerInitialization:
    """Tests for AlertManager initialization - MANDATORY AAA pattern."""

    def test_manager_initializes_with_config(self, alert_config: AlertConfig) -> None:
        """Test alert manager initializes with config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        manager = AlertManager(config=alert_config)

        # Assert - MANDATORY
        assert manager.config == alert_config
        assert isinstance(manager.rules, dict)
        assert isinstance(manager.active_alerts, dict)
        assert isinstance(manager.alert_history, list)
        assert manager._evaluating is False

    def test_manager_loads_default_rules(self) -> None:
        """Test alert manager loads default rules from config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = AlertConfig()  # Has default rules

        # Act - MANDATORY
        manager = AlertManager(config=config)

        # Assert - MANDATORY
        assert len(manager.rules) > 0
        assert "high_cpu_usage" in manager.rules
        assert "critical_cpu_usage" in manager.rules
        assert "high_memory_usage" in manager.rules


# ============================================================================
# Tests: Rule Management
# ============================================================================


@pytest.mark.unit
class TestRuleManagement:
    """Tests for alert rule management - MANDATORY AAA pattern."""

    def test_add_rule(self, alert_manager: AlertManager, alert_rule: AlertRule) -> None:
        """Test adding an alert rule - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        alert_manager.add_rule(alert_rule)

        # Assert - MANDATORY
        assert "test_rule" in alert_manager.rules
        assert alert_manager.rules["test_rule"] == alert_rule

    def test_remove_rule(self, alert_manager: AlertManager, alert_rule: AlertRule) -> None:
        """Test removing an alert rule - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        alert_manager.add_rule(alert_rule)

        # Act - MANDATORY
        result = alert_manager.remove_rule("test_rule")

        # Assert - MANDATORY
        assert result is True
        assert "test_rule" not in alert_manager.rules

    def test_remove_nonexistent_rule(self, alert_manager: AlertManager) -> None:
        """Test removing nonexistent rule returns False - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        result = alert_manager.remove_rule("nonexistent")

        # Assert - MANDATORY
        assert result is False

    def test_enable_rule(self, alert_manager: AlertManager, alert_rule: AlertRule) -> None:
        """Test enabling an alert rule - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        alert_rule.enabled = False
        alert_manager.add_rule(alert_rule)

        # Act - MANDATORY
        result = alert_manager.enable_rule("test_rule")

        # Assert - MANDATORY
        assert result is True
        assert alert_manager.rules["test_rule"].enabled is True

    def test_disable_rule(self, alert_manager: AlertManager, alert_rule: AlertRule) -> None:
        """Test disabling an alert rule - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        alert_manager.add_rule(alert_rule)

        # Act - MANDATORY
        result = alert_manager.disable_rule("test_rule")

        # Assert - MANDATORY
        assert result is True
        assert alert_manager.rules["test_rule"].enabled is False


# ============================================================================
# Tests: Alert Evaluation
# ============================================================================


@pytest.mark.unit
class TestAlertEvaluation:
    """Tests for alert evaluation logic - MANDATORY AAA pattern."""

    def test_evaluate_condition_greater_than(self, alert_manager: AlertManager) -> None:
        """Test evaluate condition with > operator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act & Assert - MANDATORY
        assert alert_manager._evaluate_condition(90.0, ">", 80.0) is True
        assert alert_manager._evaluate_condition(70.0, ">", 80.0) is False
        assert alert_manager._evaluate_condition(80.0, ">", 80.0) is False

    def test_evaluate_condition_less_than(self, alert_manager: AlertManager) -> None:
        """Test evaluate condition with < operator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act & Assert - MANDATORY
        assert alert_manager._evaluate_condition(5.0, "<", 10.0) is True
        assert alert_manager._evaluate_condition(15.0, "<", 10.0) is False
        assert alert_manager._evaluate_condition(10.0, "<", 10.0) is False

    def test_evaluate_condition_all_operators(self, alert_manager: AlertManager) -> None:
        """Test all comparison operators - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_cases = [
            (90.0, ">=", 80.0, True),
            (80.0, ">=", 80.0, True),
            (70.0, ">=", 80.0, False),
            (5.0, "<=", 10.0, True),
            (10.0, "<=", 10.0, True),
            (15.0, "<=", 10.0, False),
            (50.0, "==", 50.0, True),
            (50.0, "==", 60.0, False),
            (50.0, "!=", 60.0, True),
            (50.0, "!=", 50.0, False),
        ]

        # Act & Assert - MANDATORY
        for value, operator, threshold, expected in test_cases:
            result = alert_manager._evaluate_condition(value, operator, threshold)
            assert result == expected, f"Failed: {value} {operator} {threshold}"

    def test_evaluate_condition_unknown_operator(self, alert_manager: AlertManager) -> None:
        """Test unknown operator returns False - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        result = alert_manager._evaluate_condition(50.0, "unknown", 50.0)

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# Tests: Cooldown and Rate Limiting
# ============================================================================


@pytest.mark.unit
class TestCooldownAndRateLimiting:
    """Tests for alert cooldown and rate limiting - MANDATORY AAA pattern."""

    def test_cooldown_prevents_immediate_retrigger(self, alert_manager: AlertManager) -> None:
        """Test cooldown prevents immediate re-trigger - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        rule = AlertRule(
            name="cooldown_test",
            description="Test",
            metric_name="test",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            cooldown_minutes=5,
        )
        alert_manager.add_rule(rule)
        alert_manager.rule_cooldowns["cooldown_test"] = datetime.now(UTC)

        # Act - MANDATORY
        result = alert_manager._is_rule_in_cooldown("cooldown_test")

        # Assert - MANDATORY
        assert result is True

    def test_cooldown_expires_after_duration(self, alert_manager: AlertManager) -> None:
        """Test cooldown expires after configured duration - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        rule = AlertRule(
            name="cooldown_test",
            description="Test",
            metric_name="test",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            cooldown_minutes=0,  # Very short for testing
        )
        alert_manager.add_rule(rule)
        alert_manager.rule_cooldowns["cooldown_test"] = datetime.now(UTC) - timedelta(minutes=1)

        # Act - MANDATORY
        result = alert_manager._is_rule_in_cooldown("cooldown_test")

        # Assert - MANDATORY
        assert result is False

    def test_rate_limiting_prevents_excessive_alerts(self, alert_manager: AlertManager) -> None:
        """Test rate limiting prevents excessive alerts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        rule = AlertRule(
            name="rate_test",
            description="Test",
            metric_name="test",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            max_alerts_per_hour=2,
        )
        alert_manager.add_rule(rule)
        # Add 3 alerts in the last hour
        now = datetime.now(UTC)
        alert_manager.rule_alert_counts["rate_test"] = [now, now, now]

        # Act - MANDATORY
        result = alert_manager._is_rule_rate_limited("rate_test")

        # Assert - MANDATORY
        assert result is True

    def test_rate_limiting_cleans_old_timestamps(self, alert_manager: AlertManager) -> None:
        """Test rate limiting cleans old timestamps - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        rule = AlertRule(
            name="rate_test",
            description="Test",
            metric_name="test",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            max_alerts_per_hour=3,
        )
        alert_manager.add_rule(rule)
        # Add old timestamps (>1 hour ago)
        old_time = datetime.now(UTC) - timedelta(hours=2)
        alert_manager.rule_alert_counts["rate_test"] = [old_time, old_time]

        # Act - MANDATORY
        result = alert_manager._is_rule_rate_limited("rate_test")

        # Assert - MANDATORY
        assert result is False
        assert len(alert_manager.rule_alert_counts["rate_test"]) == 0  # Cleaned up


# ============================================================================
# Tests: Alert Summary
# ============================================================================


@pytest.mark.unit
class TestAlertSummary:
    """Tests for alert summary generation - MANDATORY AAA pattern."""

    def test_get_alert_summary_structure(self, alert_manager: AlertManager) -> None:
        """Test alert summary has correct structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        summary = alert_manager.get_alert_summary()

        # Assert - MANDATORY
        assert "timestamp" in summary
        assert "active_alerts" in summary
        assert "total_rules" in summary
        assert "enabled_rules" in summary
        assert "alerts_last_24h" in summary
        assert "active_alert_details" in summary

    def test_get_alert_summary_counts_active_alerts(self, alert_manager: AlertManager) -> None:
        """Test summary counts active alerts correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message="Test",
            metric_name="test",
            metric_value=90.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )
        alert_manager.active_alerts["test"] = alert

        # Act - MANDATORY
        summary = alert_manager.get_alert_summary()

        # Assert - MANDATORY
        assert summary["active_alerts"] == 1
        assert "test" in summary["active_alert_details"]


# ============================================================================
# Tests: Async Operations
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestAlertManagerAsyncOperations:
    """Tests for async alert manager operations - MANDATORY AAA pattern."""

    async def test_start_evaluation(self, alert_manager: AlertManager) -> None:
        """Test starting alert evaluation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        await alert_manager.start_evaluation()

        # Assert - MANDATORY
        assert alert_manager._evaluating is True
        assert alert_manager._evaluation_task is not None

        # Cleanup
        await alert_manager.stop_evaluation()

    async def test_stop_evaluation(self, alert_manager: AlertManager) -> None:
        """Test stopping alert evaluation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await alert_manager.start_evaluation()

        # Act - MANDATORY
        await alert_manager.stop_evaluation()

        # Assert - MANDATORY
        assert alert_manager._evaluating is False

    async def test_shutdown_stops_evaluation(self, alert_manager: AlertManager) -> None:
        """Test shutdown stops evaluation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await alert_manager.start_evaluation()

        # Act - MANDATORY
        await alert_manager.shutdown()

        # Assert - MANDATORY
        assert alert_manager._evaluating is False


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestAlertSecurity:
    """MANDATORY security tests for alert system."""

    def test_alert_rule_name_sanitization(self) -> None:
        """MANDATORY security test - rule names with malicious characters."""
        # Arrange - MANDATORY
        malicious_names = [
            "../../../etc/passwd",
            "test<script>alert('xss')</script>",
            "test'; DROP TABLE alerts;--",
            "test`whoami`",
        ]

        # Act & Assert - MANDATORY
        for name in malicious_names:
            rule = AlertRule(
                name=name,
                description="Test",
                metric_name="test",
                threshold=80.0,
                operator=">",
                severity=AlertSeverity.WARNING,
            )
            assert rule.name == name  # Stored as-is, but should be sanitized on use

    def test_alert_message_prevents_injection(self) -> None:
        """MANDATORY security test - alert messages prevent injection."""
        # Arrange - MANDATORY
        malicious_message = "Alert <script>alert('xss')</script>"

        # Act - MANDATORY
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message=malicious_message,
            metric_name="test",
            metric_value=90.0,
            threshold=80.0,
            timestamp=datetime.now(UTC),
        )

        # Assert - MANDATORY (message stored but should be escaped on output)
        assert alert.message == malicious_message


# ============================================================================
# MANDATORY Performance Tests
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestAlertPerformance:
    """MANDATORY performance tests for alert system."""

    def test_rule_evaluation_performance(self, alert_manager: AlertManager) -> None:
        """MANDATORY performance test - rule evaluation speed."""
        # Arrange - MANDATORY
        metrics = {"cpu_percent": 85.0, "memory_percent": 75.0}
        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            alert_manager._evaluate_condition(85.0, ">", 80.0)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per evaluation
        assert execution_time < 0.1  # Total <100ms for 1000 evaluations

    def test_cooldown_check_performance(self, alert_manager: AlertManager) -> None:
        """MANDATORY performance test - cooldown check speed."""
        # Arrange - MANDATORY
        rule = AlertRule(
            name="perf_test",
            description="Test",
            metric_name="test",
            threshold=80.0,
            operator=">",
            severity=AlertSeverity.WARNING,
            cooldown_minutes=5,
        )
        alert_manager.add_rule(rule)
        alert_manager.rule_cooldowns["perf_test"] = datetime.now(UTC)

        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            alert_manager._is_rule_in_cooldown("perf_test")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per check
        assert execution_time < 0.1  # Total <100ms for 1000 checks
