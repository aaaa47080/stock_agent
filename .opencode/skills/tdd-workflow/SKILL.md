---
name: tdd-workflow
description: Test-driven development: red-green-refactor for this project
---
## TDD Workflow

### Cycle
1. **Red**: Write a failing test that defines expected behavior
2. **Green**: Write minimal code to pass the test
3. **Refactor**: Clean up while keeping tests green

### Test Organization
```
tests/
├── conftest.py          # Shared fixtures (TEST_MODE=true)
├── test_database_schema.py   # Phase 0: schema tests
├── test_database_connection.py # Phase 0: connection pool
├── test_orm.py          # Phase 5: ORM models
├── test_orm_repos.py    # Phase 5: ORM repositories
├── test_orm_startup.py  # Phase 5: startup integration
├── test_rate_limiting.py # Phase 1: security
├── test_xss_prevention.py # Phase 1: security
└── e2e/                # Playwright browser tests
```

### When to Write Tests
- **Before** writing new features (TDD)
- **With** bug fixes (regression test first)
- **After** refactoring (verify behavior unchanged)

### Test Types
- **Unit**: `@pytest.mark.unit` — Pure logic, mocked deps
- **Integration**: `@pytest.mark.integration` — Real DB connection
- **E2E**: `@pytest.mark.e2e` — Full browser testing
- **Inspect**: No markers, uses `inspect.getsource()` for static analysis

### Key Rules
- Always run `--no-cov` (coverage breaks SlowAPI)
- Test file names: `test_<feature>.py`
- Use `ruff check` after writing new code
- All tests must pass before committing
