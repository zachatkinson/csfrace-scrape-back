"""Comprehensive tests for PluginRegistry."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.plugins.base import BasePlugin, PluginConfig, PluginType
from src.plugins.registry import PluginRegistry, plugin_registry

# Import module for coverage


class MockPlugin(BasePlugin):
    """Mock plugin for testing."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)

    @property
    def plugin_info(self):
        return {
            "name": "MockPlugin",
            "version": "1.0.0",
            "description": "Mock plugin for testing",
            "author": "Test Suite",
            "plugin_type": "html_processor",
        }

    async def initialize(self):
        pass

    async def process(self, data, context):
        return data


def create_mock_plugin_class(name, plugin_type="html_processor", version="1.0.0"):
    """Create a mock plugin class with custom name and type."""

    class CustomMockPlugin(BasePlugin):
        def __init__(self, config: PluginConfig):
            super().__init__(config)

        @property
        def plugin_info(self):
            return {
                "name": name,
                "version": version,
                "description": f"Mock plugin {name}",
                "author": "Test Suite",
                "plugin_type": plugin_type,
            }

        async def initialize(self):
            pass

        async def process(self, data, context):
            return data

    CustomMockPlugin.__name__ = name
    return CustomMockPlugin


class InvalidPlugin:
    """Invalid plugin that doesn't inherit from BasePlugin."""

    @property
    def plugin_info(self):
        return {"name": "Invalid"}

    async def process(self, data, context):
        return data


class BrokenInfoPlugin(BasePlugin):
    """Plugin with broken plugin_info."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)

    @property
    def plugin_info(self):
        raise Exception("Broken plugin info")

    async def initialize(self):
        pass

    async def process(self, data, context):
        return data


class TestPluginRegistryInitialization:
    """Test PluginRegistry initialization."""

    def test_registry_initialization(self):
        """Test registry initialization with empty state."""
        registry = PluginRegistry()

        assert registry._plugins == {}
        assert registry._plugin_configs == {}
        assert registry._search_paths == []
        assert registry._initialized is False

    def test_registry_attributes_are_private(self):
        """Test that registry uses private attributes correctly."""
        registry = PluginRegistry()

        assert hasattr(registry, "_plugins")
        assert hasattr(registry, "_plugin_configs")
        assert hasattr(registry, "_search_paths")
        assert hasattr(registry, "_initialized")


class TestSearchPathManagement:
    """Test search path management functionality."""

    def test_add_search_path_valid_directory(self):
        """Test adding valid directory to search paths."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            with patch("src.plugins.registry.logger") as mock_logger:
                registry.add_search_path(path)

            assert path.resolve() in registry._search_paths
            mock_logger.debug.assert_called_once()

    def test_add_search_path_nonexistent_directory(self):
        """Test adding nonexistent directory to search paths."""
        registry = PluginRegistry()
        nonexistent_path = Path("/nonexistent/directory")

        with patch("src.plugins.registry.logger") as mock_logger:
            registry.add_search_path(nonexistent_path)

        assert nonexistent_path.resolve() not in registry._search_paths
        mock_logger.warning.assert_called_once()

    def test_add_search_path_file_instead_of_directory(self):
        """Test adding file instead of directory to search paths."""
        registry = PluginRegistry()

        with tempfile.NamedTemporaryFile() as temp_file:
            file_path = Path(temp_file.name)

            with patch("src.plugins.registry.logger") as mock_logger:
                registry.add_search_path(file_path)

            assert file_path.resolve() not in registry._search_paths
            mock_logger.warning.assert_called_once()

    def test_add_search_path_string_input(self):
        """Test adding search path as string."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.plugins.registry.logger"):
                registry.add_search_path(temp_dir)  # String instead of Path

            assert Path(temp_dir).resolve() in registry._search_paths

    def test_add_multiple_search_paths(self):
        """Test adding multiple search paths."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir1, tempfile.TemporaryDirectory() as temp_dir2:
            path1 = Path(temp_dir1)
            path2 = Path(temp_dir2)

            with patch("src.plugins.registry.logger"):
                registry.add_search_path(path1)
                registry.add_search_path(path2)

            assert path1.resolve() in registry._search_paths
            assert path2.resolve() in registry._search_paths
            assert len(registry._search_paths) == 2

    def test_add_duplicate_search_paths(self):
        """Test adding duplicate search paths."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            with patch("src.plugins.registry.logger"):
                registry.add_search_path(path)
                registry.add_search_path(path)  # Duplicate

            # Should allow duplicates (registry doesn't check for them)
            assert registry._search_paths.count(path.resolve()) == 2


class TestPluginRegistration:
    """Test plugin registration functionality."""

    def test_register_plugin_valid_class(self):
        """Test registering valid plugin class."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger") as mock_logger:
            registry.register_plugin(MockPlugin)

        assert "MockPlugin" in registry._plugins
        assert "MockPlugin" in registry._plugin_configs
        assert registry._plugins["MockPlugin"] == MockPlugin

        config = registry._plugin_configs["MockPlugin"]
        assert config.name == "MockPlugin"
        assert config.version == "1.0.0"
        assert config.plugin_type == PluginType.HTML_PROCESSOR

        mock_logger.info.assert_called_once()

    def test_register_plugin_with_custom_config(self):
        """Test registering plugin with custom configuration."""
        registry = PluginRegistry()

        custom_config = PluginConfig(
            name="CustomMockPlugin",
            version="2.0.0",
            plugin_type=PluginType.METADATA_EXTRACTOR,
            enabled=False,
            priority=50,
            settings={"custom": "value"},
        )

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin, custom_config)

        # Registry uses plugin_info["name"] as key, not config.name
        assert "MockPlugin" in registry._plugins
        stored_config = registry._plugin_configs["MockPlugin"]
        assert stored_config == custom_config
        assert stored_config.enabled is False
        assert stored_config.priority == 50
        assert stored_config.settings == {"custom": "value"}

    def test_register_plugin_invalid_class(self):
        """Test registering invalid plugin class."""
        registry = PluginRegistry()

        with pytest.raises(ValueError, match="must inherit from BasePlugin"):
            registry.register_plugin(InvalidPlugin)

    def test_register_plugin_broken_plugin_info(self):
        """Test registering plugin with broken plugin_info."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger") as mock_logger:
            with pytest.raises(ValueError, match="Invalid plugin"):
                registry.register_plugin(BrokenInfoPlugin)

            mock_logger.error.assert_called_once()

    def test_register_plugin_creates_config_from_info(self):
        """Test that registration creates config from plugin info."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        config = registry._plugin_configs["MockPlugin"]
        assert config.name == "MockPlugin"
        assert config.version == "1.0.0"
        assert config.plugin_type.value == "html_processor"

    def test_register_plugin_overwrites_existing(self):
        """Test that registering overwrites existing plugin."""
        registry = PluginRegistry()

        # Register first plugin
        config1 = PluginConfig(
            name="MockPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
        )

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin, config1)

            # Register same plugin again with different config
            config2 = PluginConfig(
                name="MockPlugin", version="2.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
            )
            registry.register_plugin(MockPlugin, config2)

        # Should have the second configuration (key is from plugin_info["name"])
        stored_config = registry._plugin_configs["MockPlugin"]
        assert stored_config.version == "2.0.0"
        assert stored_config.plugin_type == PluginType.METADATA_EXTRACTOR


