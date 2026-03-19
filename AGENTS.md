# AGENTS.md - Agentic Coding Guidelines

This file provides guidelines for AI agents working in this codebase.

## Project Overview

**Pi Crypto Insight** - AI-Powered Crypto Analysis × Community Ecosystem built with FastAPI, LangGraph, and PostgreSQL.

---

## 1. Build / Lint / Test Commands

### Development Environment
```bash
# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Dev tools only
```

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run a single test file
pytest tests/test_utils_functions.py

# Run a single test function
pytest tests/test_utils_functions.py::TestSafeFloat::test_integer_conversion

# Run tests by marker
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests
pytest -m slow        # Slow tests
pytest -m e2e         # E2E browser tests

# Run without coverage (faster)
pytest -o addopts='-v --tb=short'

# Custom test runner
python run_tests.py
```

### Linting & Formatting

```bash
# Python linting (ruff)
ruff check .

# Python formatting
ruff format .

# JavaScript linting
npx eslint .

# Prettier formatting (JS/HTML/CSS)
npx prettier --write .

# Python syntax check (compiled)
python -m py_compile <file.py>
```

### Verification Scripts

```bash
# Run verified mode checks (CI/CD quality gate)
./scripts/run_verified_mode_checks.sh

# Post-deploy smoke test
API_URL=https://yourdomain.com bash scripts/post_deploy_smoke.sh

# Security check
./scripts/security-check.sh

# Dependency hygiene
./scripts/refresh_lock_and_audit.sh
```

### Running the Application

```bash
# Development server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production server
gunicorn -c gunicorn.conf.py api.main:app
```

---

## 2. Code Style Guidelines

### Python (Primary Backend Language)

**Imports**
- Standard library first, third-party second, local/project third
- Use absolute imports from package root (e.g., `from api.deps import ...`)
- Group imports with blank lines between groups
- Sort alphabetically within groups

```python
# ✅ Correct
import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from core.database.user import get_user
from api.deps import get_current_user
```

**Type Annotations**
- Use type hints for all function parameters and return values
- Use `Optional[X]` over `X | None` for compatibility
- Import types from `typing` module

```python
# ✅ Correct
def process_data(user_id: int, limit: Optional[int] = None) -> list[dict[str, Any]]:
    ...

# ❌ Avoid
def process_data(user_id, limit=None):
    ...
```

**Naming Conventions**
- Classes: `PascalCase` (e.g., `UserProfile`, `MarketData`)
- Functions/variables: `snake_case` (e.g., `get_user_by_id`, `total_amount`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`, `API_TIMEOUT`)
- Private methods: prefix with `_` (e.g., `_internal_method`)
- Type variables: `PascalCase` (e.g., `T`, `ResponseType`)

**Docstrings**
- Use triple-quoted strings for all public functions/classes
- Include Args, Returns, Raises sections for complex functions

```python
def calculate_profit(entry: float, exit: float, quantity: float) -> float:
    """
    Calculate profit from a trade.

    Args:
        entry: Entry price per unit
        exit: Exit price per unit
        quantity: Number of units

    Returns:
        Profit amount (can be negative for loss)
    """
    return (exit - entry) * quantity
```

**Error Handling**
- Use custom exceptions from `core.error_handling`
- Log errors with context before raising
- Return appropriate HTTP status codes in API routes

```python
# ✅ Correct
from core.error_handling import AuthenticationError

def authenticate_user(token: str) -> User:
    try:
        payload = verify_token(token)
    except InvalidTokenError as e:
        logger.warning(f"Invalid token attempt: {e}")
        raise AuthenticationError("Invalid or expired token")
```

### JavaScript (Frontend)

**ESLint Rules**
- Semi-colons required
- Single quotes preferred
- No `console.log` in production code (use `console.warn`, `console.error`)

**Prettier Configuration**
- Single quotes: `true`
- Trailing commas: `es5`
- Print width: `100`
- Tab width: `4` spaces

```javascript
// ✅ Correct
const user = {
  name: 'John',
  email: 'john@example.com',
};

// ❌ Avoid
const user = { name: "John", email: "john@example.com" };
```

---

## 3. Project Structure

```
stock_agent/
├── api/                    # FastAPI routes and endpoints
│   ├── deps.py            # Dependency injection (auth, db)
│   ├── main.py            # FastAPI app entry point
│   ├── models.py          # Pydantic request/response models
│   └── routers/           # API route modules
├── core/                   # Business logic layer
│   ├── agents/            # LangGraph multi-agent system
│   ├── database/          # Database models and queries
│   ├── tools/             # Agent tools (market data, etc.)
│   └── validators/        # Input validation
├── tests/                  # Test suite (pytest)
│   ├── conftest.py        # Pytest fixtures
│   ├── e2e/               # Playwright E2E tests
│   └── test_*.py          # Unit/integration tests
├── web/                    # Frontend (HTML/CSS/JS)
├── scripts/               # DevOps and utility scripts
├── config/                # Configuration files
└── requirements.txt       # Production dependencies
```

---

## 4. Testing Conventions

### Test Structure
- Test files: `test_*.py` in `tests/` directory
- Test classes: `Test*`
- Test functions: `test_*`

### Markers
- `@pytest.mark.unit` - Fast, no external dependencies
- `@pytest.mark.integration` - Requires database
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.slow` - Takes >5 seconds
- `@pytest.mark.e2e` - Browser-based E2E tests

### Fixtures (conftest.py)
- Database URL: `postgresql://test:test@localhost:5432/test`
- Redis URL: `redis://localhost:6379/1`
- `TEST_MODE=true` environment variable set automatically

---

## 5. Database Conventions

- Use async database operations when possible
- All mutations in transactions
- Soft deletes for user data (`deleted_at` timestamp)
- Timestamps in UTC (`timezone.utc`)

---

## 6. API Design Conventions

### Response Format
```python
from api.models import APIResponse

def get_user_endpoint() -> APIResponse[UserSchema]:
    ...
    return APIResponse(success=True, data=user)
```

### Error Responses
```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="User not found"
)
```

---

## 7. Security Guidelines

- Never commit secrets to git (use `.env`)
- JWT_SECRET_KEY must be 32+ characters
- Validate all user inputs with Pydantic models
- Use parameterized queries (never string concatenation)
- Rate limit public endpoints

---

## 8. LLM/AI Agent Conventions

### LangGraph Agents
- Manager Agent: Query classification and orchestration
- Market Agents: Crypto, US Stock, TW Stock specialists
- Use Human-in-the-loop for complex decisions
- Store agent state in `ManagerState`

### Tool Registry
- Register tools via `ToolRegistry`
- Use `@tool` decorator for new tools
- Include descriptions for AI routing

---

## 9. Git Conventions

- Commit message format: `type: description`
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- Example: `feat: add user profile endpoint`

---

## 10. Quick Reference

| Task | Command |
|------|---------|
| Run single test | `pytest tests/test_foo.py::TestClass::test_method` |
| Run tests by marker | `pytest -m unit` |
| Format Python | `ruff format .` |
| Lint Python | `ruff check .` |
| Start dev server | `uvicorn api.main:app --reload` |
| Run verified checks | `./scripts/run_verified_mode_checks.sh` |
