---
name: changelog-generator
description: Generate changelogs from git history for releases and PRs
---
## Changelog Generation

### When to Use
- Before creating a release tag
- When summarizing work for PR descriptions
- When DANNY asks "what changed since..."

### Steps

#### 1. Gather Commit Data
```bash
# Since last tag
git log --oneline $(git describe --tags --abbrev=0)..HEAD

# Since specific commit
git log --oneline <sha>..HEAD

# With details
git log --pretty=format:"- %s (%h)" <sha>..HEAD
```

#### 2. Categorize Commits
Group by conventional commit prefix:
- `feat:` → Features
- `fix:` → Bug Fixes
- `refactor:` → Code Changes
- `docs:` → Documentation
- `test:` → Tests
- `chore:` → Maintenance

#### 3. Format Changelog
```
## vX.Y.Z (YYYY-MM-DD)

### Features
- Description (abc1234)

### Bug Fixes
- Description (def5678)

### Stats
- X tests passing
- Y files changed
```

#### 4. Include Test Stats
```bash
.venv\Scripts\python.exe -m pytest --no-cov -q 2>&1 | tail -1
```

### Conventions
- Always include commit SHAs in parentheses
- Link to PR if available (`gh pr view --json url`)
- Note any breaking changes prominently
- Include test count and pass rate
