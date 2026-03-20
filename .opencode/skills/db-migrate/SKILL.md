---
name: db-migrate
description: Database migration: schema changes, column cleanup, Alembic
---
## Database Migration Workflow

### Available Commands
- `.venv\Scripts\python.exe -m alembic upgrade head` — Run pending migrations
- `.venv\Scripts\python.exe -m alembic downgrade -1` — Rollback last migration
- `.venv\Scripts\python.exe -m alembic revision -m "description"` — Create new migration
- `.venv\Scripts\python.exe -m alembic history` — View migration history
- `.venv\Scripts\python.exe -m alembic current` — Show current revision

### Schema File Location
- Raw SQL schema: `core/database/schema.py`
- ORM models: `core/orm/models.py`
- Reconcile functions: `core/database/schema.py` → `reconcile_existing_tables()`
- Auto-migrate: `core/orm/auto_migrate.py`

### When to Use Alembic vs Reconcile
- **Alembic**: Version-controlled, reversible schema changes for production
- **Reconcile**: Auto-runs on every startup, safe-only (ADD/DROP IF EXISTS)
- For breaking changes (DROP column, rename, type change): always use Alembic
- For additive changes (new table, new column): reconcile handles it

### Production DB Safety Rules
1. Always create BOTH upgrade() and downgrade() in Alembic
2. Test migration against dev DB first
3. Never DROP data without backup
4. Use IF EXISTS / IF NOT EXISTS for safety
5. Notify user before running any destructive migration

### Connection Strings
- Dev: DATABASE_URL from .env
- Prod: via Zeabur environment variable (never hardcode)
