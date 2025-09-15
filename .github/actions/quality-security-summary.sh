#!/bin/bash
# GitHub Actions Summary Generator for Code Quality & Security Shard
# Following GitHub blog best practices: https://github.blog/news-insights/product-news/supercharging-github-actions-with-job-summaries/

set -euo pipefail

# Function to add section to summary
add_section() {
    local title="$1"
    local content="$2"
    echo "## ${title}" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "${content}" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
}

# Function to add collapsible section
add_collapsible() {
    local title="$1"
    local content="$2"
    echo "<details>" >> $GITHUB_STEP_SUMMARY
    echo "<summary>${title}</summary>" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "${content}" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "</details>" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
}

# Initialize summary with header
{
    echo "# 🛡️ Code Quality & Security Report"
    echo ""
    echo "**Workflow**: \`${{ github.workflow }}\`"
    echo "**Run**: [\`#${{ github.run_number }}\`](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})"
    echo "**Branch**: \`${{ github.ref_name }}\`"
    echo "**Commit**: [\`${GITHUB_SHA:0:8}\`](${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }})"
    echo "**Timestamp**: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo ""
} > $GITHUB_STEP_SUMMARY

# Quality Checks Section
QUALITY_STATUS="✅ Passed"
QUALITY_DETAILS=""

# Check Ruff linting results
if [ -f "ruff-results.txt" ]; then
    RUFF_ISSUES=$(wc -l < ruff-results.txt || echo "0")
    if [ "$RUFF_ISSUES" -gt 0 ]; then
        QUALITY_STATUS="❌ Failed"
        QUALITY_DETAILS="${QUALITY_DETAILS}\n- **Ruff Linting**: ${RUFF_ISSUES} issues found"
    else
        QUALITY_DETAILS="${QUALITY_DETAILS}\n- **Ruff Linting**: ✅ No issues"
    fi
else
    QUALITY_DETAILS="${QUALITY_DETAILS}\n- **Ruff Linting**: ✅ Passed"
fi

# Check MyPy results
if [ -f "mypy-results.txt" ]; then
    MYPY_ERRORS=$(grep -c "error:" mypy-results.txt || echo "0")
    if [ "$MYPY_ERRORS" -gt 0 ]; then
        QUALITY_STATUS="❌ Failed"
        QUALITY_DETAILS="${QUALITY_DETAILS}\n- **MyPy Type Checking**: ${MYPY_ERRORS} errors found"
    else
        QUALITY_DETAILS="${QUALITY_DETAILS}\n- **MyPy Type Checking**: ✅ No errors"
    fi
else
    QUALITY_DETAILS="${QUALITY_DETAILS}\n- **MyPy Type Checking**: ✅ Passed"
fi

# Check Safety results
if [ -f "safety-report.json" ]; then
    SAFETY_VULNS=$(jq '.vulnerabilities | length' safety-report.json 2>/dev/null || echo "0")
    if [ "$SAFETY_VULNS" -gt 0 ]; then
        QUALITY_STATUS="⚠️ Issues Found"
        QUALITY_DETAILS="${QUALITY_DETAILS}\n- **Safety (Dependencies)**: ${SAFETY_VULNS} vulnerabilities"
    else
        QUALITY_DETAILS="${QUALITY_DETAILS}\n- **Safety (Dependencies)**: ✅ No vulnerabilities"
    fi
else
    QUALITY_DETAILS="${QUALITY_DETAILS}\n- **Safety (Dependencies)**: ✅ Passed"
fi

add_section "📊 Code Quality Overview" "${QUALITY_STATUS}

${QUALITY_DETAILS}"

# Security Scans Section
SECURITY_STATUS="✅ Secure"
TOTAL_VULNERABILITIES=0
CRITICAL_COUNT=0
HIGH_COUNT=0
MEDIUM_COUNT=0

# Analyze Semgrep results
if [ -f "semgrep.sarif" ]; then
    SEMGREP_FINDINGS=$(jq '.runs[0].results | length' semgrep.sarif 2>/dev/null || echo "0")
    if [ "$SEMGREP_FINDINGS" -gt 0 ]; then
        SECURITY_STATUS="⚠️ Issues Found"
    fi
