---
name: e2e-testing
description: Playwright E2E test patterns for SPA market pages
---
## E2E Testing Patterns

### Project Structure
```
pw_test/                          # Playwright test scripts (standalone)
  test_market_ui_smoke.py         # Market page smoke tests
  test_frontend_interaction_smoke.py  # Full UI interaction tests
tests/e2e/                        # pytest wrappers
  test_market_ui_smoke.py         # Pytest entry for market tests
  test_frontend_interaction_smoke.py
```

### Running E2E Tests
```bash
# Run all E2E
.venv\Scripts\python.exe -m pytest tests/e2e/ --no-cov -v

# Run standalone (no pytest)
.venv\Scripts\python.exe pw_test/test_market_ui_smoke.py
```

### Test Pattern
1. Static server serves `web/` directory on port 8768/8769
2. Mock API routes with `page.route("**/*", handler)`
3. Seed context with `add_init_script()` (user, WebSocket mock, localStorage)
4. Navigate, wait, assert, cleanup

### Key Patterns
- Use `wait_for_function()` for dynamic content
- Use `wait_for_timeout(2000)` as fallback (not as primary wait)
- Mock WebSocket with stub class (real WS needs server)
- Use `page.evaluate()` to call JS functions directly
- Each test gets fresh browser context (no state leakage)

### Windows Notes
- Playwright must be installed: `python -m playwright install chromium`
- Use `powershell -Command` for running tests
- CRLF warnings are normal
