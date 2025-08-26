"""Tests for plugin system components."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.plugins.base import (
    BasePlugin, HTMLProcessorPlugin, ContentFilterPlugin, 
    ImageProcessorPlugin, MetadataExtractorPlugin, OutputFormatterPlugin,
    PostProcessorPlugin, PluginConfig, PluginType
)
from src.plugins.manager import PluginManager
from src.plugins.registry import PluginRegistry


class TestPluginConfig:
    """Test plugin configuration."""

    def test_plugin_config_creation(self):
        """Test basic plugin configuration creation."""
        config = PluginConfig(
            name="test_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=100
        )
        
        assert config.name == "test_plugin"
        assert config.version == "1.0.0"
        assert config.plugin_type == PluginType.HTML_PROCESSOR
        assert config.enabled is True
        assert config.priority == 100
        assert config.settings == {}

    def test_plugin_config_with_settings(self):
        """Test plugin configuration with custom settings."""
        settings = {"setting1": "value1", "setting2": 123}
        config = PluginConfig(
            name="test_plugin",
            version="1.0.0",
            plugin_type=PluginType.CONTENT_FILTER,
            settings=settings
        )
        
        assert config.settings == settings

    def test_plugin_config_defaults(self):
        """Test plugin configuration defaults."""
        config = PluginConfig(
            name="minimal_plugin",
            version="1.0.0",
            plugin_type=PluginType.POST_PROCESSOR
        )
        
        assert config.enabled is True
        assert config.priority == 100
        assert config.settings == {}


class TestBasePlugin:
    """Test base plugin functionality."""

    class MockPlugin(BasePlugin):
        """Mock plugin for testing base functionality."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_plugin",
                "version": "1.0.0",
                "description": "Mock plugin for testing",
                "author": "Test Author",
                "plugin_type": PluginType.HTML_PROCESSOR
            }
        
        async def initialize(self):
            self._initialized = True
        
        async def process(self, data, context):
            return f"processed_{data}"

    def test_base_plugin_initialization(self, plugin_config):
        """Test base plugin initialization."""
        plugin = self.MockPlugin(plugin_config)
        
        assert plugin.config == plugin_config
        assert hasattr(plugin, 'logger')
        assert plugin._initialized is False

    def test_plugin_info_property(self, plugin_config):
        """Test plugin info property."""
        plugin = self.MockPlugin(plugin_config)
        info = plugin.plugin_info
        
        assert info["name"] == "mock_plugin"
        assert info["version"] == "1.0.0"
        assert info["plugin_type"] == PluginType.HTML_PROCESSOR

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, plugin_config):
        """Test plugin initialization process."""
        plugin = self.MockPlugin(plugin_config)
        
        assert plugin._initialized is False
        await plugin.initialize()
        assert plugin._initialized is True

    @pytest.mark.asyncio
    async def test_plugin_processing(self, plugin_config):
        """Test plugin processing."""
        plugin = self.MockPlugin(plugin_config)
        
        result = await plugin.process("test_data", {})
        assert result == "processed_test_data"

    def test_plugin_settings(self, plugin_config):
        """Test plugin settings management."""
        plugin_config.settings = {"test_setting": "test_value"}
        plugin = self.MockPlugin(plugin_config)
        
        # Test getting setting
        value = plugin.get_setting("test_setting")
        assert value == "test_value"
        
        # Test getting non-existent setting with default
        default_value = plugin.get_setting("missing_setting", "default")
        assert default_value == "default"
        
        # Test setting value
        plugin.set_setting("new_setting", "new_value")
        assert plugin.get_setting("new_setting") == "new_value"

    def test_plugin_enabled_check(self, plugin_config):
        """Test plugin enabled check."""
        plugin = self.MockPlugin(plugin_config)
        
        plugin_config.enabled = True
        assert plugin.is_enabled() is True
        
        plugin_config.enabled = False
        assert plugin.is_enabled() is False

    def test_plugin_priority(self, plugin_config):
        """Test plugin priority."""
        plugin_config.priority = 50
        plugin = self.MockPlugin(plugin_config)
        
        assert plugin.get_priority() == 50

    @pytest.mark.asyncio
    async def test_plugin_cleanup(self, plugin_config):
        """Test plugin cleanup."""
        plugin = self.MockPlugin(plugin_config)
        
        # Should not raise error (default implementation does nothing)
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_plugin_config_validation(self, plugin_config):
        """Test plugin configuration validation."""
        plugin = self.MockPlugin(plugin_config)
        
        # Default implementation should return True
        assert await plugin.validate_config() is True


