---
name: api-testing
description: API testing patterns for FastAPI endpoints using pytest and httpx
---
## API Testing Patterns

### Project Test Setup
- Test client via `httpx.AsyncClient` with `app` from `api.main`
- Fixtures in `tests/conftest.py` (TEST_MODE=true, mock DB)
- Always use `--no-cov` flag: `.venv\Scripts\python.exe -m pytest --no-cov`

### Running Tests
```bash
# All API tests
.venv\Scripts\python.exe -m pytest tests/ --no-cov -v

# Single test file
.venv\Scripts\python.exe -m pytest tests/test_premium_upgrade.py --no-cov -v

# Single test
.venv\Scripts\python.exe -m pytest tests/test_rate_limiting.py::test_login_rate_limit --no-cov -v

# By marker
.venv\Scripts\python.exe -m pytest -m unit --no-cov
```

### Test Structure
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_endpoint_name():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/endpoint",
            json={"key": "value"},
            headers={"Authorization": "Bearer test_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
```

### Auth Patterns
- Use TEST_MODE headers: `{"X-Test-User-ID": "123"}`
- Or mock `get_current_user` dependency
- Never hit real auth in tests

### Rate Limit Testing
```python
# SlowAPI stores limits in limiter._route_limits dict
key = "module.path"  # e.g., "api.routers.user.login"
limits = app.state.limiter._route_limits.get(key)
assert limits is not None
```

### DB Mock Patterns
- Use `pytest.mark.unit` for no-DB tests
- Use `pytest.mark.integration` for real DB tests
- Mock DB functions for unit tests of business logic

### What NOT to Do
- Don't run `tests/test_agent_scenarios.py` (pre-existing, broken)
- Don't use `--cov` flag (breaks SlowAPI inspect.signature)
- Don't run all `tests/` files together (hangs on external service tests)
- Run only our 16 test files explicitly
