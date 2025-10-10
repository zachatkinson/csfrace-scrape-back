"""Content extraction processors following Single Responsibility Principle.

Each processor handles ONE specific aspect of HTML content extraction
and conversion, eliminating SOLID principle violations.
"""

import re
from abc import ABC, abstractmethod
from typing import Any

from bs4 import Tag

from src.core.decorators import content_processing_error_handler
from src.core.logging_hierarchy import get_scraping_logger

from ..core.exceptions import ProcessingError

logger = get_scraping_logger()


class ContentExtractorBase(ABC):
    """Base class for all content extractors.

    Follows Single Responsibility Principle - each extractor handles
    ONE specific type of content extraction or conversion.
    """

    def __init__(self, name: str) -> None:
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

    def _log_processing(self, message: str, **kwargs: Any) -> None:
        """Consistent logging across all extractors."""
        logger.debug(f"{self.name}: {message}", extractor=self.name, **kwargs)


class MainContentExtractor(ContentExtractorBase):
    """Extracts main content area from webpage.

    Single Responsibility: Find and extract the primary content area.
    """

    def __init__(self) -> None:
        super().__init__("MainContentExtractor")

    @content_processing_error_handler("extract main content")
    async def extract(self, content: Tag) -> Tag:
        """Find and extract main content area."""
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
            found_content = content.select_one(selector) if hasattr(content, "select_one") else None
            if found_content and len(found_content.get_text().strip()) > 100:
                self._log_processing("Found main content", selector=selector)
                return found_content

        # Fallback to body if no main content found
        body = content.find("body") if hasattr(content, "find") else None
        if body and isinstance(body, Tag):
            self._log_processing("Using body as fallback content")
            return body

        raise ProcessingError("No main content area found")


class FontProcessor(ContentExtractorBase):
    """Processes font formatting and typography.

    Single Responsibility: Handle all font-related conversions.
    """

    def __init__(self) -> None:
        super().__init__("FontProcessor")

    @content_processing_error_handler("process font formatting")
    async def extract(self, content: Tag) -> Tag:
        """Convert font formatting to Shopify-compatible styles."""
        # Convert font-weight styles
        for element in content.find_all(style=True):
            if not isinstance(element, Tag):
                continue
            style_attr = element.get("style", "")
            if not isinstance(style_attr, str):
                continue
            if "font-weight:" in style_attr:
                # Convert numerical font weights to semantic names
                style_attr = re.sub(r"font-weight:\s*([1-3]00)", r"font-weight: light", style_attr)
                style_attr = re.sub(r"font-weight:\s*([4-6]00)", r"font-weight: normal", style_attr)
                style_attr = re.sub(r"font-weight:\s*([7-9]00)", r"font-weight: bold", style_attr)
                element["style"] = style_attr

        # Convert font elements to spans with appropriate styles
        for font_tag in content.find_all("font"):
            if not isinstance(font_tag, Tag):
                continue
            # Verify new_tag method exists before using
            if not hasattr(content, "new_tag") or not callable(content.new_tag):
                continue
            # Create new span tag (BeautifulSoup returns Any type, but it's actually a Tag)
            span_tag = content.new_tag("span")
            if not isinstance(span_tag, Tag):
                continue

            # Copy all attributes except face and size (which are handled separately)
            for attr, value in font_tag.attrs.items():
                if attr not in ["face", "size"]:
                    span_tag.attrs[attr] = value

            # Convert font attributes to CSS
            face_attr = font_tag.get("face")
            if face_attr:
                # Handle both str and list[str] from BeautifulSoup attrs
                face_str = (
                    face_attr
                    if isinstance(face_attr, str)
                    else " ".join(face_attr)
                    if isinstance(face_attr, list)
                    else str(face_attr)
                )
                current_style = span_tag.get("style")
                current_style_str = (
                    current_style
                    if isinstance(current_style, str)
                    else " ".join(current_style)
                    if isinstance(current_style, list)
                    else ""
                )
                span_tag.attrs["style"] = current_style_str + f"font-family: {face_str};"

            size_attr = font_tag.get("size")
            if size_attr:
                # Handle both str and list[str] from BeautifulSoup attrs
                size_str = (
                    size_attr
                    if isinstance(size_attr, str)
                    else " ".join(size_attr)
                    if isinstance(size_attr, list)
                    else str(size_attr)
                )
                current_style = span_tag.get("style")
                current_style_str = (
                    current_style
                    if isinstance(current_style, str)
                    else " ".join(current_style)
                    if isinstance(current_style, list)
                    else ""
                )
                span_tag.attrs["style"] = current_style_str + f"font-size: {size_str}em;"

            span_tag.string = font_tag.get_text()
            font_tag.replace_with(span_tag)

        self._log_processing("Font formatting processed")
        return content


