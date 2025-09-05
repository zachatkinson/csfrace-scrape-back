#!/bin/bash
# Test PyLint locally with the same configuration as Super-Linter v7.1.0
# This ensures CI failures can be caught before pushing

cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
    files="src/auth/dependencies.py src/auth/router.py src/api/utils.py"
else
    files="$*"
fi

echo "Running PyLint with Super-Linter v7.1.0 configuration..."
echo "Testing files: $files"

PYTHONPATH="$(pwd)" uv run python -m pylint --rcfile .python-lint $files