class TestPluginUnregistration:
    """Test plugin unregistration functionality."""

    def test_unregister_existing_plugin(self):
        """Test unregistering existing plugin."""
        registry = PluginRegistry()

        # Register plugin first
        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        assert "MockPlugin" in registry._plugins
        assert "MockPlugin" in registry._plugin_configs

        # Unregister plugin
        with patch("src.plugins.registry.logger") as mock_logger:
            registry.unregister_plugin("MockPlugin")

        assert "MockPlugin" not in registry._plugins
        assert "MockPlugin" not in registry._plugin_configs
        mock_logger.info.assert_called_with("Unregistered plugin", name="MockPlugin")

    def test_unregister_nonexistent_plugin(self):
        """Test unregistering nonexistent plugin."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger") as mock_logger:
            registry.unregister_plugin("NonexistentPlugin")

        mock_logger.warning.assert_called_with(
            "Plugin not found for unregistration", name="NonexistentPlugin"
        )

    def test_unregister_plugin_cleanup(self):
        """Test that unregistration cleans up both dictionaries."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        # Verify both dictionaries have the plugin
        assert len(registry._plugins) == 1
        assert len(registry._plugin_configs) == 1

        with patch("src.plugins.registry.logger"):
            registry.unregister_plugin("MockPlugin")

        # Verify both dictionaries are cleaned
        assert len(registry._plugins) == 0
        assert len(registry._plugin_configs) == 0


