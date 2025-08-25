"""Plugin manager for orchestrating plugin execution and lifecycle management."""

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Optional

import structlog

from .base import BasePlugin, PluginType
from .registry import PluginRegistry, plugin_registry

logger = structlog.get_logger(__name__)


class PluginExecutionContext:
    """Context for plugin execution with shared state and utilities."""

    def __init__(self, url: str, output_dir: Path):
        """Initialize execution context.

        Args:
            url: Source URL being processed
            output_dir: Output directory for results
        """
        self.url = url
        self.output_dir = output_dir
        self.shared_state: dict[str, Any] = {}
        self.execution_stats: dict[str, dict[str, Any]] = {}
        self.start_time = None
        self.end_time = None

    def get_shared_data(self, key: str, default: Any = None) -> Any:
        """Get shared data from context.

        Args:
            key: Data key
            default: Default value if key doesn't exist

        Returns:
            Shared data value
        """
        return self.shared_state.get(key, default)

    def set_shared_data(self, key: str, value: Any) -> None:
        """Set shared data in context.

        Args:
            key: Data key
            value: Data value
        """
        self.shared_state[key] = value

    def record_plugin_stats(self, plugin_name: str, stats: dict[str, Any]) -> None:
        """Record plugin execution statistics.

        Args:
            plugin_name: Name of the plugin
            stats: Plugin execution statistics
        """
        self.execution_stats[plugin_name] = stats


