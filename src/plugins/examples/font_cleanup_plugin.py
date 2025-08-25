"""Example font cleanup plugin that replicates HTMLProcessor font functionality."""

import re
from typing import Dict, Any

from bs4 import BeautifulSoup, Tag, NavigableString

from src.plugins.base import HTMLProcessorPlugin


class FontCleanupPlugin(HTMLProcessorPlugin):
    """Plugin to clean up font-related HTML elements and styles."""
    
    @property
    def plugin_info(self) -> Dict[str, Any]:
        return {
            'name': 'Font Cleanup',
            'version': '1.0.0',
            'description': 'Removes font tags and font-related CSS styles for cleaner HTML',
            'author': 'CSFrace Development Team',
            'plugin_type': 'html_processor'
        }
    
    async def initialize(self) -> None:
        """Initialize the plugin."""
        # Define font-related CSS properties to remove
        self.font_properties = {
            'font-family', 'font-size', 'font-weight', 'font-style',
            'font-variant', 'font-stretch', 'line-height', 'font'
        }
        
        self.logger.info("Font Cleanup Plugin initialized")
    
    async def process_html(
        self,
        html_content: str,
        metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Process HTML to remove font-related elements and styles."""
        if not html_content or not html_content.strip():
            return html_content
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove font tags
        self._remove_font_tags(soup)
        
        # Clean font-related CSS from style attributes
        self._clean_font_styles(soup)
        
        # Remove empty elements that might be left after cleanup
        self._remove_empty_elements(soup)
        
        result = str(soup)
        
        self.logger.debug("Font cleanup completed", 
                         original_length=len(html_content),
                         cleaned_length=len(result))
        
        return result
    
    def _remove_font_tags(self, soup: BeautifulSoup) -> None:
        """Remove font tags while preserving their content."""
        font_tags = soup.find_all('font')
        removed_count = 0
        
        for font_tag in font_tags:
            # Move children to parent and remove the font tag
            if font_tag.parent:
                # Extract and insert children before the font tag
                for child in list(font_tag.children):
                    font_tag.insert_before(child)
                
                # Remove the now-empty font tag
                font_tag.decompose()
                removed_count += 1
        
        if removed_count > 0:
            self.logger.debug("Removed font tags", count=removed_count)
    
    def _clean_font_styles(self, soup: BeautifulSoup) -> None:
        """Remove font-related CSS properties from style attributes."""
        elements_with_style = soup.find_all(attrs={'style': True})
        cleaned_count = 0
        
        for element in elements_with_style:
            style_attr = element.get('style', '')
            if not style_attr:
                continue
            
            # Parse CSS properties
            css_props = []
            for prop in style_attr.split(';'):
                prop = prop.strip()
                if not prop:
                    continue
                
                # Check if this is a font-related property
                prop_name = prop.split(':')[0].strip().lower()
                if prop_name not in self.font_properties:
                    css_props.append(prop)
                else:
                    cleaned_count += 1
            
            # Update style attribute
            if css_props:
                element['style'] = '; '.join(css_props) + ';' if css_props else ''
            else:
                # Remove empty style attribute
                del element['style']
        
        if cleaned_count > 0:
            self.logger.debug("Cleaned font styles", properties_removed=cleaned_count)
    
    def _remove_empty_elements(self, soup: BeautifulSoup) -> None:
        """Remove elements that became empty after font cleanup."""
        # Elements that are OK to be empty
        void_elements = {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 
            'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'
        }
        
        removed_count = 0
        
        # Find elements that are now empty (no text content and no meaningful children)
        for element in soup.find_all():
            if element.name in void_elements:
                continue
            
            # Check if element is effectively empty
            if self._is_empty_element(element):
                element.decompose()
                removed_count += 1
        
        if removed_count > 0:
            self.logger.debug("Removed empty elements", count=removed_count)
    
    def _is_empty_element(self, element: Tag) -> bool:
        """Check if an element is effectively empty after font cleanup."""
        # Get text content, stripping whitespace
        text_content = element.get_text().strip()
        
        # If has text, not empty
        if text_content:
            return False
        
        # Check for meaningful children (images, inputs, etc.)
        meaningful_children = element.find_all([
            'img', 'input', 'button', 'select', 'textarea', 'video', 
            'audio', 'canvas', 'svg', 'iframe', 'embed', 'object'
        ])
        
        if meaningful_children:
            return False
        
        # Check if it has any attributes that might be important
        important_attrs = {'id', 'class', 'data-*'}
        for attr in element.attrs:
            if attr in important_attrs or attr.startswith('data-'):
                return False
        
        return True