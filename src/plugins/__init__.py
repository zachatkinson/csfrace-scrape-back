"""Plugin system for extensible content processors."""

from .base import BasePlugin, PluginType, PluginConfig
from .manager import PluginManager
from .registry import PluginRegistry

__all__ = ['BasePlugin', 'PluginType', 'PluginConfig', 'PluginManager', 'PluginRegistry']