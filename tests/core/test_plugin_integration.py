"""Comprehensive tests for plugin integration."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.plugin_integration import PluginIntegration, plugin_integration
from src.plugins.manager import PluginManager


class TestPluginIntegrationInitialization:
    """Test plugin integration initialization."""

    def test_plugin_integration_init_with_default_manager(self):
        """Test initialization with default plugin manager."""
        integration = PluginIntegration()

        assert integration.manager is not None
        assert integration.enabled is False

    def test_plugin_integration_init_with_custom_manager(self):
        """Test initialization with custom plugin manager."""
        mock_manager = MagicMock(spec=PluginManager)
        integration = PluginIntegration(manager=mock_manager)

        assert integration.manager is mock_manager
        assert integration.enabled is False

    def test_plugin_integration_init_with_none_manager(self):
        """Test initialization with None manager falls back to default."""
        integration = PluginIntegration(manager=None)

        assert integration.manager is not None
        assert integration.enabled is False


class TestPluginIntegrationInitialize:
    """Test plugin integration initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful plugin system initialization."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.initialize = AsyncMock()

        integration = PluginIntegration(manager=mock_manager)

        with patch("src.core.plugin_integration.logger") as mock_logger:
            await integration.initialize()

            mock_manager.initialize.assert_called_once()
            assert integration.enabled is True
            mock_logger.info.assert_called_once_with("Plugin system initialized")

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test plugin system initialization failure."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.initialize = AsyncMock(side_effect=Exception("Init failed"))

        integration = PluginIntegration(manager=mock_manager)

        with patch("src.core.plugin_integration.logger") as mock_logger:
            await integration.initialize()

            mock_manager.initialize.assert_called_once()
            assert integration.enabled is False
            mock_logger.warning.assert_called_once_with(
                "Failed to initialize plugin system", error="Init failed"
            )

    @pytest.mark.asyncio
    async def test_initialize_with_runtime_error(self):
        """Test initialization with RuntimeError."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.initialize = AsyncMock(side_effect=RuntimeError("Runtime error"))

        integration = PluginIntegration(manager=mock_manager)

        with patch("src.core.plugin_integration.logger") as mock_logger:
            await integration.initialize()

            assert integration.enabled is False
            mock_logger.warning.assert_called_once_with(
                "Failed to initialize plugin system", error="Runtime error"
            )


class TestPluginIntegrationProcessContent:
    """Test plugin integration process_content_with_plugins method."""

    @pytest.mark.asyncio
    async def test_process_content_plugins_disabled(self):
        """Test processing content when plugins are disabled."""
        mock_manager = MagicMock(spec=PluginManager)
        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = False

        html_content = "<p>Test content</p>"
        url = "https://example.com"
        output_dir = Path("/tmp/output")
        metadata = {"title": "Test"}

        result = await integration.process_content_with_plugins(
            html_content, url, output_dir, metadata
        )

        expected = {
            "content": html_content,
            "html": html_content,
            "metadata": metadata,
            "files": [],
            "plugin_processed": False,
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_process_content_plugins_disabled_no_metadata(self):
        """Test processing content when plugins disabled with no metadata."""
        mock_manager = MagicMock(spec=PluginManager)
        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = False

        html_content = "<p>Test content</p>"
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        result = await integration.process_content_with_plugins(html_content, url, output_dir)

        expected = {
            "content": html_content,
            "html": html_content,
            "metadata": {},
            "files": [],
            "plugin_processed": False,
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_process_content_plugins_enabled_success(self):
        """Test successful content processing with plugins enabled."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.process_content = AsyncMock(
            return_value={
                "content": "<p>Processed content</p>",
                "html": "<p>Processed HTML</p>",
                "metadata": {"title": "Processed"},
                "files": ["file1.txt", "file2.txt"],
            }
        )

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = True

        html_content = "<p>Test content</p>"
        url = "https://example.com"
        output_dir = Path("/tmp/output")
        metadata = {"title": "Test"}

        result = await integration.process_content_with_plugins(
            html_content, url, output_dir, metadata
        )

        mock_manager.process_content.assert_called_once_with(
            html_content, url, output_dir, metadata
        )

        expected = {
            "content": "<p>Processed content</p>",
            "html": "<p>Processed HTML</p>",
            "metadata": {"title": "Processed"},
            "files": ["file1.txt", "file2.txt"],
            "plugin_processed": True,
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_process_content_plugins_enabled_failure(self):
        """Test content processing failure with plugins enabled."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.process_content = AsyncMock(side_effect=Exception("Plugin processing failed"))

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = True

        html_content = "<p>Test content</p>"
        url = "https://example.com"
        output_dir = Path("/tmp/output")
        metadata = {"title": "Test"}

        with patch("src.core.plugin_integration.logger") as mock_logger:
            result = await integration.process_content_with_plugins(
                html_content, url, output_dir, metadata
            )

            mock_manager.process_content.assert_called_once_with(
                html_content, url, output_dir, metadata
            )

            expected = {
                "content": html_content,
                "html": html_content,
                "metadata": metadata,
                "files": [],
                "plugin_processed": False,
                "plugin_error": "Plugin processing failed",
            }
            assert result == expected

            mock_logger.error.assert_called_once_with(
                "Plugin processing failed, falling back", error="Plugin processing failed"
            )

    @pytest.mark.asyncio
    async def test_process_content_with_runtime_error(self):
        """Test content processing with RuntimeError."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.process_content = AsyncMock(
            side_effect=RuntimeError("Runtime error in plugin")
        )

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = True

        html_content = "<p>Test content</p>"
        url = "https://example.com"
        output_dir = Path("/tmp/output")

        with patch("src.core.plugin_integration.logger") as mock_logger:
            result = await integration.process_content_with_plugins(html_content, url, output_dir)

            expected = {
                "content": html_content,
                "html": html_content,
                "metadata": {},
                "files": [],
                "plugin_processed": False,
                "plugin_error": "Runtime error in plugin",
            }
            assert result == expected