class PluginManager:
    """Manages plugin lifecycle and execution pipeline."""

    def __init__(self, registry: Optional[PluginRegistry] = None):
        """Initialize plugin manager.

        Args:
            registry: Plugin registry to use (defaults to global registry)
        """
        self.registry = registry or plugin_registry
        self._plugins: dict[str, BasePlugin] = {}
        self._pipeline: dict[PluginType, list[str]] = defaultdict(list)
        self._initialized = False
        self._hooks: dict[str, list[Callable]] = defaultdict(list)

    async def initialize(self) -> None:
        """Initialize the plugin manager and all registered plugins."""
        if self._initialized:
            return

        logger.info("Initializing plugin manager")

        # Discover plugins from search paths
        self.registry.discover_plugins()

        # Initialize all enabled plugins
        for plugin_name in self.registry.list_plugins(enabled_only=True):
            await self._initialize_plugin(plugin_name)

        # Build execution pipeline
        self._build_pipeline()

        self._initialized = True
        logger.info("Plugin manager initialized", loaded_plugins=len(self._plugins))

    async def shutdown(self) -> None:
        """Shutdown the plugin manager and cleanup all plugins."""
        if not self._initialized:
            return

        logger.info("Shutting down plugin manager")

        # Cleanup all plugins
        for plugin in self._plugins.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.warning("Plugin cleanup failed", plugin=plugin.config.name, error=str(e))

        self._plugins.clear()
        self._pipeline.clear()
        self._initialized = False

        logger.info("Plugin manager shutdown complete")

    async def _initialize_plugin(self, plugin_name: str) -> None:
        """Initialize a single plugin.

        Args:
            plugin_name: Name of plugin to initialize
        """
        plugin_class = self.registry.get_plugin_class(plugin_name)
        plugin_config = self.registry.get_plugin_config(plugin_name)

        if not plugin_class or not plugin_config:
            logger.warning("Plugin not found in registry", name=plugin_name)
            return

        try:
            # Create plugin instance
            plugin = plugin_class(plugin_config)

            # Validate configuration
            if not await plugin.validate_config():
                logger.warning("Plugin configuration validation failed", name=plugin_name)
                return

            # Initialize plugin
            await plugin.initialize()
            plugin._initialized = True

            # Store plugin
            self._plugins[plugin_name] = plugin

            logger.info(
                "Plugin initialized", name=plugin_name, type=plugin_config.plugin_type.value
            )

        except Exception as e:
            logger.error("Plugin initialization failed", name=plugin_name, error=str(e))

    def _build_pipeline(self) -> None:
        """Build the execution pipeline based on plugin priorities."""
        self._pipeline.clear()

        # Group plugins by type and sort by priority
        for plugin_name, plugin in self._plugins.items():
            plugin_type = plugin.config.plugin_type
            self._pipeline[plugin_type].append(plugin_name)

        # Sort each type by priority
        for plugin_type in self._pipeline:
            self._pipeline[plugin_type].sort(key=lambda name: self._plugins[name].config.priority)

        logger.debug(
            "Built plugin execution pipeline",
            pipeline={ptype.value: plugins for ptype, plugins in self._pipeline.items()},
        )

    async def execute_pipeline(
        self,
        plugin_type: PluginType,
        data: Any,
        context: PluginExecutionContext,
        stop_on_error: bool = False,
    ) -> Any:
        """Execute a plugin pipeline for a specific type.

        Args:
            plugin_type: Type of plugins to execute
            data: Input data for processing
            context: Execution context
            stop_on_error: Whether to stop on first error

        Returns:
            Processed data after pipeline execution

        Raises:
            Exception: If stop_on_error=True and a plugin fails
        """
        if not self._initialized:
            await self.initialize()

        plugins = self._pipeline.get(plugin_type, [])
        if not plugins:
            logger.debug("No plugins found for type", type=plugin_type.value)
            return data

        logger.debug(
            "Executing plugin pipeline",
            type=plugin_type.value,
            plugins=plugins,
            data_type=type(data).__name__,
        )

        result = data

        for plugin_name in plugins:
            plugin = self._plugins.get(plugin_name)
            if not plugin or not plugin.is_enabled():
                continue

            try:
                start_time = asyncio.get_event_loop().time()

                # Execute plugin
                result = await plugin.process(result, context.shared_state)

                end_time = asyncio.get_event_loop().time()
                duration = end_time - start_time

                # Record execution stats
                context.record_plugin_stats(
                    plugin_name,
                    {
                        "duration": duration,
                        "success": True,
                        "input_type": type(data).__name__,
                        "output_type": type(result).__name__,
                    },
                )

                logger.debug(
                    "Plugin executed successfully",
                    name=plugin_name,
                    duration_ms=round(duration * 1000, 2),
                )

                # Call post-execution hooks
                await self._call_hooks("post_plugin_execute", plugin_name, result, context)

            except Exception as e:
                logger.error("Plugin execution failed", name=plugin_name, error=str(e))

                # Record failure stats
                context.record_plugin_stats(
                    plugin_name, {"duration": 0, "success": False, "error": str(e)}
                )

                # Call error hooks
                await self._call_hooks("plugin_error", plugin_name, e, context)

                if stop_on_error:
                    raise

        return result

    async def process_content(
        self,
        html_content: str,
        url: str,
        output_dir: Path,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Process content through the complete plugin pipeline.

        Args:
            html_content: HTML content to process
            url: Source URL
            output_dir: Output directory
            metadata: Optional initial metadata

        Returns:
            Processing results with content, metadata, and stats
        """
        context = PluginExecutionContext(url, output_dir)
        context.start_time = asyncio.get_event_loop().time()

        # Initial data structure
        data = {
            "html": html_content,
            "content": html_content,
            "url": url,
            "output_dir": output_dir,
            "metadata": metadata or {},
            "files": [],
        }

        try:
            # Execute plugin pipelines in order

            # 1. Metadata extraction
            data = await self.execute_pipeline(PluginType.METADATA_EXTRACTOR, data, context)

            # 2. HTML processing
            data = await self.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)

            # 3. Content filtering
            data = await self.execute_pipeline(PluginType.CONTENT_FILTER, data, context)

            # 4. Image processing
            data = await self.execute_pipeline(PluginType.IMAGE_PROCESSOR, data, context)

            # 5. Output formatting
            data = await self.execute_pipeline(PluginType.OUTPUT_FORMATTER, data, context)

            # 6. Post processing
            data = await self.execute_pipeline(PluginType.POST_PROCESSOR, data, context)

        except Exception as e:
            logger.error("Plugin pipeline execution failed", url=url, error=str(e))
            raise

        context.end_time = asyncio.get_event_loop().time()

        # Return results
        return {
            "content": data.get("content", html_content),
            "html": data.get("html", html_content),
            "metadata": data.get("metadata", {}),
            "files": data.get("files", []),
            "context": context,
            "execution_stats": context.execution_stats,
            "total_duration": context.end_time - context.start_time,
        }

    def add_hook(self, event: str, callback: Callable) -> None:
        """Add a hook callback for plugin events.

        Args:
            event: Event name to hook into
            callback: Callback function to call
        """
        self._hooks[event].append(callback)
        logger.debug("Added plugin hook", event=event, callback=callback.__name__)

    async def _call_hooks(self, event: str, *args, **kwargs) -> None:
        """Call all hooks for a specific event.

        Args:
            event: Event name
            *args: Event arguments
            **kwargs: Event keyword arguments
        """
        for callback in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Hook callback failed", event=event, callback=callback.__name__, error=str(e)
                )

    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin.

        Args:
            plugin_name: Name of plugin to enable

        Returns:
            True if plugin was enabled successfully
        """
        config = self.registry.get_plugin_config(plugin_name)
        if config:
            config.enabled = True
            self._build_pipeline()
            logger.info("Plugin enabled", name=plugin_name)
            return True
        return False

    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin.

        Args:
            plugin_name: Name of plugin to disable

        Returns:
            True if plugin was disabled successfully
        """
        config = self.registry.get_plugin_config(plugin_name)
        if config:
            config.enabled = False
            self._build_pipeline()
            logger.info("Plugin disabled", name=plugin_name)
            return True
        return False

    def get_plugin_info(self) -> dict[str, Any]:
        """Get information about loaded plugins.

        Returns:
            Dictionary with plugin information
        """
        info = {
            "total_plugins": len(self._plugins),
            "enabled_plugins": len([p for p in self._plugins.values() if p.is_enabled()]),
            "plugin_types": {},
            "plugins": {},
        }

        # Count by type
        for plugin in self._plugins.values():
            ptype = plugin.config.plugin_type.value
            info["plugin_types"][ptype] = info["plugin_types"].get(ptype, 0) + 1

        # Plugin details
        for name, plugin in self._plugins.items():
            info["plugins"][name] = {
                "type": plugin.config.plugin_type.value,
                "version": plugin.config.version,
                "enabled": plugin.is_enabled(),
                "priority": plugin.get_priority(),
                "info": plugin.plugin_info,
            }

        return info


# Global plugin manager instance
plugin_manager = PluginManager()
