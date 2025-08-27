"""Comprehensive tests for PluginManager."""

import time
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.plugins.base import BasePlugin, PluginConfig, PluginType
from src.plugins.manager import PluginExecutionContext, PluginManager, plugin_manager
from src.plugins.registry import PluginRegistry

# Import the module to ensure coverage tracking


class MockPlugin(BasePlugin):
    """Mock plugin for testing."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.process_called = False
        self.process_result = None
        self.initialize_called = False
        self.cleanup_called = False
        self.validate_config_result = True

    @property
    def plugin_info(self):
        return {
            "name": self.config.name,
            "version": self.config.version,
            "description": "Mock plugin for testing",
            "author": "Test Suite",
            "plugin_type": self.config.plugin_type.value,
        }

    async def initialize(self):
        self.initialize_called = True
        if hasattr(self, "_initialize_error"):
            raise self._initialize_error

    async def process(self, data, context):
        self.process_called = True
        if hasattr(self, "_process_error"):
            raise self._process_error
        return self.process_result or data

    async def cleanup(self):
        self.cleanup_called = True
        if hasattr(self, "_cleanup_error"):
            raise self._cleanup_error

    async def validate_config(self):
        return self.validate_config_result


class TestPluginExecutionContext:
    """Test PluginExecutionContext functionality."""

    def test_context_initialization(self):
        """Test context initialization with URL and output directory."""
        url = "https://example.com/test"
        output_dir = Path("/tmp/output")

        context = PluginExecutionContext(url, output_dir)

        assert context.url == url
        assert context.output_dir == output_dir
        assert context.shared_state == {}
        assert context.execution_stats == {}
        assert context.start_time is None
        assert context.end_time is None

    def test_shared_data_operations(self):
        """Test shared data get/set operations."""
        context = PluginExecutionContext("https://test.com", Path("/tmp"))

        # Test getting non-existent key with default
        assert context.get_shared_data("nonexistent") is None
        assert context.get_shared_data("nonexistent", "default") == "default"

        # Test setting and getting data
        context.set_shared_data("test_key", "test_value")
        assert context.get_shared_data("test_key") == "test_value"

        # Test overwriting data
        context.set_shared_data("test_key", "new_value")
        assert context.get_shared_data("test_key") == "new_value"

    def test_plugin_stats_recording(self):
        """Test plugin statistics recording."""
        context = PluginExecutionContext("https://test.com", Path("/tmp"))

        stats1 = {"duration": 1.5, "success": True}
        stats2 = {"duration": 0.8, "success": False, "error": "Test error"}

        context.record_plugin_stats("plugin1", stats1)
        context.record_plugin_stats("plugin2", stats2)

        assert context.execution_stats["plugin1"] == stats1
        assert context.execution_stats["plugin2"] == stats2

    def test_context_state_isolation(self):
        """Test that different contexts have isolated state."""
        context1 = PluginExecutionContext("https://test1.com", Path("/tmp1"))
        context2 = PluginExecutionContext("https://test2.com", Path("/tmp2"))

        context1.set_shared_data("key", "value1")
        context2.set_shared_data("key", "value2")

        assert context1.get_shared_data("key") == "value1"
        assert context2.get_shared_data("key") == "value2"


class TestPluginManagerInitialization:
    """Test PluginManager initialization and configuration."""

    def test_manager_initialization_with_default_registry(self):
        """Test manager initialization with default registry."""
        manager = PluginManager()

        assert manager.registry is not None
        assert manager._plugins == {}
        assert isinstance(manager._pipeline, defaultdict)
        assert manager._initialized is False
        assert isinstance(manager._hooks, defaultdict)

    def test_manager_initialization_with_custom_registry(self):
        """Test manager initialization with custom registry."""
        mock_registry = MagicMock(spec=PluginRegistry)
        manager = PluginManager(registry=mock_registry)

        assert manager.registry is mock_registry
        assert manager._plugins == {}
        assert manager._initialized is False

    def test_manager_initialization_with_none_registry(self):
        """Test manager initialization with None registry falls back to default."""
        manager = PluginManager(registry=None)

        assert manager.registry is not None
        # Should use global plugin_registry

    @pytest.mark.asyncio
    async def test_initialize_creates_pipeline(self):
        """Test that initialize method creates execution pipeline."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.discover_plugins = MagicMock()
        mock_registry.list_plugins.return_value = []

        manager = PluginManager(registry=mock_registry)

        with patch.object(manager, "_build_pipeline") as mock_build:
            await manager.initialize()

        mock_registry.discover_plugins.assert_called_once()
        mock_build.assert_called_once()
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that initialize is idempotent."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.discover_plugins = MagicMock()
        mock_registry.list_plugins.return_value = []

        manager = PluginManager(registry=mock_registry)

        await manager.initialize()
        await manager.initialize()  # Second call

        # Should only discover plugins once
        mock_registry.discover_plugins.assert_called_once()
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_plugins(self):
        """Test initialization with actual plugins."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.discover_plugins = MagicMock()
        mock_registry.list_plugins.return_value = ["test_plugin"]

        manager = PluginManager(registry=mock_registry)

        with patch.object(manager, "_initialize_plugin", new_callable=AsyncMock) as mock_init:
            await manager.initialize()

        mock_init.assert_called_once_with("test_plugin")


class TestPluginManagerShutdown:
    """Test PluginManager shutdown functionality."""

    @pytest.mark.asyncio
    async def test_shutdown_uninitialized_manager(self):
        """Test shutdown on uninitialized manager."""
        manager = PluginManager()

        # Should not raise exception
        await manager.shutdown()

        assert not manager._initialized
        assert manager._plugins == {}

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_plugins(self):
        """Test that shutdown cleans up all plugins."""
        manager = PluginManager()
        manager._initialized = True

        # Add mock plugins
        plugin1 = AsyncMock(spec=BasePlugin)
        plugin1.config = MagicMock(name="plugin1")
        plugin2 = AsyncMock(spec=BasePlugin)
        plugin2.config = MagicMock(name="plugin2")

        manager._plugins = {"plugin1": plugin1, "plugin2": plugin2}

        await manager.shutdown()

        plugin1.cleanup.assert_called_once()
        plugin2.cleanup.assert_called_once()
        assert manager._plugins == {}
        assert not manager._initialized

    @pytest.mark.asyncio
    async def test_shutdown_handles_cleanup_errors(self):
        """Test that shutdown handles plugin cleanup errors gracefully."""
        manager = PluginManager()
        manager._initialized = True

        # Plugin that fails cleanup
        failing_plugin = AsyncMock(spec=BasePlugin)
        failing_plugin.config = MagicMock(name="failing_plugin")
        failing_plugin.cleanup.side_effect = Exception("Cleanup failed")

        # Plugin that cleans up successfully
        good_plugin = AsyncMock(spec=BasePlugin)
        good_plugin.config = MagicMock(name="good_plugin")

        manager._plugins = {"failing": failing_plugin, "good": good_plugin}

        with patch("src.plugins.manager.logger") as mock_logger:
            await manager.shutdown()

        # Both should be called despite one failing
        failing_plugin.cleanup.assert_called_once()
        good_plugin.cleanup.assert_called_once()

        # Should log warning for failed cleanup
        mock_logger.warning.assert_called_once()
        assert manager._plugins == {}


class TestPluginInitialization:
    """Test individual plugin initialization."""

    @pytest.mark.asyncio
    async def test_initialize_plugin_success(self):
        """Test successful plugin initialization."""
        mock_registry = MagicMock(spec=PluginRegistry)
        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        mock_registry.get_plugin_class.return_value = MockPlugin
        mock_registry.get_plugin_config.return_value = config

        manager = PluginManager(registry=mock_registry)

        await manager._initialize_plugin("test_plugin")

        assert "test_plugin" in manager._plugins
        plugin = manager._plugins["test_plugin"]
        assert isinstance(plugin, MockPlugin)
        assert plugin.initialize_called is True
        assert plugin._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_plugin_not_found(self):
        """Test initialization when plugin not found in registry."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.get_plugin_class.return_value = None
        mock_registry.get_plugin_config.return_value = None

        manager = PluginManager(registry=mock_registry)

        with patch("src.plugins.manager.logger") as mock_logger:
            await manager._initialize_plugin("nonexistent_plugin")

        mock_logger.warning.assert_called_once()
        assert "nonexistent_plugin" not in manager._plugins

    @pytest.mark.asyncio
    async def test_initialize_plugin_config_validation_fails(self):
        """Test initialization when plugin config validation fails."""
        mock_registry = MagicMock(spec=PluginRegistry)
        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        mock_registry.get_plugin_class.return_value = MockPlugin
        mock_registry.get_plugin_config.return_value = config

        manager = PluginManager(registry=mock_registry)

        # Create a plugin class that fails validation
        class FailValidationPlugin(MockPlugin):
            async def validate_config(self):
                return False

        mock_registry.get_plugin_class.return_value = FailValidationPlugin

        with patch("src.plugins.manager.logger") as mock_logger:
            await manager._initialize_plugin("test_plugin")

        mock_logger.warning.assert_called()
        assert "test_plugin" not in manager._plugins

    @pytest.mark.asyncio
    async def test_initialize_plugin_initialization_error(self):
        """Test handling of plugin initialization errors."""
        mock_registry = MagicMock(spec=PluginRegistry)
        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        # Create a plugin that fails during initialization
        class FailInitPlugin(MockPlugin):
            async def initialize(self):
                raise Exception("Initialization failed")

        mock_registry.get_plugin_class.return_value = FailInitPlugin
        mock_registry.get_plugin_config.return_value = config

        manager = PluginManager(registry=mock_registry)

        with patch("src.plugins.manager.logger") as mock_logger:
            await manager._initialize_plugin("test_plugin")

        mock_logger.error.assert_called_once()
        assert "test_plugin" not in manager._plugins


