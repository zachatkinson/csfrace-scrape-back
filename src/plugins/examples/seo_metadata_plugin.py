"""Example SEO metadata extraction plugin."""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.plugins.base import MetadataExtractorPlugin


class SEOMetadataPlugin(MetadataExtractorPlugin):
    """Plugin to extract comprehensive SEO metadata."""

    @property
    def plugin_info(self) -> dict[str, Any]:
        return {
            "name": "SEO Metadata Extractor",
            "version": "1.0.0",
            "description": "Extracts comprehensive SEO metadata from HTML content",
            "author": "CSFrace Development Team",
            "plugin_type": "metadata_extractor",
        }

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.logger.info("SEO Metadata Plugin initialized")

    async def extract_metadata(
        self, html_content: str, url: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract SEO metadata from HTML content."""
        soup = BeautifulSoup(html_content, "html.parser")
        metadata = {}

        # Basic SEO elements
        metadata.update(self._extract_basic_seo(soup, url))

        # Open Graph metadata
        metadata.update(self._extract_open_graph(soup, url))

        # Twitter Card metadata
        metadata.update(self._extract_twitter_card(soup))

        # Schema.org structured data
        metadata.update(self._extract_schema_org(soup))

        # Additional SEO signals
        metadata.update(self._extract_seo_signals(soup))

        self.logger.debug("Extracted SEO metadata", metadata_keys=list(metadata.keys()))
        return metadata

    def _extract_basic_seo(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """Extract basic SEO elements."""
        metadata = {}

        # Title tag
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text().strip()
            metadata["title_length"] = len(metadata["title"])

        from ...utils.html import find_meta_content

        # Meta description
        description = find_meta_content(soup, name="description")
        if description:
            metadata["description"] = description.strip()
            metadata["description_length"] = len(metadata["description"])

        # Meta keywords
        keywords = find_meta_content(soup, name="keywords")
        if keywords:
            metadata["keywords"] = [k.strip() for k in keywords.split(",") if k.strip()]

        # Canonical URL
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        if canonical_tag:
            metadata["canonical_url"] = urljoin(url, canonical_tag.get("href", ""))

        # Meta robots
        robots_tag = soup.find("meta", attrs={"name": "robots"})
        if robots_tag:
            metadata["robots"] = robots_tag.get("content", "").strip()

        return metadata

    def _extract_open_graph(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """Extract Open Graph metadata."""
        og_metadata = {}

        og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
        for tag in og_tags:
            property_name = tag.get("property", "")
            content = tag.get("content", "").strip()

            if property_name and content:
                # Convert og:property to open_graph_property
                key = property_name.replace("og:", "open_graph_")
                og_metadata[key] = content

        return {"open_graph": og_metadata} if og_metadata else {}

    def _extract_twitter_card(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract Twitter Card metadata."""
        twitter_metadata = {}

        twitter_tags = soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")})
        for tag in twitter_tags:
            name = tag.get("name", "")
            content = tag.get("content", "").strip()

            if name and content:
                # Convert twitter:property to twitter_property
                key = name.replace("twitter:", "twitter_")
                twitter_metadata[key] = content

        return {"twitter": twitter_metadata} if twitter_metadata else {}

    def _extract_schema_org(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract Schema.org structured data."""
        import json

        schema_data = []

        # JSON-LD structured data
        json_ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in json_ld_scripts:
            try:
                data = json.loads(script.get_text())
                schema_data.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        # Microdata (basic extraction)
        microdata_items = soup.find_all(attrs={"itemscope": True})
        for item in microdata_items:
            item_type = item.get("itemtype", "")
            if item_type:
                microdata = {"@type": item_type.split("/")[-1]}

                # Extract itemprop values
                props = item.find_all(attrs={"itemprop": True})
                for prop in props:
                    prop_name = prop.get("itemprop")
                    prop_value = (
                        prop.get("content") or prop.get("datetime") or prop.get_text().strip()
                    )
                    if prop_name and prop_value:
                        microdata[prop_name] = prop_value

                if len(microdata) > 1:  # Has properties beyond @type
                    schema_data.append(microdata)

        return {"schema_org": schema_data} if schema_data else {}

    def _extract_seo_signals(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract additional SEO signals."""
        signals = {}

        # Heading structure
        headings = {}
        for i in range(1, 7):  # h1-h6
            h_tags = soup.find_all(f"h{i}")
            if h_tags:
                headings[f"h{i}"] = [h.get_text().strip() for h in h_tags]
                headings[f"h{i}_count"] = len(h_tags)

        if headings:
            signals["headings"] = headings

        # Image optimization
        images = soup.find_all("img")
        if images:
            img_without_alt = len([img for img in images if not img.get("alt")])
            signals["images"] = {
                "total_count": len(images),
                "missing_alt_count": img_without_alt,
                "alt_optimization_score": (len(images) - img_without_alt) / len(images) * 100,
            }

        # Internal/external links
        links = soup.find_all("a", href=True)
        if links:
            internal_links = 0
            external_links = 0

            for link in links:
                href = link.get("href", "")
                if href.startswith("http"):
                    parsed = urlparse(href)
                    # This is simplified - in reality you'd check against the current domain
                    if "csfrace.com" in parsed.netloc:
                        internal_links += 1
                    else:
                        external_links += 1
                elif href.startswith("/") or href.startswith("."):
                    internal_links += 1

            signals["links"] = {
                "total_count": len(links),
                "internal_count": internal_links,
                "external_count": external_links,
            }

        # Word count (approximate)
        text_content = soup.get_text()
        word_count = len(text_content.split())
        signals["content_analysis"] = {
            "word_count": word_count,
            "character_count": len(text_content),
            "reading_time_minutes": max(1, word_count // 200),  # ~200 WPM average
        }

        return signals
