---
name: deploy
description: Deploy to production: run tests, push, verify health
---
## Deploy Workflow

### 1. Pre-deploy Checks
```bash
.venv\Scripts\python.exe -m pytest tests/test_db_cleanup.py tests/test_database_schema.py tests/test_database_connection.py tests/test_premium_upgrade.py tests/test_forum_tips.py tests/test_check_secrets.py tests/test_friends_security.py tests/test_rate_limiting.py tests/test_race_conditions.py tests/test_xss_prevention.py tests/test_testmode_hardening.py tests/test_database_robustness.py tests/test_performance.py tests/test_orm.py tests/test_orm_repos.py tests/test_orm_startup.py --no-cov -q
```

### 2. Lint Check
```bash
.venv\Scripts\python.exe -m ruff check core/ api/
```

### 3. Git Status
```bash
git status --short
git log --oneline -5
```

### 4. Push
```bash
git push
```

### 5. Post-deploy Smoke Test
Wait 10 seconds after push, then:
```bash
curl -s https://yourdomain.com/api/config | python -m json.tool
```

## Important Notes
- Always run tests BEFORE pushing
- If tests fail, fix and re-run before proceeding
- Never push with failing tests
- If ruff finds errors in our modified files, fix them first
- ORM_AUTO_MIGRATE is enabled in dev (auto), disabled in prod (ENVIRONMENT=production)
- Database reconcile runs automatically on every startup
