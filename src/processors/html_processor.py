"""HTML content processing and conversion rules."""

import re

import structlog
from bs4 import BeautifulSoup, NavigableString, Tag

from ..constants import CONSTANTS, IFRAME_ASPECT_RATIO
from ..core.config import config
from ..core.exceptions import ProcessingError
from ..utils.html import safe_copy_attributes

logger = structlog.get_logger(__name__)


class HTMLProcessor:
    """Processes and converts WordPress HTML to Shopify-compatible format."""

    async def process(self, soup: BeautifulSoup) -> str:
        """Main processing method that applies all conversion rules.

        Args:
            soup: BeautifulSoup object of the webpage

        Returns:
            Converted HTML string

        Raises:
            ProcessingError: If processing fails
        """
        try:
            logger.info("Starting HTML processing")

            # Find main content area
            content = self._find_main_content(soup)

            # Apply all conversion rules in order
            content = await self._convert_font_formatting(content)
            content = await self._convert_text_alignment(content)
            content = await self._convert_kadence_layouts(content)
            content = await self._convert_image_galleries(content)
            content = await self._convert_simple_images(content)
            content = await self._convert_buttons(content)
            content = await self._convert_blockquotes(content)
            content = await self._convert_youtube_embeds(content)
            content = await self._convert_instagram_embeds(content)
            content = await self._fix_external_links(content)

            # Remove unwanted elements
            await self._remove_scripts(content)

            # Final cleanup
            content = await self._cleanup_wordpress_artifacts(content)

            result = str(content)
            logger.info("HTML processing completed", output_size=len(result))

            return result

        except Exception as e:
            raise ProcessingError(f"HTML processing failed: {e}") from e

    def _find_main_content(self, soup: BeautifulSoup) -> Tag:
        """Find the main content area of the page.

        Args:
            soup: BeautifulSoup object

        Returns:
            Content container element
        """
        # Try to find entry-content div (common WordPress pattern)
        entry_content = soup.find("div", class_="entry-content")
        if entry_content:
            logger.debug("Found entry-content div")
            return entry_content

        # Try other common content selectors
        selectors = [
            "main",
            ".post-content",
            ".content",
            "#content",
            "article",
            ".single-post-content",
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                logger.debug("Found main content", selector=selector)
                return element

        # Fall back to body or entire document
        body = soup.find("body")
        if body:
            logger.warning("Using entire body as content")
            return body

        logger.warning("Using entire document as content")
        return soup

    async def _convert_font_formatting(self, content: Tag) -> Tag:
        """Convert font formatting tags to semantic HTML.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        # Replace <b> with <strong>
        for b_tag in content.find_all("b"):
            b_tag.name = "strong"

        # Replace <i> with <em>
        for i_tag in content.find_all("i"):
            i_tag.name = "em"

        logger.debug("Converted font formatting tags")
        return content

    async def _convert_text_alignment(self, content: Tag) -> Tag:
        """Convert WordPress text alignment classes to Shopify format.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        # Convert text-align-center to center class
        for elem in content.find_all(class_="has-text-align-center"):
            elem["class"] = ["center"]

        logger.debug("Converted text alignment classes")
        return content

    async def _convert_kadence_layouts(self, content: Tag) -> Tag:
        """Convert Kadence row layouts to media-grid format.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for row_layout in content.find_all("div", class_="wp-block-kadence-rowlayout"):
            col_container = row_layout.find("div", class_=re.compile(r"kt-has-\d+-columns"))

            if col_container:
                # Determine grid class based on column count
                grid_class = self._determine_grid_class(col_container)
                new_div = soup_root.new_tag("div", **{"class": grid_class})

                # Convert each column to media-grid-text-box
                for column in col_container.find_all("div", class_="wp-block-kadence-column"):
                    text_box = self._create_text_box_from_column(soup_root, column)
                    new_div.append(text_box)

                row_layout.replace_with(new_div)

        logger.debug("Converted Kadence layouts")
        return content

    def _determine_grid_class(self, container: Tag) -> str:
        """Determine appropriate media-grid class based on column count."""
        class_str = " ".join(container.get("class", []))

        if "kt-has-2-columns" in class_str:
            return "media-grid-2"
        elif "kt-has-4-columns" in class_str:
            return "media-grid-4"
        elif "kt-has-5-columns" in class_str:
            return "media-grid-5"
        else:
            return "media-grid"  # Default for 3 columns or unknown

    def _create_text_box_from_column(self, soup_root: BeautifulSoup, column: Tag) -> Tag:
        """Create media-grid-text-box from Kadence column."""
        text_box = soup_root.new_tag("div", **{"class": "media-grid-text-box"})

        # Find the inner content container
        inner_col = column.find("div", class_="kt-inside-inner-col")
        source = inner_col if inner_col else column

        # Move all meaningful content
        for child in list(source.children):
            if isinstance(child, NavigableString):
                if child.strip():  # Only move non-empty text
                    text_box.append(child.extract())
            elif isinstance(child, Tag):
                text_box.append(child.extract())

        return text_box

    async def _convert_image_galleries(self, content: Tag) -> Tag:
        """Convert Kadence advanced galleries to media-grid format.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for gallery in content.find_all("div", class_="wp-block-kadence-advancedgallery"):
            media_grid = soup_root.new_tag("div", **{"class": "media-grid"})

            # Convert each image in the gallery
            for img in gallery.find_all("img"):
                img_container = self._create_image_container(soup_root, img)
                media_grid.append(img_container)

            gallery.replace_with(media_grid)

        logger.debug("Converted image galleries")
        return content

    def _create_image_container(self, soup_root: BeautifulSoup, img: Tag) -> Tag:
        """Create image container with optional caption."""
        img_div = soup_root.new_tag("div")

        # Create clean img tag
        new_img = soup_root.new_tag("img")
        safe_copy_attributes(img, new_img, {"src": "src", "alt": "alt"})

        # Copy important attributes
        if img.get("width"):
            new_img["width"] = img["width"]
        if img.get("height"):
            new_img["height"] = img["height"]

        img_div.append(new_img)

        # Handle captions
        figure = img.find_parent("figure")
        if figure:
            figcaption = figure.find("figcaption")
            if figcaption and figcaption.get_text().strip():
                caption_p = soup_root.new_tag("p")
                caption_em = soup_root.new_tag("em")
                caption_em.string = figcaption.get_text().strip()
                caption_p.append(caption_em)
                img_div.append(caption_p)

        return img_div

    async def _convert_simple_images(self, content: Tag) -> Tag:
        """Convert wp-block-image to simple img tags.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for img_block in content.find_all("div", class_="wp-block-image"):
            img_tag = img_block.find("img")
            if img_tag:
                # Create new clean img tag
                new_img = soup_root.new_tag("img")
                safe_copy_attributes(img_tag, new_img, {"src": "src", "alt": "alt"})

                # Preserve dimensions if available
                if img_tag.get("width"):
                    new_img["width"] = img_tag["width"]
                if img_tag.get("height"):
                    new_img["height"] = img_tag["height"]

                img_block.replace_with(new_img)

        logger.debug("Converted simple images")
        return content

    async def _convert_buttons(self, content: Tag) -> Tag:
        """Convert Kadence advanced buttons to Shopify format.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for btn_block in content.find_all("div", class_="wp-block-kadence-advancedbtn"):
            btn_link = btn_block.find("a", class_="button")
            if btn_link:
                new_btn = self._create_shopify_button(soup_root, btn_link)
                btn_block.replace_with(new_btn)

        logger.debug("Converted buttons")
        return content

    def _create_shopify_button(self, soup_root: BeautifulSoup, original_btn: Tag) -> Tag:
        """Create Shopify-formatted button."""
        new_btn = soup_root.new_tag("a")
        safe_copy_attributes(original_btn, new_btn, {"href": "href"})
        new_btn["class"] = [
            "button",
            "button--full-width",
            "button--primary",
            "press-release-button",
        ]

        # Handle external links
        href = original_btn.get("href", "")
        if self._is_external_link(href):
            new_btn["target"] = "_blank"
            new_btn["rel"] = "noreferrer noopener"

        # Copy button text
        new_btn.string = original_btn.get_text().strip()

        return new_btn

    def _is_external_link(self, href: str) -> bool:
        """Check if a link is external (not csfrace.com)."""
        if not href:
            return False

        href_lower = href.lower()
        return (
            href_lower.startswith((CONSTANTS.HTTP_PROTOCOL, CONSTANTS.HTTPS_PROTOCOL))
            and CONSTANTS.TARGET_DOMAIN not in href_lower
        )

    async def _convert_blockquotes(self, content: Tag) -> Tag:
        """Convert pullquote blocks to testimonial format.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for pullquote in content.find_all("figure", class_="wp-block-pullquote"):
            blockquote = pullquote.find("blockquote")
            if blockquote:
                testimonial = self._create_testimonial(soup_root, blockquote)
                pullquote.replace_with(testimonial)

        logger.debug("Converted blockquotes")
        return content

    def _create_testimonial(self, soup_root: BeautifulSoup, blockquote: Tag) -> Tag:
        """Create testimonial-style quote structure."""
        testimonial_div = soup_root.new_tag("div", **{"class": "testimonial-quote group"})
        quote_container = soup_root.new_tag("div", **{"class": "quote-container"})

        # Create new blockquote
        new_blockquote = soup_root.new_tag("blockquote")

        # Handle quote content
        quote_p = blockquote.find("p")
        if quote_p:
            new_p = soup_root.new_tag("p")
            new_p.string = quote_p.get_text().strip()
            new_blockquote.append(new_p)

        quote_container.append(new_blockquote)

        # Handle citation
        cite = blockquote.find("cite")
        if cite and cite.get_text().strip():
            new_cite = soup_root.new_tag("cite")
            cite_span = soup_root.new_tag("span")
            cite_span.string = cite.get_text().strip()
            new_cite.append(cite_span)
            quote_container.append(new_cite)

        testimonial_div.append(quote_container)
        return testimonial_div

    async def _convert_youtube_embeds(self, content: Tag) -> Tag:
        """Convert YouTube embeds to responsive format.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for youtube_embed in content.find_all("figure", class_="wp-block-embed-youtube"):
            iframe = youtube_embed.find("iframe")
            if iframe:
                responsive_embed = self._create_responsive_youtube(soup_root, iframe, youtube_embed)
                youtube_embed.replace_with(responsive_embed)

        logger.debug("Converted YouTube embeds")
        return content

    def _create_responsive_youtube(
        self, soup_root: BeautifulSoup, iframe: Tag, original_embed: Tag
    ) -> Tag:
        """Create responsive YouTube embed."""
        # Container with centered layout
        container_div = soup_root.new_tag("div")
        container_div["style"] = "display: flex; justify-content: center;"

        # Responsive iframe
        new_iframe = soup_root.new_tag("iframe")
        new_iframe["style"] = (
            f"aspect-ratio: {IFRAME_ASPECT_RATIO}; width: 100% !important;"
        )
        safe_copy_attributes(
            iframe, new_iframe, {"src": "src", "title": ("title", "YouTube Video")}
        )
        new_iframe["frameborder"] = "0"
        new_iframe["allowfullscreen"] = True

        container_div.append(new_iframe)

        # Handle captions
        figcaption = original_embed.find("figcaption")
        if figcaption and figcaption.get_text().strip():
            wrapper = soup_root.new_tag("div")
            wrapper.append(container_div)

            caption_p = soup_root.new_tag("p")
            caption_strong = soup_root.new_tag("strong")
            caption_strong.string = figcaption.get_text().strip()
            caption_p.append(caption_strong)
            wrapper.append(caption_p)

            return wrapper

        return container_div

    async def _convert_instagram_embeds(self, content: Tag) -> Tag:
        """Convert Instagram embeds with proper container.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        soup_root = self._get_root_soup(content)

        for iframe in content.find_all("iframe", class_="instagram-media"):
            # Create wrapper div
            wrapper_div = soup_root.new_tag("div")

            # Copy iframe with all attributes
            new_iframe = soup_root.new_tag("iframe")
            for attr, value in iframe.attrs.items():
                new_iframe[attr] = value

            wrapper_div.append(new_iframe)
            iframe.replace_with(wrapper_div)

        logger.debug("Converted Instagram embeds")
        return content

    async def _fix_external_links(self, content: Tag) -> Tag:
        """Add target and rel attributes to external links.

        Args:
            content: Content element to process

        Returns:
            Modified content element
        """
        for link in content.find_all("a", href=True):
            href = link.get("href")
            if self._is_external_link(href):
                # Only set if not already set
                if not link.get("target"):
                    link["target"] = "_blank"
                if not link.get("rel"):
                    link["rel"] = "noreferrer noopener"

        logger.debug("Fixed external links")
        return content

    async def _remove_scripts(self, content: Tag) -> None:
        """Remove all script tags for security.

        Args:
            content: Content element to process
        """
        scripts_removed = 0
        for script in content.find_all("script"):
            script.decompose()
            scripts_removed += 1

        if scripts_removed > 0:
            logger.debug("Removed script tags", count=scripts_removed)

    async def _cleanup_wordpress_artifacts(self, content: Tag) -> Tag:
        """Remove WordPress-specific classes and attributes.

        Args:
            content: Content element to process

        Returns:
            Cleaned content element
        """
        elements_cleaned = 0

        # Process the content element itself and all its descendants
        elements_to_process = [content] + content.find_all()

        for elem in elements_to_process:
            # Clean CSS classes
            if elem.get("class"):
                original_classes = elem.get("class", [])
                preserved_classes = [
                    cls for cls in original_classes if cls in config.preserve_classes
                ]

                if preserved_classes:
                    elem["class"] = preserved_classes
                    if len(preserved_classes) < len(original_classes):
                        elements_cleaned += 1
                else:
                    del elem["class"]
                    elements_cleaned += 1

            # Remove inline styles (except for specific media embeds)
            if elem.get("style"):
                style = elem.get("style")
                # Keep specific styles for embeds
                if not any(
                    keep_style in style
                    for keep_style in [
                        f"aspect-ratio: {IFRAME_ASPECT_RATIO}",
                        "display: flex; justify-content: center;",
                    ]
                ):
                    del elem["style"]
                    elements_cleaned += 1

            # Remove WordPress-specific attributes
            wp_attrs = ["data-align", "data-type", "data-responsive-size", "id"]
            for attr in wp_attrs:
                if elem.get(attr):
                    del elem[attr]
                    elements_cleaned += 1

        if elements_cleaned > 0:
            logger.debug("Cleaned WordPress artifacts", elements_cleaned=elements_cleaned)

        return content

    def _get_root_soup(self, element: Tag) -> BeautifulSoup:
        """Get the root BeautifulSoup object for creating new tags."""
        root = element
        while root.parent:
            root = root.parent
        return root
