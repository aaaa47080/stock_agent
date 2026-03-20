---
name: verification-loop
description: Post-change verification checklist: lint, test, security, diff review
---
## Verification Loop

### After Every Change
Run these checks in order:

### 1. Lint
```bash
.venv\Scripts\python.exe -m ruff check core/ api/
```

### 2. Type Check (if applicable)
```bash
.venv\Scripts\python.exe -m ruff check --select ANN core/ api/
```

### 3. Tests
```bash
.venv\Scripts\python.exe -m pytest tests/ --no-cov -q
```

### 4. Security Scan
- Check for hardcoded secrets: `rg "password|api_key|secret" --type py`
- Check for SQL injection: `rg "f\".*SELECT.*\+" --type py`
- Check for XSS: `rg "innerHTML.*\+" web/js/`

### 5. Diff Review
```bash
git diff --stat
git diff
```

### 6. JSON Validation
```bash
.venv\Scripts\python.exe -c "import json; json.load(open('web/js/i18n/en.json')); json.load(open('web/js/i18n/zh-TW.json')); print('OK')"
```

### Verification Report Format
```
✅ Lint: passed
✅ Tests: 407 passed
✅ Security: no secrets found
✅ Diff: 5 files changed (+120, -30)
```

### When to Break the Loop
- ALL checks pass → ready to commit
- Any check fails → fix and re-run from step 1
