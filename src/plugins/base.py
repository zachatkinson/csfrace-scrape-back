"""Base plugin interface and types for the extensible processor system."""

import abc
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class PluginType(Enum):
    """Types of plugins supported by the system."""
    HTML_PROCESSOR = "html_processor"
    CONTENT_FILTER = "content_filter" 
    IMAGE_PROCESSOR = "image_processor"
    METADATA_EXTRACTOR = "metadata_extractor"
    OUTPUT_FORMATTER = "output_formatter"
    POST_PROCESSOR = "post_processor"


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    name: str
    version: str
    plugin_type: PluginType
    enabled: bool = True
    priority: int = 100  # Lower number = higher priority
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


class BasePlugin(abc.ABC):
    """Base class for all plugins.
    
    All plugins must inherit from this class and implement the required methods.
    """
    
    def __init__(self, config: PluginConfig):
        """Initialize the plugin.
        
        Args:
            config: Plugin configuration
        """
        self.config = config
        self.logger = structlog.get_logger(self.__class__.__name__)
        self._initialized = False
    
    @property
    @abc.abstractmethod
    def plugin_info(self) -> Dict[str, Any]:
        """Return plugin metadata.
        
        Returns:
            Dictionary containing plugin information:
            - name: Plugin name
            - version: Plugin version
            - description: Brief description
            - author: Plugin author
            - plugin_type: Type of plugin
        """
        pass
    
    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin.
        
        Called once when the plugin is loaded. Use this to set up
        any resources, validate configuration, etc.
        
        Raises:
            Exception: If initialization fails
        """
        pass
    
    @abc.abstractmethod
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process data through the plugin.
        
        Args:
            data: Input data to process
            context: Processing context with metadata
            
        Returns:
            Processed data
            
        Raises:
            Exception: If processing fails
        """
        pass
    
    async def cleanup(self) -> None:
        """Clean up plugin resources.
        
        Called when the plugin is unloaded or the system shuts down.
        Override this method if your plugin needs to clean up resources.
        """
        pass
    
    async def validate_config(self) -> bool:
        """Validate plugin configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        return True
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a plugin setting value.
        
        Args:
            key: Setting key
            default: Default value if key doesn't exist
            
        Returns:
            Setting value or default
        """
        return self.config.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a plugin setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        self.config.settings[key] = value
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled.
        
        Returns:
            True if plugin is enabled
        """
        return self.config.enabled
    
    def get_priority(self) -> int:
        """Get plugin priority.
        
        Returns:
            Plugin priority (lower number = higher priority)
        """
        return self.config.priority


class HTMLProcessorPlugin(BasePlugin):
    """Base class for HTML processing plugins."""
    
    @abc.abstractmethod
    async def process_html(
        self,
        html_content: str,
        metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Process HTML content.
        
        Args:
            html_content: Raw HTML content to process
            metadata: Page metadata
            context: Processing context
            
        Returns:
            Processed HTML content
        """
        pass
    
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process method implementation for HTML processors."""
        if not isinstance(data, dict) or 'html' not in data:
            raise ValueError("HTMLProcessorPlugin expects dict with 'html' key")
        
        html_content = data['html']
        metadata = data.get('metadata', {})
        
        processed_html = await self.process_html(html_content, metadata, context)
        
        return {**data, 'html': processed_html}


class ContentFilterPlugin(BasePlugin):
    """Base class for content filtering plugins."""
    
    @abc.abstractmethod
    async def filter_content(
        self,
        content: str,
        content_type: str,
        context: Dict[str, Any]
    ) -> str:
        """Filter content.
        
        Args:
            content: Content to filter
            content_type: Type of content (html, text, etc.)
            context: Processing context
            
        Returns:
            Filtered content
        """
        pass
    
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process method implementation for content filters."""
        if not isinstance(data, dict) or 'content' not in data:
            raise ValueError("ContentFilterPlugin expects dict with 'content' key")
        
        content = data['content']
        content_type = data.get('content_type', 'html')
        
        filtered_content = await self.filter_content(content, content_type, context)
        
        return {**data, 'content': filtered_content}


class ImageProcessorPlugin(BasePlugin):
    """Base class for image processing plugins."""
    
    @abc.abstractmethod
    async def process_image(
        self,
        image_url: str,
        image_data: bytes,
        metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process an image.
        
        Args:
            image_url: Original image URL
            image_data: Raw image data
            metadata: Image metadata
            context: Processing context
            
        Returns:
            Dictionary with processed image data:
            - data: Processed image bytes
            - metadata: Updated metadata
            - format: Image format
            - size: (width, height) tuple
        """
        pass
    
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process method implementation for image processors."""
        if not isinstance(data, dict) or 'image_data' not in data:
            raise ValueError("ImageProcessorPlugin expects dict with 'image_data' key")
        
        image_url = data.get('url', '')
        image_data = data['image_data']
        metadata = data.get('metadata', {})
        
        result = await self.process_image(image_url, image_data, metadata, context)
        
        return {**data, **result}


class MetadataExtractorPlugin(BasePlugin):
    """Base class for metadata extraction plugins."""
    
    @abc.abstractmethod
    async def extract_metadata(
        self,
        html_content: str,
        url: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract metadata from HTML content.
        
        Args:
            html_content: HTML content to analyze
            url: Source URL
            context: Processing context
            
        Returns:
            Dictionary with extracted metadata
        """
        pass
    
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process method implementation for metadata extractors."""
        if not isinstance(data, dict) or 'html' not in data:
            raise ValueError("MetadataExtractorPlugin expects dict with 'html' key")
        
        html_content = data['html']
        url = data.get('url', '')
        
        metadata = await self.extract_metadata(html_content, url, context)
        
        existing_metadata = data.get('metadata', {})
        merged_metadata = {**existing_metadata, **metadata}
        
        return {**data, 'metadata': merged_metadata}


class OutputFormatterPlugin(BasePlugin):
    """Base class for output formatting plugins."""
    
    @abc.abstractmethod
    async def format_output(
        self,
        content: str,
        metadata: Dict[str, Any],
        output_format: str,
        context: Dict[str, Any]
    ) -> str:
        """Format content for output.
        
        Args:
            content: Content to format
            metadata: Content metadata
            output_format: Desired output format
            context: Processing context
            
        Returns:
            Formatted content
        """
        pass
    
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process method implementation for output formatters."""
        if not isinstance(data, dict) or 'content' not in data:
            raise ValueError("OutputFormatterPlugin expects dict with 'content' key")
        
        content = data['content']
        metadata = data.get('metadata', {})
        output_format = data.get('output_format', 'html')
        
        formatted_content = await self.format_output(content, metadata, output_format, context)
        
        return {**data, 'content': formatted_content}


class PostProcessorPlugin(BasePlugin):
    """Base class for post-processing plugins."""
    
    @abc.abstractmethod
    async def post_process(
        self,
        output_dir: Path,
        files: List[Path],
        metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post-process generated files.
        
        Args:
            output_dir: Output directory
            files: List of generated files
            metadata: Processing metadata
            context: Processing context
            
        Returns:
            Dictionary with post-processing results
        """
        pass
    
    async def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process method implementation for post processors."""
        if not isinstance(data, dict):
            raise ValueError("PostProcessorPlugin expects dict data")
        
        output_dir = data.get('output_dir')
        files = data.get('files', [])
        metadata = data.get('metadata', {})
        
        if not output_dir:
            raise ValueError("PostProcessorPlugin requires 'output_dir' in data")
        
        result = await self.post_process(Path(output_dir), files, metadata, context)
        
        return {**data, 'post_process_result': result}