class TestPluginRetrieval:
    """Test plugin class and config retrieval."""

    def test_get_plugin_class_existing(self):
        """Test getting existing plugin class."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        plugin_class = registry.get_plugin_class("MockPlugin")
        assert plugin_class == MockPlugin

    def test_get_plugin_class_nonexistent(self):
        """Test getting nonexistent plugin class."""
        registry = PluginRegistry()

        plugin_class = registry.get_plugin_class("NonexistentPlugin")
        assert plugin_class is None

    def test_get_plugin_config_existing(self):
        """Test getting existing plugin configuration."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        config = registry.get_plugin_config("MockPlugin")
        assert config is not None
        assert config.name == "MockPlugin"
        assert config.version == "1.0.0"

    def test_get_plugin_config_nonexistent(self):
        """Test getting nonexistent plugin configuration."""
        registry = PluginRegistry()

        config = registry.get_plugin_config("NonexistentPlugin")
        assert config is None

    def test_get_plugin_class_and_config_consistency(self):
        """Test that plugin class and config retrieval is consistent."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        plugin_class = registry.get_plugin_class("MockPlugin")
        config = registry.get_plugin_config("MockPlugin")

        assert plugin_class is not None
        assert config is not None
        assert config.name == "MockPlugin"


class TestPluginListing:
    """Test plugin listing functionality."""

    def setup_test_plugins(self, registry):
        """Setup test plugins for listing tests."""
        plugins_data = [
            ("HTMLPlugin1", "html_processor", True, 100),
            ("HTMLPlugin2", "html_processor", False, 50),
            ("MetaPlugin", "metadata_extractor", True, 75),
        ]

        configs = []

        with patch("src.plugins.registry.logger"):
            for name, ptype, enabled, priority in plugins_data:
                plugin_class = create_mock_plugin_class(name, ptype)
                config = PluginConfig(
                    name=name,
                    version="1.0.0",
                    plugin_type=PluginType(ptype),
                    enabled=enabled,
                    priority=priority,
                )
                registry.register_plugin(plugin_class, config)
                configs.append(config)

        return configs

    def test_list_plugins_all(self):
        """Test listing all plugins."""
        registry = PluginRegistry()
        self.setup_test_plugins(registry)

        plugins = registry.list_plugins()

        assert len(plugins) == 3
        assert "HTMLPlugin1" in plugins
        assert "HTMLPlugin2" in plugins
        assert "MetaPlugin" in plugins

    def test_list_plugins_by_type(self):
        """Test listing plugins filtered by type."""
        registry = PluginRegistry()
        self.setup_test_plugins(registry)

        html_plugins = registry.list_plugins(plugin_type=PluginType.HTML_PROCESSOR)
        meta_plugins = registry.list_plugins(plugin_type=PluginType.METADATA_EXTRACTOR)

        assert len(html_plugins) == 2
        assert "HTMLPlugin1" in html_plugins
        assert "HTMLPlugin2" in html_plugins

        assert len(meta_plugins) == 1
        assert "MetaPlugin" in meta_plugins

    def test_list_plugins_enabled_only(self):
        """Test listing only enabled plugins."""
        registry = PluginRegistry()
        self.setup_test_plugins(registry)

        enabled_plugins = registry.list_plugins(enabled_only=True)

        assert len(enabled_plugins) == 2
        assert "HTMLPlugin1" in enabled_plugins
        assert "MetaPlugin" in enabled_plugins
        assert "HTMLPlugin2" not in enabled_plugins

    def test_list_plugins_type_and_enabled(self):
        """Test listing plugins with both type and enabled filters."""
        registry = PluginRegistry()
        self.setup_test_plugins(registry)

        enabled_html = registry.list_plugins(
            plugin_type=PluginType.HTML_PROCESSOR, enabled_only=True
        )

        assert len(enabled_html) == 1
        assert "HTMLPlugin1" in enabled_html
        assert "HTMLPlugin2" not in enabled_html

    def test_list_plugins_sorted_by_priority(self):
        """Test that plugins are sorted by priority."""
        registry = PluginRegistry()
        self.setup_test_plugins(registry)

        plugins = registry.list_plugins()

        # Should be sorted by priority (lower number = higher priority)
        priorities = [registry._plugin_configs[name].priority for name in plugins]
        assert priorities == sorted(priorities)

    def test_list_plugins_empty_registry(self):
        """Test listing plugins from empty registry."""
        registry = PluginRegistry()

        plugins = registry.list_plugins()
        assert plugins == []

    def test_list_plugins_no_matches(self):
        """Test listing plugins with filters that match nothing."""
        registry = PluginRegistry()
        self.setup_test_plugins(registry)

        # Filter for type that doesn't exist
        no_plugins = registry.list_plugins(plugin_type=PluginType.IMAGE_PROCESSOR)
        assert no_plugins == []


class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    def test_discover_plugins_no_search_paths(self):
        """Test discovery with no search paths."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger") as mock_logger:
            discovered = registry.discover_plugins()

        assert discovered == 0
        mock_logger.info.assert_called_with("Plugin discovery completed", discovered=0)

    def test_discover_plugins_with_search_paths(self):
        """Test discovery with search paths."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            registry._search_paths = [Path(temp_dir)]

            with patch.object(
                registry, "_discover_plugins_in_path", return_value=2
            ) as mock_discover:
                with patch("src.plugins.registry.logger") as mock_logger:
                    discovered = registry.discover_plugins()

            assert discovered == 2
            mock_discover.assert_called_once_with(Path(temp_dir))
            mock_logger.info.assert_called_with("Plugin discovery completed", discovered=2)

    def test_discover_plugins_multiple_paths(self):
        """Test discovery with multiple search paths."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir1, tempfile.TemporaryDirectory() as temp_dir2:
            registry._search_paths = [Path(temp_dir1), Path(temp_dir2)]

            with patch.object(
                registry, "_discover_plugins_in_path", side_effect=[1, 3]
            ) as mock_discover:
                discovered = registry.discover_plugins()

            assert discovered == 4
            assert mock_discover.call_count == 2