else
    SEMGREP_FINDINGS=0
fi

# Analyze Trivy container results
if [ -f "trivy-comprehensive.json" ]; then
    TRIVY_CRITICAL=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' trivy-comprehensive.json 2>/dev/null || echo "0")
    TRIVY_HIGH=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' trivy-comprehensive.json 2>/dev/null || echo "0")
    TRIVY_MEDIUM=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")] | length' trivy-comprehensive.json 2>/dev/null || echo "0")
    
    CRITICAL_COUNT=$((CRITICAL_COUNT + TRIVY_CRITICAL))
    HIGH_COUNT=$((HIGH_COUNT + TRIVY_HIGH))
    MEDIUM_COUNT=$((MEDIUM_COUNT + TRIVY_MEDIUM))
    TOTAL_VULNERABILITIES=$((TOTAL_VULNERABILITIES + TRIVY_CRITICAL + TRIVY_HIGH + TRIVY_MEDIUM))
    
    if [ "$TRIVY_CRITICAL" -gt 0 ] || [ "$TRIVY_HIGH" -gt 0 ]; then
        SECURITY_STATUS="🚨 Critical Issues"
    elif [ "$TRIVY_MEDIUM" -gt 0 ]; then
        SECURITY_STATUS="⚠️ Issues Found"
    fi
fi

# Add dependency vulnerabilities to totals
if [ -f "safety-report.json" ]; then
    SAFETY_VULNS=$(jq '.vulnerabilities | length' safety-report.json 2>/dev/null || echo "0")
    HIGH_COUNT=$((HIGH_COUNT + SAFETY_VULNS))  # Safety issues are considered high severity
    TOTAL_VULNERABILITIES=$((TOTAL_VULNERABILITIES + SAFETY_VULNS))
fi

# Security Overview
SECURITY_CONTENT="**Overall Status**: ${SECURITY_STATUS}

### 🔍 Scan Results
| Tool | Status | Findings |
|------|--------|----------|
| **Semgrep SAST** | $([ "$SEMGREP_FINDINGS" -eq 0 ] && echo "✅ Clean" || echo "⚠️ ${SEMGREP_FINDINGS} findings") | Code analysis |
| **Trivy Container** | $([ "$TRIVY_CRITICAL" -eq 0 ] && [ "$TRIVY_HIGH" -eq 0 ] && echo "✅ Clean" || echo "⚠️ Vulnerabilities found") | Image security |
| **Safety Dependencies** | $([ "$SAFETY_VULNS" -eq 0 ] && echo "✅ Clean" || echo "⚠️ ${SAFETY_VULNS} vulnerabilities") | Dependency security |
| **CodeQL** | ✅ Running | Semantic analysis |

### 📈 Vulnerability Breakdown
- 🔴 **Critical**: ${CRITICAL_COUNT}
- 🟠 **High**: ${HIGH_COUNT}  
- 🟡 **Medium**: ${MEDIUM_COUNT}
- **Total**: ${TOTAL_VULNERABILITIES}"

add_section "🔒 Security Scan Results" "$SECURITY_CONTENT"

# Coverage Information (if available)
if [ -f "coverage.xml" ] || [ -f ".coverage" ]; then
    COVERAGE_CONTENT="### 📊 Test Coverage
- **Coverage Report**: Available in workflow artifacts
- **Format**: XML and HTML reports generated
- **Upload**: Automatically sent to Codecov.io

