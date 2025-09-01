"""HTML processing utilities to eliminate DRY violations."""

from typing import Any

from bs4 import BeautifulSoup, Tag


def safe_copy_attributes(
    source_element: Tag, target_element: Tag, attribute_map: dict[str, str | tuple[str, str]]
) -> None:
    """Safely copy attributes from source to target element with defaults.

    Args:
        source_element: Source HTML element
        target_element: Target HTML element to copy attributes to
        attribute_map: Dict mapping source attr names to target attr names or (target_name, default_value)

    Example:
        safe_copy_attributes(img, new_img, {
            "src": "src",
            "alt": ("alt", ""),
            "title": ("title", "Image")
        })
    """
    for source_attr, target_config in attribute_map.items():
        if isinstance(target_config, tuple):
            target_attr, default_value = target_config
        else:
            target_attr, default_value = target_config, ""

        target_element[target_attr] = source_element.get(source_attr, default_value)


def find_meta_content(
    soup: BeautifulSoup, name: str | None = None, property: str | None = None
) -> str | None:
    """Find meta tag content by name or property attribute.

    Args:
        soup: BeautifulSoup object
        name: Meta name attribute (for name="description")
        property: Meta property attribute (for property="og:title")

    Returns:
        Meta content value or None
    """
    if name:
        meta_tag = soup.find("meta", attrs={"name": name})
    elif property:
        meta_tag = soup.find("meta", attrs={"property": property})
    else:
        return None

    if meta_tag and isinstance(meta_tag, Tag):
        content = meta_tag.get("content")
        return content if isinstance(content, str) else ""
    return None


def find_multiple_selectors(soup: BeautifulSoup, selectors: list[str]) -> Tag | None:
    """Try multiple CSS selectors until one matches.

    Args:
        soup: BeautifulSoup object
        selectors: List of CSS selectors to try in order

    Returns:
        First matching element or None
    """
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            return element
    return None


def extract_basic_element_data(element: Tag) -> dict[str, str]:
    """Extract common attributes from HTML element.

    Args:
        element: HTML element

    Returns:
        Dictionary with common attributes (src, alt, href, title, etc.)
    """

    def _get_str_attr(attr_name: str, default: str = "") -> str:
        """Safely get string attribute from element."""
        value = element.get(attr_name, default)
        return value if isinstance(value, str) else default

    def _get_class_str() -> str:
        """Safely get class attribute as joined string."""
        class_attr = element.get("class", [])
        if isinstance(class_attr, list):
            return " ".join(str(cls) for cls in class_attr)
        elif isinstance(class_attr, str):
            return class_attr
        return ""

    return {
        "src": _get_str_attr("src"),
        "alt": _get_str_attr("alt"),
        "href": _get_str_attr("href"),
        "title": _get_str_attr("title"),
        "class": _get_class_str(),
        "id": _get_str_attr("id"),
    }


def create_element_with_attributes(
    soup: BeautifulSoup, tag_name: str, attributes: dict[str, Any]
) -> Tag:
    """Create new HTML element with specified attributes.

    Args:
        soup: BeautifulSoup object (for creating new tags)
        tag_name: HTML tag name (div, img, a, etc.)
        attributes: Dictionary of attributes to set

    Returns:
        New HTML element with attributes set
    """
    element = soup.new_tag(tag_name)
    for attr, value in attributes.items():
        if value:  # Only set non-empty values
            element[attr] = value
    return element
