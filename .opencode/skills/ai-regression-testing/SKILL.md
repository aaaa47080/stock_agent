---
name: ai-regression-testing
description: Use when AI agent modifies API routes or backend logic - catch systematic blind spots where the same model writes and reviews code
---
## AI Regression Testing

### The Core Problem
When AI writes code and reviews its own work, it carries the same assumptions:
```
AI writes fix → AI reviews fix → "looks correct" → Bug still exists
```

### Most Common AI Regressions (by frequency)

**#1 Sandbox/Production Path Mismatch**
Fixed production path but forgot sandbox/test path (or vice versa).
```python
# Our project: TEST_MODE vs production paths
if TEST_MODE:
    return {"data": mock_data}  # ← forgot new field
return {"data": real_data}  # ← has new field
```

**#2 SELECT/Query Omission**
Added new column to response but forgot to include in DB query.
```python
# Forgot to add new_field in SELECT
c.execute("SELECT id, name FROM users WHERE id = %s", (uid,))
```

**#3 Error State Leakage**
Error set but old state not cleared.
```python
except Exception:
    return {"error": "failed"}  # stale data still in caller
```

### Testing Strategy
**Write tests WHERE bugs were found, not everywhere:**
```
Bug in premium.py     → Write test for premium
Bug in messages.py    → Write test for messages
No bug in forum.py    → Don't write test (yet)
```

### Our Project Patterns
- Use `TEST_MODE=true` for DB-free API testing
- Test response shape (required fields present), not implementation
- Run `.venv\Scripts\python.exe -m pytest --no-cov -q` as first step of any bug check
- Name tests after the bug they prevent: `test_bug_x_missing_field_regression`

### Bug-Check Workflow
```
Step 1: pytest --no-cov -q        → FAIL = highest priority
Step 2: ruff check .              → FAIL = type/style errors
Step 3: AI code review             → with known blind spots above
Step 4: For each fix → regression test
```

### Quick Reference
| AI Regression | Test Strategy | Priority |
|-------------|---------------|----------|
| Sandbox/prod mismatch | Assert same response shape | High |
| Query omission | Assert all required fields | High |
| Error state leakage | Assert state cleanup on error | Medium |
| Missing rollback | Assert state on failure | Medium |