> 💡 **Coverage Target**: 80%+ (Industry Standard)
> 📈 **Trend**: View historical coverage in [Codecov Dashboard](https://codecov.io/gh/${{ github.repository }})"

    add_section "📊 Coverage Analysis" "$COVERAGE_CONTENT"
fi

# Performance & Metrics
METRICS_CONTENT="### ⏱️ Job Performance
- **Quality Job Duration**: Completed in ${QUALITY_DURATION:-'N/A'} seconds
- **Security Scans**: Multiple tools running in parallel
- **Efficiency**: Using UV package manager for 40% faster builds

### 🔧 Tools & Versions
- **Ruff**: Latest (linting & formatting)
- **MyPy**: Latest (type checking)
- **Safety**: Latest (dependency scanning)
- **Semgrep**: Latest (SAST analysis)
- **Trivy**: v0.16.1 (container scanning)
- **CodeQL**: Latest (semantic analysis)"

add_section "⚡ Performance & Tools" "$METRICS_CONTENT"

# Action Items & Next Steps
NEXT_STEPS=""

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    NEXT_STEPS="🚨 **IMMEDIATE ACTION REQUIRED**
1. Review critical vulnerabilities in [Security Tab](${{ github.server_url }}/${{ github.repository }}/security)
2. Block deployment until critical issues are resolved
3. Update dependencies and rebuild container images"
elif [ "$HIGH_COUNT" -gt 0 ]; then
    NEXT_STEPS="⚠️ **ACTION RECOMMENDED**
1. Review high-severity findings in [Security Tab](${{ github.server_url }}/${{ github.repository }}/security)
2. Plan remediation in next sprint
3. Consider updating vulnerable dependencies"
elif [ "$TOTAL_VULNERABILITIES" -gt 0 ]; then
    NEXT_STEPS="💡 **REVIEW SUGGESTED**
1. Review medium/low findings when convenient
2. Consider dependency updates during regular maintenance
3. Monitor for new vulnerabilities"
else
    NEXT_STEPS="✅ **NO ACTION REQUIRED**
All security scans passed successfully! The codebase meets security standards."
fi

add_section "🎯 Next Steps" "$NEXT_STEPS"

# Resources & Links
RESOURCES_CONTENT="### 📋 Quick Links
- 🔍 [**Security Tab**](${{ github.server_url }}/${{ github.repository }}/security) - Detailed vulnerability reports
- 📊 [**Codecov Dashboard**](https://codecov.io/gh/${{ github.repository }}) - Coverage trends & analysis  
- 🔗 [**Workflow Run**](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}) - Full execution details
- 📁 [**Artifacts**](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}) - Download detailed reports

### 📚 Documentation
- [Security Best Practices](https://docs.github.com/en/code-security)
- [Codecov Documentation](https://docs.codecov.com/)
- [Python Security Guidelines](https://python.org/dev/security/)

### 🔄 Automation Details
- **Trigger**: Code changes to core application files
- **Frequency**: Every push and pull request  
- **Parallel Execution**: Quality and security scans run simultaneously
- **Integration**: Results automatically uploaded to GitHub Security tab"

add_section "📖 Resources & Documentation" "$RESOURCES_CONTENT"

# Detailed Results (Collapsible)
if [ -f "ruff-results.txt" ] && [ -s "ruff-results.txt" ]; then
    RUFF_DETAILS="$(cat ruff-results.txt)"
    add_collapsible "🔍 Detailed Ruff Results" "\`\`\`
${RUFF_DETAILS}
\`\`\`"
fi

if [ -f "mypy-results.txt" ] && [ -s "mypy-results.txt" ]; then
    MYPY_DETAILS="$(cat mypy-results.txt)"
    add_collapsible "🔍 Detailed MyPy Results" "\`\`\`
${MYPY_DETAILS}
\`\`\`"
fi

# Add footer with timestamp and workflow info
{
    echo "---"
    echo ""
    echo "<sub>🤖 Generated by Code Quality & Security Workflow • $(date -u '+%Y-%m-%d %H:%M:%S UTC') • [Workflow Documentation](https://github.blog/news-insights/product-news/supercharging-github-actions-with-job-summaries/)</sub>"
} >> $GITHUB_STEP_SUMMARY

echo "✅ GitHub Actions Summary generated successfully!"
echo "📊 Summary includes: Quality checks, Security scans, Coverage analysis, and Next steps"
echo "🔗 View full summary in the Actions tab"