#!/bin/bash
# Local Super Linter that matches CI configuration EXACTLY
# This ensures perfect alignment between local and CI validation

set -e

echo "🔍 Running Super Linter with EXACT CI configuration..."
echo "📍 Platform: $(uname -m)"
echo "🐳 Docker version: $(docker --version)"

# Get the absolute path to the backend directory
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "🎯 Backend directory: $BACKEND_DIR"

# Ensure we're in a git repository (directory or submodule)
if [ -d "$BACKEND_DIR/.git" ]; then
    echo "✅ Found standalone git repository"
elif [ -f "$BACKEND_DIR/.git" ]; then
    echo "✅ Found git submodule (backend repo used as submodule)"
    echo "📍 Git dir: $(cat "$BACKEND_DIR/.git")"
else
    echo "❌ Error: No git repository found"
    echo "🔧 Current directory: $BACKEND_DIR"
    exit 1
fi

# Check if we're on Apple Silicon and warn about platform
if [[ "$(uname -m)" == "arm64" ]]; then
    echo "⚠️  Running on Apple Silicon - using platform emulation"
    PLATFORM_ARG="--platform linux/amd64"
else
    PLATFORM_ARG=""
fi

# Run Super Linter with EXACT CI configuration
echo "🚀 Starting Super Linter with CI-identical configuration..."

docker run \
    $PLATFORM_ARG \
    --rm \
    --env RUN_LOCAL=true \
    --env DEFAULT_BRANCH=master \
    --env VALIDATE_PYTHON_RUFF=true \
    --env VALIDATE_PYTHON_BLACK=true \
    --env VALIDATE_PYTHON_ISORT=true \
    --env VALIDATE_PYTHON_MYPY=true \
    --env VALIDATE_PYTHON_FLAKE8=true \
    --env VALIDATE_PYTHON_BANDIT=true \
    --env VALIDATE_PYTHON_PYLINT=true \
    --env VALIDATE_ALL_CODEBASE=false \
    --env FILTER_REGEX_INCLUDE=".*\\.(py)$" \
    --env FIX_PYTHON_BLACK=true \
    --env FIX_PYTHON_ISORT=true \
    --env FIX_PYTHON_RUFF=true \
    --env SUPPRESS_POSSUM=true \
    --volume "$BACKEND_DIR":/tmp/lint \
    --workdir /tmp/lint \
    ghcr.io/super-linter/super-linter:v7.1.0

echo "✅ Super Linter completed with CI-identical configuration"