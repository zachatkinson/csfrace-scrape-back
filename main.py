#!/usr/bin/env python3
"""
WordPress to Shopify Content Converter

Scrapes WordPress content and converts it to Shopify-friendly format
according to specified formatting rules.

Author: CSFrace Development Team
License: MIT
"""

import argparse
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from requests.exceptions import RequestException, Timeout, HTTPError


# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application.
    
    Args:
        verbose: Enable verbose logging if True
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler],
        format=log_format
    )


# Get logger for this module
logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Custom exception for conversion errors."""
    pass


class WordPressToShopifyConverter:
    """Converts WordPress content to Shopify-compatible HTML format."""
    
    # Class constants
    DEFAULT_OUTPUT_DIR = "converted_content"
    DEFAULT_TIMEOUT = 10
    RATE_LIMIT_DELAY = 0.5
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    
    # Shopify-compatible CSS classes to preserve
    PRESERVE_CLASSES = frozenset([
        'center', 'media-grid', 'media-grid-2', 'media-grid-4', 'media-grid-5',
        'media-grid-text-box', 'testimonial-quote', 'group', 'quote-container',
        'button', 'button--full-width', 'button--primary', 'press-release-button'
    ])
    
    def __init__(self, base_url: str, output_dir: str = DEFAULT_OUTPUT_DIR):
        """Initialize the converter.
        
        Args:
            base_url: The WordPress URL to convert
            output_dir: Directory to save converted content
            
        Raises:
            ValueError: If the URL is invalid
        """
        self.base_url = self._validate_url(base_url)
        self.output_dir = Path(output_dir)
        self.session = self._create_session()
        
        # Create output directories
        self._setup_directories()
        
        logger.info(f"Initialized converter for URL: {self.base_url}")
        logger.info(f"Output directory: {self.output_dir}")
    
    def _validate_url(self, url: str) -> str:
        """Validate and normalize the URL.
        
        Args:
            url: URL to validate
            
        Returns:
            Normalized URL string
            
        Raises:
            ValueError: If URL is invalid
        """
        if not url:
            raise ValueError("URL cannot be empty")
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        # Parse URL to validate structure
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")
        
        return url
    
    def _create_session(self) -> requests.Session:
        """Create a configured requests session.
        
        Returns:
            Configured requests.Session object
        """
        session = requests.Session()
        session.headers.update({
            'User-Agent': self.DEFAULT_USER_AGENT
        })
        return session
    
    def _setup_directories(self) -> None:
        """Create necessary output directories."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.images_dir = self.output_dir / "images"
            self.images_dir.mkdir(exist_ok=True)
            logger.debug(f"Created output directories at {self.output_dir}")
        except OSError as e:
            raise ConversionError(f"Failed to create output directories: {e}")
    
    def fetch_page(self) -> Optional[str]:
        """Fetch the webpage content.
        
        Returns:
            HTML content as string, or None if fetch fails
        """
        try:
            logger.info(f"Fetching content from {self.base_url}")
            response = self.session.get(self.base_url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            logger.info(f"Successfully fetched {len(response.content)} bytes")
            return response.text
            
        except Timeout:
            logger.error(f"Timeout while fetching {self.base_url}")
            return None
        except HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code} for {self.base_url}")
            return None
        except RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract page metadata.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Dictionary containing metadata fields
        """
        metadata: Dict[str, str] = {}
        
        # Page Title
        title_tag = soup.find('title')
        metadata['title'] = title_tag.get_text().strip() if title_tag else "No Title Found"
        
        # URL and URL Slug
        metadata['url'] = self.base_url
        parsed_url = urlparse(self.base_url)
        metadata['url_slug'] = parsed_url.path.strip('/').split('/')[-1] or "homepage"
        
        # Meta Description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        metadata['meta_description'] = (
            meta_desc.get('content', 'No description found') if meta_desc 
            else "No description found"
        )
        
        # Published Date
        metadata['published_date'] = self._extract_published_date(soup)
        
        logger.debug(f"Extracted metadata: {metadata}")
        return metadata
    
    def _extract_published_date(self, soup: BeautifulSoup) -> str:
        """Extract published date from various possible locations.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Published date string or default message
        """
        date_selectors = [
            ('meta[property="article:published_time"]', 'content'),
            ('meta[name="article:published_time"]', 'content'),
            ('time[datetime]', 'datetime'),
            ('.entry-date', 'text'),
            ('.published', 'text')
        ]
        
        for selector, attr_type in date_selectors:
            elem = soup.select_one(selector)
            if elem:
                if attr_type == 'content':
                    return elem.get('content', '')
                elif attr_type == 'datetime':
                    return elem.get('datetime', elem.get_text())
                else:
                    return elem.get_text()
        
        return "Date not found"
    
    def convert_font_formatting(self, content: Tag) -> Tag:
        """Convert font formatting tags.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        # Replace <b> with <strong>
        for b_tag in content.find_all('b'):
            b_tag.name = 'strong'
        
        # Replace <i> with <em>
        for i_tag in content.find_all('i'):
            i_tag.name = 'em'
        
        return content
    
    def convert_text_alignment(self, content: Tag) -> Tag:
        """Convert text alignment classes.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        for elem in content.find_all(class_="has-text-align-center"):
            elem['class'] = ['center']
        
        return content
    
    def convert_kadence_layouts(self, content: Tag) -> Tag:
        """Convert Kadence row layouts to media-grid.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        # Get the root soup for creating new tags
        soup_root = self._get_root_soup(content)
        
        for row_layout in content.find_all('div', class_='wp-block-kadence-rowlayout'):
            col_container = row_layout.find('div', class_=re.compile(r'kt-has-\d+-columns'))
            
            if col_container:
                new_class = self._determine_grid_class(col_container)
                new_div = soup_root.new_tag('div', **{'class': new_class})
                
                # Convert columns to media-grid-text-box
                for column in col_container.find_all('div', class_='wp-block-kadence-column'):
                    text_box = self._create_text_box_from_column(soup_root, column)
                    new_div.append(text_box)
                
                row_layout.replace_with(new_div)
        
        return content
    
    def _get_root_soup(self, element: Tag) -> BeautifulSoup:
        """Get the root BeautifulSoup object.
        
        Args:
            element: Any BeautifulSoup element
            
        Returns:
            Root BeautifulSoup object
        """
        root = element
        while root.parent:
            root = root.parent
        return root
    
    def _determine_grid_class(self, container: Tag) -> str:
        """Determine the appropriate media-grid class.
        
        Args:
            container: Container element with column count class
            
        Returns:
            Appropriate media-grid class name
        """
        class_name = str(container.get('class', ''))
        
        if 'kt-has-2-columns' in class_name:
            return 'media-grid-2'
        elif 'kt-has-3-columns' in class_name:
            return 'media-grid'
        elif 'kt-has-4-columns' in class_name:
            return 'media-grid-4'
        elif 'kt-has-5-columns' in class_name:
            return 'media-grid-5'
        else:
            return 'media-grid'
    
    def _create_text_box_from_column(self, soup_root: BeautifulSoup, column: Tag) -> Tag:
        """Create a media-grid-text-box from a Kadence column.
        
        Args:
            soup_root: Root soup for creating new tags
            column: Column element to convert
            
        Returns:
            New text box element
        """
        text_box = soup_root.new_tag('div', **{'class': 'media-grid-text-box'})
        
        # Find content container
        inner_col = column.find('div', class_='kt-inside-inner-col')
        source = inner_col if inner_col else column
        
        # Move all content
        for child in list(source.children):
            if hasattr(child, 'name') or (hasattr(child, 'strip') and child.strip()):
                text_box.append(child.extract())
        
        return text_box
    
    def convert_image_galleries(self, content: Tag) -> Tag:
        """Convert Kadence advanced galleries to media-grid.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        soup_root = self._get_root_soup(content)
        
        for gallery in content.find_all('div', class_='wp-block-kadence-advancedgallery'):
            media_grid = soup_root.new_tag('div', **{'class': 'media-grid'})
            
            for img in gallery.find_all('img'):
                img_div = self._create_image_container(soup_root, img)
                media_grid.append(img_div)
            
            gallery.replace_with(media_grid)
        
        return content
    
    def _create_image_container(self, soup_root: BeautifulSoup, img: Tag) -> Tag:
        """Create an image container with optional caption.
        
        Args:
            soup_root: Root soup for creating new tags
            img: Image element
            
        Returns:
            Container div with image and optional caption
        """
        img_div = soup_root.new_tag('div')
        
        # Create new img tag
        new_img = soup_root.new_tag('img')
        new_img['src'] = img.get('src', '')
        new_img['alt'] = img.get('alt', '')
        img_div.append(new_img)
        
        # Check for captions
        figure = img.find_parent('figure')
        if figure:
            figcaption = figure.find('figcaption')
            if figcaption:
                caption_p = soup_root.new_tag('p')
                caption_em = soup_root.new_tag('em')
                caption_em.string = figcaption.get_text()
                caption_p.append(caption_em)
                img_div.append(caption_p)
        
        return img_div
    
    def convert_simple_images(self, content: Tag) -> Tag:
        """Convert wp-block-image to simple img tags.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        soup_root = self._get_root_soup(content)
        
        for img_block in content.find_all('div', class_='wp-block-image'):
            img_tag = img_block.find('img')
            if img_tag:
                new_img = soup_root.new_tag('img')
                new_img['src'] = img_tag.get('src', '')
                new_img['alt'] = img_tag.get('alt', '')
                img_block.replace_with(new_img)
        
        return content
    
    def convert_buttons(self, content: Tag) -> Tag:
        """Convert Kadence advanced buttons to Shopify format.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        soup_root = self._get_root_soup(content)
        
        for btn_block in content.find_all('div', class_='wp-block-kadence-advancedbtn'):
            btn_link = btn_block.find('a', class_='button')
            if btn_link:
                new_btn = self._create_shopify_button(soup_root, btn_link)
                btn_block.replace_with(new_btn)
        
        return content
    
    def _create_shopify_button(self, soup_root: BeautifulSoup, original_btn: Tag) -> Tag:
        """Create a Shopify-formatted button.
        
        Args:
            soup_root: Root soup for creating new tags
            original_btn: Original button element
            
        Returns:
            New button element with Shopify classes
        """
        new_btn = soup_root.new_tag('a')
        new_btn['href'] = original_btn.get('href', '')
        new_btn['class'] = ['button', 'button--full-width', 'button--primary', 'press-release-button']
        
        # Check if URL is external
        href = original_btn.get('href', '')
        if href and 'csfrace.com' not in href and href.startswith(('http://', 'https://')):
            new_btn['target'] = '_blank'
            new_btn['rel'] = 'noreferrer noopener'
        
        new_btn.string = original_btn.get_text().strip()
        return new_btn
    
    def convert_blockquotes(self, content: Tag) -> Tag:
        """Convert pullquote blocks to testimonial format.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        soup_root = self._get_root_soup(content)
        
        for pullquote in content.find_all('figure', class_='wp-block-pullquote'):
            blockquote = pullquote.find('blockquote')
            if blockquote:
                testimonial_div = self._create_testimonial(soup_root, blockquote)
                pullquote.replace_with(testimonial_div)
        
        return content
    
    def _create_testimonial(self, soup_root: BeautifulSoup, blockquote: Tag) -> Tag:
        """Create a testimonial-style quote structure.
        
        Args:
            soup_root: Root soup for creating new tags
            blockquote: Original blockquote element
            
        Returns:
            Testimonial div structure
        """
        testimonial_div = soup_root.new_tag('div', **{'class': 'testimonial-quote group'})
        quote_container = soup_root.new_tag('div', **{'class': 'quote-container'})
        
        # Create new blockquote
        new_blockquote = soup_root.new_tag('blockquote')
        quote_p = blockquote.find('p')
        if quote_p:
            new_p = soup_root.new_tag('p')
            new_p.string = quote_p.get_text()
            new_blockquote.append(new_p)
        
        quote_container.append(new_blockquote)
        
        # Handle citation
        cite = blockquote.find('cite')
        if cite:
            new_cite = soup_root.new_tag('cite')
            cite_span = soup_root.new_tag('span')
            cite_span.string = cite.get_text()
            new_cite.append(cite_span)
            quote_container.append(new_cite)
        
        testimonial_div.append(quote_container)
        return testimonial_div
    
    def convert_youtube_embeds(self, content: Tag) -> Tag:
        """Convert YouTube embeds to responsive format.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        soup_root = self._get_root_soup(content)
        
        for youtube_embed in content.find_all('figure', class_='wp-block-embed-youtube'):
            iframe = youtube_embed.find('iframe')
            if iframe:
                replacement = self._create_youtube_embed(soup_root, iframe, youtube_embed)
                youtube_embed.replace_with(replacement)
        
        return content
    
    def _create_youtube_embed(self, soup_root: BeautifulSoup, iframe: Tag, 
                             original_embed: Tag) -> Tag:
        """Create a responsive YouTube embed.
        
        Args:
            soup_root: Root soup for creating new tags
            iframe: Original iframe element
            original_embed: Original embed container
            
        Returns:
            New embed structure
        """
        container_div = soup_root.new_tag('div')
        container_div['style'] = 'display: flex; justify-content: center;'
        
        new_iframe = soup_root.new_tag('iframe')
        new_iframe['style'] = 'aspect-ratio: 16/9; width: 100% !important;'
        new_iframe['src'] = iframe.get('src', '')
        new_iframe['title'] = iframe.get('title', 'YouTube Video')
        
        container_div.append(new_iframe)
        
        # Check for captions
        figcaption = original_embed.find('figcaption')
        if figcaption:
            wrapper = soup_root.new_tag('div')
            wrapper.append(container_div)
            
            caption_p = soup_root.new_tag('p')
            caption_strong = soup_root.new_tag('strong')
            caption_strong.string = figcaption.get_text()
            caption_p.append(caption_strong)
            wrapper.append(caption_p)
            
            return wrapper
        
        return container_div
    
    def convert_instagram_embeds(self, content: Tag) -> Tag:
        """Convert Instagram embeds.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        soup_root = self._get_root_soup(content)
        
        for iframe in content.find_all('iframe', class_='instagram-media'):
            wrapper_div = soup_root.new_tag('div')
            iframe_copy = soup_root.new_tag('iframe')
            
            # Copy all attributes
            for attr, value in iframe.attrs.items():
                iframe_copy[attr] = value
            
            wrapper_div.append(iframe_copy)
            iframe.replace_with(wrapper_div)
        
        return content
    
    def remove_wordpress_classes_and_styling(self, content: Tag) -> Tag:
        """Remove WordPress classes and inline styling.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        for elem in content.find_all():
            # Remove WordPress-specific classes
            if elem.get('class'):
                new_classes = [cls for cls in elem.get('class') 
                             if cls in self.PRESERVE_CLASSES]
                
                if new_classes:
                    elem['class'] = new_classes
                else:
                    del elem['class']
            
            # Remove inline styles except for specific cases
            if elem.get('style'):
                style = elem.get('style')
                # Keep specific styles for YouTube embeds
                if not ('aspect-ratio: 16/9' in style or 
                       'display: flex; justify-content: center;' in style):
                    del elem['style']
            
            # Remove WordPress-specific attributes
            wp_attrs = ['data-align', 'data-type', 'data-responsive-size', 'id']
            for attr in wp_attrs:
                if elem.get(attr):
                    del elem[attr]
        
        return content
    
    def fix_external_links(self, content: Tag) -> Tag:
        """Add target and rel attributes to external links.
        
        Args:
            content: BeautifulSoup Tag to process
            
        Returns:
            Modified Tag object
        """
        for link in content.find_all('a', href=True):
            href = link.get('href')
            if href and 'csfrace.com' not in href and href.startswith(('http://', 'https://')):
                if not link.get('target'):
                    link['target'] = '_blank'
                    link['rel'] = 'noreferrer noopener'
        
        return content
    
    def download_image(self, img_url: str) -> bool:
        """Download a single image.
        
        Args:
            img_url: URL of the image to download
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(img_url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            filename = self._generate_image_filename(img_url, response)
            image_path = self.images_dir / filename
            
            with open(image_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading {img_url}: {e}")
            return False
    
    def _generate_image_filename(self, url: str, response: requests.Response) -> str:
        """Generate a filename for the downloaded image.
        
        Args:
            url: Image URL
            response: Response object containing the image
            
        Returns:
            Generated filename string
        """
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name
        
        # If no filename or extension, generate one
        if not filename or '.' not in filename:
            content_type = response.headers.get('content-type', '')
            ext = self._get_extension_from_content_type(content_type)
            filename = f"image_{hash(url) % 10000}{ext}"
        
        return filename
    
    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type.
        
        Args:
            content_type: HTTP content-type header value
            
        Returns:
            File extension including dot
        """
        type_map = {
            'jpeg': '.jpg',
            'jpg': '.jpg',
            'png': '.png',
            'gif': '.gif',
            'webp': '.webp'
        }
        
        for key, ext in type_map.items():
            if key in content_type.lower():
                return ext
        
        return '.jpg'  # Default
    
    def process_content(self, html_content: str) -> Tuple[Dict[str, str], str]:
        """Process and convert the HTML content according to rules.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Tuple of (metadata dict, converted HTML string)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract metadata
        metadata = self.extract_metadata(soup)
        
        # Find the entry-content div
        entry_content = soup.find('div', class_='entry-content')
        if not entry_content:
            logger.warning("No entry-content div found. Processing entire body.")
            entry_content = soup.find('body') or soup
        
        logger.info("Applying conversion rules...")
        
        # Apply all conversion rules
        entry_content = self.convert_font_formatting(entry_content)
        entry_content = self.convert_text_alignment(entry_content)
        entry_content = self.convert_kadence_layouts(entry_content)
        entry_content = self.convert_image_galleries(entry_content)
        entry_content = self.convert_simple_images(entry_content)
        entry_content = self.convert_buttons(entry_content)
        entry_content = self.convert_blockquotes(entry_content)
        entry_content = self.convert_youtube_embeds(entry_content)
        entry_content = self.convert_instagram_embeds(entry_content)
        entry_content = self.fix_external_links(entry_content)
        
        # Remove scripts
        for script in entry_content.find_all('script'):
            script.decompose()
        
        # Final cleanup
        entry_content = self.remove_wordpress_classes_and_styling(entry_content)
        
        return metadata, str(entry_content)
    
    def save_converted_content(self, metadata: Dict[str, str], converted_html: str) -> None:
        """Save the converted content and metadata.
        
        Args:
            metadata: Metadata dictionary
            converted_html: Converted HTML string
            
        Raises:
            ConversionError: If saving fails
        """
        try:
            # Save metadata
            metadata_file = self.output_dir / "metadata.txt"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                f.write("EXTRACTED METADATA\n")
                f.write("=" * 50 + "\n\n")
                for key, value in metadata.items():
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            
            # Save converted HTML
            html_file = self.output_dir / "converted_content.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(converted_html)
            
            # Save combined output
            combined_file = self.output_dir / "shopify_ready_content.html"
            with open(combined_file, 'w', encoding='utf-8') as f:
                f.write("<!-- METADATA -->\n")
                for key, value in metadata.items():
                    f.write(f"<!-- {key.replace('_', ' ').title()}: {value} -->\n")
                f.write("<!-- END METADATA -->\n\n")
                f.write(converted_html)
            
            logger.info(f"Metadata saved to: {metadata_file}")
            logger.info(f"Converted HTML saved to: {html_file}")
            logger.info(f"Combined content saved to: {combined_file}")
            
        except OSError as e:
            raise ConversionError(f"Failed to save files: {e}")
    
    def get_image_urls(self, html_content: str) -> List[str]:
        """Extract all image URLs from the HTML.
        
        Args:
            html_content: HTML content string
            
        Returns:
            List of unique image URLs
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tags = soup.find_all('img')
        
        image_urls = []
        for img in img_tags:
            src = img.get('src')
            if src:
                full_url = urljoin(self.base_url, src)
                image_urls.append(full_url)
        
        return list(set(image_urls))
    
    def download_all_images(self, image_urls: List[str]) -> None:
        """Download all images with rate limiting.
        
        Args:
            image_urls: List of image URLs to download
        """
        if not image_urls:
            logger.info("No images found to download")
            return
        
        logger.info(f"Found {len(image_urls)} images to download...")
        
        successful = 0
        for i, img_url in enumerate(image_urls, 1):
            logger.info(f"Downloading {i}/{len(image_urls)}: {img_url}")
            
            if self.download_image(img_url):
                successful += 1
            
            # Rate limiting
            time.sleep(self.RATE_LIMIT_DELAY)
        
        logger.info(f"Successfully downloaded {successful}/{len(image_urls)} images")
    
    def convert(self) -> None:
        """Main conversion method.
        
        Raises:
            ConversionError: If conversion fails
        """
        logger.info(f"Starting conversion for: {self.base_url}")
        
        # Fetch the webpage
        html_content = self.fetch_page()
        if not html_content:
            raise ConversionError("Failed to fetch webpage content")
        
        # Process and convert content
        metadata, converted_html = self.process_content(html_content)
        
        # Save converted content
        self.save_converted_content(metadata, converted_html)
        
        # Extract and download images
        image_urls = self.get_image_urls(converted_html)
        self.download_all_images(image_urls)
        
        logger.info(f"Conversion completed! Check the '{self.output_dir}' directory for results.")
        print("\nFiles created:")
        print(f"  - metadata.txt (extracted metadata)")
        print(f"  - converted_content.html (converted HTML only)")
        print(f"  - shopify_ready_content.html (metadata + converted HTML)")
        print(f"  - images/ (downloaded images)")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Convert WordPress content to Shopify-friendly format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://csfrace.com/blog/sample-post
  %(prog)s https://csfrace.com/blog/sample-post -o my-output
  %(prog)s csfrace.com/blog/sample-post --verbose
        """
    )
    
    parser.add_argument(
        "url",
        help="WordPress URL to convert"
    )
    parser.add_argument(
        "-o", "--output",
        default=WordPressToShopifyConverter.DEFAULT_OUTPUT_DIR,
        help="Output directory (default: %(default)s)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Create converter and run
        converter = WordPressToShopifyConverter(args.url, args.output)
        converter.convert()
        
    except ConversionError as e:
        logger.error(f"Conversion failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Conversion interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if running interactively without arguments
    if len(sys.argv) == 1:
        print("WordPress to Shopify Content Converter")
        print("-" * 40)
        url = input("Enter WordPress URL to convert: ").strip()
        
        if url:
            # Setup basic logging for interactive mode
            setup_logging(verbose=False)
            
            try:
                converter = WordPressToShopifyConverter(url)
                converter.convert()
            except ConversionError as e:
                logger.error(f"Conversion failed: {e}")
                sys.exit(1)
            except Exception as e:
                logger.exception(f"Unexpected error: {e}")
                sys.exit(1)
        else:
            print("No URL provided. Exiting.")
            sys.exit(0)
    else:
        main()