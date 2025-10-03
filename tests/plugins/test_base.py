"""Comprehensive tests for plugin base classes and types.

MANDATORY: All tests follow TEST_BUILDING.md ZERO TOLERANCE standards.
"""

import time
from pathlib import Path
from typing import Any

import pytest

from src.plugins.base import (
    BasePlugin,
    ContentFilterPlugin,
    HTMLProcessorPlugin,
    ImageProcessorPlugin,
    MetadataExtractorPlugin,
    OutputFormatterPlugin,
    PluginConfig,
    PluginType,
    PostProcessorPlugin,
)

# ============================================================================
# FACTORY FIXTURES - DRY PRINCIPLE (MANDATORY)
# ============================================================================


@pytest.fixture
def plugin_config() -> PluginConfig:
    """Factory for PluginConfig - DRY principle."""
    return PluginConfig(
        name="test_plugin",
        version="1.0.0",
        plugin_type=PluginType.HTML_PROCESSOR,
        enabled=True,
        priority=100,
        settings={"key": "value"},
    )


# ============================================================================
# PLUGIN TYPE ENUM TESTS
# ============================================================================


@pytest.mark.unit
class TestPluginType:
    """Tests for PluginType enum."""

    def test_all_plugin_types_exist(self):
        """Test all expected plugin types exist - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_types = [
            "HTML_PROCESSOR",
            "CONTENT_FILTER",
            "IMAGE_PROCESSOR",
            "METADATA_EXTRACTOR",
            "OUTPUT_FORMATTER",
            "POST_PROCESSOR",
        ]

        # Act - MANDATORY
        actual_types = [t.name for t in PluginType]

        # Assert - MANDATORY
        for expected in expected_types:
            assert expected in actual_types

    def test_plugin_type_values(self):
        """Test plugin type values are correct - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        types_map = {
            PluginType.HTML_PROCESSOR: "html_processor",
            PluginType.CONTENT_FILTER: "content_filter",
            PluginType.IMAGE_PROCESSOR: "image_processor",
            PluginType.METADATA_EXTRACTOR: "metadata_extractor",
            PluginType.OUTPUT_FORMATTER: "output_formatter",
            PluginType.POST_PROCESSOR: "post_processor",
        }

        # Assert - MANDATORY
        for plugin_type, expected_value in types_map.items():
            assert plugin_type.value == expected_value


# ============================================================================
# PLUGIN CONFIG TESTS
# ============================================================================


@pytest.mark.unit
class TestPluginConfig:
    """Tests for PluginConfig dataclass."""

    def test_config_creation_with_defaults(self):
        """Test PluginConfig creation with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        name = "test_plugin"
        version = "1.0.0"
        plugin_type = PluginType.HTML_PROCESSOR

        # Act - MANDATORY
        config = PluginConfig(name=name, version=version, plugin_type=plugin_type)

        # Assert - MANDATORY
        assert config.name == name
        assert config.version == version
        assert config.plugin_type == plugin_type
        assert config.enabled is True
        assert config.priority == 100
        assert config.settings == {}

    def test_config_customization(self):
        """Test PluginConfig allows customization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        settings = {"custom": "setting", "value": 123}

        # Act - MANDATORY
        config = PluginConfig(
            name="custom",
            version="2.0.0",
            plugin_type=PluginType.CONTENT_FILTER,
            enabled=False,
            priority=50,
            settings=settings,
        )

        # Assert - MANDATORY
        assert config.name == "custom"
        assert config.version == "2.0.0"
        assert config.plugin_type == PluginType.CONTENT_FILTER
        assert config.enabled is False
        assert config.priority == 50
        assert config.settings == settings

    def test_config_settings_default_initialization(self):
        """Test PluginConfig initializes empty settings dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, settings=None
        )

        # Assert - MANDATORY
        assert config.settings == {}


# ============================================================================
# BASE PLUGIN TESTS
# ============================================================================


# Test implementation of BasePlugin for testing
class _MockPluginImpl(BasePlugin):
    """Concrete implementation of BasePlugin for testing."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "plugin_type": "html_processor",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def process(self, data: Any, context: dict[str, Any]) -> Any:
        return data


