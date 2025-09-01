"""Alerting system with configurable thresholds and notification channels."""

import asyncio
import smtplib
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Available alert notification channels."""

    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"


@dataclass
class AlertRule:
    """Configuration for an alert rule."""

    name: str
    description: str
    metric_name: str
    threshold: float
    operator: str  # >, <, >=, <=, ==, !=
    severity: AlertSeverity
    channels: list[AlertChannel] = field(default_factory=list)
    cooldown_minutes: int = 15
    max_alerts_per_hour: int = 4
    enabled: bool = True


@dataclass
class Alert:
    """Represents an active alert."""

    rule_name: str
    severity: AlertSeverity
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: datetime | None = None


@dataclass
class AlertConfig:
    """Configuration for alerting system."""

    enabled: bool = True
    evaluation_interval: float = 60.0  # seconds

    # Email configuration
    email_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    from_email: str = "alerts@scraper.local"
    to_emails: list[str] = field(default_factory=list)

    # Webhook configuration
    webhook_enabled: bool = False
    webhook_url: str | None = None
    webhook_timeout: float = 10.0

    # Default alert rules
    default_rules: list[AlertRule] = field(
        default_factory=lambda: [
            AlertRule(
                name="high_cpu_usage",
                description="CPU usage is above 80%",
                metric_name="cpu_percent",
                threshold=80.0,
                operator=">",
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            ),
            AlertRule(
                name="critical_cpu_usage",
                description="CPU usage is above 95%",
                metric_name="cpu_percent",
                threshold=95.0,
                operator=">",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            ),
            AlertRule(
                name="high_memory_usage",
                description="Memory usage is above 85%",
                metric_name="memory_percent",
                threshold=85.0,
                operator=">",
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            ),
            AlertRule(
                name="low_disk_space",
                description="Disk space is below 10%",
                metric_name="disk_free_percent",
                threshold=10.0,
                operator="<",
                severity=AlertSeverity.ERROR,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            ),
            AlertRule(
                name="database_connection_failed",
                description="Database connection check failed",
                metric_name="database_connection_healthy",
                threshold=1.0,
                operator="<",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            ),
        ]
    )


class AlertManager:
    """Manages alert rules, evaluation, and notifications."""

    def __init__(self, config: AlertConfig | None = None):
        """Initialize alert manager.

        Args:
            config: Alert configuration
        """
        self.config = config or AlertConfig()
        self.rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []
        self.rule_cooldowns: dict[str, datetime] = {}
        self.rule_alert_counts: dict[str, list[datetime]] = {}

        self._evaluation_task: asyncio.Task | None = None
        self._evaluating = False

        # Load default rules
        for rule in self.config.default_rules:
            self.add_rule(rule)

        logger.info("Alert manager initialized", enabled=self.config.enabled, rules=len(self.rules))

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule.

        Args:
            rule: Alert rule to add
        """
        self.rules[rule.name] = rule
        logger.debug("Added alert rule", name=rule.name, severity=rule.severity.value)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove an alert rule.

        Args:
            rule_name: Name of rule to remove

        Returns:
            True if rule was removed
        """
        if rule_name in self.rules:
            del self.rules[rule_name]
            # Clean up related data
            if rule_name in self.active_alerts:
                del self.active_alerts[rule_name]
            if rule_name in self.rule_cooldowns:
                del self.rule_cooldowns[rule_name]
            if rule_name in self.rule_alert_counts:
                del self.rule_alert_counts[rule_name]

            logger.debug("Removed alert rule", name=rule_name)
            return True
        return False

    def enable_rule(self, rule_name: str) -> bool:
        """Enable an alert rule.

        Args:
            rule_name: Name of rule to enable

        Returns:
            True if rule was enabled
        """
        if rule_name in self.rules:
            self.rules[rule_name].enabled = True
            logger.debug("Enabled alert rule", name=rule_name)
            return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Disable an alert rule.

        Args:
            rule_name: Name of rule to disable

        Returns:
            True if rule was disabled
        """
        if rule_name in self.rules:
            self.rules[rule_name].enabled = False
            logger.debug("Disabled alert rule", name=rule_name)
            return True
        return False

    async def start_evaluation(self) -> None:
        """Start periodic alert rule evaluation."""
        if not self.config.enabled or self._evaluating:
            return

        self._evaluating = True
        self._evaluation_task = asyncio.create_task(self._evaluation_loop())
        logger.info("Started alert evaluation", interval=self.config.evaluation_interval)

    async def stop_evaluation(self) -> None:
        """Stop alert rule evaluation."""
        if not self._evaluating:
            return

        self._evaluating = False
        if self._evaluation_task:
            self._evaluation_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._evaluation_task

        logger.info("Stopped alert evaluation")

    async def _evaluation_loop(self) -> None:
        """Main alert evaluation loop."""
        while self._evaluating:
            try:
                await self.evaluate_rules()
                await asyncio.sleep(self.config.evaluation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Alert evaluation failed", error=str(e))
                await asyncio.sleep(5.0)

    async def evaluate_rules(self) -> None:
        """Evaluate all alert rules against current metrics."""
        if not self.rules:
            return

        try:
            # Get current metrics
            metrics = await self._get_current_metrics()

            for rule_name, rule in self.rules.items():
                if not rule.enabled:
                    continue

                try:
                    await self._evaluate_rule(rule, metrics)
                except Exception as e:
                    logger.error("Rule evaluation failed", rule=rule_name, error=str(e))

        except Exception as e:
            logger.error("Failed to get metrics for evaluation", error=str(e))

    async def _get_current_metrics(self) -> dict[str, float]:
        """Get current metrics for evaluation.

        Returns:
            Dictionary of current metric values
        """
        metrics = {}

        try:
            # Get system metrics
            from .metrics import metrics_collector

            snapshot = metrics_collector.get_metrics_snapshot()

            # Extract system metrics
            system_metrics = snapshot.get("system_metrics", {})
            for key, value in system_metrics.items():
                if isinstance(value, int | float):
                    metrics[key] = float(value)

            # Get health check metrics
            from .health import health_checker

            health_results = health_checker._results

            # Convert health status to numeric values for alerting
            for name, result in health_results.items():
                # Healthy=1, Degraded=0.5, Unhealthy=0, Unknown=0
                if result.status.value == "healthy":
                    metrics[f"{name}_healthy"] = 1.0
                elif result.status.value == "degraded":
                    metrics[f"{name}_healthy"] = 0.5
                else:
                    metrics[f"{name}_healthy"] = 0.0

            # Calculate derived metrics
            if "disk_used" in metrics and "disk_total" in metrics:
                metrics["disk_free_percent"] = (
                    (metrics["disk_total"] - metrics["disk_used"]) / metrics["disk_total"]
                ) * 100

        except Exception as e:
            logger.error("Failed to collect metrics for alerting", error=str(e))

        return metrics

    async def _evaluate_rule(self, rule: AlertRule, metrics: dict[str, float]) -> None:
        """Evaluate a single alert rule.

        Args:
            rule: Alert rule to evaluate
            metrics: Current metric values
        """
        # Check if metric exists
        if rule.metric_name not in metrics:
            return

        metric_value = metrics[rule.metric_name]

        # Evaluate condition
        triggered = self._evaluate_condition(metric_value, rule.operator, rule.threshold)

        # Handle alert state
        if triggered:
            await self._handle_alert_triggered(rule, metric_value)
        else:
            await self._handle_alert_resolved(rule, metric_value)

    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate alert condition.

        Args:
            value: Current metric value
            operator: Comparison operator
            threshold: Threshold value

        Returns:
            True if condition is met
        """
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            logger.warning("Unknown operator", operator=operator)
            return False

    async def _handle_alert_triggered(self, rule: AlertRule, metric_value: float) -> None:
        """Handle when an alert is triggered.

        Args:
            rule: Alert rule that was triggered
            metric_value: Current metric value
        """
        # Check cooldown
        if self._is_rule_in_cooldown(rule.name):
            return

        # Check rate limiting
        if self._is_rule_rate_limited(rule.name):
            return

        # Create alert
        alert = Alert(
            rule_name=rule.name,
            severity=rule.severity,
            message=f"{rule.description}: {metric_value} {rule.operator} {rule.threshold}",
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            timestamp=datetime.now(UTC),
        )

        # Store active alert
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)

        # Update cooldown and rate limiting
        self.rule_cooldowns[rule.name] = datetime.now(UTC)
        if rule.name not in self.rule_alert_counts:
            self.rule_alert_counts[rule.name] = []
        self.rule_alert_counts[rule.name].append(datetime.now(UTC))

        # Send notifications
        await self._send_alert_notifications(alert, rule)

        logger.warning(
            "Alert triggered",
            rule=rule.name,
            severity=rule.severity.value,
            metric=rule.metric_name,
            value=metric_value,
            threshold=rule.threshold,
        )

    async def _handle_alert_resolved(self, rule: AlertRule, metric_value: float) -> None:
        """Handle when an alert is resolved.

        Args:
            rule: Alert rule that was resolved
            metric_value: Current metric value
        """
        if rule.name in self.active_alerts:
            alert = self.active_alerts[rule.name]
            alert.resolved = True
            alert.resolved_at = datetime.now(UTC)

            # Remove from active alerts
            del self.active_alerts[rule.name]

            logger.info(
                "Alert resolved", rule=rule.name, metric=rule.metric_name, value=metric_value
            )

    def _is_rule_in_cooldown(self, rule_name: str) -> bool:
        """Check if rule is in cooldown period.

        Args:
            rule_name: Name of rule to check

        Returns:
            True if rule is in cooldown
        """
        if rule_name not in self.rule_cooldowns:
            return False

        rule = self.rules.get(rule_name)
        if not rule:
            return False

        cooldown_until = self.rule_cooldowns[rule_name] + timedelta(minutes=rule.cooldown_minutes)

        return datetime.now(UTC) < cooldown_until

    def _is_rule_rate_limited(self, rule_name: str) -> bool:
        """Check if rule is rate limited.

        Args:
            rule_name: Name of rule to check

        Returns:
            True if rule is rate limited
        """
        if rule_name not in self.rule_alert_counts:
            return False

        rule = self.rules.get(rule_name)
        if not rule:
            return False

        # Clean up old timestamps
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        self.rule_alert_counts[rule_name] = [
            ts for ts in self.rule_alert_counts[rule_name] if ts > one_hour_ago
        ]

        return len(self.rule_alert_counts[rule_name]) >= rule.max_alerts_per_hour

    async def _send_alert_notifications(self, alert: Alert, rule: AlertRule) -> None:
        """Send alert notifications through configured channels.

        Args:
            alert: Alert to send
            rule: Alert rule configuration
        """
        for channel in rule.channels:
            try:
                if channel == AlertChannel.LOG:
                    await self._send_log_notification(alert)
                elif channel == AlertChannel.EMAIL:
                    await self._send_email_notification(alert)
                elif channel == AlertChannel.WEBHOOK:
                    await self._send_webhook_notification(alert)
                elif channel == AlertChannel.CONSOLE:
                    await self._send_console_notification(alert)
            except Exception as e:
                logger.error(
                    "Failed to send alert notification",
                    channel=channel.value,
                    rule=rule.name,
                    error=str(e),
                )

    async def _send_log_notification(self, alert: Alert) -> None:
        """Send alert via structured logging."""
        logger.bind(
            alert_rule=alert.rule_name,
            alert_severity=alert.severity.value,
            metric_name=alert.metric_name,
            metric_value=alert.metric_value,
            threshold=alert.threshold,
        ).warning(f"ALERT: {alert.message}")

    async def _send_email_notification(self, alert: Alert) -> None:
        """Send alert via email."""
        if not self.config.email_enabled or not self.config.to_emails:
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.from_email
            msg["To"] = ", ".join(self.config.to_emails)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.rule_name}"

            body = f"""
Alert: {alert.rule_name}
Severity: {alert.severity.value.upper()}
Message: {alert.message}
Metric: {alert.metric_name}
Value: {alert.metric_value}
Threshold: {alert.threshold}
Time: {alert.timestamp.isoformat()}
"""
            msg.attach(MIMEText(body, "plain"))

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)

                server.send_message(msg)

            logger.debug("Email notification sent", alert=alert.rule_name)

        except Exception as e:
            logger.error("Failed to send email notification", error=str(e))

    async def _send_webhook_notification(self, alert: Alert) -> None:
        """Send alert via webhook."""
        if not self.config.webhook_enabled or not self.config.webhook_url:
            return

        try:
            import aiohttp

            payload = {
                "alert": {
                    "rule_name": alert.rule_name,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "metric_name": alert.metric_name,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "timestamp": alert.timestamp.isoformat(),
                }
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.config.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.webhook_timeout),
                ) as response,
            ):
                if response.status < 400:
                    logger.debug("Webhook notification sent", alert=alert.rule_name)
                else:
                    logger.error(
                        "Webhook notification failed",
                        alert=alert.rule_name,
                        status=response.status,
                    )

        except Exception as e:
            logger.error("Failed to send webhook notification", error=str(e))

    async def _send_console_notification(self, alert: Alert) -> None:
        """Send alert to console."""
        print(f"\n🚨 ALERT [{alert.severity.value.upper()}]: {alert.message}")
        print(f"   Rule: {alert.rule_name}")
        print(f"   Metric: {alert.metric_name} = {alert.metric_value}")
        print(f"   Threshold: {alert.threshold}")
        print(f"   Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    def get_alert_summary(self) -> dict[str, Any]:
        """Get summary of current alert state.

        Returns:
            Alert summary dictionary
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "active_alerts": len(self.active_alerts),
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules.values() if r.enabled),
            "alerts_last_24h": sum(
                1
                for alert in self.alert_history
                if alert.timestamp > datetime.now(UTC) - timedelta(days=1)
            ),
            "active_alert_details": {
                name: {
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for name, alert in self.active_alerts.items()
            },
        }

    async def shutdown(self) -> None:
        """Shutdown alert manager."""
        await self.stop_evaluation()
        logger.info("Alert manager shutdown")


# Global alert manager instance
alert_manager = AlertManager()