class TestPluginDiscoveryInPath:
    """Test plugin discovery in specific paths."""

    def test_discover_plugins_in_path_no_files(self):
        """Test discovery in path with no Python files."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            discovered = registry._discover_plugins_in_path(path)

        assert discovered == 0

    def test_discover_plugins_in_path_with_python_files(self):
        """Test discovery in path with Python files."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            # Create a Python file
            py_file = path / "test_plugin.py"
            py_file.write_text("# Empty Python file")

            with patch.object(registry, "_load_plugin_from_file", return_value=1) as mock_load:
                discovered = registry._discover_plugins_in_path(path)

            assert discovered == 1
            mock_load.assert_called_once_with(py_file)

    def test_discover_plugins_in_path_skips_dunder_files(self):
        """Test that discovery skips __init__.py and other dunder files."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            # Create dunder files
            (path / "__init__.py").write_text("")
            (path / "__pycache__").mkdir()
            (path / "regular_file.py").write_text("")

            with patch.object(registry, "_load_plugin_from_file", return_value=0) as mock_load:
                registry._discover_plugins_in_path(path)

            # Should only be called for regular_file.py
            assert mock_load.call_count == 1
            mock_load.assert_called_with(path / "regular_file.py")

    def test_discover_plugins_in_path_with_manifest_files(self):
        """Test discovery with plugin.json manifest files."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            # Create manifest file
            manifest_file = path / "plugin.json"
            manifest_file.write_text('{"name": "test"}')

            with patch.object(registry, "_load_plugin_from_manifest", return_value=1) as mock_load:
                discovered = registry._discover_plugins_in_path(path)

            assert discovered == 1
            mock_load.assert_called_once_with(manifest_file)

    def test_discover_plugins_in_path_handles_load_errors(self):
        """Test that discovery handles plugin loading errors."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            # Create files
            py_file = path / "broken.py"
            py_file.write_text("# Python file")
            manifest_file = path / "plugin.json"
            manifest_file.write_text('{"name": "test"}')

            with patch.object(
                registry, "_load_plugin_from_file", side_effect=Exception("Load error")
            ):
                with patch.object(
                    registry, "_load_plugin_from_manifest", side_effect=Exception("Manifest error")
                ):
                    with patch("src.plugins.registry.logger") as mock_logger:
                        discovered = registry._discover_plugins_in_path(path)

            assert discovered == 0
            assert mock_logger.warning.call_count == 2

    def test_discover_plugins_in_path_recursive(self):
        """Test that discovery searches subdirectories recursively."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            # Create nested structure
            subdir = path / "subdir"
            subdir.mkdir()

            py_file1 = path / "plugin1.py"
            py_file1.write_text("# Plugin 1")
            py_file2 = subdir / "plugin2.py"
            py_file2.write_text("# Plugin 2")

            with patch.object(registry, "_load_plugin_from_file", return_value=1) as mock_load:
                discovered = registry._discover_plugins_in_path(path)

            assert discovered == 2
            assert mock_load.call_count == 2


