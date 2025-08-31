#!/usr/bin/env python3
"""Update version in pyproject.toml for semantic release."""

import sys
import re
from pathlib import Path


def update_version(new_version: str) -> None:
    """Update version in pyproject.toml
    
    Args:
        new_version: The new version string (e.g., "1.2.3")
    """
    pyproject_path = Path("pyproject.toml")
    
    if not pyproject_path.exists():
        print(f"❌ pyproject.toml not found at {pyproject_path.absolute()}")
        sys.exit(1)
    
    content = pyproject_path.read_text(encoding='utf-8')
    
    # Update version line - more specific to avoid matching other version fields
    version_pattern = r'^version = "[^"]+"'
    new_version_line = f'version = "{new_version}"'
    
    if re.search(version_pattern, content, re.MULTILINE):
        updated_content = re.sub(version_pattern, new_version_line, content, flags=re.MULTILINE)
        pyproject_path.write_text(updated_content, encoding='utf-8')
        print(f"✅ Updated version to {new_version} in pyproject.toml")
    else:
        print(f"❌ Could not find version line in pyproject.toml")
        print("Expected pattern: version = \"x.y.z\"")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_version.py <version>")
        print("Example: python update_version.py 1.2.3")
        sys.exit(1)
    
    new_version = sys.argv[1]
    
    # Basic version validation
    if not re.match(r'^\d+\.\d+\.\d+', new_version):
        print(f"❌ Invalid version format: {new_version}")
        print("Expected format: x.y.z (semantic version)")
        sys.exit(1)
    
    update_version(new_version)