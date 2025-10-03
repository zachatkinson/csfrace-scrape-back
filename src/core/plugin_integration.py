"""Integration layer between core converter and plugin system."""

from pathlib import Path
from typing import Any

from src.core.decorators import content_processing_error_handler
from src.core.logging_hierarchy import get_core_logger

from ..plugins.manager import PluginManager, plugin_manager

logger = get_core_logger()


class PluginIntegration:
    """Handles integration between core converter and plugin system."""

    def __init__(self, manager: PluginManager | None = None):
        """Initialize plugin integration.

        Args:
            manager: Plugin manager to use (defaults to global manager)
        """
        self.manager = manager or plugin_manager
        self.enabled = False

    @content_processing_error_handler("initialize plugin system")
    async def initialize(self) -> None:
        """Initialize plugin system if enabled."""
        await self.manager.initialize()
        self.enabled = True
        logger.info("Plugin system initialized")

    async def process_content_with_plugins(
        self,
        html_content: str,
        url: str,
        output_dir: Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process content through plugin pipeline.

        Args:
            html_content: HTML content to process
            url: Source URL
            output_dir: Output directory
            metadata: Optional initial metadata

        Returns:
            Processing results from plugin pipeline
        """
        if not self.enabled:
            # Return minimal result if plugins disabled
            return {
                "content": html_content,
                "html": html_content,
                "metadata": metadata or {},
                "files": [],
                "plugin_processed": False,
            }

        result = await self._process_content_safe(html_content, url, output_dir, metadata)
        result["plugin_processed"] = True
        return result

    @content_processing_error_handler("process content with plugins")
    async def _process_content_safe(
        self,
        html_content: str,
        url: str,
        output_dir: Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process content through plugin pipeline with error handling."""
        return await self.manager.process_content(html_content, url, output_dir, metadata)

    async def shutdown(self) -> None:
        """Shutdown plugin system."""
        if self.enabled:
            await self.manager.shutdown()
            self.enabled = False


# Global plugin integration instance
plugin_integration = PluginIntegration()
