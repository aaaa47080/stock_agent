#!/bin/bash
#
# ============================================================================
# WARNING: THIS SCRIPT REWRITES GIT HISTORY!
#
# ALL COLLABORATORS MUST RE-CLONE THE REPOSITORY AFTER RUNNING THIS SCRIPT.
# Force-pushed commits will have different SHAs and existing clones will break.
# ============================================================================
#
# Purge Sensitive Files from Git History
#
# This script provides step-by-step instructions for removing secrets and
# sensitive files from the entire git history using BFG Repo-Cleaner.
#
# Prerequisites:
#   - Java Runtime Environment (JRE) 8+
#   - BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
#
# Usage:
#   chmod +x scripts/purge_git_history.sh
#   ./scripts/purge_git_history.sh
#
# ============================================================================

set -e

BOLD='\033[1m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}${BOLD}"
echo "======================================================================"
echo "  WARNING: GIT HISTORY REWRITE - READ BEFORE PROCEEDING"
echo "======================================================================"
echo -e "${NC}"
echo ""
echo -e "${YELLOW}This process will permanently rewrite git history.${NC}"
echo -e "${YELLOW}Every collaborator MUST re-clone after this is done.${NC}"
echo -e "${YELLOW}There is no undo.${NC}"
echo ""
echo "Sensitive files that will be purged from ALL commits:"
echo ""
echo "  FILE                        CONTENT"
echo "  ----                        -------"
echo "  .env                        DATABASE_URL, API keys, secrets"
echo "  .env.local                  Local environment secrets"
echo "  .env.production             Production environment secrets"
echo "  .env.*.local                Local environment variants"
echo "  key.txt                     OPENROUTER API key"
echo ""
echo -e "${BOLD}Steps to purge:${NC}"
echo ""
echo "  1. Install BFG Repo-Cleaner"
echo "  2. Create a bare mirror clone of your repository"
echo "  3. Run BFG to delete the sensitive files"
echo "  4. Clean up refs and garbage collect"
echo "  5. Force-push the rewritten history"
echo "  6. Verify and notify collaborators"
echo ""
echo "======================================================================"
echo ""

REPO_URL="${1:-}"

if [ -z "$REPO_URL" ]; then
    echo -e "${BOLD}Step 1: Install BFG Repo-Cleaner${NC}"
    echo ""
    echo "  Download the latest BFG jar from:"
    echo "    https://github.com/rtyley/bfg-repo-cleaner/releases"
    echo ""
    echo "  Example (Linux/macOS):"
    echo "    wget -O bfg.jar https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar"
    echo ""
    echo "  Example (macOS with Homebrew):"
    echo "    brew install bfg"
    echo ""
    echo "  Requires Java 8+:"
    echo "    java -version"
    echo ""
    echo "======================================================================"
    echo ""
    echo -e "${BOLD}Step 2: Create a bare mirror clone${NC}"
    echo ""
    echo "  git clone --mirror <your-repo-url> repo-bare.git"
    echo ""
    echo "  Example:"
    echo "    git clone --mirror git@github.com:your-org/stock_agent.git repo-bare.git"
    echo ""
    echo "======================================================================"
    echo ""
    echo -e "${BOLD}Step 3: Run BFG to delete sensitive files${NC}"
    echo ""
    echo "  cd repo-bare.git"
    echo ""
    echo "  # Delete specific files by name:"
    echo "  java -jar /path/to/bfg.jar --delete-files .env,.env.local,.env.production,key.txt"
    echo ""
    echo "  # Alternatively, delete by glob pattern:"
    echo "  java -jar /path/to/bfg.jar --delete-files '{.env,.env.local,.env.production,key.txt}'"
    echo ""
    echo "  # To also replace strings inside files (e.g., if secrets were committed in code):"
    echo "  java -jar /path/to/bfg.jar --replace-text passwords.txt"
    echo ""
    echo "  Where passwords.txt contains entries like:"
    echo "    DATABASE_URL==>***REDACTED***"
    echo "    OPENROUTER_API_KEY==>***REDACTED***"
    echo ""
    echo "======================================================================"
    echo ""
    echo -e "${BOLD}Step 4: Clean up refs and garbage collect${NC}"
    echo ""
    echo "  # Expire all reflog entries (removes old commit references)"
    echo "  git reflog expire --expire=now --all"
    echo ""
    echo "  # Run aggressive garbage collection to permanently remove objects"
    echo "  git gc --prune=now --aggressive"
    echo ""
    echo "======================================================================"
    echo ""
    echo -e "${BOLD}Step 5: Force-push the rewritten history${NC}"
    echo ""
    echo "  git push --force --all"
    echo "  git push --force --tags"
    echo ""
    echo "======================================================================"
    echo ""
    echo -e "${BOLD}Step 6: Verify and notify collaborators${NC}"
    echo ""
    echo "  # Verify the sensitive files are gone from history:"
    echo "  git log --all --full-history -- .env"
    echo "  git log --all --full-history -- key.txt"
    echo "  git log --all --full-history -- .env.local"
    echo "  git log --all --full-history -- .env.production"
    echo ""
    echo "  # Search for any remaining secrets in blobs:"
    echo "  git log --all -p | grep -i 'database_url\\|openrouter\\|api_key\\|secret'"
    echo ""
    echo -e "${RED}${BOLD}  IMPORTANT: Notify ALL collaborators to delete their local clones"
    echo "  and re-clone from the rewritten repository. Old clones will have"
    echo "  diverged history and cannot be reconciled with a simple merge.${NC}"
    echo ""
    echo "======================================================================"
    echo ""
    echo -e "${BOLD}Step 7: Rotate all exposed credentials${NC}"
    echo ""
    echo "  Even after purging from git history, assume the secrets were compromised:"
    echo "  - Rotate DATABASE_URL credentials"
    echo "  - Rotate all API keys (OPENROUTER, etc.)"
    echo "  - Invalidate any JWT signing keys"
    echo "  - Review access logs for suspicious activity"
    echo ""
    echo "======================================================================"
    exit 0
fi

echo -e "${BOLD}Detected repo URL: ${REPO_URL}${NC}"
echo ""
echo -e "${YELLOW}This is informational only. Review the steps above and execute manually.${NC}"
