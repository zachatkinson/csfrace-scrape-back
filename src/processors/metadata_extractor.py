"""Metadata extraction from WordPress pages."""

from urllib.parse import urlparse

import structlog
from bs4 import BeautifulSoup

from ..core.exceptions import ProcessingError

logger = structlog.get_logger(__name__)


class MetadataExtractor:
    """Extracts metadata from WordPress pages."""

    def __init__(self, base_url: str):
        """Initialize metadata extractor.

        Args:
            base_url: Base URL for context
        """
        self.base_url = base_url

    async def extract(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract metadata from BeautifulSoup object.

        Args:
            soup: Parsed HTML document

        Returns:
            Dictionary of metadata fields
        """
        try:
            metadata = {}

            # Page title
            title_tag = soup.find("title")
            if title_tag and title_tag.get_text().strip():
                metadata["title"] = title_tag.get_text().strip()
            else:
                metadata["title"] = "No Title Found"

            # URL and slug
            metadata["url"] = self.base_url
            parsed_url = urlparse(self.base_url)
            metadata["url_slug"] = parsed_url.path.strip("/").split("/")[-1] or "homepage"

            # Meta description
            meta_desc = await self._extract_meta_description(soup)
            metadata["meta_description"] = meta_desc

            # Published date
            published_date = await self._extract_published_date(soup)
            metadata["published_date"] = published_date

            logger.debug("Extracted metadata", metadata=metadata)
            return metadata

        except Exception as e:
            raise ProcessingError(f"Failed to extract metadata: {e}") from e

    async def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description from various sources."""
        # Try standard meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()

        # Try Open Graph description
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            return og_desc["content"].strip()

        # Try Twitter description
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        if twitter_desc and twitter_desc.get("content"):
            return twitter_desc["content"].strip()

        return "No description found"

    async def _extract_published_date(self, soup: BeautifulSoup) -> str:
        """Extract published date from various possible locations."""
        date_selectors = [
            # Structured data
            ('meta[property="article:published_time"]', "content"),
            ('meta[name="article:published_time"]', "content"),
            # Time elements
            ("time[datetime]", "datetime"),
            ("time[pubdate]", "datetime"),
            # Common WordPress classes
            (".entry-date", "text"),
            (".published", "text"),
            (".post-date", "text"),
            # Schema.org microdata
            ('[itemprop="datePublished"]', "datetime"),
            ('[itemprop="datePublished"]', "content"),
        ]

        for selector, attr_type in date_selectors:
            elem = soup.select_one(selector)
            if elem:
                if attr_type == "content":
                    date_value = elem.get("content", "").strip()
                elif attr_type == "datetime":
                    date_value = elem.get("datetime", elem.get_text()).strip()
                else:  # text
                    date_value = elem.get_text().strip()

                if date_value:
                    return date_value

        return "Date not found"
