"""Cross-platform path utilities."""

import os
from pathlib import Path, PurePath
from typing import Union

PathLike = Union[str, Path, PurePath]


def normalize_path_separators(path: PathLike) -> str:
    """Normalize path separators to forward slashes for consistent behavior.

    Args:
        path: Path to normalize

    Returns:
        Path string with forward slash separators
    """
    return str(Path(path)).replace(os.sep, "/")


def get_path_parts(path: PathLike) -> list[str]:
    """Get path parts in a cross-platform way.

    Args:
        path: Path to split into parts

    Returns:
        List of path parts
    """
    return list(Path(path).parts)


def join_path_parts(*parts: str) -> str:
    """Join path parts using the correct separator for the current platform.

    Args:
        *parts: Path parts to join

    Returns:
        Joined path string
    """
    return str(Path(*parts))


def get_directory_name(path: PathLike) -> str:
    """Get the final directory or file name from a path.

    Args:
        path: Path to extract name from

    Returns:
        Directory or file name
    """
    return Path(path).name


def split_directory_path(path: PathLike) -> tuple[str, str]:
    """Split a path into directory and name components.

    Args:
        path: Path to split

    Returns:
        Tuple of (parent_directory, name)
    """
    path_obj = Path(path)
    return str(path_obj.parent), path_obj.name


def ensure_path_exists(path: PathLike) -> Path:
    """Ensure a directory path exists, creating it if necessary.

    Args:
        path: Directory path to create

    Returns:
        Path object for the created directory
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def is_absolute_path(path: PathLike) -> bool:
    """Check if a path is absolute.

    Args:
        path: Path to check

    Returns:
        True if path is absolute
    """
    return Path(path).is_absolute()


def make_relative_to(path: PathLike, base: PathLike) -> str:
    """Make a path relative to a base path.

    Args:
        path: Path to make relative
        base: Base path

    Returns:
        Relative path string
    """
    return str(Path(path).relative_to(base))


def resolve_path(path: PathLike) -> str:
    """Resolve a path to an absolute path.

    Args:
        path: Path to resolve

    Returns:
        Absolute path string
    """
    return str(Path(path).resolve())


def path_exists(path: PathLike) -> bool:
    """Check if a path exists.

    Args:
        path: Path to check

    Returns:
        True if path exists
    """
    return Path(path).exists()


def is_directory(path: PathLike) -> bool:
    """Check if a path is a directory.

    Args:
        path: Path to check

    Returns:
        True if path is a directory
    """
    return Path(path).is_dir()


def is_file(path: PathLike) -> bool:
    """Check if a path is a file.

    Args:
        path: Path to check

    Returns:
        True if path is a file
    """
    return Path(path).is_file()


def get_file_extension(path: PathLike) -> str:
    """Get the file extension from a path.

    Args:
        path: Path to get extension from

    Returns:
        File extension including the dot (e.g., '.txt')
    """
    return Path(path).suffix


def get_filename_without_extension(path: PathLike) -> str:
    """Get the filename without extension.

    Args:
        path: Path to get filename from

    Returns:
        Filename without extension
    """
    return Path(path).stem


def safe_filename(filename: str, replacement: str = "_") -> str:
    """Create a safe filename by replacing unsafe characters.

    Args:
        filename: Original filename
        replacement: Character to use for replacement

    Returns:
        Safe filename
    """
    unsafe_chars = '<>:"/\\|?*'
    safe_name = filename
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, replacement)

    # Remove multiple consecutive replacement characters
    while replacement + replacement in safe_name:
        safe_name = safe_name.replace(replacement + replacement, replacement)

    # Remove leading/trailing replacement characters
    safe_name = safe_name.strip(replacement)

    return safe_name


def truncate_path_component(component: str, max_length: int = 50) -> str:
    """Truncate a path component to a maximum length.

    Args:
        component: Path component to truncate
        max_length: Maximum length allowed

    Returns:
        Truncated component
    """
    if len(component) <= max_length:
        return component

    # Keep some characters from the beginning and end
    if max_length >= 10:
        start_chars = max_length // 2 - 2
        end_chars = max_length - start_chars - 4  # Account for ellipsis
        return f"{component[:start_chars]}...{component[-end_chars:]}"
    else:
        return component[:max_length]