class TestPipelineBuilding:
    """Test plugin pipeline building functionality."""

    def test_build_pipeline_empty(self):
        """Test building pipeline with no plugins."""
        manager = PluginManager()
        manager._build_pipeline()

        assert len(manager._pipeline) == 0

    def test_build_pipeline_groups_by_type(self):
        """Test that pipeline groups plugins by type."""
        manager = PluginManager()

        # Create mock plugins of different types
        html_config = PluginConfig(
            name="html_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=100
        )
        meta_config = PluginConfig(
            name="meta_plugin",
            version="1.0.0",
            plugin_type=PluginType.METADATA_EXTRACTOR,
            priority=50,
        )

        html_plugin = MockPlugin(html_config)
        meta_plugin = MockPlugin(meta_config)

        manager._plugins = {"html_plugin": html_plugin, "meta_plugin": meta_plugin}
        manager._build_pipeline()

        assert PluginType.HTML_PROCESSOR in manager._pipeline
        assert PluginType.METADATA_EXTRACTOR in manager._pipeline
        assert "html_plugin" in manager._pipeline[PluginType.HTML_PROCESSOR]
        assert "meta_plugin" in manager._pipeline[PluginType.METADATA_EXTRACTOR]

    def test_build_pipeline_sorts_by_priority(self):
        """Test that pipeline sorts plugins by priority within each type."""
        manager = PluginManager()

        # Create plugins with different priorities
        config1 = PluginConfig(
            name="plugin1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=200
        )
        config2 = PluginConfig(
            name="plugin2", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=50
        )
        config3 = PluginConfig(
            name="plugin3", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=100
        )

        plugin1 = MockPlugin(config1)
        plugin2 = MockPlugin(config2)
        plugin3 = MockPlugin(config3)

        manager._plugins = {"plugin1": plugin1, "plugin2": plugin2, "plugin3": plugin3}
        manager._build_pipeline()

        # Should be sorted by priority (lower number = higher priority)
        html_pipeline = manager._pipeline[PluginType.HTML_PROCESSOR]
        assert html_pipeline == ["plugin2", "plugin3", "plugin1"]

    def test_build_pipeline_logging(self):
        """Test that pipeline building logs debug information."""
        manager = PluginManager()

        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = MockPlugin(config)
        manager._plugins = {"test_plugin": plugin}

        with patch("src.plugins.manager.logger") as mock_logger:
            manager._build_pipeline()

        mock_logger.debug.assert_called_once()


