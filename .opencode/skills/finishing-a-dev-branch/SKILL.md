---
name: finishing-a-dev-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - merge, PR, keep, or discard
---
## Finishing a Development Branch

### Step 1: Verify Tests
```bash
.venv\Scripts\python.exe -m pytest --no-cov -q
```
If tests fail: STOP. Fix before proceeding.

### Step 2: Determine Base Branch
```bash
git merge-base HEAD main 2>/dev/null
```

### Step 3: Present Options
```
Implementation complete. What would you like to do?

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is
4. Discard this work
```

### Step 4: Execute

**Option 1 - Merge locally:**
```bash
git checkout main && git pull && git merge <branch> && git branch -d <branch>
```

**Option 2 - Create PR:**
```bash
git push -u origin <branch>
gh pr create --title "title" --body "## Summary&#10;- bullets"
```

**Option 3 - Keep:** Report branch preserved.

**Option 4 - Discard:** Require typed "discard" confirmation.
```bash
git checkout main && git branch -D <branch>
```

### Step 5: Cleanup Worktree (Options 1, 4 only)
```bash
git worktree remove .worktrees/<branch-name> 2>/dev/null
```

### Quick Reference
| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge | Y | - | - | Y |
| 2. PR | - | Y | Y | - |
| 3. Keep | - | - | Y | - |
| 4. Discard | - | - | - | Y (force) |