@pytest.mark.unit
class TestBasePlugin:
    """Tests for BasePlugin base class."""

    def test_plugin_initialization(self, plugin_config: PluginConfig):
        """Test plugin initializes with config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Assert - MANDATORY
        assert plugin.config == plugin_config
        assert plugin.logger is not None
        assert plugin._initialized is False

    @pytest.mark.asyncio
    async def test_plugin_initialize_sets_flag(self, plugin_config: PluginConfig):
        """Test initialize sets initialized flag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        await plugin.initialize()

        # Assert - MANDATORY
        assert plugin._initialized is True

    @pytest.mark.asyncio
    async def test_plugin_cleanup_default_behavior(self, plugin_config: PluginConfig):
        """Test cleanup default behavior does nothing - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        await plugin.cleanup()

        # Assert - MANDATORY
        # Should not raise errors
        assert True

    @pytest.mark.asyncio
    async def test_plugin_validate_config_default(self, plugin_config: PluginConfig):
        """Test validate_config default returns True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        result = await plugin.validate_config()

        # Assert - MANDATORY
        assert result is True

    def test_get_setting_returns_value(self, plugin_config: PluginConfig):
        """Test get_setting returns correct value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        result = plugin.get_setting("key")

        # Assert - MANDATORY
        assert result == "value"

    def test_get_setting_returns_default(self, plugin_config: PluginConfig):
        """Test get_setting returns default for missing key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        result = plugin.get_setting("nonexistent", "default_value")

        # Assert - MANDATORY
        assert result == "default_value"

    def test_set_setting_updates_value(self, plugin_config: PluginConfig):
        """Test set_setting updates setting value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        plugin.set_setting("new_key", "new_value")

        # Assert - MANDATORY
        assert plugin.get_setting("new_key") == "new_value"

    def test_set_setting_creates_settings_dict(self):
        """Test set_setting creates settings dict if None - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, settings=None
        )
        plugin = _MockPluginImpl(config=config)

        # Act - MANDATORY
        plugin.set_setting("key", "value")

        # Assert - MANDATORY
        assert plugin.config.settings == {"key": "value"}

    def test_is_enabled_returns_config_value(self, plugin_config: PluginConfig):
        """Test is_enabled returns config enabled value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        result = plugin.is_enabled()

        # Assert - MANDATORY
        assert result is True

    def test_get_priority_returns_config_value(self, plugin_config: PluginConfig):
        """Test get_priority returns config priority - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)

        # Act - MANDATORY
        result = plugin.get_priority()

        # Assert - MANDATORY
        assert result == 100


# ============================================================================
# HTML PROCESSOR PLUGIN TESTS
# ============================================================================


class _MockHTMLProcessorImpl(HTMLProcessorPlugin):
    """Test implementation of HTMLProcessorPlugin."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_html_processor",
            "version": "1.0.0",
            "description": "Test HTML processor",
            "author": "Test",
            "plugin_type": "html_processor",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def process_html(
        self, html_content: str, metadata: dict[str, Any], context: dict[str, Any]
    ) -> str:
        return html_content.upper()


@pytest.mark.unit
class TestHTMLProcessorPlugin:
    """Tests for HTMLProcessorPlugin base class."""

    @pytest.mark.asyncio
    async def test_process_transforms_html(self):
        """Test process method transforms HTML - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockHTMLProcessorImpl(config=config)
        data = {"html": "<p>test</p>", "metadata": {"key": "value"}}
        context = {}

        # Act - MANDATORY
        result = await plugin.process(data, context)

        # Assert - MANDATORY
        assert result["html"] == "<P>TEST</P>"
        assert result["metadata"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_process_raises_error_for_invalid_data(self):
        """Test process raises error for invalid data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockHTMLProcessorImpl(config=config)
        data = {"no_html": "value"}
        context = {}

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="expects dict with 'html' key"):
            await plugin.process(data, context)


# ============================================================================
# CONTENT FILTER PLUGIN TESTS
# ============================================================================


class _MockContentFilterImpl(ContentFilterPlugin):
    """Test implementation of ContentFilterPlugin."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_filter",
            "version": "1.0.0",
            "description": "Test filter",
            "author": "Test",
            "plugin_type": "content_filter",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def filter_content(self, content: str, content_type: str, context: dict[str, Any]) -> str:
        return content.replace("bad", "good")


@pytest.mark.unit
class TestContentFilterPlugin:
    """Tests for ContentFilterPlugin base class."""

    @pytest.mark.asyncio
    async def test_process_filters_content(self):
        """Test process method filters content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.CONTENT_FILTER)
        plugin = _MockContentFilterImpl(config=config)
        data = {"content": "bad word", "content_type": "html"}
        context = {}

        # Act - MANDATORY
        result = await plugin.process(data, context)

        # Assert - MANDATORY
        assert result["content"] == "good word"

    @pytest.mark.asyncio
    async def test_process_raises_error_for_invalid_data(self):
        """Test process raises error for invalid data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.CONTENT_FILTER)
        plugin = _MockContentFilterImpl(config=config)
        data = {"no_content": "value"}
        context = {}

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="expects dict with 'content' key"):
            await plugin.process(data, context)


