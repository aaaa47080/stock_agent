---
name: test
description: Run test suite with proper flags and coverage
---
## Test Commands

### Run All Project Tests (407 tests)
```bash
.venv\Scripts\python.exe -m pytest tests/test_db_cleanup.py tests/test_database_schema.py tests/test_database_connection.py tests/test_premium_upgrade.py tests/test_forum_tips.py tests/test_check_secrets.py tests/test_friends_security.py tests/test_rate_limiting.py tests/test_race_conditions.py tests/test_xss_prevention.py tests/test_testmode_hardening.py tests/test_database_robustness.py tests/test_performance.py tests/test_orm.py tests/test_orm_repos.py tests/test_orm_startup.py --no-cov -q
```

### Run Single Test File
```bash
.venv\Scripts\python.exe -m pytest tests/test_<name>.py --no-cov -v
```

### Run Single Test Function
```bash
.venv\Scripts\python.exe -m pytest tests/test_<name>.py::TestClass::test_method --no-cov -v
```

### Run E2E Tests
```bash
.venv\Scripts\python.exe -m pytest tests/e2e/ --no-cov -v
```

### Important Flags
- Always use `--no-cov` — pytest.ini has coverage enabled which breaks SlowAPI inspect
- Use `-v` for verbose output when debugging
- Use `-q` for quick summary
- Use `-x` to stop at first failure

### Test File Map
| File | Tests | Phase |
|------|-------|-------|
| test_database_schema.py | 8 | Phase 0 |
| test_database_connection.py | 33 | Phase 0 |
| test_premium_upgrade.py | 11 | Phase 0 |
| test_forum_tips.py | 12 | Phase 0 |
| test_check_secrets.py | 9 | Phase 0 |
| test_friends_security.py | 16 | Phase 1 |
| test_rate_limiting.py | 19 | Phase 1 |
| test_race_conditions.py | 17 | Phase 1 |
| test_xss_prevention.py | 30 | Phase 1 |
| test_testmode_hardening.py | 8 | Phase 1 |
| test_database_robustness.py | 44 | Phase 2 |
| test_performance.py | 26 | Phase 3 |
| test_orm.py | 33 | Phase 5 |
| test_orm_repos.py | 98 | Phase 5 |
| test_orm_startup.py | 16 | Phase 5 |
| test_db_cleanup.py | 27 | DB Cleanup |
