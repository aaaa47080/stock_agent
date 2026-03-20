---
name: search-first
description: Research before coding: check existing code, docs, and libraries first
---
## Search-First Workflow

### Before Writing Any Code
1. **Search the codebase** — Does this already exist?
2. **Check dependencies** — Does an installed package handle this?
3. **Read existing patterns** — How is similar code structured here?

### Decision Matrix
| Approach | When |
|----------|------|
| **Adopt** | Existing solution fits perfectly |
| **Extend** | Existing solution needs minor changes |
| **Build** | No existing solution, or none fits |

### Search Commands
```bash
# Search codebase
rg "pattern" --type py core/ api/
rg "pattern" --type js web/js/

# Check if a function exists
rg "def function_name" --type py

# Find where something is used
rg "function_name" --type py core/ api/ tests/

# Check installed packages
pip list | grep -i "keyword"
```

### Project-Specific Context
- DB layer: `core/database/` (raw psycopg2) + `core/orm/` (SQLAlchemy)
- Routes: `api/routers/` (FastAPI endpoints)
- Frontend: `web/js/` (vanilla JS modules)
- Tests: `tests/` (pytest) + `pw_test/` (Playwright)
- Config: `.env` + `core/database/connection.py`
