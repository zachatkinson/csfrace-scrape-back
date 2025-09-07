#!/usr/bin/env python3
"""Script to fix remaining docstring issues systematically."""

import re
import subprocess
from pathlib import Path

# Mapping of common non-imperative phrases to imperative versions
IMPERATIVE_FIXES = {
    "Simple liveness check": "Perform simple liveness check",
    "Decorator factory for": "Create decorator factory for",
    "Wrapper for functions": "Wrap functions",
    "Decorator to handle": "Handle",
    "Custom JSON deserializer": "Deserialize JSON with custom types",
    "Custom JSON serializer": "Serialize JSON with custom types",
    "Convenience function to": "Load",
    "Main conversion method": "Convert content",
    "String representation of": "Return string representation of",
}

# Templates for missing docstrings
INIT_DOCSTRING_TEMPLATE = '''"""Initialize {class_name}.

        Args:
            {args}

        """'''

MAGIC_METHOD_TEMPLATES = {
    "__str__": '''"""Return string representation."""''',
    "__repr__": '''"""Return string representation for debugging."""''',
    "__aenter__": '''"""Enter async context."""''',
    "__aexit__": '''"""Exit async context."""''',
}


def get_ruff_issues() -> list[str]:
    """Get all remaining docstring issues from ruff."""
    try:
        import os

        env = os.environ.copy()
        env["SECRET_KEY"] = (  # nosec S105 - test key
            "b18939e378f6b5e6c6f2ac8a7b3ee49eb3f5d6a909902abbdb4358a4093e2900"
        )

        result = subprocess.run(
            [
                "/Users/zach/Web Projects/csfrace-scrape/backend/.venv/bin/ruff",
                "check",
                "src/",
                "tests/",
                "--select=D",
                "--output-format=concise",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        return (
            result.stdout.strip().split("\n")
            if result.stdout.strip()
            else []
        )
    except Exception as e:
        print(f"Error running ruff: {e}")
        return []


def fix_imperative_mood(file_path: str, line_num: int, issue: str):
    """Fix D401 imperative mood issues."""
    try:
        path = Path(file_path)
        content = path.read_text()
        lines = content.split("\n")

        if line_num <= len(lines):
            line = lines[line_num - 1]

            # Extract the docstring content from the issue
            match = re.search(r'"([^"]+)"', issue)
            if match:
                original_text = match.group(1)

                # Try to find a fix in our mapping
                for pattern, replacement in IMPERATIVE_FIXES.items():
                    if pattern in original_text:
                        new_text = original_text.replace(pattern, replacement)
                        lines[line_num - 1] = line.replace(original_text, new_text)
                        path.write_text("\n".join(lines))
                        print(f"Fixed imperative mood in {file_path}:{line_num}")
                        return True

                # Generic fixes for common patterns
                if original_text.startswith("Decorator factory"):
                    new_text = "Create " + original_text.lower()
                elif original_text.startswith("Wrapper for"):
                    # Remove "Wrapper for"
                    new_text = "Wrap " + original_text[11:]
                elif original_text.startswith("Custom "):
                    new_text = "Handle " + original_text.lower()
                elif "representation of" in original_text:
                    new_text = "Return " + original_text.lower()
                else:
                    # Try to add a verb at the beginning
                    verbs = [
                        "get", "set", "create", "update", "delete",
                        "handle", "process", "perform", "return",
                        "load", "save", "check", "validate",
                        "convert", "transform",
                    ]
                    if not any(
                        original_text.lower().startswith(verb)
                        for verb in verbs
                    ):
                        new_text = "Handle " + original_text.lower()
                    else:
                        return False

                lines[line_num - 1] = line.replace(original_text, new_text)
                path.write_text("\n".join(lines))
                print(f"Fixed imperative mood in {file_path}:{line_num}")
                return True

    except Exception as e:
        print(f"Error fixing imperative mood in {file_path}: {e}")
    return False


def add_missing_docstring(file_path: str, line_num: int, _issue: str):
    """Add missing docstrings for __init__ and magic methods."""
    try:
        path = Path(file_path)
        content = path.read_text()
        lines = content.split("\n")

        if line_num <= len(lines):
            # Determine the type of missing docstring
            method_line = lines[line_num - 1].strip()

            if "def __init__(" in method_line:
                # Extract class name from context
                class_name = "instance"
                for i in range(line_num - 2, max(0, line_num - 20), -1):
                    if lines[i].strip().startswith("class "):
                        class_match = re.match(r"class\s+(\w+)", lines[i].strip())
                        if class_match:
                            class_name = class_match.group(1)
                            break

                # Extract argument names
                args_match = re.search(r"__init__\([^)]+\)", method_line)
                if args_match:
                    # Remove "__init__(" and ")"
                    args_str = args_match.group(0)[9:-1]
                    args = [
                        arg.strip().split(":")[0].split("=")[0].strip()
                        for arg in args_str.split(",")
                        if arg.strip() and arg.strip() != "self"
                    ]

                    if args:
                        args_doc = "\n            ".join([
                            f"{arg}: {arg.replace('_', ' ').title()} parameter"
                            for arg in args
                        ])
                    else:
                        args_doc = "No parameters"

                    docstring = (
                        f'        """Initialize {class_name}.\n\n        '
                        f'Args:\n            {args_doc}\n\n        """'
                    )
                else:
                    docstring = f'        """Initialize {class_name}."""'

                # Insert docstring after the method definition line
                lines.insert(line_num, docstring)
                path.write_text("\n".join(lines))
                print(f"Added __init__ docstring in {file_path}:{line_num}")
                return True

            elif any(
                method in method_line
                for method in MAGIC_METHOD_TEMPLATES
            ):
                # Find which magic method it is
                for method, template in MAGIC_METHOD_TEMPLATES.items():
                    if method in method_line:
                        lines.insert(line_num, f"        {template}")
                        path.write_text("\n".join(lines))
                        print(f"Added {method} docstring in {file_path}:{line_num}")
                        return True

    except Exception as e:
        print(f"Error adding docstring in {file_path}: {e}")
    return False


def remove_overload_docstring(file_path: str, line_num: int):
    """Remove docstrings from @overload methods."""
    try:
        path = Path(file_path)
        content = path.read_text()
        lines = content.split("\n")

        # Find the docstring and remove it
        if line_num <= len(lines):
            # Look for the docstring (usually a few lines after the method definition)
            for i in range(line_num, min(len(lines), line_num + 10)):
                line = lines[i].strip()
                if line.startswith('"""') or line.startswith("'''"):
                    # Found start of docstring
                    if (
                        line.count('"""') == 2 or line.count("'''") == 2
                    ):
                        # Single line docstring
                        del lines[i]
                    else:
                        # Multi-line docstring
                        start = i
                        end = start
                        quote_type = '"""' if '"""' in line else "'''"
                        for j in range(i + 1, len(lines)):
                            if quote_type in lines[j]:
                                end = j
                                break
                        # Remove the docstring lines
                        del lines[start:end + 1]

                    path.write_text("\n".join(lines))
                    print(f"Removed @overload docstring in {file_path}:{line_num}")
                    return True

    except Exception as e:
        print(f"Error removing overload docstring in {file_path}: {e}")
    return False


def process_issues():
    """Process all docstring issues systematically."""
    issues = get_ruff_issues()
    print(f"Found {len(issues)} docstring issues to fix")

    fixed_count = 0

    for issue in issues:
        if not issue.strip() or "warning:" in issue:
            continue

        # Parse issue format: file:line:col: code message
        parts = issue.split(":", 4)
        if len(parts) < 4:
            continue

        file_path = parts[0]
        line_num = int(parts[1])
        error_code = parts[3].strip().split()[0]

        if error_code == "D401":
            if fix_imperative_mood(file_path, line_num, issue):
                fixed_count += 1
        elif error_code in ["D107", "D105"]:
            if add_missing_docstring(file_path, line_num, issue):
                fixed_count += 1
        elif error_code == "D418" and remove_overload_docstring(file_path, line_num):
            fixed_count += 1

    print(f"Fixed {fixed_count} docstring issues")
    return fixed_count


if __name__ == "__main__":
    process_issues()
