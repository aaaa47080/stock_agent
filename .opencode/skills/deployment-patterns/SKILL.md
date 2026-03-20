---
name: deployment-patterns
description: CI/CD, Docker, health checks, production readiness
---
## Deployment Patterns

### CI/CD Pipeline (GitHub Actions)
- `.github/workflows/ci.yml` — lint + test + JSON validate (on push/PR)
- `.github/workflows/e2e.yml` — Playwright E2E (on push to main, after CI)

### Environment Variables
```
TEST_MODE=false           # Required for production
ENVIRONMENT=production    # Disables ORM_AUTO_MIGRATE
DATABASE_URL=...           # Set via Zeabur, never hardcode
JWT_SECRET_KEY=...        # 32+ characters
```

### Health Check
```
GET /api/config → {"test_mode": false}
```

### Startup Sequence
1. Load environment variables
2. Initialize raw psycopg2 connection pool
3. Run reconcile_existing_tables() (safe schema sync)
4. Run auto_migrate() (if ORM_AUTO_MIGRATE=true)
5. Start FastAPI app

### Production Checklist
- [ ] TEST_MODE=false
- [ ] ORM_AUTO_MIGRATE=false (or ENVIRONMENT=production)
- [ ] DATABASE_URL points to prod (not dev)
- [ ] JWT_SECRET_KEY is strong and unique
- [ ] Rate limits are enabled
- [ ] CORS origins are restricted (not *)
- [ ] SSL enabled (HTTPS)
- [ ] .env is NOT in git