class TestHTMLProcessorPlugin:
    """Test HTML processor plugin base class."""

    class MockHTMLProcessor(HTMLProcessorPlugin):
        """Mock HTML processor plugin."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_html_processor",
                "version": "1.0.0",
                "description": "Mock HTML processor",
                "author": "Test Author",
                "plugin_type": PluginType.HTML_PROCESSOR
            }
        
        async def initialize(self):
            pass
        
        async def process_html(self, html_content, metadata, context):
            return html_content.replace("old", "new")

    @pytest.mark.asyncio
    async def test_html_processor_plugin(self, plugin_config):
        """Test HTML processor plugin functionality."""
        plugin = self.MockHTMLProcessor(plugin_config)
        
        data = {
            "html": "<p>This is old content</p>",
            "metadata": {"title": "Test"}
        }
        context = {"url": "http://example.com"}
        
        result = await plugin.process(data, context)
        
        assert result["html"] == "<p>This is new content</p>"
        assert result["metadata"] == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_html_processor_invalid_data(self, plugin_config):
        """Test HTML processor with invalid data."""
        plugin = self.MockHTMLProcessor(plugin_config)
        
        # Test with invalid data structure
        with pytest.raises(ValueError, match="HTMLProcessorPlugin expects dict with 'html' key"):
            await plugin.process("invalid_data", {})
        
        with pytest.raises(ValueError, match="HTMLProcessorPlugin expects dict with 'html' key"):
            await plugin.process({"no_html": "content"}, {})


class TestContentFilterPlugin:
    """Test content filter plugin base class."""

    class MockContentFilter(ContentFilterPlugin):
        """Mock content filter plugin."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_content_filter",
                "version": "1.0.0",
                "description": "Mock content filter",
                "author": "Test Author",
                "plugin_type": PluginType.CONTENT_FILTER
            }
        
        async def initialize(self):
            pass
        
        async def filter_content(self, content, content_type, context):
            if content_type == "html":
                return content.replace("bad", "good")
            return content

    @pytest.mark.asyncio
    async def test_content_filter_plugin(self, plugin_config):
        """Test content filter plugin functionality."""
        plugin = self.MockContentFilter(plugin_config)
        
        data = {
            "content": "<p>This is bad content</p>",
            "content_type": "html"
        }
        context = {}
        
        result = await plugin.process(data, context)
        
        assert result["content"] == "<p>This is good content</p>"
        assert result["content_type"] == "html"

    @pytest.mark.asyncio
    async def test_content_filter_invalid_data(self, plugin_config):
        """Test content filter with invalid data."""
        plugin = self.MockContentFilter(plugin_config)
        
        with pytest.raises(ValueError, match="ContentFilterPlugin expects dict with 'content' key"):
            await plugin.process({"no_content": "data"}, {})


