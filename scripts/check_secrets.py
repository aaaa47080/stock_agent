"""
Secret leak detection scanner.

Checks:
1. Whether .env or other sensitive files are tracked in git
2. Whether sensitive keys appear in git history
3. Whether hardcoded secrets exist in source code

Usage: python scripts/check_secrets.py
"""

import os
import re
import subprocess
import sys

SENSITIVE_PATTERNS = [
    (r"JWT_SECRET_KEY\s*=\s*[\"']([^\"']{8,})[\"']", "JWT Secret Key"),
    (r"PI_API_KEY\s*=\s*[\"']([^\"']{8,})[\"']", "Pi API Key"),
    (r"PI_WALLET_PRIVATE_SEED\s*=\s*[\"']([^\"']{8,})[\"']", "Pi Wallet Seed"),
    (r"LANGFUSE_SECRET_KEY\s*=\s*[\"']([^\"']{8,})[\"']", "Langfuse Secret Key"),
    (
        r"DATABASE_URL\s*=\s*[\"'][^\"']*:[^\"']*@[^\"']+[\"']",
        "Database URL with password",
    ),
    (r"POSTGRESQL_PASSWORD\s*=\s*[\"']([^\"']+)[\"']", "PostgreSQL Password"),
]

SENSITIVE_EXTENSIONS = {".env", ".key", ".pem", ".p12", ".pfx"}
SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    "key.txt",
    "admin.txt",
}

GITIGNORED = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.*.local",
    "config/keys/",
    "config/api_key_encryption.json",
    "key.txt",
    "admin.txt",
    "payment_test.txt",
}


def check_gitignore():
    issues = []
    for filename in SENSITIVE_FILENAMES:
        if os.path.exists(filename):
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", filename],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                issues.append(f"CRITICAL: {filename} is tracked in git!")
    return issues


def check_git_history():
    issues = []
    result = subprocess.run(
        ["git", "log", "--all", "--diff-filter=A", "--", ".env", "--format=%H"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout and result.stdout.strip():
        commits = result.stdout.strip().split("\n")
        issues.append(
            f"WARNING: .env was committed in {len(commits)} commit(s). "
            "Run `git filter-branch` or BFG Repo-Cleaner to purge."
        )

    for filename in ["config/api_key_encryption.json", "key.txt", "admin.txt"]:
        result = subprocess.run(
            ["git", "log", "--all", "--diff-filter=A", "--", filename, "--format=%H"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.stdout and result.stdout.strip():
            issues.append(f"WARNING: {filename} was committed to git history.")
    return issues


def check_source_code_secrets():
    issues = []
    skip_dirs = {".venv", "__pycache__", "node_modules", ".git", "htmlcov", "_archive"}

    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        stripped = line.strip()
                        if (
                            stripped.startswith("#")
                            or stripped.startswith('"')
                            or "os.getenv" in stripped
                            or "environ" in stripped
                        ):
                            continue
                        for pattern, name in SENSITIVE_PATTERNS:
                            if re.search(pattern, stripped):
                                value = re.search(pattern, stripped).group(1)[:8]
                                issues.append(
                                    f"WARNING: Possible {name} hardcoded in {fpath}:{i} (...{value})"
                                )
                                break
            except (OSError, UnicodeDecodeError):
                pass  # Skip files that can't be read
    return issues


def main():
    print("=" * 60)
    print("Secret Leak Detection Scanner")
    print("=" * 60)
    print()

    all_issues = []

    print("[1/3] Checking if sensitive files are tracked in git...")
    issues = check_gitignore()
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  OK - No sensitive files tracked")
    print()

    print("[2/3] Checking git history for leaked secrets...")
    issues = check_git_history()
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  OK - No leaked secrets in history")
    print()

    print("[3/3] Checking source code for hardcoded secrets...")
    issues = check_source_code_secrets()
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  OK - No hardcoded secrets found")
    print()

    print("=" * 60)
    if all_issues:
        print(f"FOUND {len(all_issues)} issue(s). Review and fix.")
        return 1
    else:
        print("All checks passed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
