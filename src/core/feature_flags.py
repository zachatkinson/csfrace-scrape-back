"""
Feature flags system for controlled rollouts and gradual feature deployment.

This module provides a flexible feature flag system that supports:
1. Environment-based flags (dev/staging/prod)
2. User-based rollouts (gradual percentage rollouts)
3. A/B testing capabilities
4. Runtime flag updates (via config files or environment)
5. Safe defaults (fail closed)
"""

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RolloutStrategy(Enum):
    """Feature rollout strategies."""

    ALL_USERS = "all_users"  # Enable for everyone
    PERCENTAGE = "percentage"  # Enable for X% of users
    ALLOWLIST = "allowlist"  # Enable for specific user IDs
    ENVIRONMENT = "environment"  # Enable based on environment
    DISABLED = "disabled"  # Completely disabled


@dataclass
class FeatureFlag:
    """Configuration for a single feature flag."""

    name: str
    description: str
    strategy: RolloutStrategy = RolloutStrategy.DISABLED
    enabled: bool = False

    # Percentage rollout (0-100)
    percentage: int = 0

    # Allowlist of user IDs
    allowlist: set[str] = field(default_factory=set)

    # Environment restrictions
    environments: set[str] = field(default_factory=set)

    # Metadata for tracking
    created_by: str = "system"
    created_at: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate flag configuration."""
        if self.percentage < 0 or self.percentage > 100:
            raise ValueError(f"Percentage must be 0-100, got {self.percentage}")

        if not self.name:
            raise ValueError("Feature flag name cannot be empty")


class FeatureFlagManager:
    """Manages feature flags for the application."""

    def __init__(
        self,
        config_path: Path | None = None,
        environment: str | None = None,
        user_id_provider: Callable[[], str] | None = None,
    ):
        """
        Initialize feature flag manager.

        Args:
            config_path: Path to feature flags configuration file
            environment: Current environment (dev/staging/prod)
            user_id_provider: Function that returns current user ID
        """
        self.config_path = config_path or Path("config/feature_flags.json")
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.user_id_provider = user_id_provider or self._default_user_id

        self._flags: dict[str, FeatureFlag] = {}
        self._load_flags()

        logger.info(f"FeatureFlagManager initialized with {len(self._flags)} flags")

    def _default_user_id(self) -> str:
        """Default user ID provider - returns a consistent ID for the session."""
        return os.getenv("USER_ID", "anonymous")

    def _load_flags(self) -> None:
        """Load feature flags from configuration file and environment variables."""
        # Load from JSON config file
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config_data = json.load(f)
                    self._load_flags_from_dict(config_data)
                logger.info(f"Loaded {len(self._flags)} flags from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load flags from {self.config_path}: {e}")

        # Override with environment variables
        self._load_flags_from_env()

    def _load_flags_from_dict(self, config: dict[str, Any]) -> None:
        """Load flags from dictionary configuration."""
        for flag_name, flag_config in config.get("features", {}).items():
            try:
                flag = FeatureFlag(
                    name=flag_name,
                    description=flag_config.get("description", ""),
                    strategy=RolloutStrategy(flag_config.get("strategy", "disabled")),
                    enabled=flag_config.get("enabled", False),
                    percentage=flag_config.get("percentage", 0),
                    allowlist=set(flag_config.get("allowlist", [])),
                    environments=set(flag_config.get("environments", [])),
                    created_by=flag_config.get("created_by", "config"),
                    created_at=flag_config.get("created_at"),
                    tags=flag_config.get("tags", []),
                )
                self._flags[flag_name] = flag
            except Exception as e:
                logger.error(f"Failed to load flag {flag_name}: {e}")

    def _load_flags_from_env(self) -> None:
        """Load flag overrides from environment variables."""
        # Format: FEATURE_FLAG_<NAME>=true/false
        for key, value in os.environ.items():
            if key.startswith("FEATURE_FLAG_"):
                flag_name = key.replace("FEATURE_FLAG_", "").lower()

                if flag_name in self._flags:
                    # Override existing flag
                    self._flags[flag_name].enabled = value.lower() in ("true", "1", "yes")
                    logger.info(
                        f"Environment override: {flag_name} = {self._flags[flag_name].enabled}"
                    )
                else:
                    # Create new flag from environment
                    self._flags[flag_name] = FeatureFlag(
                        name=flag_name,
                        description=f"Environment flag: {key}",
                        strategy=RolloutStrategy.ALL_USERS
                        if value.lower() in ("true", "1", "yes")
                        else RolloutStrategy.DISABLED,
                        enabled=value.lower() in ("true", "1", "yes"),
                        created_by="environment",
                    )
                    logger.info(
                        f"Environment flag created: {flag_name} = {self._flags[flag_name].enabled}"
                    )

    def is_enabled(self, flag_name: str, user_id: str | None = None) -> bool:
        """
        Check if a feature flag is enabled for the current context.

        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID (uses provider if not specified)

        Returns:
            True if feature is enabled, False otherwise (safe default)
        """
        flag = self._flags.get(flag_name)
        if not flag:
            logger.warning(f"Unknown feature flag: {flag_name}")
            return False

        # Check if flag is globally disabled
        if not flag.enabled or flag.strategy == RolloutStrategy.DISABLED:
            return False

        # Get user ID
        if user_id is None:
            try:
                user_id = self.user_id_provider()
            except Exception as e:
                logger.error(f"Failed to get user ID: {e}")
                return False

        # Apply rollout strategy
        return self._evaluate_strategy(flag, user_id)

    def _evaluate_strategy(self, flag: FeatureFlag, user_id: str) -> bool:
        """Evaluate if flag should be enabled based on its strategy."""
        try:
            # Environment check
            if flag.environments and self.environment not in flag.environments:
                return False

            # Strategy-specific logic
            if flag.strategy == RolloutStrategy.ALL_USERS:
                return True

            elif flag.strategy == RolloutStrategy.ALLOWLIST:
                return user_id in flag.allowlist

            elif flag.strategy == RolloutStrategy.PERCENTAGE:
                # Consistent hash-based percentage rollout
                import hashlib

                hash_input = f"{flag.name}:{user_id}".encode()
                hash_value = int(hashlib.md5(hash_input).hexdigest()[:8], 16)
                user_percentage = hash_value % 100
                return user_percentage < flag.percentage

            elif flag.strategy == RolloutStrategy.ENVIRONMENT:
                return self.environment in flag.environments

            else:
                return False

        except Exception as e:
            logger.error(f"Error evaluating flag {flag.name}: {e}")
            return False  # Fail safe

    def get_enabled_flags(self, user_id: str | None = None) -> list[str]:
        """Get list of all enabled flag names for the current context."""
        return [flag_name for flag_name in self._flags if self.is_enabled(flag_name, user_id)]

    def get_flag_info(self, flag_name: str) -> dict[str, Any] | None:
        """Get detailed information about a flag."""
        flag = self._flags.get(flag_name)
        if not flag:
            return None

        return {
            "name": flag.name,
            "description": flag.description,
            "strategy": flag.strategy.value,
            "enabled": flag.enabled,
            "percentage": flag.percentage,
            "allowlist_size": len(flag.allowlist),
            "environments": list(flag.environments),
            "created_by": flag.created_by,
            "created_at": flag.created_at,
            "tags": flag.tags,
        }

    def list_all_flags(self) -> dict[str, dict[str, Any]]:
        """Get information about all flags."""
        return {
            flag_name: flag_info
            for flag_name in self._flags
            if (flag_info := self.get_flag_info(flag_name)) is not None
        }

    def add_flag(self, flag: FeatureFlag) -> None:
        """Add or update a feature flag."""
        self._flags[flag.name] = flag
        logger.info(f"Added/updated flag: {flag.name}")

    def remove_flag(self, flag_name: str) -> bool:
        """Remove a feature flag."""
        if flag_name in self._flags:
            del self._flags[flag_name]
            logger.info(f"Removed flag: {flag_name}")
            return True
        return False


# Global feature flag manager instance
_feature_manager: FeatureFlagManager | None = None


def initialize_feature_flags(
    config_path: Path | None = None,
    environment: str | None = None,
    user_id_provider: Callable[[], str] | None = None,
) -> FeatureFlagManager:
    """Initialize the global feature flag manager."""
    global _feature_manager
    _feature_manager = FeatureFlagManager(config_path, environment, user_id_provider)
    return _feature_manager


def get_feature_manager() -> FeatureFlagManager:
    """Get the global feature flag manager instance."""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureFlagManager()
    return _feature_manager


def feature_enabled(flag_name: str, user_id: str | None = None) -> bool:
    """
    Convenience function to check if a feature is enabled.

    Usage:
        if feature_enabled("new_wordpress_parser"):
            return new_parser.parse(content)
        else:
            return legacy_parser.parse(content)
    """
    return get_feature_manager().is_enabled(flag_name, user_id)


def with_feature_flag(flag_name: str, user_id: str | None = None):
    """
    Decorator for feature-flagged functions.

    Usage:
        @with_feature_flag("new_wordpress_parser")
        def parse_with_new_method(content):
            return new_parser.parse(content)
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            if feature_enabled(flag_name, user_id):
                return func(*args, **kwargs)
            else:
                logger.debug(f"Feature {flag_name} disabled, skipping {func.__name__}")
                return None

        return wrapper

    return decorator