class TestImageProcessorPlugin:
    """Test image processor plugin base class."""

    class MockImageProcessor(ImageProcessorPlugin):
        """Mock image processor plugin."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_image_processor",
                "version": "1.0.0",
                "description": "Mock image processor",
                "author": "Test Author",
                "plugin_type": PluginType.IMAGE_PROCESSOR
            }
        
        async def initialize(self):
            pass
        
        async def process_image(self, image_url, image_data, metadata, context):
            return {
                "data": image_data + b"_processed",
                "metadata": {**metadata, "processed": True},
                "format": "jpeg",
                "size": (100, 100)
            }

    @pytest.mark.asyncio
    async def test_image_processor_plugin(self, plugin_config):
        """Test image processor plugin functionality."""
        plugin = self.MockImageProcessor(plugin_config)
        
        data = {
            "url": "http://example.com/image.jpg",
            "image_data": b"image_data",
            "metadata": {"alt": "test image"}
        }
        context = {}
        
        result = await plugin.process(data, context)
        
        assert result["data"] == b"image_data_processed"
        assert result["metadata"]["processed"] is True
        assert result["format"] == "jpeg"
        assert result["size"] == (100, 100)

    @pytest.mark.asyncio
    async def test_image_processor_invalid_data(self, plugin_config):
        """Test image processor with invalid data."""
        plugin = self.MockImageProcessor(plugin_config)
        
        with pytest.raises(ValueError, match="ImageProcessorPlugin expects dict with 'image_data' key"):
            await plugin.process({"no_image_data": "data"}, {})


class TestMetadataExtractorPlugin:
    """Test metadata extractor plugin base class."""

    class MockMetadataExtractor(MetadataExtractorPlugin):
        """Mock metadata extractor plugin."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_metadata_extractor",
                "version": "1.0.0",
                "description": "Mock metadata extractor",
                "author": "Test Author",
                "plugin_type": PluginType.METADATA_EXTRACTOR
            }
        
        async def initialize(self):
            pass
        
        async def extract_metadata(self, html_content, url, context):
            return {
                "extracted_title": "Test Title",
                "word_count": len(html_content.split())
            }

    @pytest.mark.asyncio
    async def test_metadata_extractor_plugin(self, plugin_config):
        """Test metadata extractor plugin functionality."""
        plugin = self.MockMetadataExtractor(plugin_config)
        
        data = {
            "html": "<p>This is test content</p>",
            "url": "http://example.com/page",
            "metadata": {"existing": "value"}
        }
        context = {}
        
        result = await plugin.process(data, context)
        
        assert result["metadata"]["extracted_title"] == "Test Title"
        assert result["metadata"]["word_count"] == 4
        assert result["metadata"]["existing"] == "value"  # Preserved


