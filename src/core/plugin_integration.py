"""Integration layer between core converter and plugin system."""

from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

from ..plugins.manager import PluginManager, plugin_manager

logger = get_logger(__name__)


class PluginIntegration:
    """Handles integration between core converter and plugin system."""

    def __init__(self, manager: PluginManager | None = None):
        """Initialize plugin integration.

        Args:
            manager: Plugin manager to use (defaults to global manager)
        """
        self.manager = manager or plugin_manager
        self.enabled = False

    async def initialize(self) -> None:
        """Initialize plugin system if enabled."""
        try:
            await self.manager.initialize()
            self.enabled = True
            logger.info("Plugin system initialized")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to initialize plugin system", error=str(e))
            self.enabled = False

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

        try:
            result = await self.manager.process_content(html_content, url, output_dir, metadata)
            result["plugin_processed"] = True
            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Plugin processing failed, falling back", error=str(e))
            return {
                "content": html_content,
                "html": html_content,
                "metadata": metadata or {},
                "files": [],
                "plugin_processed": False,
                "plugin_error": str(e),
            }

    async def shutdown(self) -> None:
        """Shutdown plugin system."""
        if self.enabled:
            await self.manager.shutdown()
            self.enabled = False


# Global plugin integration instance
plugin_integration = PluginIntegration()