class TestPluginIntegrationShutdown:
    """Test plugin integration shutdown method."""

    @pytest.mark.asyncio
    async def test_shutdown_when_enabled(self):
        """Test shutdown when plugin system is enabled."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.shutdown = AsyncMock()

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = True

        await integration.shutdown()

        mock_manager.shutdown.assert_called_once()
        assert integration.enabled is False

    @pytest.mark.asyncio
    async def test_shutdown_when_disabled(self):
        """Test shutdown when plugin system is already disabled."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.shutdown = AsyncMock()

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = False

        await integration.shutdown()

        mock_manager.shutdown.assert_not_called()
        assert integration.enabled is False

    @pytest.mark.asyncio
    async def test_shutdown_with_exception(self):
        """Test shutdown handling exceptions by propagating them."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.shutdown = AsyncMock(side_effect=Exception("Shutdown failed"))

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = True

        # Should raise exception (no exception handling in shutdown)
        with pytest.raises(Exception, match="Shutdown failed"):
            await integration.shutdown()

        mock_manager.shutdown.assert_called_once()
        # enabled should still be True since exception occurred before it could be set to False
        assert integration.enabled is True


class TestPluginIntegrationFullWorkflow:
    """Test complete plugin integration workflows."""

    @pytest.mark.asyncio
    async def test_complete_workflow_success(self):
        """Test complete workflow from init to shutdown."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.initialize = AsyncMock()
        mock_manager.process_content = AsyncMock(
            return_value={
                "content": "<p>Processed</p>",
                "html": "<p>Processed</p>",
                "metadata": {"processed": True},
                "files": [],
            }
        )
        mock_manager.shutdown = AsyncMock()

        integration = PluginIntegration(manager=mock_manager)

        # Initialize
        with patch("src.core.plugin_integration.logger"):
            await integration.initialize()
        assert integration.enabled is True

        # Process content
        result = await integration.process_content_with_plugins(
            "<p>Original</p>", "https://example.com", Path("/tmp")
        )
        assert result["plugin_processed"] is True

        # Shutdown
        await integration.shutdown()
        assert integration.enabled is False

        # Verify all manager methods were called
        mock_manager.initialize.assert_called_once()
        mock_manager.process_content.assert_called_once()
        mock_manager.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_with_init_failure(self):
        """Test workflow when initialization fails."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.initialize = AsyncMock(side_effect=Exception("Init failed"))

        integration = PluginIntegration(manager=mock_manager)

        # Initialize (fails)
        with patch("src.core.plugin_integration.logger"):
            await integration.initialize()
        assert integration.enabled is False

        # Process content (should fallback)
        result = await integration.process_content_with_plugins(
            "<p>Content</p>", "https://example.com", Path("/tmp")
        )
        assert result["plugin_processed"] is False

        # Shutdown (should be no-op)
        await integration.shutdown()
        assert integration.enabled is False


class TestGlobalPluginIntegrationInstance:
    """Test the global plugin integration instance."""

    def test_global_instance_exists(self):
        """Test that global plugin_integration instance exists."""
        assert plugin_integration is not None
        assert isinstance(plugin_integration, PluginIntegration)
        assert plugin_integration.enabled is False

    def test_global_instance_manager(self):
        """Test that global instance has a manager."""
        assert plugin_integration.manager is not None
        assert hasattr(plugin_integration.manager, "initialize")
        assert hasattr(plugin_integration.manager, "process_content")
        assert hasattr(plugin_integration.manager, "shutdown")

    @pytest.mark.asyncio
    async def test_global_instance_functionality(self):
        """Test that global instance methods work correctly."""
        # Test process_content_with_plugins when disabled
        result = await plugin_integration.process_content_with_plugins(
            "<p>Test</p>", "https://example.com", Path("/tmp")
        )

        assert result["plugin_processed"] is False
        assert result["content"] == "<p>Test</p>"
        assert result["html"] == "<p>Test</p>"
        assert result["metadata"] == {}
        assert result["files"] == []


class TestPluginIntegrationEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_process_content_with_empty_html(self):
        """Test processing with empty HTML content."""
        integration = PluginIntegration()
        integration.enabled = False

        result = await integration.process_content_with_plugins(
            "", "https://example.com", Path("/tmp")
        )

        assert result["content"] == ""
        assert result["html"] == ""
        assert result["plugin_processed"] is False

    @pytest.mark.asyncio
    async def test_process_content_with_none_metadata(self):
        """Test processing with None metadata."""
        integration = PluginIntegration()
        integration.enabled = False

        result = await integration.process_content_with_plugins(
            "<p>Test</p>", "https://example.com", Path("/tmp"), None
        )

        assert result["metadata"] == {}
        assert result["plugin_processed"] is False

    @pytest.mark.asyncio
    async def test_multiple_initialize_calls(self):
        """Test multiple initialize calls."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.initialize = AsyncMock()

        integration = PluginIntegration(manager=mock_manager)

        with patch("src.core.plugin_integration.logger"):
            await integration.initialize()
            await integration.initialize()  # Second call

        # Should be called twice
        assert mock_manager.initialize.call_count == 2
        assert integration.enabled is True

    @pytest.mark.asyncio
    async def test_multiple_shutdown_calls(self):
        """Test multiple shutdown calls."""
        mock_manager = AsyncMock(spec=PluginManager)
        mock_manager.shutdown = AsyncMock()

        integration = PluginIntegration(manager=mock_manager)
        integration.enabled = True

        await integration.shutdown()
        await integration.shutdown()  # Second call (should be no-op)

        # Should be called only once
        mock_manager.shutdown.assert_called_once()
        assert integration.enabled is False