class TestOutputFormatterPlugin:
    """Test output formatter plugin base class."""

    class MockOutputFormatter(OutputFormatterPlugin):
        """Mock output formatter plugin."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_output_formatter",
                "version": "1.0.0",
                "description": "Mock output formatter",
                "author": "Test Author",
                "plugin_type": PluginType.OUTPUT_FORMATTER
            }
        
        async def initialize(self):
            pass
        
        async def format_output(self, content, metadata, output_format, context):
            if output_format == "markdown":
                return f"# {metadata.get('title', 'No Title')}\n\n{content}"
            return content

    @pytest.mark.asyncio
    async def test_output_formatter_plugin(self, plugin_config):
        """Test output formatter plugin functionality."""
        plugin = self.MockOutputFormatter(plugin_config)
        
        data = {
            "content": "This is content",
            "metadata": {"title": "Test Page"},
            "output_format": "markdown"
        }
        context = {}
        
        result = await plugin.process(data, context)
        
        assert result["content"] == "# Test Page\n\nThis is content"


class TestPostProcessorPlugin:
    """Test post processor plugin base class."""

    class MockPostProcessor(PostProcessorPlugin):
        """Mock post processor plugin."""
        
        @property
        def plugin_info(self):
            return {
                "name": "mock_post_processor",
                "version": "1.0.0",
                "description": "Mock post processor",
                "author": "Test Author",
                "plugin_type": PluginType.POST_PROCESSOR
            }
        
        async def initialize(self):
            pass
        
        async def post_process(self, output_dir, files, metadata, context):
            return {
                "processed_files": len(files),
                "output_dir": str(output_dir)
            }

    @pytest.mark.asyncio
    async def test_post_processor_plugin(self, plugin_config, temp_dir):
        """Test post processor plugin functionality."""
        plugin = self.MockPostProcessor(plugin_config)
        
        data = {
            "output_dir": str(temp_dir),
            "files": ["file1.html", "file2.txt"],
            "metadata": {"title": "Test"}
        }
        context = {}
        
        result = await plugin.process(data, context)
        
        assert result["post_process_result"]["processed_files"] == 2
        assert result["post_process_result"]["output_dir"] == str(temp_dir)

    @pytest.mark.asyncio
    async def test_post_processor_invalid_data(self, plugin_config):
        """Test post processor with invalid data."""
        plugin = self.MockPostProcessor(plugin_config)
        
        with pytest.raises(ValueError, match="PostProcessorPlugin requires 'output_dir' in data"):
            await plugin.process({"files": []}, {})


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def test_plugin_registry_initialization(self):
        """Test plugin registry initialization."""
        registry = PluginRegistry()
        
        assert isinstance(registry._plugins, dict)
        assert len(registry._plugins) == 0

    def test_register_plugin(self, plugin_config):
        """Test plugin registration."""
        registry = PluginRegistry()
        
        class TestPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        registry.register_plugin(TestPlugin, plugin_config)
        
        assert "test" in registry._plugins
        assert registry._plugins["test"] == TestPlugin

    def test_register_duplicate_plugin(self, plugin_config):
        """Test registering duplicate plugin names overwrites existing."""
        registry = PluginRegistry()
        
        class TestPlugin1(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
            
        class TestPlugin2(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "2.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        registry.register_plugin(TestPlugin1, plugin_config)
        assert registry.get_plugin_class("test") == TestPlugin1
        
        # Registering with same name should overwrite
        registry.register_plugin(TestPlugin2, plugin_config)
        assert registry.get_plugin_class("test") == TestPlugin2

    def test_get_plugin(self, plugin_config):
        """Test getting plugin from registry."""
        registry = PluginRegistry()
        
        class TestPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        registry.register_plugin(TestPlugin, plugin_config)
        
        retrieved = registry.get_plugin_class("test")
        assert retrieved == TestPlugin
        
        # Test non-existent plugin
        assert registry.get_plugin_class("non_existent") is None

    def test_get_plugins_by_type(self, plugin_config):
        """Test getting plugins by type."""
        registry = PluginRegistry()
        
        class HTMLPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "html", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        class FilterPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "filter", "version": "1.0.0", "plugin_type": PluginType.CONTENT_FILTER}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        html_config = PluginConfig("html", "1.0.0", PluginType.HTML_PROCESSOR)
        filter_config = PluginConfig("filter", "1.0.0", PluginType.CONTENT_FILTER)
        
        registry.register_plugin(HTMLPlugin, html_config)
        registry.register_plugin(FilterPlugin, filter_config)
        
        html_plugins = registry.list_plugins(plugin_type=PluginType.HTML_PROCESSOR)
        assert len(html_plugins) == 1
        assert html_plugins[0] == "html"
        
        filter_plugins = registry.list_plugins(plugin_type=PluginType.CONTENT_FILTER)
        assert len(filter_plugins) == 1
        assert filter_plugins[0] == "filter"

    def test_list_plugins(self, plugin_config):
        """Test listing all plugins."""
        registry = PluginRegistry()
        
        class TestPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        registry.register_plugin(TestPlugin, plugin_config)
        
        plugins = registry.list_plugins()
        assert len(plugins) == 1
        assert plugins[0] == "test"

    def test_unregister_plugin(self, plugin_config):
        """Test unregistering plugins."""
        registry = PluginRegistry()
        
        class TestPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process(self, data, context): return data
        
        registry.register_plugin(TestPlugin, plugin_config)
        
        assert registry.get_plugin_class("test") is not None
        
        registry.unregister_plugin("test")
        assert registry.get_plugin_class("test") is None


class TestPluginManager:
    """Test plugin manager functionality."""

    @pytest.fixture
    def manager(self):
        """Create plugin manager instance."""
        return PluginManager()

    @pytest.mark.asyncio
    async def test_plugin_manager_initialization(self, manager):
        """Test plugin manager initialization."""
        await manager.initialize()
        
        # Should initialize without errors
        assert manager is not None

    @pytest.mark.asyncio
    async def test_load_plugin_through_registry(self, manager, plugin_config):
        """Test loading plugins through registry."""
        class TestPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "test", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): 
                self._test_initialized = True
            async def process(self, data, context): return data
        
        # Register plugin in the registry
        manager.registry.register_plugin(TestPlugin, plugin_config)
        
        # Initialize manager to load plugins from registry
        await manager.initialize()
        
        # Plugin should be loaded and initialized
        assert "test" in manager._plugins
        plugin_instance = manager._plugins["test"]
        assert hasattr(plugin_instance, '_test_initialized')

    @pytest.mark.asyncio
    async def test_process_with_plugins(self, manager, plugin_config):
        """Test processing data through plugins."""
        class TestHTMLProcessor(HTMLProcessorPlugin):
            @property
            def plugin_info(self):
                return {"name": "test_html", "version": "1.0.0", "plugin_type": PluginType.HTML_PROCESSOR}
            async def initialize(self): pass
            async def process_html(self, html, metadata, context):
                return html.replace("test", "processed")
        
        # Register plugin and initialize manager
        manager.registry.register_plugin(TestHTMLProcessor, plugin_config)
        await manager.initialize()
        
        data = {"html": "This is test content"}
        from src.plugins.manager import PluginExecutionContext
        from pathlib import Path
        context = PluginExecutionContext("http://test.com", Path("/tmp"))
        
        result = await manager.execute_pipeline(PluginType.HTML_PROCESSOR, data, context)
        
        assert result["html"] == "This is processed content"

    @pytest.mark.asyncio
    async def test_plugin_priority_ordering(self, manager):
        """Test that plugins are processed in priority order."""
        class HighPriorityPlugin(BasePlugin):
            def __init__(self, config):
                config.priority = 1  # High priority
                super().__init__(config)
            
            @property
            def plugin_info(self):
                return {"name": "high", "version": "1.0.0", "plugin_type": PluginType.CONTENT_FILTER}
            async def initialize(self): pass
            async def process(self, data, context): 
                data["processed"] = data.get("processed", "") + "high"
                return data
        
        class LowPriorityPlugin(BasePlugin):
            def __init__(self, config):
                config.priority = 100  # Low priority
                super().__init__(config)
            
            @property
            def plugin_info(self):
                return {"name": "low", "version": "1.0.0", "plugin_type": PluginType.CONTENT_FILTER}
            async def initialize(self): pass
            async def process(self, data, context): 
                data["processed"] = data.get("processed", "") + "low"
                return data
        
        high_config = PluginConfig("high", "1.0.0", PluginType.CONTENT_FILTER, priority=1)
        low_config = PluginConfig("low", "1.0.0", PluginType.CONTENT_FILTER, priority=100)
        
        manager.registry.register_plugin(LowPriorityPlugin, low_config)  # Load low first
        manager.registry.register_plugin(HighPriorityPlugin, high_config)  # Load high second
        await manager.initialize()
        
        data = {"processed": ""}
        from src.plugins.manager import PluginExecutionContext
        from pathlib import Path
        context = PluginExecutionContext("http://test.com", Path("/tmp"))
        
        result = await manager.execute_pipeline(PluginType.CONTENT_FILTER, data, context)
        
        # High priority should run first
        assert result["processed"] == "highlow"