#!/bin/bash

# Exact CI Super-Linter Alignment Script
# Uses identical CLI flags and default settings as Super-Linter
# No custom configurations - uses tool defaults just like CI

set -euo pipefail

# Colors for output  
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔍 Exact CI Super-Linter Alignment${NC}"
echo -e "${BLUE}📍 Using identical CLI flags and default settings${NC}"
echo -e "${BLUE}🎯 Target: Python files (*.py)${NC}"
echo ""

# Initialize counters
total_checks=0
passed_checks=0
failed_checks=0

# Function to run check and track results
run_check() {
    local tool_name=$1
    local command=$2
    
    ((total_checks++))
    echo ""
    echo -e "${BLUE}[INFO]${NC} Running $tool_name..."
    echo "Command: $command"
    
    if eval "$command"; then
        echo -e "${GREEN}[PASS]${NC} $tool_name completed successfully"
        ((passed_checks++))
        return 0
    else
        echo -e "${RED}[FAIL]${NC} $tool_name found issues"
        ((failed_checks++))
        return 1
    fi
}

echo -e "${BLUE}=== Python Linting (Exact Super-Linter CLI) ===${NC}"

# EXACT Super-Linter command line invocations (using tool defaults)
# Source: https://github.com/super-linter/super-linter/blob/main/lib/functions/linterCommands.sh

# 1. Ruff - uses default configuration when no --config specified
run_check "Ruff Check" "uv run ruff check src/ tests/"

# 2. Black - uses default formatting rules when no --config specified  
run_check "Black Check" "uv run black --check --diff src/ tests/"

# 3. isort - uses default import sorting when no --sp specified
# NOTE: This is the main source of our import sorting conflicts
run_check "isort Check" "uv run isort --check-only --diff src/ tests/"

# 4. MyPy - uses default configuration when no --config-file specified
# Super-Linter adds --install-types --non-interactive
run_check "MyPy Check" "uv run mypy src/ --install-types --non-interactive"

# 5. Flake8 - uses default rules when no --config specified
run_check "Flake8 Check" "uv run flake8 src/ tests/"

# 6. Pylint - uses default rules when no --rcfile specified  
run_check "Pylint Check" "uv run pylint src/ tests/"

# 7. Bandit - default security checks (not part of main Super-Linter but often used)
if command -v bandit >/dev/null 2>&1; then
    run_check "Bandit Security Check" "uv run bandit -r src/"
fi

echo ""
echo -e "${BLUE}=== Super-Linter Alignment Summary ===${NC}"
echo -e "Total Checks: $total_checks"
echo -e "${GREEN}Passed: $passed_checks${NC}"
echo -e "${RED}Failed: $failed_checks${NC}"

if [[ $failed_checks -eq 0 ]]; then
    echo -e "${GREEN}🎉 Perfect alignment with Super-Linter defaults!${NC}"
    echo -e "${GREEN}✅ All checks passed using identical CLI flags${NC}"
    echo ""
    echo -e "${BLUE}💡 Key Success Factors:${NC}"
    echo -e "   • Using tool default configurations (no custom configs)"
    echo -e "   • Identical CLI flags as Super-Linter"
    echo -e "   • Same tool invocation patterns"
    exit 0
else
    echo -e "${RED}❌ $failed_checks checks failed${NC}"
    echo ""
    echo -e "${YELLOW}💡 Common Issues & Solutions:${NC}"
    echo -e "   • Import sorting conflicts: Use 'ruff check --fix --select I' instead of isort"
    echo -e "   • Black formatting: Run 'black src/ tests/' to fix"
    echo -e "   • MyPy errors: Check type annotations and imports"
    echo -e "   • Flake8 issues: Check code style and complexity"
    echo -e "   • Pylint warnings: Address code quality issues"
    echo ""
    echo -e "${BLUE}🔧 Quick Fix Commands:${NC}"
    echo -e "   uv run black src/ tests/                    # Fix formatting"
    echo -e "   uv run ruff check --fix src/ tests/         # Fix auto-fixable issues"  
    echo -e "   uv run isort src/ tests/                    # Fix import sorting"
    exit 1
fi