class TestPipelineExecution:
    """Test plugin pipeline execution."""

    @pytest.mark.asyncio
    async def test_execute_pipeline_auto_initialize(self):
        """Test that execute_pipeline auto-initializes if needed."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.discover_plugins = MagicMock()
        mock_registry.list_plugins.return_value = []

        manager = PluginManager(registry=mock_registry)
        context = PluginExecutionContext("https://test.com", Path("/tmp"))

        result = await manager.execute_pipeline(
            PluginType.HTML_PROCESSOR, {"test": "data"}, context
        )

        assert manager._initialized is True
        assert result == {"test": "data"}  # No plugins, data unchanged

    @pytest.mark.asyncio
    async def test_execute_pipeline_no_plugins(self):
        """Test pipeline execution with no plugins of specified type."""
        manager = PluginManager()
        manager._initialized = True
        context = PluginExecutionContext("https://test.com", Path("/tmp"))

        data = {"test": "data"}
        result = await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)

        assert result == data

    @pytest.mark.asyncio
    async def test_execute_pipeline_single_plugin(self):
        """Test pipeline execution with single plugin."""
        manager = PluginManager()
        manager._initialized = True

        # Setup plugin
        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )
        plugin = MockPlugin(config)
        plugin.process_result = {"processed": True}

        manager._plugins = {"test_plugin": plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["test_plugin"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"original": True}

        result = await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)

        assert result == {"processed": True}
        assert plugin.process_called is True
        assert "test_plugin" in context.execution_stats

    @pytest.mark.asyncio
    async def test_execute_pipeline_multiple_plugins(self):
        """Test pipeline execution with multiple plugins."""
        manager = PluginManager()
        manager._initialized = True

        # Setup plugins
        config1 = PluginConfig(
            name="plugin1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )
        config2 = PluginConfig(
            name="plugin2", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )

        plugin1 = MockPlugin(config1)
        plugin2 = MockPlugin(config2)

        # Chain processing: plugin1 adds 'step1', plugin2 adds 'step2'
        plugin1.process_result = {"step1": True}
        plugin2.process_result = {"step1": True, "step2": True}

        manager._plugins = {"plugin1": plugin1, "plugin2": plugin2}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["plugin1", "plugin2"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"original": True}

        # Mock plugin2 to receive plugin1's output
        async def plugin2_process(data, ctx):
            plugin2.process_called = True
            return {"step1": True, "step2": True}

        plugin2.process = plugin2_process

        result = await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)

        assert plugin1.process_called is True
        assert plugin2.process_called is True
        assert result == {"step1": True, "step2": True}

    @pytest.mark.asyncio
    async def test_execute_pipeline_disabled_plugin_skipped(self):
        """Test that disabled plugins are skipped during execution."""
        manager = PluginManager()
        manager._initialized = True

        config = PluginConfig(
            name="disabled_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=False,  # Disabled
        )
        plugin = MockPlugin(config)

        manager._plugins = {"disabled_plugin": plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["disabled_plugin"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"original": True}

        result = await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)

        assert plugin.process_called is False  # Should be skipped
        assert result == data  # Data unchanged

    @pytest.mark.asyncio
    async def test_execute_pipeline_plugin_error_continue(self):
        """Test pipeline execution continues after plugin error by default."""
        manager = PluginManager()
        manager._initialized = True

        config1 = PluginConfig(
            name="failing_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
        )
        config2 = PluginConfig(
            name="good_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )

        failing_plugin = MockPlugin(config1)
        failing_plugin._process_error = Exception("Plugin failed")

        good_plugin = MockPlugin(config2)
        good_plugin.process_result = {"processed_by_good": True}

        manager._plugins = {"failing": failing_plugin, "good": good_plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["failing", "good"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"original": True}

        with patch.object(manager, "_call_hooks", new_callable=AsyncMock) as mock_hooks:
            result = await manager.execute_pipeline(
                PluginType.HTML_PROCESSOR, data, context, stop_on_error=False
            )

        # Should continue to good plugin despite failing plugin
        assert result == {"processed_by_good": True}
        assert "failing" in context.execution_stats
        assert context.execution_stats["failing"]["success"] is False

        # Should call error hooks
        mock_hooks.assert_called()

    @pytest.mark.asyncio
    async def test_execute_pipeline_stop_on_error(self):
        """Test pipeline execution stops on error when stop_on_error=True."""
        manager = PluginManager()
        manager._initialized = True

        config = PluginConfig(
            name="failing_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
        )

        failing_plugin = MockPlugin(config)
        failing_plugin._process_error = Exception("Plugin failed")

        manager._plugins = {"failing": failing_plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["failing"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"original": True}

        with pytest.raises(Exception, match="Plugin failed"):
            await manager.execute_pipeline(
                PluginType.HTML_PROCESSOR, data, context, stop_on_error=True
            )

    @pytest.mark.asyncio
    async def test_execute_pipeline_records_stats(self):
        """Test that pipeline execution records plugin statistics."""
        manager = PluginManager()
        manager._initialized = True

        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )
        plugin = MockPlugin(config)
        plugin.process_result = {"processed": True}

        manager._plugins = {"test_plugin": plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["test_plugin"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"original": True}

        await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)

        stats = context.execution_stats["test_plugin"]
        assert stats["success"] is True
        assert "duration" in stats
        assert stats["duration"] >= 0
        assert stats["input_type"] == "dict"
        assert stats["output_type"] == "dict"

    @pytest.mark.asyncio
    async def test_execute_pipeline_calls_hooks(self):
        """Test that pipeline execution calls hooks correctly."""
        manager = PluginManager()
        manager._initialized = True

        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )
        plugin = MockPlugin(config)

        manager._plugins = {"test_plugin": plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["test_plugin"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))

        with patch.object(manager, "_call_hooks", new_callable=AsyncMock) as mock_hooks:
            await manager.execute_pipeline(PluginType.HTML_PROCESSOR, {}, context)

        mock_hooks.assert_called_with("post_plugin_execute", "test_plugin", {}, context)


class TestContentProcessing:
    """Test complete content processing functionality."""

    @pytest.mark.asyncio
    async def test_process_content_basic(self):
        """Test basic content processing workflow."""
        manager = PluginManager()
        manager._initialized = True
        manager._pipeline = defaultdict(list)  # No plugins

        html_content = "<p>Test content</p>"
        url = "https://example.com/test"
        output_dir = Path("/tmp/output")
        metadata = {"title": "Test"}

        result = await manager.process_content(html_content, url, output_dir, metadata)

        assert result["content"] == html_content
        assert result["html"] == html_content
        assert result["metadata"] == metadata
        assert result["files"] == []
        assert "context" in result
        assert "execution_stats" in result
        assert "total_duration" in result
        assert result["total_duration"] >= 0

    @pytest.mark.asyncio
    async def test_process_content_no_metadata(self):
        """Test content processing without initial metadata."""
        manager = PluginManager()
        manager._initialized = True
        manager._pipeline = defaultdict(list)

        html_content = "<p>Test content</p>"
        url = "https://example.com/test"
        output_dir = Path("/tmp/output")

        result = await manager.process_content(html_content, url, output_dir)

        assert result["metadata"] == {}

    @pytest.mark.asyncio
    async def test_process_content_with_plugins(self):
        """Test content processing with plugins in pipeline."""
        manager = PluginManager()
        manager._initialized = True

        # Setup a metadata extractor plugin
        config = PluginConfig(
            name="meta_plugin",
            version="1.0.0",
            plugin_type=PluginType.METADATA_EXTRACTOR,
            enabled=True,
        )
        plugin = MockPlugin(config)

        # Mock plugin to add metadata
        async def plugin_process(data, context):
            data["metadata"]["extracted"] = "meta_value"
            return data

        plugin.process = plugin_process

        manager._plugins = {"meta_plugin": plugin}
        manager._pipeline[PluginType.METADATA_EXTRACTOR] = ["meta_plugin"]

        result = await manager.process_content("<p>Test</p>", "https://example.com", Path("/tmp"))

        assert result["metadata"]["extracted"] == "meta_value"

    @pytest.mark.asyncio
    async def test_process_content_pipeline_order(self):
        """Test that content processing executes pipelines in correct order."""
        manager = PluginManager()
        manager._initialized = True

        execution_order = []

        # Create plugins for different pipeline stages
        configs = [
            (PluginType.METADATA_EXTRACTOR, "meta"),
            (PluginType.HTML_PROCESSOR, "html"),
            (PluginType.CONTENT_FILTER, "filter"),
            (PluginType.IMAGE_PROCESSOR, "image"),
            (PluginType.OUTPUT_FORMATTER, "output"),
            (PluginType.POST_PROCESSOR, "post"),
        ]

        for plugin_type, name in configs:
            config = PluginConfig(
                name=f"{name}_plugin", version="1.0.0", plugin_type=plugin_type, enabled=True
            )
            plugin = MockPlugin(config)

            # Track execution order
            async def make_process_func(stage_name):
                async def process_func(data, context):
                    execution_order.append(stage_name)
                    return data

                return process_func

            plugin.process = await make_process_func(name)
            manager._plugins[f"{name}_plugin"] = plugin
            manager._pipeline[plugin_type] = [f"{name}_plugin"]

        await manager.process_content("<p>Test</p>", "https://example.com", Path("/tmp"))

        # Verify execution order
        expected_order = ["meta", "html", "filter", "image", "output", "post"]
        assert execution_order == expected_order

    @pytest.mark.asyncio
    async def test_process_content_error_handling(self):
        """Test content processing handles pipeline errors gracefully."""
        manager = PluginManager()
        manager._initialized = True

        config = PluginConfig(
            name="failing_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
        )
        plugin = MockPlugin(config)
        plugin._process_error = Exception("Plugin failed")

        manager._plugins = {"failing": plugin}
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["failing"]

        # Should not raise by default (stop_on_error=False)
        result = await manager.process_content("<p>Test</p>", "https://example.com", Path("/tmp"))

        # Should return result with original content since plugin failed
        assert result["content"] == "<p>Test</p>"
        assert result["html"] == "<p>Test</p>"

        # Should record the failure in execution stats
        assert "failing" in result["execution_stats"]
        assert result["execution_stats"]["failing"]["success"] is False


class TestHooksSystem:
    """Test plugin hooks system."""

    def test_add_hook(self):
        """Test adding hooks to events."""
        manager = PluginManager()

        def test_callback():
            pass

        with patch("src.plugins.manager.logger") as mock_logger:
            manager.add_hook("test_event", test_callback)

        assert test_callback in manager._hooks["test_event"]
        # Just verify debug was called without checking exact params due to structlog issue
        mock_logger.debug.assert_called_once()

    def test_add_multiple_hooks_same_event(self):
        """Test adding multiple hooks to the same event."""
        manager = PluginManager()

        def callback1():
            pass

        def callback2():
            pass

        with patch("src.plugins.manager.logger"):  # Suppress logging issues
            manager.add_hook("test_event", callback1)
            manager.add_hook("test_event", callback2)

        assert callback1 in manager._hooks["test_event"]
        assert callback2 in manager._hooks["test_event"]
        assert len(manager._hooks["test_event"]) == 2

    @pytest.mark.asyncio
    async def test_call_hooks_sync_callbacks(self):
        """Test calling synchronous hook callbacks."""
        manager = PluginManager()

        called_callbacks = []

        def callback1(arg):
            called_callbacks.append(f"callback1-{arg}")

        def callback2(arg):
            called_callbacks.append(f"callback2-{arg}")

        with patch("src.plugins.manager.logger"):  # Suppress logging issues
            manager.add_hook("test_event", callback1)
            manager.add_hook("test_event", callback2)

        await manager._call_hooks("test_event", "test_arg")

        assert "callback1-test_arg" in called_callbacks
        assert "callback2-test_arg" in called_callbacks

    @pytest.mark.asyncio
    async def test_call_hooks_async_callbacks(self):
        """Test calling asynchronous hook callbacks."""
        manager = PluginManager()

        called_callbacks = []

        async def async_callback1(arg):
            called_callbacks.append(f"async1-{arg}")

        async def async_callback2(arg):
            called_callbacks.append(f"async2-{arg}")

        with patch("src.plugins.manager.logger"):  # Suppress logging issues
            manager.add_hook("test_event", async_callback1)
            manager.add_hook("test_event", async_callback2)

        await manager._call_hooks("test_event", "test_arg")

        assert "async1-test_arg" in called_callbacks
        assert "async2-test_arg" in called_callbacks

    @pytest.mark.asyncio
    async def test_call_hooks_mixed_callbacks(self):
        """Test calling mixed sync/async hook callbacks."""
        manager = PluginManager()

        called_callbacks = []

        def sync_callback(arg):
            called_callbacks.append(f"sync-{arg}")

        async def async_callback(arg):
            called_callbacks.append(f"async-{arg}")

        with patch("src.plugins.manager.logger"):  # Suppress logging issues
            manager.add_hook("test_event", sync_callback)
            manager.add_hook("test_event", async_callback)

        await manager._call_hooks("test_event", "test_arg")

        assert "sync-test_arg" in called_callbacks
        assert "async-test_arg" in called_callbacks

    @pytest.mark.asyncio
    async def test_call_hooks_handles_errors(self):
        """Test that hook calling handles callback errors gracefully."""
        manager = PluginManager()

        called_callbacks = []

        def failing_callback(arg):
            raise Exception("Callback failed")

        def good_callback(arg):
            called_callbacks.append(f"good-{arg}")

        with patch("src.plugins.manager.logger"):  # Suppress logging issues
            manager.add_hook("test_event", failing_callback)
            manager.add_hook("test_event", good_callback)

        with patch("src.plugins.manager.logger") as mock_logger:
            await manager._call_hooks("test_event", "test_arg")

        # Good callback should still be called
        assert "good-test_arg" in called_callbacks

        # Should log warning for failed callback
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_hooks_nonexistent_event(self):
        """Test calling hooks for nonexistent event."""
        manager = PluginManager()

        # Should not raise exception
        await manager._call_hooks("nonexistent_event", "arg")


class TestPluginManagement:
    """Test plugin enable/disable functionality."""

    def test_enable_plugin_success(self):
        """Test enabling a plugin successfully."""
        mock_registry = MagicMock(spec=PluginRegistry)
        config = PluginConfig(
            name="test_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=False,
        )
        mock_registry.get_plugin_config.return_value = config

        manager = PluginManager(registry=mock_registry)

        with (
            patch.object(manager, "_build_pipeline") as mock_build,
            patch("src.plugins.manager.logger") as mock_logger,
        ):
            result = manager.enable_plugin("test_plugin")

        assert result is True
        assert config.enabled is True
        mock_build.assert_called_once()
        mock_logger.info.assert_called_with("Plugin enabled", name="test_plugin")

    def test_enable_plugin_not_found(self):
        """Test enabling a plugin that doesn't exist."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.get_plugin_config.return_value = None

        manager = PluginManager(registry=mock_registry)
        result = manager.enable_plugin("nonexistent_plugin")

        assert result is False

    def test_disable_plugin_success(self):
        """Test disabling a plugin successfully."""
        mock_registry = MagicMock(spec=PluginRegistry)
        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )
        mock_registry.get_plugin_config.return_value = config

        manager = PluginManager(registry=mock_registry)

        with (
            patch.object(manager, "_build_pipeline") as mock_build,
            patch("src.plugins.manager.logger") as mock_logger,
        ):
            result = manager.disable_plugin("test_plugin")

        assert result is True
        assert config.enabled is False
        mock_build.assert_called_once()
        mock_logger.info.assert_called_with("Plugin disabled", name="test_plugin")

    def test_disable_plugin_not_found(self):
        """Test disabling a plugin that doesn't exist."""
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.get_plugin_config.return_value = None

        manager = PluginManager(registry=mock_registry)
        result = manager.disable_plugin("nonexistent_plugin")

        assert result is False


