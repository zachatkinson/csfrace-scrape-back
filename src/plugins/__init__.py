"""Plugin system for extensible content processors."""

from .base import BasePlugin, PluginConfig, PluginType
from .manager import PluginManager
from .registry import PluginRegistry

__all__ = ["BasePlugin", "PluginType", "PluginConfig", "PluginManager", "PluginRegistry"]