class TestPluginLoadingFromFile:
    """Test plugin loading from Python files."""

    def test_load_plugin_from_file_module_spec_creation_fails(self):
        """Test handling when module spec creation fails."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "invalid.py"
            py_file.write_text("invalid python syntax {{{")

            with patch("importlib.util.spec_from_file_location", return_value=None):
                loaded = registry._load_plugin_from_file(py_file)

            assert loaded == 0

    def test_load_plugin_from_file_no_loader(self):
        """Test handling when spec has no loader."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "test.py"
            py_file.write_text("# Empty file")

            mock_spec = MagicMock()
            mock_spec.loader = None

            with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
                loaded = registry._load_plugin_from_file(py_file)

            assert loaded == 0

    def test_load_plugin_from_file_sys_path_management(self):
        """Test that sys.path is managed correctly during loading."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "test.py"
            py_file.write_text("class TestPlugin: pass")

            # Mock sys.path to not include the directory
            original_path = sys.path.copy()

            try:
                if str(temp_dir) in sys.path:
                    sys.path.remove(str(temp_dir))

                with patch("importlib.util.spec_from_file_location") as mock_spec:
                    mock_spec.return_value = None  # Will return early

                    registry._load_plugin_from_file(py_file)

                # Path should be restored
                assert str(temp_dir) not in sys.path

            finally:
                sys.path[:] = original_path

    def test_load_plugin_from_file_finds_plugin_classes(self):
        """Test that loading finds and registers plugin classes."""
        registry = PluginRegistry()

        # Create a module with a plugin class
        module_code = """
from src.plugins.base import BasePlugin, PluginConfig

class TestFilePlugin(BasePlugin):
    @property
    def plugin_info(self):
        return {
            "name": "TestFilePlugin",
            "version": "1.0.0",
            "plugin_type": "html_processor"
        }

    async def initialize(self):
        pass

    async def process(self, data, context):
        return data
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "test_plugin.py"
            py_file.write_text(module_code)

            # Add temp_dir to sys.path for imports to work
            sys.path.insert(0, str(temp_dir))

            try:
                with patch.object(registry, "register_plugin") as mock_register:
                    loaded = registry._load_plugin_from_file(py_file)

                assert loaded == 1
                mock_register.assert_called_once()

            finally:
                if str(temp_dir) in sys.path:
                    sys.path.remove(str(temp_dir))

    def test_load_plugin_from_file_skips_abstract_classes(self):
        """Test that loading skips abstract plugin classes."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "abstract.py"
            py_file.write_text(
                "from src.plugins.base import BasePlugin\nclass Abstract(BasePlugin): pass"
            )

            with patch("inspect.isabstract", return_value=True):
                with patch.object(registry, "register_plugin") as mock_register:
                    loaded = registry._load_plugin_from_file(py_file)

            assert loaded == 0
            mock_register.assert_not_called()

    def test_load_plugin_from_file_handles_registration_errors(self):
        """Test handling of plugin registration errors."""
        registry = PluginRegistry()

        # Create a mock module that contains a proper plugin class
        mock_module = MagicMock()

        # Create a proper plugin class that inherits from BasePlugin
        class TestPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {"name": "TestPlugin", "version": "1.0.0"}

        with patch("importlib.util.spec_from_file_location") as mock_spec:
            mock_spec_obj = MagicMock()
            mock_spec_obj.loader = MagicMock()
            mock_spec.return_value = mock_spec_obj

            with patch("importlib.util.module_from_spec", return_value=mock_module):
                with patch("inspect.getmembers") as mock_getmembers:
                    mock_getmembers.return_value = [("TestPlugin", TestPlugin)]

                    with patch("inspect.isclass", return_value=True):
                        with patch("inspect.isabstract", return_value=False):
                            with patch.object(
                                registry,
                                "register_plugin",
                                side_effect=Exception("Registration failed"),
                            ):
                                with patch("src.plugins.registry.logger") as mock_logger:
                                    loaded = registry._load_plugin_from_file(Path("/fake/path.py"))

            assert loaded == 0
            mock_logger.warning.assert_called_with(
                "Failed to register plugin class",
                class_name="TestPlugin",
                error="Registration failed",
            )

    def test_load_plugin_from_file_handles_import_errors(self):
        """Test handling of import errors."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "broken.py"
            py_file.write_text("import nonexistent_module")

            with patch("src.plugins.registry.logger") as mock_logger:
                loaded = registry._load_plugin_from_file(py_file)

            assert loaded == 0
            mock_logger.warning.assert_called()


