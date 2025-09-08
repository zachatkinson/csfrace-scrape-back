#!/bin/bash

# Modern Python Linting Best Practices (2025)
# Minimal, fast, effective tool stack
# Industry standard for professional Python development

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Modern Python Linting Stack (2025 Best Practices)${NC}"
echo -e "${BLUE}📍 Fast, minimal, effective toolset${NC}"
echo -e "${BLUE}🎯 Target: Python files (*.py)${NC}"
echo ""

total_checks=0
passed_checks=0
failed_checks=0

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

echo -e "${BLUE}=== Modern Python Linting Stack ===${NC}"

# 1. Ruff - The New Standard (replaces flake8 + isort + many pylint rules)
echo -e "${YELLOW}🦀 Ruff: Ultra-fast Python linter (40x faster than alternatives)${NC}"
run_check "Ruff Code Quality Check" "uv run ruff check src/ tests/ --output-format=github"

# 2. Black - Code Formatting (industry standard)
echo -e "${YELLOW}⚫ Black: Uncompromising code formatter${NC}"
run_check "Black Code Formatting" "uv run black --check --diff src/ tests/"

# 3. MyPy - Type Checking (static analysis)
echo -e "${YELLOW}🔍 MyPy: Static type checking${NC}"
run_check "MyPy Type Checking" "uv run mypy src/ --show-error-codes"

# Optional: Security scanning (if needed)
if [[ "${INCLUDE_SECURITY:-false}" == "true" ]]; then
    echo -e "${YELLOW}🛡️ Bandit: Security linting${NC}"
    run_check "Bandit Security Scan" "uv run bandit -r src/ -ll"
fi

echo ""
echo -e "${BLUE}=== Modern Linting Summary ===${NC}"
echo -e "Total Checks: $total_checks"
echo -e "${GREEN}Passed: $passed_checks${NC}"
echo -e "${RED}Failed: $failed_checks${NC}"

if [[ $failed_checks -eq 0 ]]; then
    echo -e "${GREEN}🎉 All modern linting checks passed!${NC}"
    echo -e "${GREEN}✅ Code meets 2025 Python standards${NC}"
    echo ""
    echo -e "${BLUE}🏆 Benefits of Modern Stack:${NC}"
    echo -e "   • 40x faster than traditional tools"
    echo -e "   • No conflicting rules between tools"  
    echo -e "   • Industry standard configuration"
    echo -e "   • Maintained by Rust ecosystem (fast & reliable)"
    exit 0
else
    echo -e "${RED}❌ $failed_checks checks failed${NC}"
    echo ""
    echo -e "${YELLOW}🔧 Quick Fix Commands:${NC}"
    echo -e "   uv run black src/ tests/                 # Fix all formatting"
    echo -e "   uv run ruff check --fix src/ tests/      # Auto-fix violations"
    echo -e "   # Then manually address remaining MyPy type issues"
    exit 1
fi