class LayoutProcessor(ContentExtractorBase):
    """Processes layout and alignment elements.

    Single Responsibility: Handle layout-related conversions.
    """

    def __init__(self) -> None:
        super().__init__("LayoutProcessor")

    @content_processing_error_handler("process layout elements")
    async def extract(self, content: Tag) -> Tag:
        """Convert layout elements to Shopify-compatible format."""
        # Convert text alignment
        for element in content.find_all(style=True):
            if not isinstance(element, Tag):
                continue
            style = element.get("style")
            if not isinstance(style, str):
                continue
            if "text-align:" in style:
                # Ensure text alignment is preserved
                align_match = re.search(r"text-align:\s*(left|center|right|justify)", style)
                if align_match:
                    alignment = align_match.group(1)
                    current_class = element.get("class")
                    class_list = (
                        current_class
                        if isinstance(current_class, list)
                        else [current_class]
                        if current_class
                        else []
                    )
                    element.attrs["class"] = class_list + [f"text-{alignment}"]  # type: ignore[assignment]

        # Convert deprecated align attributes to CSS
        for element in content.find_all(align=True):
            if not isinstance(element, Tag):
                continue
            alignment = element.get("align")
            # Handle both str and list[str] from BeautifulSoup attrs
            align_str = (
                alignment
                if isinstance(alignment, str)
                else alignment[0]
                if isinstance(alignment, list) and alignment
                else None
            )
            if align_str in ["left", "center", "right", "justify"]:
                current_style = element.get("style")
                current_style_str = (
                    current_style
                    if isinstance(current_style, str)
                    else " ".join(current_style)
                    if isinstance(current_style, list)
                    else ""
                )
                element.attrs["style"] = current_style_str + f"text-align: {align_str};"
                del element.attrs["align"]

        self._log_processing("Layout processing completed")
        return content


class MediaProcessor(ContentExtractorBase):
    """Processes media elements (images, videos, embeds).

    Single Responsibility: Handle all media-related conversions.
    """

    def __init__(self) -> None:
        super().__init__("MediaProcessor")

    @content_processing_error_handler("process media elements")
    async def extract(self, content: Tag) -> Tag:
        """Process media elements for Shopify compatibility."""
        # Process images
        content = await self._process_images(content)

        # Process video embeds
        content = await self._process_video_embeds(content)

        # Process galleries
        content = await self._process_galleries(content)

        self._log_processing("Media processing completed")
        return content

    async def _process_images(self, content: Tag) -> Tag:
        """Process individual images."""
        for img in content.find_all("img"):
            if not isinstance(img, Tag):
                continue
            # Add responsive classes
            current_classes = img.get("class")
            class_list = (
                current_classes
                if isinstance(current_classes, list)
                else [current_classes]
                if current_classes
                else []
            )
            if "responsive" not in class_list:
                img.attrs["class"] = class_list + ["responsive"]  # type: ignore[assignment]

            # Ensure alt text exists
            if not img.get("alt"):
                img.attrs["alt"] = "Image"

        return content

    async def _process_video_embeds(self, content: Tag) -> Tag:
        """Process YouTube and other video embeds."""
        # Convert YouTube embeds to responsive format
        for iframe in content.find_all("iframe"):
            if not isinstance(iframe, Tag):
                continue
            src = iframe.get("src")
            src_str = (
                src if isinstance(src, str) else " ".join(src) if isinstance(src, list) else ""
            )
            # Secure URL validation: parse and check actual domain
            from urllib.parse import urlparse

            parsed = urlparse(src_str)
            allowed_domains = {"youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"}
            if (
                parsed.netloc in allowed_domains
                and hasattr(content, "new_tag")
                and callable(content.new_tag)
            ):
                # Wrap in responsive container (BeautifulSoup returns Any type, but it's actually a Tag)
                wrapper_tag = content.new_tag("div")
                if isinstance(wrapper_tag, Tag):
                    wrapper_tag.attrs["class"] = ["video-responsive"]
                    iframe.wrap(wrapper_tag)

        return content

    async def _process_galleries(self, content: Tag) -> Tag:
        """Process image galleries."""
        for gallery in content.find_all(class_=re.compile(r"gallery")):
            if not isinstance(gallery, Tag):
                continue
            # Add gallery styling
            current_classes = gallery.get("class")
            class_list = (
                current_classes
                if isinstance(current_classes, list)
                else [current_classes]
                if current_classes
                else []
            )
            gallery.attrs["class"] = class_list + ["shopify-gallery"]  # type: ignore[assignment]

        return content


