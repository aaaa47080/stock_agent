@echo off
REM ============================================================================
REM WARNING: THIS SCRIPT REWRITES GIT HISTORY!
REM
REM ALL COLLABORATORS MUST RE-CLONE THE REPOSITORY AFTER RUNNING THIS SCRIPT.
REM Force-pushed commits will have different SHAs and existing clones will break.
REM ============================================================================
REM
REM Purge Sensitive Files from Git History
REM
REM This script provides step-by-step instructions for removing secrets and
REM sensitive files from the entire git history using BFG Repo-Cleaner.
REM
REM Prerequisites:
REM   - Java Runtime Environment (JRE) 8+
REM   - BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
REM   - Git for Windows
REM
REM Usage:
REM   scripts\purge_git_history.bat
REM   scripts\purge_git_history.bat https://github.com/your-org/stock_agent.git
REM
REM ============================================================================

echo.
echo  ============================================================
echo  ** WARNING: GIT HISTORY REWRITE - READ BEFORE PROCEEDING **
echo  ============================================================
echo.
echo  This process will permanently rewrite git history.
echo  Every collaborator MUST re-clone after this is done.
echo  There is no undo.
echo.
echo  Sensitive files that will be purged from ALL commits:
echo.
echo    FILE                        CONTENT
echo    ----                        -------
echo    .env                        DATABASE_URL, API keys, secrets
echo    .env.local                  Local environment secrets
echo    .env.production             Production environment secrets
echo    .env.*.local                Local environment variants
echo    key.txt                     OPENROUTER API key
echo.
echo  ============================================================
echo.

if "%~1"=="" (
    echo  STEP 1: Install BFG Repo-Cleaner
    echo  -----------------------------------
    echo  Download the latest BFG jar from:
    echo    https://github.com/rtyley/bfg-repo-cleaner/releases
    echo.
    echo  Example (PowerShell):
    echo    Invoke-WebRequest -OutFile bfg.jar https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
    echo.
    echo  Requires Java 8+:
    echo    java -version
    echo.
    echo  ============================================================
    echo.
    echo  STEP 2: Create a bare mirror clone
    echo  -----------------------------------
    echo    git clone --mirror ^<your-repo-url^> repo-bare.git
    echo.
    echo  Example:
    echo    git clone --mirror https://github.com/your-org/stock_agent.git repo-bare.git
    echo.
    echo  ============================================================
    echo.
    echo  STEP 3: Run BFG to delete sensitive files
    echo  ------------------------------------------
    echo    cd repo-bare.git
    echo.
    echo    REM Delete specific files by name:
    echo    java -jar C:\path\to\bfg.jar --delete-files .env,.env.local,.env.production,key.txt
    echo.
    echo    REM To also replace strings inside files (e.g., secrets committed in code):
    echo    java -jar C:\path\to\bfg.jar --replace-text passwords.txt
    echo.
    echo  Where passwords.txt contains entries like:
    echo    DATABASE_URL==^>***REDACTED***
    echo    OPENROUTER_API_KEY==^>***REDACTED***
    echo.
    echo  ============================================================
    echo.
    echo  STEP 4: Clean up refs and garbage collect
    echo  ------------------------------------------
    echo    REM Expire all reflog entries
    echo    git reflog expire --expire=now --all
    echo.
    echo    REM Run aggressive garbage collection
    echo    git gc --prune=now --aggressive
    echo.
    echo  ============================================================
    echo.
    echo  STEP 5: Force-push the rewritten history
    echo  -----------------------------------------
    echo    git push --force --all
    echo    git push --force --tags
    echo.
    echo  ============================================================
    echo.
    echo  STEP 6: Verify and notify collaborators
    echo  -----------------------------------------
    echo    REM Verify the sensitive files are gone from history:
    echo    git log --all --full-history -- .env
    echo    git log --all --full-history -- key.txt
    echo    git log --all --full-history -- .env.local
    echo    git log --all --full-history -- .env.production
    echo.
    echo    REM Search for any remaining secrets in blobs:
    echo    git log --all -p ^| findstr /i "database_url openrouter api_key secret"
    echo.
    echo    ** IMPORTANT: Notify ALL collaborators to delete their local clones
    echo    and re-clone from the rewritten repository. Old clones will have
    echo    diverged history and cannot be reconciled with a simple merge.
    echo.
    echo  ============================================================
    echo.
    echo  STEP 7: Rotate all exposed credentials
    echo  ----------------------------------------
    echo  Even after purging from git history, assume the secrets were compromised:
    echo  - Rotate DATABASE_URL credentials
    echo  - Rotate all API keys (OPENROUTER, etc.)
    echo  - Invalidate any JWT signing keys
    echo  - Review access logs for suspicious activity
    echo.
    echo  ============================================================
    echo.
    echo  This script is informational only. Execute each step manually.
    echo.
    goto :EOF
)

echo  Detected repo URL: %~1
echo.
echo  This is informational only. Review the steps above and execute manually.
echo.
goto :EOF