class TestPluginLoadingFromManifest:
    """Test plugin loading from manifest files."""

    def test_load_plugin_from_manifest_basic(self):
        """Test basic manifest loading."""
        registry = PluginRegistry()

        manifest_data = {
            "name": "ManifestPlugin",
            "version": "1.0.0",
            "type": "html_processor",
            "main": "plugin.py",
            "enabled": True,
            "priority": 50,
            "settings": {"key": "value"},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = Path(temp_dir) / "plugin.json"
            plugin_file = Path(temp_dir) / "plugin.py"

            manifest_file.write_text(json.dumps(manifest_data))
            plugin_file.write_text("# Plugin code")

            with patch.object(registry, "_load_plugin_from_file", return_value=1) as mock_load:
                loaded = registry._load_plugin_from_manifest(manifest_file)

            assert loaded == 1
            mock_load.assert_called_once_with(plugin_file)

    def test_load_plugin_from_manifest_default_main_file(self):
        """Test manifest loading with default main file."""
        registry = PluginRegistry()

        manifest_data = {"name": "TestPlugin", "version": "1.0.0"}

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = Path(temp_dir) / "plugin.json"
            plugin_file = Path(temp_dir) / "plugin.py"  # Default main file

            manifest_file.write_text(json.dumps(manifest_data))
            plugin_file.write_text("# Plugin code")

            with patch.object(registry, "_load_plugin_from_file", return_value=1) as mock_load:
                registry._load_plugin_from_manifest(manifest_file)

            mock_load.assert_called_once_with(plugin_file)

    def test_load_plugin_from_manifest_missing_main_file(self):
        """Test manifest loading when main file is missing."""
        registry = PluginRegistry()

        manifest_data = {"name": "TestPlugin", "main": "nonexistent.py"}

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = Path(temp_dir) / "plugin.json"
            manifest_file.write_text(json.dumps(manifest_data))

            with patch("src.plugins.registry.logger") as mock_logger:
                loaded = registry._load_plugin_from_manifest(manifest_file)

            assert loaded == 0
            mock_logger.warning.assert_called()

    def test_load_plugin_from_manifest_updates_config(self):
        """Test that manifest loading updates plugin config."""
        registry = PluginRegistry()

        manifest_data = {
            "name": "TestPlugin",
            "version": "2.0.0",
            "type": "metadata_extractor",
            "enabled": False,
            "priority": 25,
            "settings": {"custom": "setting"},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = Path(temp_dir) / "plugin.json"
            plugin_file = Path(temp_dir) / "plugin.py"

            manifest_file.write_text(json.dumps(manifest_data))
            plugin_file.write_text("# Plugin code")

            # Mock successful loading and pre-populate config
            registry._plugin_configs["TestPlugin"] = PluginConfig(
                name="TestPlugin", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR
            )

            with patch.object(registry, "_load_plugin_from_file", return_value=1):
                registry._load_plugin_from_manifest(manifest_file)

            # Config should be updated with manifest data
            config = registry._plugin_configs["TestPlugin"]
            assert config.version == "2.0.0"
            assert config.plugin_type == PluginType.METADATA_EXTRACTOR
            assert config.enabled is False
            assert config.priority == 25
            assert config.settings == {"custom": "setting"}

    def test_load_plugin_from_manifest_invalid_json(self):
        """Test handling of invalid JSON in manifest."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = Path(temp_dir) / "plugin.json"
            manifest_file.write_text("{ invalid json }")

            with patch("src.plugins.registry.logger") as mock_logger:
                loaded = registry._load_plugin_from_manifest(manifest_file)

            assert loaded == 0
            mock_logger.error.assert_called()

    def test_load_plugin_from_manifest_file_not_found(self):
        """Test handling when manifest file doesn't exist."""
        registry = PluginRegistry()

        nonexistent_file = Path("/nonexistent/plugin.json")

        with patch("src.plugins.registry.logger") as mock_logger:
            loaded = registry._load_plugin_from_manifest(nonexistent_file)

        assert loaded == 0
        mock_logger.error.assert_called()


class TestConfigurationSaving:
    """Test plugin configuration saving."""

    def test_save_config_basic(self):
        """Test basic configuration saving."""
        registry = PluginRegistry()

        # Register a plugin
        config = PluginConfig(
            name="TestPlugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=100,
            settings={"key": "value"},
        )

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin, config)

        # Save config
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"

            with patch("src.plugins.registry.logger") as mock_logger:
                registry.save_config(config_file)

            # Verify file was created
            assert config_file.exists()

            # Verify content
            with open(config_file) as f:
                saved_data = json.load(f)

            assert "MockPlugin" in saved_data  # Registry uses plugin_info["name"] as key
            plugin_data = saved_data["MockPlugin"]
            assert plugin_data["version"] == "1.0.0"
            assert plugin_data["plugin_type"] == "html_processor"
            assert plugin_data["enabled"] is True
            assert plugin_data["priority"] == 100
            assert plugin_data["settings"] == {"key": "value"}

            mock_logger.info.assert_called()

    def test_save_config_multiple_plugins(self):
        """Test saving configuration with multiple plugins."""
        registry = PluginRegistry()

        # Create two different plugin classes with different names
        Plugin1Class = create_mock_plugin_class("Plugin1", "html_processor", "1.0.0")
        Plugin2Class = create_mock_plugin_class("Plugin2", "metadata_extractor", "2.0.0")

        configs = [
            PluginConfig(name="Plugin1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR),
            PluginConfig(
                name="Plugin2", version="2.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
            ),
        ]

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(Plugin1Class, configs[0])
            registry.register_plugin(Plugin2Class, configs[1])

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"
            registry.save_config(config_file)

            with open(config_file) as f:
                saved_data = json.load(f)

            assert len(saved_data) == 2
            assert "Plugin1" in saved_data  # Based on plugin_info["name"]
            assert "Plugin2" in saved_data  # Based on plugin_info["name"]

    def test_save_config_empty_registry(self):
        """Test saving configuration from empty registry."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"

            with patch("src.plugins.registry.logger"):
                registry.save_config(config_file)

            with open(config_file) as f:
                saved_data = json.load(f)

            assert saved_data == {}

    def test_save_config_file_permissions(self):
        """Test that save_config handles file permission errors."""
        registry = PluginRegistry()

        # Try to save to a directory we can't write to
        config_file = Path("/root/config.json")

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                registry.save_config(config_file)


class TestConfigurationLoading:
    """Test plugin configuration loading."""

    def test_load_config_basic(self):
        """Test basic configuration loading."""
        registry = PluginRegistry()

        # Register plugin first
        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)

        # Prepare config data (use plugin_info name as key)
        config_data = {
            "MockPlugin": {"enabled": False, "priority": 50, "settings": {"loaded": "setting"}}
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            with patch("src.plugins.registry.logger") as mock_logger:
                registry.load_config(config_file)

            # Verify config was updated
            config = registry._plugin_configs["MockPlugin"]
            assert config.enabled is False
            assert config.priority == 50
            assert config.settings["loaded"] == "setting"

            mock_logger.info.assert_called()

    def test_load_config_nonexistent_file(self):
        """Test loading from nonexistent config file."""
        registry = PluginRegistry()

        nonexistent_file = Path("/nonexistent/config.json")

        with patch("src.plugins.registry.logger") as mock_logger:
            registry.load_config(nonexistent_file)

        mock_logger.warning.assert_called()

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON config file."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"
            config_file.write_text("{ invalid json }")

            with patch("src.plugins.registry.logger") as mock_logger:
                registry.load_config(config_file)

            mock_logger.error.assert_called()

    def test_load_config_plugin_not_registered(self):
        """Test loading config for plugin that isn't registered."""
        registry = PluginRegistry()

        config_data = {"UnknownPlugin": {"enabled": False, "priority": 50}}

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            # Should not raise error, just skip unknown plugins
            with patch("src.plugins.registry.logger"):
                registry.load_config(config_file)

    def test_load_config_partial_update(self):
        """Test that loading config only updates specified fields."""
        registry = PluginRegistry()

        # Register plugin with initial config
        initial_config = PluginConfig(
            name="MockPlugin",  # Use plugin_info name
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            enabled=True,
            priority=100,
            settings={"initial": "value"},
        )

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin, initial_config)

        # Load partial config (key must match plugin_info["name"])
        config_data = {"MockPlugin": {"enabled": False, "settings": {"new": "setting"}}}

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            with patch("src.plugins.registry.logger"):
                registry.load_config(config_file)

            # Verify partial update
            config = registry._plugin_configs["MockPlugin"]
            assert config.enabled is False  # Updated
            assert config.priority == 100  # Unchanged
            assert config.settings["initial"] == "value"  # Original setting preserved
            assert config.settings["new"] == "setting"  # New setting added

    def test_load_config_settings_merge(self):
        """Test that settings are merged, not replaced."""
        registry = PluginRegistry()

        initial_config = PluginConfig(
            name="TestPlugin",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            settings={"existing": "value", "keep": "this"},
        )

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin, initial_config)

        config_data = {
            "MockPlugin": {  # Use MockPlugin since that's the plugin_info["name"]
                "settings": {"existing": "updated", "new": "added"}
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.json"

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            with patch("src.plugins.registry.logger"):
                registry.load_config(config_file)

            config = registry._plugin_configs["MockPlugin"]  # Registry key is plugin_info["name"]
            assert config.settings["existing"] == "updated"  # Updated
            assert config.settings["new"] == "added"  # Added
            assert config.settings["keep"] == "this"  # Preserved


class TestGlobalRegistryInstance:
    """Test the global plugin registry instance."""

    def test_global_registry_exists(self):
        """Test that global plugin_registry instance exists."""
        assert plugin_registry is not None
        assert isinstance(plugin_registry, PluginRegistry)

    def test_global_registry_initial_state(self):
        """Test that global registry starts in correct initial state."""
        # Note: This might be affected by other tests
        assert hasattr(plugin_registry, "_plugins")
        assert hasattr(plugin_registry, "_plugin_configs")
        assert hasattr(plugin_registry, "_search_paths")
        assert hasattr(plugin_registry, "_initialized")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_register_plugin_with_none_config(self):
        """Test registering plugin with None config."""
        registry = PluginRegistry()

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin, None)

        assert "MockPlugin" in registry._plugins
        config = registry._plugin_configs["MockPlugin"]
        assert config is not None
        assert config.name == "MockPlugin"

    def test_plugin_type_enum_conversion(self):
        """Test PluginType enum conversion in registration."""
        registry = PluginRegistry()

        class CustomPlugin(BasePlugin):
            @property
            def plugin_info(self):
                return {
                    "name": "CustomPlugin",
                    "version": "1.0.0",
                    "plugin_type": "metadata_extractor",  # String value
                }

            async def initialize(self):
                pass

            async def process(self, data, context):
                return data

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(CustomPlugin)

        config = registry._plugin_configs["CustomPlugin"]
        assert config.plugin_type == PluginType.METADATA_EXTRACTOR

    def test_list_plugins_priority_edge_cases(self):
        """Test plugin listing with same priorities."""
        registry = PluginRegistry()

        # Create three different plugin classes with different names
        Plugin1Class = create_mock_plugin_class("Plugin1", "html_processor", "1.0.0")
        Plugin2Class = create_mock_plugin_class("Plugin2", "html_processor", "1.0.0")
        Plugin3Class = create_mock_plugin_class("Plugin3", "html_processor", "1.0.0")

        configs = [
            PluginConfig(
                name="Plugin1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=100
            ),
            PluginConfig(
                name="Plugin2", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=100
            ),
            PluginConfig(
                name="Plugin3", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=50
            ),
        ]

        with patch("src.plugins.registry.logger"):
            registry.register_plugin(Plugin1Class, configs[0])
            registry.register_plugin(Plugin2Class, configs[1])
            registry.register_plugin(Plugin3Class, configs[2])

        plugins = registry.list_plugins()

        # Plugin3 should be first (priority 50), Plugin1 and Plugin2 should maintain order
        assert plugins[0] == "Plugin3"
        assert "Plugin1" in plugins[1:]
        assert "Plugin2" in plugins[1:]

    def test_empty_search_path_handling(self):
        """Test handling of empty search paths."""
        registry = PluginRegistry()
        registry._search_paths = [Path("/nonexistent")]

        with patch("src.plugins.registry.logger"):
            discovered = registry.discover_plugins()

        # Should handle gracefully
        assert discovered == 0

    def test_concurrent_registration(self):
        """Test that concurrent registration doesn't cause issues."""
        registry = PluginRegistry()

        # Simulate concurrent registration of same plugin
        with patch("src.plugins.registry.logger"):
            registry.register_plugin(MockPlugin)
            registry.register_plugin(MockPlugin)  # Duplicate

        # Should have only one instance
        assert len(registry._plugins) == 1
        assert len(registry._plugin_configs) == 1
