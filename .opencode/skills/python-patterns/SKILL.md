---
name: python-patterns
description: Python best practices: type hints, async, error handling, idioms
---
## Python Patterns for This Project

### Type Hints
- Use `Optional[X]` over `X | None` for compatibility
- Import types from `typing` module
- All function params and return values must be typed

```python
def get_user(user_id: str, include_deleted: bool = False) -> Optional[dict]:
```

### Async Patterns
- Use `async def` for all DB operations (AsyncSession)
- Use `asyncio.gather()` for parallel I/O
- Use `run_sync()` for raw psycopg2 in FastAPI endpoints

### Error Handling
- Use custom exceptions from `core.error_handling`
- Log before raising with context
- Return appropriate HTTP status codes

### Import Order
1. Standard library
2. Third-party (fastapi, sqlalchemy, pydantic)
3. Local/project (`from api.deps import ...`)

### Code Style
- Follow ruff formatting (already configured)
- No print() in production code (use logging)
- Constants: UPPER_SNAKE_CASE
- Classes: PascalCase
- Functions/variables: snake_case
