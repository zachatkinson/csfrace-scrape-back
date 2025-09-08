#!/bin/bash

# Clean Up Redundant Linting Dependencies
# Remove tools that are replaced by modern Ruff + Black + MyPy stack

set -euo pipefail

echo "🧹 Cleaning up redundant linting dependencies..."
echo ""

echo "📋 Dependencies that can be removed (replaced by Ruff):"
echo "  ❌ flake8 → ✅ ruff (covers flake8 rules + more)"
echo "  ❌ isort → ✅ ruff (handles import sorting)"  
echo "  ❌ pylint → ✅ ruff (covers most pylint rules)"
echo "  ❌ bandit → ✅ ruff (includes security rules)"
echo ""

echo "🔍 Checking current dependencies..."

# Check what's currently installed
echo "Currently installed linting tools:"
if uv show --dev | grep -E "(ruff|black|mypy|flake8|isort|pylint|bandit)"; then
    echo ""
else
    echo "  (No linting tools found in dev dependencies)"
fi

echo ""
echo "🎯 Recommended actions:"

cat << 'EOF'
1. **Keep these (modern stack):**
   - ruff (comprehensive linting + import sorting)
   - black (code formatting)
   - mypy (type checking)

2. **Remove these (redundant):**
   uv remove --dev flake8
   uv remove --dev isort  
   uv remove --dev pylint
   uv remove --dev bandit  # Optional: keep if you need detailed security reports

3. **Update pyproject.toml:**
   - Remove [tool.isort] section (Ruff handles imports)
   - Remove [tool.flake8] section (Ruff replaces it)
   - Remove [tool.pylint] section (Ruff covers most rules)
   - Keep [tool.ruff], [tool.black], [tool.mypy]

4. **Update CI configuration:**
   - Disable VALIDATE_PYTHON_FLAKE8
   - Disable VALIDATE_PYTHON_ISORT  
   - Disable VALIDATE_PYTHON_PYLINT
   - Keep VALIDATE_PYTHON_RUFF, VALIDATE_PYTHON_BLACK, VALIDATE_PYTHON_MYPY
EOF

echo ""
read -p "🤔 Remove redundant dependencies now? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️ Removing redundant dependencies..."
    
    # Remove redundant tools
    uv remove --dev flake8 || echo "flake8 not found"
    uv remove --dev isort || echo "isort not found"  
    uv remove --dev pylint || echo "pylint not found"
    
    # Optional: remove bandit (keep if you want detailed security reports)
    read -p "Remove bandit too? (Ruff covers basic security, but bandit gives detailed reports) (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        uv remove --dev bandit || echo "bandit not found"
    fi
    
    echo ""
    echo "✅ Cleanup complete!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Update pyproject.toml (remove old tool sections)"
    echo "2. Update CI workflow (disable old validators)"  
    echo "3. Test with: ./scripts/dev-lint.sh"
    
else
    echo "👍 Skipped cleanup. You can run individual commands manually."
fi

echo ""
echo "🚀 After cleanup, your linting will be:"
echo "  • Faster (Ruff is 40x faster than alternatives)"
echo "  • Simpler (3 tools instead of 6+)"
echo "  • More reliable (no conflicting rules)"
echo "  • Industry standard (used by FastAPI, Pydantic, etc.)"