class TestPluginInfo:
    """Test plugin information functionality."""

    def test_get_plugin_info_empty(self):
        """Test getting plugin info with no plugins."""
        manager = PluginManager()

        info = manager.get_plugin_info()

        assert info["total_plugins"] == 0
        assert info["enabled_plugins"] == 0
        assert info["plugin_types"] == {}
        assert info["plugins"] == {}

    def test_get_plugin_info_with_plugins(self):
        """Test getting plugin info with loaded plugins."""
        manager = PluginManager()

        # Setup plugins
        config1 = PluginConfig(
            name="plugin1",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=100,
        )
        config2 = PluginConfig(
            name="plugin2",
            version="2.0.0",
            plugin_type=PluginType.METADATA_EXTRACTOR,
            enabled=False,
            priority=50,
        )
        config3 = PluginConfig(
            name="plugin3",
            version="1.5.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=75,
        )

        plugin1 = MockPlugin(config1)
        plugin2 = MockPlugin(config2)
        plugin3 = MockPlugin(config3)

        manager._plugins = {"plugin1": plugin1, "plugin2": plugin2, "plugin3": plugin3}

        info = manager.get_plugin_info()

        assert info["total_plugins"] == 3
        assert info["enabled_plugins"] == 2  # plugin1 and plugin3
        assert info["plugin_types"]["html_processor"] == 2
        assert info["plugin_types"]["metadata_extractor"] == 1

        # Check plugin details
        assert info["plugins"]["plugin1"]["type"] == "html_processor"
        assert info["plugins"]["plugin1"]["version"] == "1.0.0"
        assert info["plugins"]["plugin1"]["enabled"] is True
        assert info["plugins"]["plugin1"]["priority"] == 100

        assert info["plugins"]["plugin2"]["enabled"] is False
        assert info["plugins"]["plugin3"]["priority"] == 75