class ComponentProcessor(ContentExtractorBase):
    """Processes interactive components (buttons, forms, etc.).

    Single Responsibility: Handle interactive component conversions.
    """

    def __init__(self) -> None:
        super().__init__("ComponentProcessor")

    @content_processing_error_handler("process interactive components")
    async def extract(self, content: Tag) -> Tag:
        """Process interactive components."""
        # Process buttons
        for button in content.find_all(["button", "input"]):
            if not isinstance(button, Tag):
                continue
            button_type = button.get("type")
            button_type_str = (
                button_type
                if isinstance(button_type, str)
                else button_type[0]
                if isinstance(button_type, list) and button_type
                else None
            )
            if button_type_str == "submit" or button.name == "button":
                current_classes = button.get("class")
                class_list = (
                    current_classes
                    if isinstance(current_classes, list)
                    else [current_classes]
                    if current_classes
                    else []
                )
                class_str = " ".join(class_list)
                if "btn" not in class_str:
                    button.attrs["class"] = class_list + ["btn", "btn-primary"]  # type: ignore[assignment]

        # Process links that look like buttons
        for link in content.find_all("a"):
            if not isinstance(link, Tag):
                continue
            current_classes = link.get("class")
            class_list = (
                current_classes
                if isinstance(current_classes, list)
                else [current_classes]
                if current_classes
                else []
            )
            classes = " ".join(class_list)
            if any(btn_class in classes for btn_class in ["button", "btn", "cta"]):
                link.attrs["class"] = class_list + ["shopify-button"]  # type: ignore[assignment]

        self._log_processing("Component processing completed")
        return content


class CleanupProcessor(ContentExtractorBase):
    """Handles cleanup and sanitization.

    Single Responsibility: Remove unwanted elements and clean up HTML.
    """

    def __init__(self) -> None:
        super().__init__("CleanupProcessor")

    @content_processing_error_handler("cleanup content")
    async def extract(self, content: Tag) -> Tag:
        """Clean up WordPress artifacts and unwanted elements."""
        # Remove script tags
        for script in content.find_all("script"):
            if isinstance(script, Tag):
                script.decompose()

        # Remove WordPress-specific classes
        wordpress_patterns = [
            r"wp-\w+",
            r"post-\d+",
            r"page-id-\d+",
            r"attachment-\w+",
        ]

        for element in content.find_all(class_=True):
            if not isinstance(element, Tag):
                continue
            classes = element.get("class")
            class_list = classes if isinstance(classes, list) else [classes] if classes else []
            cleaned_classes: list[str] = []

            for cls in class_list:
                cls_str = cls if isinstance(cls, str) else str(cls)
                if not any(re.match(pattern, cls_str) for pattern in wordpress_patterns):
                    cleaned_classes.append(cls_str)

            if cleaned_classes:
                element.attrs["class"] = cleaned_classes  # type: ignore[assignment]
            else:
                if "class" in element.attrs:
                    del element.attrs["class"]

        # Remove empty paragraphs
        for p in content.find_all("p"):
            if not isinstance(p, Tag):
                continue
            if not p.get_text().strip() and not p.find("img"):
                p.decompose()

        self._log_processing("Cleanup processing completed")
        return content
