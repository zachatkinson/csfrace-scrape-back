"""HTML processing utilities to eliminate DRY violations."""

from typing import Any, Optional, Union

from bs4 import BeautifulSoup, Tag


def safe_copy_attributes(
    source_element: Tag, target_element: Tag, attribute_map: dict[str, Union[str, tuple[str, str]]]
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
    soup: BeautifulSoup, name: Optional[str] = None, property: Optional[str] = None
) -> Optional[str]:
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

    return meta_tag.get("content", "") if meta_tag else None


def find_multiple_selectors(soup: BeautifulSoup, selectors: list[str]) -> Optional[Tag]:
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
    return {
        "src": element.get("src", ""),
        "alt": element.get("alt", ""),
        "href": element.get("href", ""),
        "title": element.get("title", ""),
        "class": " ".join(element.get("class", [])),
        "id": element.get("id", ""),
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