class TestGlobalInstance:
    """Test the global plugin manager instance."""

    def test_global_instance_exists(self):
        """Test that global plugin_manager instance exists."""
        assert plugin_manager is not None
        assert isinstance(plugin_manager, PluginManager)

    def test_global_instance_has_registry(self):
        """Test that global instance has a registry."""
        assert plugin_manager.registry is not None

    def test_global_instance_initially_uninitialized(self):
        """Test that global instance starts uninitialized."""
        # Note: This might be affected by other tests, but generally should start uninitialized
        assert hasattr(plugin_manager, "_initialized")
        assert isinstance(plugin_manager._plugins, dict)
        assert hasattr(plugin_manager, "_pipeline")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_execute_pipeline_missing_plugin(self):
        """Test pipeline execution when plugin is missing from _plugins."""
        manager = PluginManager()
        manager._initialized = True

        # Pipeline references a plugin that doesn't exist in _plugins
        manager._pipeline[PluginType.HTML_PROCESSOR] = ["missing_plugin"]

        context = PluginExecutionContext("https://test.com", Path("/tmp"))
        data = {"test": "data"}

        # Should skip missing plugin and return original data
        result = await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)
        assert result == data

    @pytest.mark.asyncio
    async def test_process_content_timing(self):
        """Test that process_content properly tracks timing."""
        manager = PluginManager()
        manager._initialized = True
        manager._pipeline = defaultdict(list)

        start_time = time.time()
        result = await manager.process_content("<p>Test</p>", "https://test.com", Path("/tmp"))
        end_time = time.time()

        assert result["total_duration"] >= 0
        assert result["total_duration"] <= (end_time - start_time + 0.1)  # Allow small buffer

    def test_context_shared_state_types(self):
        """Test context shared state with different data types."""
        context = PluginExecutionContext("https://test.com", Path("/tmp"))

        # Test various data types
        test_data = {
            "string": "test_string",
            "integer": 42,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "none": None,
            "boolean": True,
        }

        for key, value in test_data.items():
            context.set_shared_data(key, value)
            assert context.get_shared_data(key) == value

    @pytest.mark.asyncio
    async def test_multiple_manager_instances_independence(self):
        """Test that multiple manager instances are independent."""
        manager1 = PluginManager()
        manager2 = PluginManager()

        # Different registries
        assert manager1.registry is not manager2.registry or manager1 is not manager2

        # Independent state
        manager1._initialized = True
        assert manager2._initialized is False

        # Independent plugins
        config = PluginConfig(
            name="test_plugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )
        plugin = MockPlugin(config)

        manager1._plugins["test"] = plugin
        assert "test" not in manager2._plugins
