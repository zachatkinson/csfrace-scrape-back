"""Plugin registry for managing plugin discovery and registration."""

import importlib
import inspect
import json
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
import sys

import structlog

from .base import BasePlugin, PluginConfig, PluginType

logger = structlog.get_logger(__name__)


class PluginRegistry:
    """Registry for managing plugin discovery and registration."""
    
    def __init__(self):
        """Initialize the plugin registry."""
        self._plugins: Dict[str, Type[BasePlugin]] = {}
        self._plugin_configs: Dict[str, PluginConfig] = {}
        self._search_paths: List[Path] = []
        self._initialized = False
    
    def add_search_path(self, path: Path) -> None:
        """Add a directory to search for plugins.
        
        Args:
            path: Directory path to search for plugins
        """
        path = Path(path).resolve()
        if path.exists() and path.is_dir():
            self._search_paths.append(path)
            logger.debug("Added plugin search path", path=str(path))
        else:
            logger.warning("Plugin search path does not exist", path=str(path))
    
    def register_plugin(
        self,
        plugin_class: Type[BasePlugin],
        config: Optional[PluginConfig] = None
    ) -> None:
        """Register a plugin class.
        
        Args:
            plugin_class: Plugin class to register
            config: Optional plugin configuration
            
        Raises:
            ValueError: If plugin class is invalid
        """
        if not issubclass(plugin_class, BasePlugin):
            raise ValueError(f"Plugin {plugin_class.__name__} must inherit from BasePlugin")
        
        # Get plugin info
        try:
            # Create temporary instance to get plugin info
            temp_config = config or PluginConfig(
                name=plugin_class.__name__,
                version="1.0.0",
                plugin_type=PluginType.HTML_PROCESSOR
            )
            temp_instance = plugin_class(temp_config)
            plugin_info = temp_instance.plugin_info
        except Exception as e:
            logger.error("Failed to get plugin info", plugin=plugin_class.__name__, error=str(e))
            raise ValueError(f"Invalid plugin {plugin_class.__name__}: {e}")
        
        plugin_name = plugin_info['name']
        
        # Create config if not provided
        if not config:
            config = PluginConfig(
                name=plugin_name,
                version=plugin_info.get('version', '1.0.0'),
                plugin_type=PluginType(plugin_info.get('plugin_type', 'html_processor'))
            )
        
        self._plugins[plugin_name] = plugin_class
        self._plugin_configs[plugin_name] = config
        
        logger.info(
            "Registered plugin",
            name=plugin_name,
            version=config.version,
            type=config.plugin_type.value
        )
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin.
        
        Args:
            plugin_name: Name of plugin to unregister
        """
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            del self._plugin_configs[plugin_name]
            logger.info("Unregistered plugin", name=plugin_name)
        else:
            logger.warning("Plugin not found for unregistration", name=plugin_name)
    
    def get_plugin_class(self, plugin_name: str) -> Optional[Type[BasePlugin]]:
        """Get a plugin class by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin class or None if not found
        """
        return self._plugins.get(plugin_name)
    
    def get_plugin_config(self, plugin_name: str) -> Optional[PluginConfig]:
        """Get plugin configuration by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin configuration or None if not found
        """
        return self._plugin_configs.get(plugin_name)
    
    def list_plugins(
        self,
        plugin_type: Optional[PluginType] = None,
        enabled_only: bool = False
    ) -> List[str]:
        """List registered plugins.
        
        Args:
            plugin_type: Filter by plugin type
            enabled_only: Only return enabled plugins
            
        Returns:
            List of plugin names
        """
        plugins = []
        
        for name, config in self._plugin_configs.items():
            # Filter by type if specified
            if plugin_type and config.plugin_type != plugin_type:
                continue
            
            # Filter by enabled status if specified
            if enabled_only and not config.enabled:
                continue
            
            plugins.append(name)
        
        return sorted(plugins, key=lambda p: self._plugin_configs[p].priority)
    
    def discover_plugins(self) -> int:
        """Discover and load plugins from search paths.
        
        Returns:
            Number of plugins discovered
        """
        discovered = 0
        
        for search_path in self._search_paths:
            discovered += self._discover_plugins_in_path(search_path)
        
        logger.info("Plugin discovery completed", discovered=discovered)
        return discovered
    
    def _discover_plugins_in_path(self, path: Path) -> int:
        """Discover plugins in a specific path.
        
        Args:
            path: Path to search for plugins
            
        Returns:
            Number of plugins discovered in this path
        """
        discovered = 0
        
        # Look for Python files
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            try:
                discovered += self._load_plugin_from_file(py_file)
            except Exception as e:
                logger.warning("Failed to load plugin file", file=str(py_file), error=str(e))
        
        # Look for plugin.json manifest files
        for manifest_file in path.rglob("plugin.json"):
            try:
                discovered += self._load_plugin_from_manifest(manifest_file)
            except Exception as e:
                logger.warning("Failed to load plugin manifest", file=str(manifest_file), error=str(e))
        
        return discovered
    
    def _load_plugin_from_file(self, py_file: Path) -> int:
        """Load plugin from Python file.
        
        Args:
            py_file: Path to Python file
            
        Returns:
            Number of plugins loaded from file
        """
        # Add parent directory to Python path temporarily
        parent_dir = py_file.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
            path_added = True
        else:
            path_added = False
        
        try:
            # Import the module
            module_name = py_file.stem
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if not spec or not spec.loader:
                return 0
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin classes in the module
            loaded = 0
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (obj != BasePlugin and 
                    issubclass(obj, BasePlugin) and
                    not inspect.isabstract(obj)):
                    
                    try:
                        self.register_plugin(obj)
                        loaded += 1
                    except Exception as e:
                        logger.warning("Failed to register plugin class", 
                                     class_name=name, error=str(e))
            
            return loaded
            
        except Exception as e:
            logger.warning("Failed to load plugin module", file=str(py_file), error=str(e))
            return 0
        
        finally:
            # Remove from path if we added it
            if path_added:
                sys.path.remove(str(parent_dir))
    
    def _load_plugin_from_manifest(self, manifest_file: Path) -> int:
        """Load plugin from manifest file.
        
        Args:
            manifest_file: Path to plugin.json manifest
            
        Returns:
            Number of plugins loaded from manifest
        """
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            plugin_file = manifest_file.parent / manifest.get('main', 'plugin.py')
            if not plugin_file.exists():
                logger.warning("Plugin main file not found", 
                             manifest=str(manifest_file), 
                             main=str(plugin_file))
                return 0
            
            # Create plugin config from manifest
            config = PluginConfig(
                name=manifest['name'],
                version=manifest.get('version', '1.0.0'),
                plugin_type=PluginType(manifest.get('type', 'html_processor')),
                enabled=manifest.get('enabled', True),
                priority=manifest.get('priority', 100),
                settings=manifest.get('settings', {})
            )
            
            # Load the plugin file with the config
            loaded = self._load_plugin_from_file(plugin_file)
            
            # Update config for loaded plugins
            if loaded > 0 and config.name in self._plugin_configs:
                self._plugin_configs[config.name] = config
            
            return loaded
            
        except Exception as e:
            logger.error("Failed to load plugin manifest", file=str(manifest_file), error=str(e))
            return 0
    
    def save_config(self, config_file: Path) -> None:
        """Save plugin configurations to file.
        
        Args:
            config_file: Path to save configuration
        """
        config_data = {}
        
        for name, config in self._plugin_configs.items():
            config_data[name] = {
                'version': config.version,
                'plugin_type': config.plugin_type.value,
                'enabled': config.enabled,
                'priority': config.priority,
                'settings': config.settings
            }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, sort_keys=True)
        
        logger.info("Saved plugin configuration", file=str(config_file))
    
    def load_config(self, config_file: Path) -> None:
        """Load plugin configurations from file.
        
        Args:
            config_file: Path to configuration file
        """
        if not config_file.exists():
            logger.warning("Plugin config file not found", file=str(config_file))
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for name, data in config_data.items():
                if name in self._plugin_configs:
                    config = self._plugin_configs[name]
                    config.enabled = data.get('enabled', config.enabled)
                    config.priority = data.get('priority', config.priority)
                    config.settings.update(data.get('settings', {}))
            
            logger.info("Loaded plugin configuration", file=str(config_file))
            
        except Exception as e:
            logger.error("Failed to load plugin config", file=str(config_file), error=str(e))


# Global plugin registry instance
plugin_registry = PluginRegistry()