# ============================================================================
# IMAGE PROCESSOR PLUGIN TESTS
# ============================================================================


class _MockImageProcessorImpl(ImageProcessorPlugin):
    """Test implementation of ImageProcessorPlugin."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_image",
            "version": "1.0.0",
            "description": "Test image processor",
            "author": "Test",
            "plugin_type": "image_processor",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def process_image(
        self, image_url: str, image_data: bytes, metadata: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "data": image_data,
            "metadata": {"processed": True},
            "format": "png",
            "size": (100, 100),
        }


@pytest.mark.unit
class TestImageProcessorPlugin:
    """Tests for ImageProcessorPlugin base class."""

    @pytest.mark.asyncio
    async def test_process_processes_image(self):
        """Test process method processes image - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.IMAGE_PROCESSOR)
        plugin = _MockImageProcessorImpl(config=config)
        data = {"url": "http://example.com/image.png", "image_data": b"fake_image", "metadata": {}}
        context = {}

        # Act - MANDATORY
        result = await plugin.process(data, context)

        # Assert - MANDATORY
        assert result["data"] == b"fake_image"
        assert result["metadata"]["processed"] is True
        assert result["format"] == "png"
        assert result["size"] == (100, 100)

    @pytest.mark.asyncio
    async def test_process_raises_error_for_invalid_data(self):
        """Test process raises error for invalid data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.IMAGE_PROCESSOR)
        plugin = _MockImageProcessorImpl(config=config)
        data = {"no_image": "value"}
        context = {}

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="expects dict with 'image_data' key"):
            await plugin.process(data, context)


# ============================================================================
# METADATA EXTRACTOR PLUGIN TESTS
# ============================================================================


class _MockMetadataExtractorImpl(MetadataExtractorPlugin):
    """Test implementation of MetadataExtractorPlugin."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_metadata",
            "version": "1.0.0",
            "description": "Test metadata extractor",
            "author": "Test",
            "plugin_type": "metadata_extractor",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def extract_metadata(
        self, html_content: str, url: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        return {"title": "Extracted Title", "url": url}


@pytest.mark.unit
class TestMetadataExtractorPlugin:
    """Tests for MetadataExtractorPlugin base class."""

    @pytest.mark.asyncio
    async def test_process_extracts_metadata(self):
        """Test process method extracts metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = _MockMetadataExtractorImpl(config=config)
        data = {
            "html": "<html></html>",
            "url": "http://example.com",
            "metadata": {"existing": "data"},
        }
        context = {}

        # Act - MANDATORY
        result = await plugin.process(data, context)

        # Assert - MANDATORY
        assert result["metadata"]["title"] == "Extracted Title"
        assert result["metadata"]["url"] == "http://example.com"
        assert result["metadata"]["existing"] == "data"  # Preserves existing

    @pytest.mark.asyncio
    async def test_process_raises_error_for_invalid_data(self):
        """Test process raises error for invalid data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.METADATA_EXTRACTOR
        )
        plugin = _MockMetadataExtractorImpl(config=config)
        data = {"no_html": "value"}
        context = {}

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="expects dict with 'html' key"):
            await plugin.process(data, context)


# ============================================================================
# OUTPUT FORMATTER PLUGIN TESTS
# ============================================================================


