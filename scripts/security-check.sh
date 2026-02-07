#!/bin/bash
# Security Check Script (Stage 5 Security)
#
# Runs various security checks on the codebase.
# Run this script regularly as part of your security maintenance.
#
# Usage: ./scripts/security-check.sh
#
# Requirements:
# - pip-audit: pip install pip-audit
# - bandit: pip install bandit

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}🔒 Security Hardening Check Script${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# ============================================================================
# 1. Dependency Vulnerability Scan
# ============================================================================
echo -e "${BLUE}[1/5] Checking for vulnerable dependencies...${NC}"

if command -v pip-audit &> /dev/null; then
    pip-audit --desc --format json > security-report-deps.json 2>&1 || true
    pip-audit --desc || echo -e "${YELLOW}⚠️  Some vulnerabilities found - check security-report-deps.json${NC}"
    echo -e "${GREEN}✅ Dependency check complete${NC}"
else
    echo -e "${YELLOW}⚠️  pip-audit not found. Install with: pip install pip-audit${NC}"
fi
echo ""

# ============================================================================
# 2. Code Security Linting
# ============================================================================
echo -e "${BLUE}[2/5] Running bandit security linter...${NC}"

if command -v bandit &> /dev/null; then
    bandit -r . -f json -o security-report-bandit.json 2>&1 || true
    bandit -r . || echo -e "${YELLOW}⚠️  Some security issues found - check security-report-bandit.json${NC}"
    echo -e "${GREEN}✅ Bandit scan complete${NC}"
else
    echo -e "${YELLOW}⚠️  bandit not found. Install with: pip install bandit${NC}"
fi
echo ""

# ============================================================================
# 3. Security Tests
# ============================================================================
echo -e "${BLUE}[3/5] Running security tests...${NC}"

if [ -d ".venv" ]; then
    VENV_PYTHON=".venv/bin/python"
else
    VENV_PYTHON="python3"
fi

if $VENV_PYTHON -m pytest tests/security/ -v 2>&1 | tee security-test-output.txt; then
    echo -e "${GREEN}✅ All security tests passed${NC}"
else
    echo -e "${RED}❌ Some security tests failed - check security-test-output.txt${NC}"
fi
echo ""

# ============================================================================
# 4. Configuration Security Check
# ============================================================================
echo -e "${BLUE}[4/5] Checking security configuration...${NC}"

SECURITY_ISSUES=0

# Check for wildcard CORS
if grep -q "allow_origins=\[\"*\"\]" api_server.py 2>/dev/null; then
    echo -e "${RED}❌ WILDCARD CORS ORIGIN DETECTED${NC}"
    SECURITY_ISSUES=$((SECURITY_ISSUES + 1))
fi

# Check for hardcoded JWT secret
if grep -q "SECRET_KEY = \".*\"" api/deps.py 2>/dev/null; then
    echo -e "${RED}❌ HARDCODED JWT SECRET DETECTED${NC}"
    SECURITY_ISSUES=$((SECURITY_ISSUES + 1))
fi

# Check TEST_MODE in production
if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "prod" ]; then
    if grep -q "TEST_MODE = True" core/config.py 2>/dev/null; then
        echo -e "${RED}❌ TEST_MODE ENABLED IN PRODUCTION${NC}"
        SECURITY_ISSUES=$((SECURITY_ISSUES + 1))
    fi
fi

if [ $SECURITY_ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ No configuration security issues found${NC}"
else
    echo -e "${RED}❌ Found $SECURITY_ISSUES configuration security issues${NC}"
fi
echo ""

# ============================================================================
# 5. File Permissions Check
# ============================================================================
echo -e "${BLUE}[5/5] Checking file permissions...${NC}"

PERMISSION_ISSUES=0

# Check if keys directory exists and has proper permissions
if [ -d "config/keys" ]; then
    if [ -f "config/keys/jwt_keys.json" ]; then
        PERMS=$(stat -f "%A" "config/keys/jwt_keys.json" 2>/dev/null || stat -c "%a" "config/keys/jwt_keys.json" 2>/dev/null)
        if [ "$PERMS" != "600" ]; then
            echo -e "${YELLOW}⚠️  jwt_keys.json has permissions $PERMS (should be 600)${NC}"
            PERMISSION_ISSUES=$((PERMISSION_ISSUES + 1))
        fi
    fi
fi

if [ $PERMISSION_ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ File permissions OK${NC}"
else
    echo -e "${YELLOW}⚠️  Found $PERMISSION_ISSUES file permission issues${NC}"
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}📊 Security Check Summary${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Generated reports:"
echo "  - security-report-deps.json (dependency vulnerabilities)"
echo "  - security-report-bandit.json (code security issues)"
echo "  - security-test-output.txt (test results)"
echo ""

if [ $SECURITY_ISSUES -eq 0 ] && [ $PERMISSION_ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ Security checks complete! No critical issues found.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Security checks complete. Please review the issues above.${NC}"
    exit 1
fi
