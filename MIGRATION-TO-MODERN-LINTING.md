# Migration to Modern Python Linting Stack

## 🎯 Goal: Streamline to Ruff + Black + MyPy

**Before:** 6+ linting tools with conflicts and slow feedback  
**After:** 3 modern tools, 40x faster, industry standard

---

## 📋 Migration Checklist

### ✅ **Step 1: Update Dependencies**

```bash
# Run the cleanup script
./scripts/cleanup-dependencies.sh

# Or manually:
uv remove --dev flake8 isort pylint bandit  # Remove redundant tools
uv add --dev "ruff>=0.6.0" "black>=24.0.0" "mypy>=1.11.0"  # Ensure modern versions
```

### ✅ **Step 2: Update pyproject.toml**

1. **Replace tool configurations:**
   - Copy content from `modern-pyproject-tools.toml`
   - Remove old `[tool.isort]`, `[tool.flake8]`, `[tool.pylint]` sections
   - Keep updated `[tool.ruff]`, `[tool.black]`, `[tool.mypy]`

2. **Key improvements:**
   - Ruff handles import sorting (replaces isort)
   - Comprehensive rule set (replaces flake8 + many pylint rules)
   - Security rules included (reduces need for bandit)

### ✅ **Step 3: Update CI/CD**

1. **Update GitHub Actions workflow:**
   ```yaml
   # In your .github/workflows/ file
   - name: Run Modern Super-Linter
     uses: github/super-linter@v7
     env:
       # Enable modern tools
       VALIDATE_PYTHON_RUFF: true
       VALIDATE_PYTHON_BLACK: true  
       VALIDATE_PYTHON_MYPY: true
       
       # Disable redundant tools
       VALIDATE_PYTHON_FLAKE8: false
       VALIDATE_PYTHON_ISORT: false
       VALIDATE_PYTHON_PYLINT: false
       VALIDATE_PYTHON_BANDIT: false  # Optional: keep if needed
   ```

2. **Reference:** See `.github-modern-superlinter.yml` for complete config

### ✅ **Step 4: Update Development Workflow**

1. **New daily linting command:**
   ```bash
   # Fast development linting
   ./scripts/dev-lint.sh
   
   # Quick auto-fix mode
   ./scripts/dev-lint.sh --quick
   ```

2. **Replace old commands:**
   ```bash
   # Old (multiple tools, slower)
   flake8 src/ tests/
   isort src/ tests/
   black src/ tests/
   pylint src/ tests/
   mypy src/
   
   # New (streamlined, faster)
   ruff check --fix src/ tests/  # Covers flake8 + isort + many pylint rules
   black src/ tests/             # Formatting
   mypy src/                     # Type checking
   ```

### ✅ **Step 5: Test Migration**

```bash
# Test the modern stack
./scripts/dev-lint.sh

# Should pass all checks with the new configuration
```

---

## 🚀 **Benefits After Migration**

### **Performance Improvements:**
- **40x faster** linting (Ruff vs traditional tools)
- **Instant feedback** during development
- **Parallel execution** of remaining tools

### **Consistency Improvements:**  
- **No conflicting rules** between tools
- **Single configuration** for most linting needs
- **Import sorting aligned** between local and CI

### **Maintenance Improvements:**
- **Fewer dependencies** to manage and update
- **Industry standard** configuration (FastAPI, Pydantic, etc. use this)
- **Better IDE integration** (most editors support Ruff natively)

---

## 🔧 **Troubleshooting**

### **Import Sorting Conflicts:**
**Problem:** Ruff and isort disagree on import order  
**Solution:** Remove isort, let Ruff handle imports with `--select I --fix`

### **Missing Rules:**
**Problem:** Some pylint rules not covered by Ruff  
**Solution:** Ruff covers 90%+ of important rules. Add specific rules if needed.

### **CI Still Fails:**
**Problem:** Super-Linter uses old tool combination  
**Solution:** Update workflow to disable redundant validators

---

## 📚 **Configuration Reference**

### **Ruff Rules Enabled:**
- `E`, `W`: pycodestyle (replaces most flake8 rules)
- `F`: pyflakes (error detection) 
- `I`: isort (import sorting)
- `B`: bugbear (common bugs)
- `S`: security (replaces bandit basics)
- `UP`: pyupgrade (modern Python patterns)
- `N`: naming conventions
- `ASYNC`: async/await best practices

### **What Each Tool Handles:**
- **Ruff**: Code quality, imports, security basics, style
- **Black**: Code formatting only
- **MyPy**: Type checking only

---

## 🎉 **Success Indicators**

✅ `./scripts/dev-lint.sh` passes all checks  
✅ CI pipeline uses only 3 Python validators  
✅ Local linting matches CI exactly  
✅ Faster feedback loop (< 2 seconds vs 10+ seconds)  
✅ No import sorting conflicts

---

**Questions or issues?** Check the generated scripts in `scripts/` directory for examples and troubleshooting.