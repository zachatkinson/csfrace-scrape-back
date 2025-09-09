"""Content extraction processors following Single Responsibility Principle.

Each processor handles ONE specific aspect of HTML content extraction
and conversion, eliminating SOLID principle violations.
"""

import re
from abc import ABC, abstractmethod

import structlog
from bs4 import Tag

from ..core.exceptions import ProcessingError

logger = structlog.get_logger(__name__)


class ContentExtractorBase(ABC):
    """Base class for all content extractors.

    Follows Single Responsibility Principle - each extractor handles
    ONE specific type of content extraction or conversion.
    """

    def __init__(self, name: str):
        """Initialize extractor with a descriptive name for logging."""
        self.name = name

    @abstractmethod
    async def extract(self, content: Tag) -> Tag:
        """Extract or convert specific content type.

        Args:
            content: HTML content to process

        Returns:
            Processed HTML content

        Raises:
            ProcessingError: If extraction fails
        """
        pass

    def _log_processing(self, message: str, **kwargs):
        """Consistent logging across all extractors."""
        logger.debug(f"{self.name}: {message}", extractor=self.name, **kwargs)


class MainContentExtractor(ContentExtractorBase):
    """Extracts main content area from webpage.

    Single Responsibility: Find and extract the primary content area.
    """

    def __init__(self):
        super().__init__("MainContentExtractor")

    async def extract(self, content: Tag) -> Tag:
        """Find and extract main content area."""
        try:
            # Try common content selectors in order of preference
            selectors = [
                "main",
                "article",
                ".entry-content",
                ".post-content",
                ".content",
                '[role="main"]',
                "#main",
                "#content",
            ]

            for selector in selectors:
                found_content = (
                    content.select_one(selector) if hasattr(content, "select_one") else None
                )
                if found_content and len(found_content.get_text().strip()) > 100:
                    self._log_processing("Found main content", selector=selector)
                    return found_content

            # Fallback to body if no main content found
            body = content.find("body") if hasattr(content, "find") else None
            if body:
                self._log_processing("Using body as fallback content")
                return body

            raise ProcessingError("No main content area found")

        except Exception as e:
            raise ProcessingError(f"Content extraction failed: {e}") from e


class FontProcessor(ContentExtractorBase):
    """Processes font formatting and typography.

    Single Responsibility: Handle all font-related conversions.
    """

    def __init__(self):
        super().__init__("FontProcessor")

    async def extract(self, content: Tag) -> Tag:
        """Convert font formatting to Shopify-compatible styles."""
        try:
            # Convert font-weight styles
            for element in content.find_all(style=True):
                style = element.get("style", "")
                if "font-weight:" in style:
                    # Convert numerical font weights to semantic names
                    style = re.sub(r"font-weight:\s*([1-3]00)", r"font-weight: light", style)
                    style = re.sub(r"font-weight:\s*([4-6]00)", r"font-weight: normal", style)
                    style = re.sub(r"font-weight:\s*([7-9]00)", r"font-weight: bold", style)
                    element["style"] = style

            # Convert font elements to spans with appropriate styles
            for font_tag in content.find_all("font"):
                span = content.new_tag("span")
                # Copy all attributes except face and size (which are handled separately)
                for attr, value in font_tag.attrs.items():
                    if attr not in ["face", "size"]:
                        span[attr] = value

                # Convert font attributes to CSS
                if font_tag.get("face"):
                    span["style"] = span.get("style", "") + f"font-family: {font_tag['face']};"
                if font_tag.get("size"):
                    span["style"] = span.get("style", "") + f"font-size: {font_tag['size']}em;"

                span.string = font_tag.get_text()
                font_tag.replace_with(span)

            self._log_processing("Font formatting processed")
            return content

        except Exception as e:
            raise ProcessingError(f"Font processing failed: {e}") from e


class LayoutProcessor(ContentExtractorBase):
    """Processes layout and alignment elements.

    Single Responsibility: Handle layout-related conversions.
    """

    def __init__(self):
        super().__init__("LayoutProcessor")

    async def extract(self, content: Tag) -> Tag:
        """Convert layout elements to Shopify-compatible format."""
        try:
            # Convert text alignment
            for element in content.find_all(style=True):
                style = element.get("style", "")
                if "text-align:" in style:
                    # Ensure text alignment is preserved
                    align_match = re.search(r"text-align:\s*(left|center|right|justify)", style)
                    if align_match:
                        alignment = align_match.group(1)
                        element["class"] = element.get("class", []) + [f"text-{alignment}"]

            # Convert deprecated align attributes to CSS
            for element in content.find_all(align=True):
                alignment = element.get("align")
                if alignment in ["left", "center", "right", "justify"]:
                    current_style = element.get("style", "")
                    element["style"] = current_style + f"text-align: {alignment};"
                    del element["align"]

            self._log_processing("Layout processing completed")
            return content

        except Exception as e:
            raise ProcessingError(f"Layout processing failed: {e}") from e


