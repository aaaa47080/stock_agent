---
name: release
description: Create git release with changelog and version bump
---
## Release Workflow

### 1. Check Current State
```bash
git status --short
git log --oneline -10
git tag --list
```

### 2. Version Convention
Use semantic versioning: `vMAJOR.MINOR.PATCH`
- MAJOR: breaking changes (DB migration, API removal)
- MINOR: new features (new endpoints, new pages)
- PATCH: bug fixes, i18n additions

### 3. Create Release
```bash
gh release create v1.0.0 --title "v1.0.0" --notes "## Changes
- Phase 0-5 complete
- 407 tests passing
"
```

### 4. Generate Changelog from Commits
```bash
gh release create v1.0.0 --generate-notes
```

## Commit Message Format
```
feat: new feature description
fix: bug fix description
refactor: code restructuring
docs: documentation changes
test: test additions/fixes
chore: maintenance tasks
```
