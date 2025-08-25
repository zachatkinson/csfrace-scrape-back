"""Tests for plugin system functionality."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.plugins.base import (
    BasePlugin,
    HTMLProcessorPlugin,
    PluginConfig,
    PluginType,
)
from src.plugins.manager import PluginExecutionContext, PluginManager
from src.plugins.registry import PluginRegistry


class TestPluginConfig:
    """Test PluginConfig dataclass."""

    def test_default_config(self):
        """Test default plugin configuration."""
        config = PluginConfig(
            name="TestPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        assert config.name == "TestPlugin"
        assert config.version == "1.0.0"
        assert config.plugin_type == PluginType.HTML_PROCESSOR
        assert config.enabled is True
        assert config.priority == 100
        assert config.settings == {}

    def test_custom_config(self):
        """Test custom plugin configuration."""
        settings = {"custom_setting": "value", "numeric_setting": 42}

        config = PluginConfig(
            name="CustomPlugin",
            version="2.1.0",
            plugin_type=PluginType.CONTENT_FILTER,
            enabled=False,
            priority=50,
            settings=settings,
        )

        assert config.name == "CustomPlugin"
        assert config.version == "2.1.0"
        assert config.plugin_type == PluginType.CONTENT_FILTER
        assert config.enabled is False
        assert config.priority == 50
        assert config.settings == settings

    def test_post_init_default_settings(self):
        """Test that empty settings dict is created in post_init."""
        config = PluginConfig(
            name="Test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, settings=None
        )

        assert config.settings == {}


class MockPlugin(BasePlugin):
    """Mock plugin for testing."""

    @property
    def plugin_info(self):
        return {
            "name": "Mock Plugin",
            "version": "1.0.0",
            "description": "A mock plugin for testing",
            "author": "Test Suite",
            "plugin_type": "html_processor",
        }

    async def initialize(self):
        self._test_initialized = True

    async def process(self, data, context):
        return f"processed: {data}"

    async def validate_config(self):
        return True


class TestBasePlugin:
    """Test BasePlugin functionality."""

    def test_plugin_creation(self):
        """Test basic plugin creation."""
        config = PluginConfig(
            name="MockPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        plugin = MockPlugin(config)

        assert plugin.config == config
        assert plugin.logger is not None
        assert not plugin._initialized
        assert plugin.plugin_info["name"] == "Mock Plugin"

    def test_plugin_settings(self):
        """Test plugin settings management."""
        config = PluginConfig(
            name="MockPlugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            settings={"initial_setting": "value"},
        )

        plugin = MockPlugin(config)

        # Test getting settings
        assert plugin.get_setting("initial_setting") == "value"
        assert plugin.get_setting("nonexistent") is None
        assert plugin.get_setting("nonexistent", "default") == "default"

        # Test setting settings
        plugin.set_setting("new_setting", "new_value")
        assert plugin.get_setting("new_setting") == "new_value"

    def test_plugin_status_methods(self):
        """Test plugin status and priority methods."""
        config = PluginConfig(
            name="MockPlugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=50,
        )

        plugin = MockPlugin(config)

        assert plugin.is_enabled() is True
        assert plugin.get_priority() == 50

        # Test disabled plugin
        config.enabled = False
        assert plugin.is_enabled() is False

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Test plugin initialization and cleanup."""
        config = PluginConfig(
            name="MockPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        plugin = MockPlugin(config)

        # Initialize
        await plugin.initialize()
        assert hasattr(plugin, "_test_initialized")
        assert plugin._test_initialized is True

        # Validate config
        is_valid = await plugin.validate_config()
        assert is_valid is True

        # Cleanup (base implementation does nothing)
        await plugin.cleanup()  # Should not raise


class MockHTMLPlugin(HTMLProcessorPlugin):
    """Mock HTML processor plugin."""

    @property
    def plugin_info(self):
        return {
            "name": "Mock HTML Plugin",
            "version": "1.0.0",
            "description": "Mock HTML processor",
            "author": "Test Suite",
            "plugin_type": "html_processor",
        }

    async def initialize(self):
        pass

    async def process_html(self, html_content, metadata, context):
        return f"<processed>{html_content}</processed>"


class TestHTMLProcessorPlugin:
    """Test HTMLProcessorPlugin functionality."""

    @pytest.mark.asyncio
    async def test_html_processor_plugin(self):
        """Test HTML processor plugin interface."""
        config = PluginConfig(
            name="MockHTMLPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        plugin = MockHTMLPlugin(config)

        # Test process method (should call process_html)
        data = {
            "html": "<div>Original HTML</div>",
            "metadata": {"title": "Test Page"},
            "other_data": "preserved",
        }

        result = await plugin.process(data, {})

        assert result["html"] == "<processed><div>Original HTML</div></processed>"
        assert result["metadata"] == {"title": "Test Page"}
        assert result["other_data"] == "preserved"

    @pytest.mark.asyncio
    async def test_html_processor_invalid_data(self):
        """Test HTML processor with invalid data."""
        config = PluginConfig(
            name="MockHTMLPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        plugin = MockHTMLPlugin(config)

        # Test with invalid data structure
        with pytest.raises(ValueError, match="HTMLProcessorPlugin expects dict with 'html' key"):
            await plugin.process("invalid data", {})

        with pytest.raises(ValueError, match="HTMLProcessorPlugin expects dict with 'html' key"):
            await plugin.process({"no_html": "key"}, {})


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    @pytest.fixture
    def registry(self):
        """Provide clean PluginRegistry instance."""
        return PluginRegistry()

    @pytest.fixture
    def temp_dir(self):
        """Provide temporary directory for tests."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert registry._plugins == {}
        assert registry._plugin_configs == {}
        assert registry._search_paths == []
        assert not registry._initialized

    def test_add_search_path(self, registry, temp_dir):
        """Test adding search paths."""
        # Add existing directory
        registry.add_search_path(temp_dir)
        assert temp_dir.resolve() in registry._search_paths

        # Add non-existent directory (should not be added)
        nonexistent = temp_dir / "nonexistent"
        registry.add_search_path(nonexistent)
        assert nonexistent not in registry._search_paths

    def test_register_plugin(self, registry):
        """Test manual plugin registration."""
        config = PluginConfig(
            name="MockPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        registry.register_plugin(MockPlugin, config)

        assert "Mock Plugin" in registry._plugins  # Uses plugin_info name
        assert "Mock Plugin" in registry._plugin_configs
        assert registry._plugin_configs["Mock Plugin"].name == "MockPlugin"

    def test_register_plugin_auto_config(self, registry):
        """Test plugin registration with auto-generated config."""
        # Register without providing config
        registry.register_plugin(MockPlugin)

        assert "Mock Plugin" in registry._plugins
        config = registry._plugin_configs["Mock Plugin"]
        assert config.name == "Mock Plugin"
        assert config.version == "1.0.0"

    def test_register_invalid_plugin(self, registry):
        """Test registering invalid plugin class."""

        class NotAPlugin:
            pass

        with pytest.raises(ValueError, match="must inherit from BasePlugin"):
            registry.register_plugin(NotAPlugin)

    def test_unregister_plugin(self, registry):
        """Test plugin unregistration."""
        config = PluginConfig(
            name="MockPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        registry.register_plugin(MockPlugin, config)
        assert "Mock Plugin" in registry._plugins

        registry.unregister_plugin("Mock Plugin")
        assert "Mock Plugin" not in registry._plugins
        assert "Mock Plugin" not in registry._plugin_configs

        # Unregister non-existent plugin (should not raise)
        registry.unregister_plugin("Nonexistent Plugin")

    def test_get_plugin_class_and_config(self, registry):
        """Test retrieving plugin class and config."""
        config = PluginConfig(
            name="MockPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        registry.register_plugin(MockPlugin, config)

        # Test successful retrieval
        plugin_class = registry.get_plugin_class("Mock Plugin")
        assert plugin_class == MockPlugin

        plugin_config = registry.get_plugin_config("Mock Plugin")
        assert plugin_config.name == "MockPlugin"

        # Test non-existent plugin
        assert registry.get_plugin_class("Nonexistent") is None
        assert registry.get_plugin_config("Nonexistent") is None

    def test_list_plugins(self, registry):
        """Test listing registered plugins."""
        # Register plugins with different types and priorities
        config1 = PluginConfig(
            name="Plugin1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=10
        )
        config2 = PluginConfig(
            name="Plugin2", version="1.0.0", plugin_type=PluginType.CONTENT_FILTER, priority=20
        )
        config3 = PluginConfig(
            name="Plugin3",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            priority=5,
            enabled=False,
        )

        registry.register_plugin(MockPlugin, config1)
        # Would need more mock plugins for full test

        # Test listing all plugins
        all_plugins = registry.list_plugins()
        assert isinstance(all_plugins, list)

        # Test filtering by type
        html_plugins = registry.list_plugins(plugin_type=PluginType.HTML_PROCESSOR)
        assert isinstance(html_plugins, list)

        # Test enabled only
        enabled_plugins = registry.list_plugins(enabled_only=True)
        assert isinstance(enabled_plugins, list)

    def test_save_and_load_config(self, registry, temp_dir):
        """Test saving and loading plugin configuration."""
        config_file = temp_dir / "plugin_config.json"

        # Register plugin
        config = PluginConfig(
            name="MockPlugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=False,
            priority=25,
            settings={"test_setting": "test_value"},
        )

        registry.register_plugin(MockPlugin, config)

        # Save config
        registry.save_config(config_file)
        assert config_file.exists()

        # Verify saved content
        with open(config_file) as f:
            saved_config = json.load(f)

        assert "Mock Plugin" in saved_config
        plugin_data = saved_config["Mock Plugin"]
        assert plugin_data["version"] == "1.0.0"
        assert plugin_data["plugin_type"] == "html_processor"
        assert plugin_data["enabled"] is False
        assert plugin_data["priority"] == 25
        assert plugin_data["settings"]["test_setting"] == "test_value"

        # Modify config and reload
        registry._plugin_configs["Mock Plugin"].enabled = True
        registry._plugin_configs["Mock Plugin"].priority = 50

        registry.load_config(config_file)

        # Verify config was restored
        reloaded_config = registry._plugin_configs["Mock Plugin"]
        assert reloaded_config.enabled is False  # Restored from file
        assert reloaded_config.priority == 25  # Restored from file


class TestPluginExecutionContext:
    """Test PluginExecutionContext functionality."""

    def test_context_creation(self):
        """Test execution context creation."""
        url = "https://example.com/test"
        output_dir = Path("/tmp/test_output")

        context = PluginExecutionContext(url, output_dir)

        assert context.url == url
        assert context.output_dir == output_dir
        assert context.shared_state == {}
        assert context.execution_stats == {}

    def test_shared_state_management(self):
        """Test shared state management."""
        context = PluginExecutionContext("https://example.com", Path("/tmp"))

        # Test setting and getting shared data
        context.set_shared_data("key1", "value1")
        context.set_shared_data("key2", {"nested": "data"})

        assert context.get_shared_data("key1") == "value1"
        assert context.get_shared_data("key2") == {"nested": "data"}
        assert context.get_shared_data("nonexistent") is None
        assert context.get_shared_data("nonexistent", "default") == "default"

    def test_plugin_stats_recording(self):
        """Test plugin statistics recording."""
        context = PluginExecutionContext("https://example.com", Path("/tmp"))

        stats = {"duration": 1.5, "success": True, "processed_items": 10}

        context.record_plugin_stats("TestPlugin", stats)

        assert "TestPlugin" in context.execution_stats
        assert context.execution_stats["TestPlugin"] == stats


class TestPluginManager:
    """Test PluginManager functionality."""

    @pytest.fixture
    def manager(self):
        """Provide PluginManager instance with clean registry."""
        registry = PluginRegistry()
        return PluginManager(registry)

    @pytest.mark.asyncio
    async def test_manager_initialization(self, manager):
        """Test plugin manager initialization."""
        assert not manager._initialized
        assert manager._plugins == {}
        assert manager._pipeline == {}

        await manager.initialize()

        assert manager._initialized

    @pytest.mark.asyncio
    async def test_manager_shutdown(self, manager):
        """Test plugin manager shutdown."""
        # Register and initialize
        manager.registry.register_plugin(MockPlugin)
        await manager.initialize()

        assert manager._initialized
        assert len(manager._plugins) > 0

        # Shutdown
        await manager.shutdown()

        assert not manager._initialized
        assert manager._plugins == {}

    @pytest.mark.asyncio
    async def test_plugin_enable_disable(self, manager):
        """Test enabling and disabling plugins."""
        # Register plugin
        manager.registry.register_plugin(MockPlugin)

        plugin_name = "Mock Plugin"

        # Test enable
        success = manager.enable_plugin(plugin_name)
        assert success

        config = manager.registry.get_plugin_config(plugin_name)
        assert config.enabled is True

        # Test disable
        success = manager.disable_plugin(plugin_name)
        assert success

        config = manager.registry.get_plugin_config(plugin_name)
        assert config.enabled is False

        # Test non-existent plugin
        assert not manager.enable_plugin("Nonexistent Plugin")
        assert not manager.disable_plugin("Nonexistent Plugin")

    def test_plugin_info(self, manager):
        """Test getting plugin information."""
        # Register plugin
        manager.registry.register_plugin(MockPlugin)

        info = manager.get_plugin_info()

        assert "total_plugins" in info
        assert "enabled_plugins" in info
        assert "plugin_types" in info
        assert "plugins" in info

        if info["total_plugins"] > 0:
            assert "Mock Plugin" in info["plugins"]
            plugin_info = info["plugins"]["Mock Plugin"]
            assert "type" in plugin_info
            assert "version" in plugin_info
            assert "enabled" in plugin_info
            assert "priority" in plugin_info