class _MockOutputFormatterImpl(OutputFormatterPlugin):
    """Test implementation of OutputFormatterPlugin."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_formatter",
            "version": "1.0.0",
            "description": "Test formatter",
            "author": "Test",
            "plugin_type": "output_formatter",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def format_output(
        self, content: str, metadata: dict[str, Any], output_format: str, context: dict[str, Any]
    ) -> str:
        return f"[{output_format}]{content}[/{output_format}]"


@pytest.mark.unit
class TestOutputFormatterPlugin:
    """Tests for OutputFormatterPlugin base class."""

    @pytest.mark.asyncio
    async def test_process_formats_output(self):
        """Test process method formats output - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.OUTPUT_FORMATTER)
        plugin = _MockOutputFormatterImpl(config=config)
        data = {"content": "test content", "metadata": {}, "output_format": "markdown"}
        context = {}

        # Act - MANDATORY
        result = await plugin.process(data, context)

        # Assert - MANDATORY
        assert result["content"] == "[markdown]test content[/markdown]"

    @pytest.mark.asyncio
    async def test_process_raises_error_for_invalid_data(self):
        """Test process raises error for invalid data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.OUTPUT_FORMATTER)
        plugin = _MockOutputFormatterImpl(config=config)
        data = {"no_content": "value"}
        context = {}

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="expects dict with 'content' key"):
            await plugin.process(data, context)


# ============================================================================
# POST PROCESSOR PLUGIN TESTS
# ============================================================================


class _MockPostProcessorImpl(PostProcessorPlugin):
    """Test implementation of PostProcessorPlugin."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_post",
            "version": "1.0.0",
            "description": "Test post processor",
            "author": "Test",
            "plugin_type": "post_processor",
        }

    async def initialize(self) -> None:
        self._initialized = True

    async def post_process(
        self, output_dir: Path, files: list[Path], metadata: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        return {"processed_files": len(files), "output_dir": str(output_dir)}


@pytest.mark.unit
class TestPostProcessorPlugin:
    """Tests for PostProcessorPlugin base class."""

    @pytest.mark.asyncio
    async def test_process_post_processes_files(self):
        """Test process method post-processes files - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.POST_PROCESSOR)
        plugin = _MockPostProcessorImpl(config=config)
        data = {
            "output_dir": "/tmp/output",
            "files": [Path("/tmp/file1.txt"), Path("/tmp/file2.txt")],
            "metadata": {},
        }
        context = {}

        # Act - MANDATORY
        result = await plugin.process(data, context)

        # Assert - MANDATORY
        assert result["post_process_result"]["processed_files"] == 2
        assert result["post_process_result"]["output_dir"] == "/tmp/output"

    @pytest.mark.asyncio
    async def test_process_raises_error_for_missing_output_dir(self):
        """Test process raises error for missing output_dir - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.POST_PROCESSOR)
        plugin = _MockPostProcessorImpl(config=config)
        data = {"files": []}
        context = {}

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="requires 'output_dir' in data"):
            await plugin.process(data, context)


# ============================================================================
# MANDATORY SECURITY TESTS
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestPluginSecurity:
    """MANDATORY security tests for plugin system."""

    def test_plugin_name_sanitization(self):
        """MANDATORY security test - plugin names with malicious characters."""
        # Arrange - MANDATORY
        malicious_names = [
            "../../../etc/passwd",
            "test<script>alert('xss')</script>",
            "test'; DROP TABLE plugins;--",
            "test`whoami`",
        ]

        # Act & Assert - MANDATORY
        for name in malicious_names:
            config = PluginConfig(name=name, version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
            # Name should be stored as-is (app must sanitize on display)
            assert config.name == name

    def test_plugin_settings_injection(self):
        """MANDATORY security test - plugin settings with malicious content."""
        # Arrange - MANDATORY
        malicious_settings = {
            "command": "rm -rf /",
            "sql": "'; DROP TABLE users;--",
            "path": "../../../etc/shadow",
        }

        # Act - MANDATORY
        config = PluginConfig(
            name="test",
            version="1.0.0",
            plugin_type=PluginType.HTML_PROCESSOR,
            settings=malicious_settings,
        )
        plugin = _MockPluginImpl(config=config)

        # Assert - MANDATORY
        # Settings should be stored as-is (app must validate before use)
        assert plugin.get_setting("command") == "rm -rf /"
        assert plugin.get_setting("sql") == "'; DROP TABLE users;--"


# ============================================================================
# MANDATORY PERFORMANCE BENCHMARKS
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestPluginPerformance:
    """MANDATORY performance tests for plugin system."""

    def test_get_setting_performance(self, plugin_config: PluginConfig):
        """MANDATORY performance test - setting retrieval speed."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            plugin.get_setting("key")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <10μs per retrieval
        assert execution_time < 0.1  # Total <100ms for 10000 retrievals

    def test_set_setting_performance(self, plugin_config: PluginConfig):
        """MANDATORY performance test - setting update speed."""
        # Arrange - MANDATORY
        plugin = _MockPluginImpl(config=plugin_config)
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            plugin.set_setting(f"key_{i}", f"value_{i}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <10μs per update
        assert execution_time < 0.1  # Total <100ms for 10000 updates
