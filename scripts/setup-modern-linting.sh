#!/bin/bash

# Setup Modern Python Linting (Ruff + Black + MyPy)
# Industry standard 2025 configuration

set -euo pipefail

echo "🚀 Setting up modern Python linting stack..."

# 1. Install the modern trio (remove redundant tools)
echo "📦 Installing Ruff + Black + MyPy..."
uv add --dev "ruff>=0.6.0"  # Latest stable
uv add --dev "black>=24.0.0"  # Code formatter  
uv add --dev "mypy>=1.11.0"  # Type checker

# Optional: Remove redundant tools to avoid conflicts
echo "🧹 Optional: Remove redundant tools..."
echo "You can remove these from pyproject.toml if desired:"
echo "  - flake8 (replaced by ruff)"
echo "  - isort (ruff handles import sorting)"
echo "  - pylint (ruff covers most pylint rules)"

echo ""
echo "✅ Modern linting tools installed!"
echo ""
echo "🔧 Recommended usage:"
echo "  # Daily development (fast feedback)"
echo "  ./scripts/modern-linter.sh"
echo ""
echo "  # Quick fixes"
echo "  uv run ruff check --fix src/ tests/"
echo "  uv run black src/ tests/"
echo ""
echo "  # Pre-commit (super fast)"
echo "  uv run ruff check --fix src/ && uv run black src/"

# Create optimized pyproject.toml section
cat > modern-pyproject-section.toml << 'EOF'

# Modern Python Linting Configuration (2025)
# Ruff + Black + MyPy = Fast, comprehensive, industry standard

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
# Enable comprehensive rule set (replaces flake8, isort, many pylint rules)
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort (import sorting)
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "S",   # bandit security
    "N",   # pep8-naming
    "ASYNC", # flake8-async
]

ignore = [
    "E501",   # line too long (handled by black)
    "S105",   # hardcoded password (often false positives for URLs/tokens)
    "S106",   # hardcoded password (often false positives for configs)
    "B904",   # raise from err (optional)
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]  # Allow assert in tests
"src/database/examples/*" = ["F821"]  # Example code may have undefined names

[tool.ruff.format]
# Use ruff formatter (alternative to black, but keep black for now)
quote-style = "double"
indent-style = "space"

[tool.black]
line-length = 100
target-version = ["py313"]
include = '\.pyi?$'
extend-exclude = '''
/(
    \.git
    | \.venv
    | __pycache__
    | build
    | dist
)/
'''

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

# Paths
files = ["src", "tests"]
exclude = [
    "build/",
    "dist/",
    "src/database/examples/",  # Example code
]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # More lenient for tests

[[tool.mypy.overrides]]
module = [
    "aioresponses.*",
    "pytest_postgresql.*",
    "testcontainers.*",
    "memory_profiler.*",
]
ignore_missing_imports = true

EOF

echo ""
echo "📝 Generated optimized configuration in: modern-pyproject-section.toml"
echo "💡 You can copy this to your pyproject.toml to replace existing tool configs"