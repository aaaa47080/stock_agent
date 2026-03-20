---
name: python-testing
description: pytest patterns: fixtures, markers, async tests, mocking for FastAPI
---
## Python Testing Patterns

### Test Commands
```bash
# Run all project tests (always use --no-cov)
.venv\Scripts\python.exe -m pytest tests/ --no-cov -q

# Run single file
.venv\Scripts\python.exe -m pytest tests/test_orm.py --no-cov -v

# Run single test
.venv\Scripts\python.exe -m pytest tests/test_orm.py::TestClass::test_method --no-cov -v

# Run by marker
pytest -m unit        # Fast, no external deps
pytest -m integration # Requires database
pytest -m e2e         # Browser-based
```

### Important Flags
- **Always use `--no-cov`** — pytest.ini has `--cov` which breaks SlowAPI inspect
- Use `-v` for verbose, `-q` for quick summary, `-x` to stop at first failure

### Markers
- `@pytest.mark.unit` — Fast, no external dependencies
- `@pytest.mark.integration` — Requires database
- `@pytest.mark.asyncio` — Async tests
- `@pytest.mark.slow` — Takes >5 seconds
- `@pytest.mark.e2e` — Playwright browser tests

### Test Patterns
- **Inspect-based tests**: Use `inspect.getsource()` and `inspect.getsourcefile()` when testing functions that need real DB connections
- **Mock patterns**: Use `unittest.mock.patch` for external API calls
- **Conftest**: `tests/conftest.py` sets `TEST_MODE=true` automatically

### Naming
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
