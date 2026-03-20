---
name: postgres-patterns
description: PostgreSQL optimization: indexes, types, anti-patterns for this project
---
## PostgreSQL Patterns

### Data Types
- **Financial data**: `NUMERIC` not `REAL` (already migrated)
- **Timestamps**: `TIMESTAMPTZ` not `TIMESTAMP` (already migrated)
- **Text IDs**: `TEXT` for user_id, `VARCHAR(255)` for emails
- **Booleans**: `BOOLEAN DEFAULT TRUE/FALSE`
- **JSON**: `JSONB` for flexible metadata

### Index Strategy
- Primary keys: always indexed
- Foreign keys: always indexed
- Partial unique: `CREATE UNIQUE INDEX ... WHERE payment_tx_hash IS NOT NULL`
- Time-series: `CREATE INDEX ON table(created_at DESC)`

### Query Patterns
- Always use parameterized queries (`%s` placeholders)
- Use `EXPLAIN ANALYZE` for slow queries
- Use `LIMIT` on all list endpoints
- Use `FOR UPDATE SKIP LOCKED` for queue processing

### Connection Pooling
- Pool size: configurable via env vars (default min=2, max=10)
- Statement timeout: configurable via `DB_STATEMENT_TIMEOUT` (default 30s)
- Neon pooled connections: use `-pooler` URL suffix

### Anti-Patterns to Avoid
- N+1 queries (use JOIN or batch loading)
- SELECT * (always specify columns)
- Missing indexes on foreign keys
- Storing secrets in DB (use environment variables)
- Real type for money (use NUMERIC)
