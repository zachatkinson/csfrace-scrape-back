"""Comprehensive tests for src/core/plugin_integration.py.

Test coverage: 29 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.core.plugin_integration import PluginIntegration, plugin_integration

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def mock_plugin_manager():
    """Factory for mock plugin manager - DRY principle."""
    manager = Mock()
    manager.initialize = AsyncMock()
    manager.process_content = AsyncMock(
        return_value={
            "content": "<processed>",
            "html": "<processed>",
            "metadata": {"key": "value"},
            "files": ["file1.jpg"],
        }
    )
    manager.shutdown = AsyncMock()
    return manager


@pytest.fixture
def plugin_integration_instance(mock_plugin_manager):
    """Factory for PluginIntegration instance - DRY principle."""
    return PluginIntegration(manager=mock_plugin_manager)


@pytest.fixture
def sample_html():
    """Factory for sample HTML content - DRY principle."""
    return "<html><body>Test content</body></html>"


@pytest.fixture
def sample_metadata():
    """Factory for sample metadata - DRY principle."""
    return {"title": "Test Page", "author": "Test Author"}


# =============================================================================
# TEST PluginIntegration - Initialization
# =============================================================================


@pytest.mark.unit
class TestPluginIntegrationInit:
    """Test PluginIntegration initialization."""

    def test_plugin_integration_init_with_manager(self, mock_plugin_manager):
        """Test PluginIntegration initialization with provided manager."""
        # Act
        integration = PluginIntegration(manager=mock_plugin_manager)

        # Assert
        assert integration.manager is mock_plugin_manager
        assert integration.enabled is False

    def test_plugin_integration_init_default_manager(self):
        """Test PluginIntegration initialization with default manager."""
        # Act
        integration = PluginIntegration()

        # Assert
        assert integration.manager is not None
        assert integration.enabled is False


# =============================================================================
# TEST PluginIntegration - System Initialization
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestPluginIntegrationInitialize:
    """Test PluginIntegration initialize method."""

    async def test_initialize_calls_manager_initialize(
        self, plugin_integration_instance, mock_plugin_manager
    ):
        """Test initialize calls plugin manager initialize."""
        # Act
        await plugin_integration_instance.initialize()

        # Assert
        mock_plugin_manager.initialize.assert_called_once()

    async def test_initialize_sets_enabled_flag(self, plugin_integration_instance):
        """Test initialize sets enabled flag to True."""
        # Arrange
        assert plugin_integration_instance.enabled is False

        # Act
        await plugin_integration_instance.initialize()

        # Assert
        assert plugin_integration_instance.enabled is True


# =============================================================================
# TEST PluginIntegration - Content Processing (Disabled)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestPluginIntegrationProcessContentDisabled:
    """Test PluginIntegration content processing when disabled."""

    async def test_process_content_disabled_returns_minimal_result(
        self, plugin_integration_instance, sample_html, sample_metadata
    ):
        """Test process_content returns minimal result when disabled."""
        # Arrange
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        # Act
        result = await plugin_integration_instance.process_content_with_plugins(
            sample_html, url, output_dir, sample_metadata
        )

        # Assert
        assert result["content"] == sample_html
        assert result["html"] == sample_html
        assert result["metadata"] == sample_metadata
        assert result["files"] == []
        assert result["plugin_processed"] is False

    async def test_process_content_disabled_no_metadata(
        self, plugin_integration_instance, sample_html
    ):
        """Test process_content returns empty metadata when not provided."""
        # Arrange
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        # Act
        result = await plugin_integration_instance.process_content_with_plugins(
            sample_html, url, output_dir
        )

        # Assert
        assert result["metadata"] == {}
        assert result["plugin_processed"] is False


# =============================================================================
# TEST PluginIntegration - Content Processing (Enabled)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestPluginIntegrationProcessContentEnabled:
    """Test PluginIntegration content processing when enabled."""

    async def test_process_content_enabled_calls_manager(
        self, plugin_integration_instance, mock_plugin_manager, sample_html, sample_metadata
    ):
        """Test process_content calls plugin manager when enabled."""
        # Arrange
        await plugin_integration_instance.initialize()
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        # Act
        result = await plugin_integration_instance.process_content_with_plugins(
            sample_html, url, output_dir, sample_metadata
        )

        # Assert
        mock_plugin_manager.process_content.assert_called_once_with(
            sample_html, url, output_dir, sample_metadata
        )

    async def test_process_content_enabled_returns_manager_result(
        self, plugin_integration_instance, mock_plugin_manager, sample_html
    ):
        """Test process_content returns result from plugin manager."""
        # Arrange
        await plugin_integration_instance.initialize()
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        # Act
        result = await plugin_integration_instance.process_content_with_plugins(
            sample_html, url, output_dir
        )

        # Assert
        assert result["content"] == "<processed>"
        assert result["html"] == "<processed>"
        assert result["metadata"] == {"key": "value"}
        assert result["files"] == ["file1.jpg"]
        assert result["plugin_processed"] is True

    async def test_process_content_enabled_adds_processed_flag(
        self, plugin_integration_instance, sample_html
    ):
        """Test process_content adds plugin_processed flag."""
        # Arrange
        await plugin_integration_instance.initialize()
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        # Act
        result = await plugin_integration_instance.process_content_with_plugins(
            sample_html, url, output_dir
        )

        # Assert
        assert result["plugin_processed"] is True


# =============================================================================
# TEST PluginIntegration - Shutdown
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestPluginIntegrationShutdown:
    """Test PluginIntegration shutdown method."""

    async def test_shutdown_calls_manager_when_enabled(
        self, plugin_integration_instance, mock_plugin_manager
    ):
        """Test shutdown calls plugin manager shutdown when enabled."""
        # Arrange
        await plugin_integration_instance.initialize()

        # Act
        await plugin_integration_instance.shutdown()

        # Assert
        mock_plugin_manager.shutdown.assert_called_once()

    async def test_shutdown_sets_enabled_false(self, plugin_integration_instance):
        """Test shutdown sets enabled flag to False."""
        # Arrange
        await plugin_integration_instance.initialize()
        assert plugin_integration_instance.enabled is True

        # Act
        await plugin_integration_instance.shutdown()

        # Assert
        assert plugin_integration_instance.enabled is False

    async def test_shutdown_does_not_call_manager_when_disabled(
        self, plugin_integration_instance, mock_plugin_manager
    ):
        """Test shutdown doesn't call manager when already disabled."""
        # Arrange - not initialized, so disabled
        assert plugin_integration_instance.enabled is False

        # Act
        await plugin_integration_instance.shutdown()

        # Assert
        mock_plugin_manager.shutdown.assert_not_called()


# =============================================================================
# TEST Global Instance
# =============================================================================


@pytest.mark.unit
class TestGlobalPluginIntegration:
    """Test global plugin_integration instance."""

    def test_global_plugin_integration_exists(self):
        """Test global plugin_integration instance exists."""
        # Assert
        assert plugin_integration is not None
        assert isinstance(plugin_integration, PluginIntegration)

    def test_global_plugin_integration_has_manager(self):
        """Test global plugin_integration has manager."""
        # Assert
        assert plugin_integration.manager is not None
