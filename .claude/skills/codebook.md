name: codebook
description: Use after completing any significant code change - generates AI-readable codebook entries for future reference and auto-learns from changes
---

# Codebook Entry Generator

## When to Use

Invoke this skill AFTER completing:
- Bug fixes
- Security patches
- Feature implementations
- Refactoring
- Architecture changes
- Performance optimizations

## Process

### Step 1: Analyze the Change

Run these commands to understand what was changed:

```bash
git diff --stat HEAD~1
git log -1 --pretty=format:"%s%n%b"
```

### Step 2: Generate Codebook Entry

Create a file in `docs/codebook/` with this naming convention:
- Format: `YYYY-MM-DD-{type}-{short-id}.yaml`
- Types: `fix`, `feat`, `refactor`, `security`, `perf`, `docs`

### Step 3: Template

```yaml
# docs/codebook/YYYY-MM-DD-{type}-{id}.yaml
id: CB-{YYYY}-{MMDD}-{SEQ}
date: {YYYY-MM-DD}
type: {fix|feat|refactor|security|perf|docs}
severity: {critical|high|medium|low}  # optional

problem: |
  {Describe the issue in 1-3 sentences}
  - Root cause: {why it happened}
  - Impact: {what was affected}

solution: |
  {Describe the fix in 1-3 sentences}
  - Approach: {how it was solved}
  - BEFORE: {old code pattern}
  - AFTER: {new code pattern}

files:
  - {file_path}: {number_of_changes}
  # Example:
  # - api/routers/user.py: 3 changes

keywords:
  - {tag1}
  - {tag2}
  # Examples: sql-injection, jwt, auth, performance, api

context: |
  {Optional: Additional context for AI to understand the decision}
  - Why this approach was chosen
  - Alternatives considered
  - Trade-offs made

refs:
  - {reference_url_or_doc}
  # Examples: OWASP-Top-10, Pi-SDK-Docs, GitHub-Issue-#123
```

### Step 4: Compact Format (Alternative)

For simple changes, use this compact format:

```yaml
id: CB-2026-0304-002
date: 2026-03-04
type: feat
change: "Add JWT auto-refresh using Pi SDK - silent token refresh before expiry"
files: [web/js/auth.js: +120 lines]
tags: [jwt, pi-sdk, auth, auto-refresh]
```

## Examples

### Example 1: Security Fix

```yaml
id: CB-2026-0304-001
date: 2026-03-04
type: security
severity: high

problem: |
  SQL injection vulnerability in INTERVAL clauses
  - Used f-string and % formatting for SQL parameters
  - Affected: admin stats, user membership, governance cleanup

solution: |
  Parameterized queries with proper escaping
  - BEFORE: f"INTERVAL '{days} days'"
  - AFTER: INTERVAL %s with (f"{days} days",) tuple

files:
  - api/routers/admin_panel.py: 4
  - core/database/user.py: 3
  - scripts/cron_governance.py: 1

keywords: [sql-injection, security, parameterized-query, owasp]
refs: [OWASP-Top-10, CWE-89]
```

### Example 2: Feature

```yaml
id: CB-2026-0304-002
date: 2026-03-04
type: feat

problem: |
  JWT token expires after 7 days, forcing user re-login
  - Poor UX: users logged out unexpectedly
  - No refresh mechanism existed

solution: |
  Auto-refresh JWT using Pi SDK as implicit refresh token
  - Timer checks every hour if token needs refresh
  - Silently calls Pi.authenticate() + pi-sync
  - Refreshes 24 hours before expiry

files:
  - web/js/auth.js: +120

keywords: [jwt, pi-sdk, auth, auto-refresh, token-management]
context: |
  Chose Pi SDK approach over traditional OAuth2 refresh tokens because:
  - Pi Browser environment is more secure
  - Pi SDK token is long-lived
  - Simpler implementation, fewer attack vectors
refs: [Pi-SDK-Docs, OAuth2-Best-Practices]
```

## Auto-Update MEMORY.md

After creating codebook entry, update MEMORY.md with a summary:

```markdown
## Recent Changes (Auto-generated)

### 2026-03-04
- [CB-001] Fix SQL injection in INTERVAL queries (security)
- [CB-002] Add JWT auto-refresh via Pi SDK (feat)

See: docs/codebook/ for details
```

## Important Notes

1. **Keep entries concise** - AI reads many of these, brevity matters
2. **Use consistent keywords** - Enables pattern matching across sessions
3. **Include BEFORE/AFTER** - Critical for understanding code evolution
4. **Link related entries** - Use `id` references for connected changes
5. **Don't duplicate** - Check existing entries before creating new ones
