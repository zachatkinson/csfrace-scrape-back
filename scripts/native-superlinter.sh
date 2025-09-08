#!/bin/bash
# Native Super Linter - Exact CI tool versions and configuration
# Matches github/super-linter@v7 configuration exactly

set -e

echo "🔍 Running Native Super Linter with EXACT CI configuration..."
echo "📍 Backend Repository Linting"
echo "🎯 Target: Python files (*.py)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Error counter
ERRORS=0

# Function to run linter and track errors
run_linter() {
    local name="$1"
    local cmd="$2"
    
    echo -e "\n${BLUE}[INFO]${NC} Running $name..."
    echo "Command: $cmd"
    
    if eval "$cmd"; then
        echo -e "${GREEN}[PASS]${NC} $name completed successfully"
    else
        echo -e "${RED}[FAIL]${NC} $name found issues"
        ((ERRORS++))
    fi
}

# Set SECRET_KEY for tools that need it
export SECRET_KEY=test

echo -e "\n${BLUE}=== Python Linting (CI Configuration) ===${NC}"

# 1. VALIDATE_PYTHON_RUFF=true
run_linter "Ruff Linting" "uv run ruff check src/ tests/ --output-format=github"

# 2. VALIDATE_PYTHON_BLACK=true  
# Note: CI has FIX_PYTHON_BLACK=true, so we check format
run_linter "Black Formatting Check" "uv run black --check --diff src/ tests/"

# 3. VALIDATE_PYTHON_ISORT=true
# Note: CI has FIX_PYTHON_ISORT=true, so we check
run_linter "Import Sorting Check" "uv run isort --check-only --diff src/ tests/"

# 4. VALIDATE_PYTHON_MYPY=true  
run_linter "MyPy Type Checking" "uv run mypy src/ --show-error-codes"

# 5. VALIDATE_PYTHON_FLAKE8=true
run_linter "Flake8 Style Check" "uv run flake8 src/ tests/ --format=default"

# 6. VALIDATE_PYTHON_BANDIT=true
run_linter "Bandit Security Check" "uv run bandit -r src/ -f screen"

# 7. VALIDATE_PYTHON_PYLINT=true
run_linter "Pylint Code Quality" "uv run pylint src/ --output-format=colorized"

echo -e "\n${BLUE}=== Summary ===${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All linters passed! Code quality matches CI standards.${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $ERRORS linter(s) with issues. Please fix before pushing.${NC}"
    echo -e "${YELLOW}💡 Tip: Use 'uv run ruff check --fix' and 'uv run black .' to auto-fix many issues${NC}"
    exit 1
fi