class MediaProcessor(ContentExtractorBase):
    """Processes media elements (images, videos, embeds).

    Single Responsibility: Handle all media-related conversions.
    """

    def __init__(self):
        super().__init__("MediaProcessor")

    async def extract(self, content: Tag) -> Tag:
        """Process media elements for Shopify compatibility."""
        try:
            # Process images
            content = await self._process_images(content)

            # Process video embeds
            content = await self._process_video_embeds(content)

            # Process galleries
            content = await self._process_galleries(content)

            self._log_processing("Media processing completed")
            return content

        except Exception as e:
            raise ProcessingError(f"Media processing failed: {e}") from e

    async def _process_images(self, content: Tag) -> Tag:
        """Process individual images."""
        for img in content.find_all("img"):
            # Add responsive classes
            current_classes = img.get("class", [])
            if "responsive" not in current_classes:
                img["class"] = current_classes + ["responsive"]

            # Ensure alt text exists
            if not img.get("alt"):
                img["alt"] = "Image"

        return content

    async def _process_video_embeds(self, content: Tag) -> Tag:
        """Process YouTube and other video embeds."""
        # Convert YouTube embeds to responsive format
        for iframe in content.find_all("iframe"):
            src = iframe.get("src", "")
            if "youtube.com" in src or "youtu.be" in src:
                # Wrap in responsive container
                wrapper = content.new_tag("div", class_="video-responsive")
                iframe.wrap(wrapper)

        return content

    async def _process_galleries(self, content: Tag) -> Tag:
        """Process image galleries."""
        for gallery in content.find_all(class_=re.compile(r"gallery")):
            # Add gallery styling
            current_classes = gallery.get("class", [])
            gallery["class"] = current_classes + ["shopify-gallery"]

        return content


class ComponentProcessor(ContentExtractorBase):
    """Processes interactive components (buttons, forms, etc.).

    Single Responsibility: Handle interactive component conversions.
    """

    def __init__(self):
        super().__init__("ComponentProcessor")

    async def extract(self, content: Tag) -> Tag:
        """Process interactive components."""
        try:
            # Process buttons
            for button in content.find_all(["button", "input"]):
                if button.get("type") == "submit" or button.name == "button":
                    current_classes = button.get("class", [])
                    if "btn" not in " ".join(current_classes):
                        button["class"] = current_classes + ["btn", "btn-primary"]

            # Process links that look like buttons
            for link in content.find_all("a"):
                classes = " ".join(link.get("class", []))
                if any(btn_class in classes for btn_class in ["button", "btn", "cta"]):
                    current_classes = link.get("class", [])
                    link["class"] = current_classes + ["shopify-button"]

            self._log_processing("Component processing completed")
            return content

        except Exception as e:
            raise ProcessingError(f"Component processing failed: {e}") from e


class CleanupProcessor(ContentExtractorBase):
    """Handles cleanup and sanitization.

    Single Responsibility: Remove unwanted elements and clean up HTML.
    """

    def __init__(self):
        super().__init__("CleanupProcessor")

    async def extract(self, content: Tag) -> Tag:
        """Clean up WordPress artifacts and unwanted elements."""
        try:
            # Remove script tags
            for script in content.find_all("script"):
                script.decompose()

            # Remove WordPress-specific classes
            wordpress_patterns = [
                r"wp-\w+",
                r"post-\d+",
                r"page-id-\d+",
                r"attachment-\w+",
            ]

            for element in content.find_all(class_=True):
                classes = element.get("class", [])
                cleaned_classes = []

                for cls in classes:
                    if not any(re.match(pattern, cls) for pattern in wordpress_patterns):
                        cleaned_classes.append(cls)

                if cleaned_classes:
                    element["class"] = cleaned_classes
                else:
                    if "class" in element.attrs:
                        del element.attrs["class"]

            # Remove empty paragraphs
            for p in content.find_all("p"):
                if not p.get_text().strip() and not p.find("img"):
                    p.decompose()

            self._log_processing("Cleanup processing completed")
            return content

        except Exception as e:
            raise ProcessingError(f"Cleanup processing failed: {e}") from e
