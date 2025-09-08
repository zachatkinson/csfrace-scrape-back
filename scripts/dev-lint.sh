#!/bin/bash

# Daily Development Linting
# Modern Python stack: Ruff + Black + MyPy
# Fast, effective, industry standard

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Modern Python Development Linting${NC}"
echo -e "${BLUE}⚡ Ruff + Black + MyPy (2025 Standard)${NC}"
echo ""

# Quick mode flag
QUICK_MODE=${1:-""}
if [[ "$QUICK_MODE" == "--quick" ]] || [[ "$QUICK_MODE" == "-q" ]]; then
    echo -e "${YELLOW}⚡ Quick mode: Auto-fixing only${NC}"
    echo ""
    
    echo -e "${BLUE}🔧 Auto-fixing issues...${NC}"
    uv run ruff check --fix src/ tests/
    uv run black src/ tests/
    
    echo -e "${GREEN}✅ Auto-fixes applied!${NC}"
    echo -e "${YELLOW}💡 Run without --quick for full type checking${NC}"
    exit 0
fi

# Full development linting
failed_checks=0

echo -e "${BLUE}=== Code Quality & Style ===${NC}"

# 1. Ruff - Comprehensive linting (replaces flake8 + isort + many pylint rules)
echo -e "${YELLOW}🦀 Ruff: Code quality & import sorting...${NC}"
if uv run ruff check src/ tests/; then
    echo -e "${GREEN}✅ Ruff: All good!${NC}"
else
    echo -e "${RED}❌ Ruff: Found issues${NC}"
    ((failed_checks++))
fi

# 2. Black - Code formatting
echo ""
echo -e "${YELLOW}⚫ Black: Code formatting...${NC}"
if uv run black --check --diff src/ tests/; then
    echo -e "${GREEN}✅ Black: Formatting looks good!${NC}"
else
    echo -e "${RED}❌ Black: Formatting issues found${NC}"
    ((failed_checks++))
fi

# 3. MyPy - Type checking
echo ""
echo -e "${YELLOW}🔍 MyPy: Type checking...${NC}"
if uv run mypy src/; then
    echo -e "${GREEN}✅ MyPy: Types are solid!${NC}"
else
    echo -e "${RED}❌ MyPy: Type issues found${NC}"
    ((failed_checks++))
fi

echo ""
echo -e "${BLUE}=== Development Linting Summary ===${NC}"

if [[ $failed_checks -eq 0 ]]; then
    echo -e "${GREEN}🎉 All checks passed! Code is ready.${NC}"
    echo ""
    echo -e "${BLUE}✨ Your code meets modern Python standards:${NC}"
    echo -e "   • Ruff: Code quality ✓"
    echo -e "   • Black: Consistent formatting ✓"  
    echo -e "   • MyPy: Strong typing ✓"
else
    echo -e "${RED}❌ $failed_checks tools found issues${NC}"
    echo ""
    echo -e "${YELLOW}🔧 Quick Fix Commands:${NC}"
    echo -e "   ${BLUE}# Auto-fix most issues:${NC}"
    echo -e "   uv run ruff check --fix src/ tests/"
    echo -e "   uv run black src/ tests/"
    echo ""
    echo -e "   ${BLUE}# Or use quick mode:${NC}"
    echo -e "   ./scripts/dev-lint.sh --quick"
    echo ""
    echo -e "   ${BLUE}# Then manually fix remaining MyPy issues${NC}"
    exit 1
fi