---
name: database-migrations
description: Database migration patterns for PostgreSQL + Alembic + reconcile
---
## Database Migration Strategy

### Two-Layer System
1. **Alembic** — Version-controlled, reversible migrations for production
2. **Reconcile** — Auto-runs on startup, safe-only (ADD/DROP IF EXISTS)

### When to Use Alembic
- Breaking changes (DROP column, rename, type change)
- Data migrations (transform existing data)
- Production deployments requiring rollback

### When to Use Reconcile
- Additive changes (new table, new column)
- New indexes
- New CHECK constraints or foreign keys

### Alembic Commands
```bash
.venv\Scripts\python.exe -m alembic upgrade head     # Run pending
.venv\Scripts\python.exe -m alembic downgrade -1     # Rollback last
.venv\Scripts\python.exe -m alembic revision -m "desc"  # New migration
.venv\Scripts\python.exe -m alembic current            # Current rev
.venv\Scripts\python.exe -m alembic history             # History
```

### Safety Rules
1. Always create BOTH upgrade() and downgrade()
2. Test against dev DB before production
3. Never DROP data without backup
4. Use IF EXISTS / IF NOT EXISTS for safety
5. Notify user before destructive migrations

### PostgreSQL-Specific
- Use `CREATE INDEX CONCURRENTLY` for large tables (no lock)
- Use `SKIP LOCKED` for batch updates on live data
- Expand-contract pattern for column type changes
- Always use `TIMESTAMPTZ` not `TIMESTAMP`
- Use `NUMERIC` not `REAL` for financial data
