---
name: using-git-worktrees
description: Use when starting feature work that needs isolation or before executing implementation plans - creates isolated git worktrees with safety verification
---
## Git Worktrees

### Directory Selection
```bash
# Priority: existing > .gitignore > AGENTS.md > ask
ls -d .worktrees 2>/dev/null
ls -d worktrees 2>/dev/null
```

### Safety: Verify Ignored (REQUIRED)
```bash
git check-ignore -q .worktrees 2>/dev/null
```
If NOT ignored: add to `.gitignore`, commit, then proceed.

### Creation
```bash
git worktree add .worktrees/<branch-name> -b <branch-name>
cd .worktrees/<branch-name>
```

### Project Setup
```bash
# Auto-detect
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f package.json ]; then npm install; fi
```

### Verify Clean Baseline
```bash
.venv\Scripts\python.exe -m pytest --no-cov -q  # Our project
```

### Report
```
Worktree ready at <path>
Tests passing (N tests, 0 failures)
Ready to implement <feature>
```

### Cleanup (when done)
```bash
git worktree remove .worktrees/<branch-name>
git branch -d <branch-name>
```

### Quick Reference
| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| Not ignored | Add to .gitignore + commit |
| Tests fail | Report + ask before proceeding |
| Done | Remove worktree + delete branch |
