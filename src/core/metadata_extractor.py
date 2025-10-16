"""Metadata extraction service for conversion job results.

This module handles extracting metadata from generated conversion files following
Single Responsibility Principle:
- Parse metadata.txt file
- Count words in HTML content
- Count images in output directory
- Count links in HTML content
- Return structured ContentResultsData
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from src.core.logging_hierarchy import get_api_logger

logger = get_api_logger()


@dataclass
class ContentResultsData:
    """Structured data extracted from conversion output files."""

    # File paths
    html_file_path: str | None = None
    metadata_file_path: str | None = None
    images_directory: str | None = None

    # Metadata from metadata.txt
    title: str | None = None
    meta_description: str | None = None
    published_date: datetime | None = None
    author: str | None = None

    # Statistics from HTML and files
    word_count: int | None = None
    image_count: int | None = None
    link_count: int | None = None

    # HTML content
    original_html: str | None = None
    converted_html: str | None = None
    shopify_html: str | None = None


class MetadataExtractorService:
    """Service for extracting metadata from conversion job output files.

    Follows SOLID principles:
    - Single Responsibility: Only extracts metadata from files
    - Open/Closed: Extendable through subclassing, closed for modification
    - Dependency Inversion: Depends on Path abstraction, not concrete filesystem
    """

    def __init__(self, output_dir: Path):
        """Initialize metadata extractor.

        Args:
            output_dir: Path to conversion output directory
        """
        self.output_dir = output_dir
        self.logger = logger

    def extract_all(self) -> ContentResultsData:
        """Extract all metadata from conversion output directory.

        Returns:
            ContentResultsData with all extracted metadata

        Raises:
            FileNotFoundError: If output directory doesn't exist
        """
        if not self.output_dir.exists():
            error_msg = f"Output directory does not exist: {self.output_dir}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        self.logger.info(
            "Extracting metadata from output directory", output_dir=str(self.output_dir)
        )

        # Extract from each data source
        metadata_txt_data = self._parse_metadata_file()
        html_data = self._extract_html_data()
        image_count = self._count_images()

        # Combine all extracted data with explicit type conversions
        title_value = metadata_txt_data.get("title")
        meta_desc_value = metadata_txt_data.get("meta_description")
        published_date_value = metadata_txt_data.get("published_date")
        author_value = metadata_txt_data.get("author")

        # Extract statistics from html_data with proper type conversions
        word_count_value = html_data.get("word_count")
        link_count_value = html_data.get("link_count")
        original_html_value = html_data.get("original_html")
        converted_html_value = html_data.get("converted_html")
        shopify_html_value = html_data.get("shopify_html")

        results = ContentResultsData(
            # File paths
            html_file_path=str(self.output_dir / "converted_content.html")
            if (self.output_dir / "converted_content.html").exists()
            else None,
            metadata_file_path=str(self.output_dir / "metadata.txt")
            if (self.output_dir / "metadata.txt").exists()
            else None,
            images_directory=str(self.output_dir / "images")
            if (self.output_dir / "images").exists()
            else None,
            # Metadata from metadata.txt (ensure correct types)
            title=str(title_value) if isinstance(title_value, str) else None,
            meta_description=str(meta_desc_value) if isinstance(meta_desc_value, str) else None,
            published_date=published_date_value
            if isinstance(published_date_value, datetime)
            else None,
            author=str(author_value) if isinstance(author_value, str) else None,
            # Statistics (ensure int types)
            word_count=int(word_count_value) if isinstance(word_count_value, int) else None,
            image_count=image_count,
            link_count=int(link_count_value) if isinstance(link_count_value, int) else None,
            # HTML content (ensure string types)
            original_html=str(original_html_value)
            if isinstance(original_html_value, str)
            else None,
            converted_html=str(converted_html_value)
            if isinstance(converted_html_value, str)
            else None,
            shopify_html=str(shopify_html_value) if isinstance(shopify_html_value, str) else None,
        )

        self.logger.info(
            "Metadata extraction completed",
            title=results.title,
            word_count=results.word_count,
            image_count=results.image_count,
            link_count=results.link_count,
        )

        return results

    def _parse_metadata_file(self) -> dict[str, str | datetime | None]:
        """Parse metadata.txt file for extracted metadata.

        Returns:
            Dictionary with title, meta_description, published_date, author
        """
        metadata_path = self.output_dir / "metadata.txt"
        if not metadata_path.exists():
            self.logger.warning("metadata.txt not found", path=str(metadata_path))
            return {}

        self.logger.debug("Parsing metadata.txt", path=str(metadata_path))

        try:
            with open(metadata_path, encoding="utf-8") as f:
                content = f.read()

            # Extract title
            title_match = re.search(r"^Title:\s*(.+)$", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else None

            # Extract meta description
            meta_desc_match = re.search(r"^Meta Description:\s*(.+)$", content, re.MULTILINE)
            meta_description = meta_desc_match.group(1).strip() if meta_desc_match else None

            # Extract published date (ISO 8601 format)
            date_match = re.search(r"^Published Date:\s*(.+)$", content, re.MULTILINE)
            published_date = None
            if date_match:
                try:
                    date_str = date_match.group(1).strip()
                    # Parse ISO 8601 datetime with timezone
                    published_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError) as e:
                    self.logger.warning(
                        "Failed to parse published date", date_str=date_str, error=str(e)
                    )

            # Extract author (if present)
            author_match = re.search(r"^Author:\s*(.+)$", content, re.MULTILINE)
            author = author_match.group(1).strip() if author_match else None

            metadata = {
                "title": title,
                "meta_description": meta_description,
                "published_date": published_date,
                "author": author,
            }

            self.logger.debug(
                "Metadata parsed successfully",
                title=title,
                has_description=meta_description is not None,
                has_date=published_date is not None,
            )

            return metadata

        except Exception as e:
            self.logger.error("Failed to parse metadata.txt", error=str(e), exc_info=True)
            return {}

    def _extract_html_data(self) -> dict[str, str | int]:
        """Extract data from HTML files (word count, link count, content).

        Returns:
            Dictionary with word_count, link_count, original_html, converted_html, shopify_html
        """
        html_data: dict[str, str | int] = {}

        # Read converted_content.html (primary HTML file)
        converted_path = self.output_dir / "converted_content.html"
        if converted_path.exists():
            self.logger.debug("Reading converted_content.html", path=str(converted_path))
            try:
                with open(converted_path, encoding="utf-8") as f:
                    converted_html = f.read()

                html_data["converted_html"] = converted_html

                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(converted_html, "html.parser")

                # Count words (text content only, excluding HTML tags)
                text_content = soup.get_text(separator=" ", strip=True)
                word_count = len(text_content.split())
                html_data["word_count"] = word_count

                # Count links (<a> tags)
                link_count = len(soup.find_all("a"))
                html_data["link_count"] = link_count

                self.logger.debug(
                    "HTML data extracted", word_count=word_count, link_count=link_count
                )

            except Exception as e:
                self.logger.error(
                    "Failed to read converted_content.html", error=str(e), exc_info=True
                )

        # Read shopify_ready_content.html (if exists)
        shopify_path = self.output_dir / "shopify_ready_content.html"
        if shopify_path.exists():
            self.logger.debug("Reading shopify_ready_content.html", path=str(shopify_path))
            try:
                with open(shopify_path, encoding="utf-8") as f:
                    shopify_html = f.read()
                html_data["shopify_html"] = shopify_html
            except Exception as e:
                self.logger.error(
                    "Failed to read shopify_ready_content.html", error=str(e), exc_info=True
                )

        # Read original_content.html (if exists)
        original_path = self.output_dir / "original_content.html"
        if original_path.exists():
            self.logger.debug("Reading original_content.html", path=str(original_path))
            try:
                with open(original_path, encoding="utf-8") as f:
                    original_html = f.read()
                html_data["original_html"] = original_html
            except Exception as e:
                self.logger.error(
                    "Failed to read original_content.html", error=str(e), exc_info=True
                )

        return html_data

    def _count_images(self) -> int:
        """Count images in images/ directory.

        Returns:
            Number of image files (jpg, jpeg, png, gif, webp, svg)
        """
        images_dir = self.output_dir / "images"
        if not images_dir.exists():
            self.logger.debug("Images directory does not exist", path=str(images_dir))
            return 0

        # Count image files by extension
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
        image_files = [
            f for f in images_dir.rglob("*") if f.is_file() and f.suffix.lower() in image_extensions
        ]
        image_count = len(image_files)

        self.logger.debug("Images counted", image_count=image_count, images_dir=str(images_dir))

        return image_count
