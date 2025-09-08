#!/bin/bash

# Perfect Super-Linter Alignment Script
# Uses EXACT same versions as GitHub's Super-Linter v7.1.0
# Source: https://github.com/super-linter/super-linter/tree/main/dependencies/python

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# EXACT versions from Super-Linter v7.1.0
declare -A EXACT_VERSIONS=(
    ["ruff"]="0.12.11"
    ["black"]="25.1.0"
    ["isort"]="6.0.1"
    ["mypy"]="1.17.1"
    ["flake8"]="7.3.0"
    ["pylint"]="3.3.8"
    # Note: Bandit version determined from CI logs
    ["bandit"]="1.8.0"
)

echo -e "${BLUE}🔍 Perfect Super-Linter Alignment (v7.1.0)${NC}"
echo -e "${BLUE}📍 Backend Repository Linting${NC}"
echo -e "${BLUE}🎯 Target: Python files (*.py)${NC}"
echo ""

# Function to check tool version
check_tool_version() {
    local tool=$1
    local expected_version=${EXACT_VERSIONS[$tool]}
    local current_version
    
    case $tool in
        "ruff")
            current_version=$(uv run ruff --version 2>/dev/null | cut -d' ' -f2 || echo "NOT_INSTALLED")
            ;;
        "black")
            current_version=$(uv run black --version 2>/dev/null | grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+" || echo "NOT_INSTALLED")
            ;;
        "isort")
            current_version=$(uv run isort --version 2>/dev/null | grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+" || echo "NOT_INSTALLED")
            ;;
        "mypy")
            current_version=$(uv run mypy --version 2>/dev/null | cut -d' ' -f2 || echo "NOT_INSTALLED")
            ;;
        "flake8")
            current_version=$(uv run flake8 --version 2>/dev/null | cut -d' ' -f1 || echo "NOT_INSTALLED")
            ;;
        "pylint")
            current_version=$(uv run pylint --version 2>/dev/null | head -n1 | grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+" || echo "NOT_INSTALLED")
            ;;
        "bandit")
            current_version=$(uv run bandit --version 2>/dev/null | grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+" || echo "NOT_INSTALLED")
            ;;
    esac
    
    if [[ "$current_version" == "$expected_version" ]]; then
        echo -e "${GREEN}✓${NC} $tool: $current_version (matches Super-Linter)"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $tool: $current_version (expected $expected_version)"
        return 1
    fi
}

# Function to install exact version if needed
install_exact_version() {
    local tool=$1
    local version=${EXACT_VERSIONS[$tool]}
    
    echo -e "${BLUE}[INFO]${NC} Installing $tool==$version to match Super-Linter..."
    uv add --dev "$tool==$version"
}

# Version alignment check
echo -e "${BLUE}=== Version Alignment Check ===${NC}"
version_mismatches=0

for tool in "${!EXACT_VERSIONS[@]}"; do
    if ! check_tool_version "$tool"; then
        ((version_mismatches++))
    fi
done

if [[ $version_mismatches -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}Found $version_mismatches version mismatches with Super-Linter.${NC}"
    read -p "Install exact matching versions? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for tool in "${!EXACT_VERSIONS[@]}"; do
            if ! check_tool_version "$tool" >/dev/null 2>&1; then
                install_exact_version "$tool"
            fi
        done
        echo -e "${GREEN}All tools updated to match Super-Linter exactly!${NC}"
    else
        echo -e "${YELLOW}Proceeding with current versions (may not match CI exactly)${NC}"
    fi
fi

echo ""
echo -e "${BLUE}=== Python Linting (Super-Linter v7.1.0 Configuration) ===${NC}"

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

# EXACT Super-Linter Commands (from Super-Linter source code)

# 1. Ruff Linting (with GitHub output format like Super-Linter)
run_check "Ruff Linting" "uv run ruff check src/ tests/ --output-format=github"

# 2. Black Formatting Check (exact Super-Linter behavior)
run_check "Black Formatting Check" "uv run black --check --diff src/ tests/"

# 3. Import Sorting Check (Super-Linter uses isort)
run_check "Import Sorting Check" "uv run isort --check-only --diff src/ tests/"

# 4. MyPy Type Checking (Super-Linter configuration)
run_check "MyPy Type Checking" "uv run mypy src/ --show-error-codes"

# 5. Flake8 Code Analysis (Super-Linter setup)
run_check "Flake8 Code Analysis" "uv run flake8 src/ tests/ --max-line-length=100 --max-complexity=10"

# 6. Bandit Security Linting (Super-Linter format)
run_check "Bandit Security Linting" "uv run bandit -r src/ -f json -o bandit-report.json || uv run bandit -r src/"

# 7. Pylint Code Analysis (Super-Linter standards)
run_check "Pylint Code Analysis" "uv run pylint src/ tests/ --output-format=text"

# Summary
echo ""
echo -e "${BLUE}=== Super-Linter Alignment Summary ===${NC}"
echo -e "Total Checks: $total_checks"
echo -e "${GREEN}Passed: $passed_checks${NC}"
echo -e "${RED}Failed: $failed_checks${NC}"

if [[ $failed_checks -eq 0 ]]; then
    echo -e "${GREEN}🎉 Perfect alignment with Super-Linter v7.1.0!${NC}"
    echo -e "${GREEN}✅ All checks passed - ready for CI${NC}"
    exit 0
else
    echo -e "${RED}❌ $failed_checks checks failed${NC}"
    echo -e "${YELLOW}💡 Fix the issues above to achieve perfect CI alignment${NC}"
    exit 1
fi