---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code. Enforces RED-GREEN-REFACTOR
---
## Test-Driven Development (TDD)

### The Iron Law
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over. No exceptions.

### RED-GREEN-REFACTOR

#### RED - Write Failing Test
- One behavior per test
- Clear name describing what's tested
- Real code (no mocks unless unavoidable)

```python
# Good
def test_retries_failed_operations_3_times():
    result = retry_operation(failing_operation)
    assert result == 'success'
    assert attempts == 3
```

#### Verify RED - Watch It Fail (MANDATORY)
```bash
pytest tests/path/test.py::test_name -v
```
- Test FAILS (not errors)? Good.
- Test passes? Testing existing behavior. Fix test.
- Test errors? Fix error, re-run until it fails correctly.

#### GREEN - Minimal Code
Write simplest code to pass. Don't add features, refactor, or "improve" beyond the test.

#### Verify GREEN (MANDATORY)
```bash
pytest tests/path/test.py -v
```
- All tests pass? Good.
- Other tests broken? Fix now.

#### REFACTOR - Clean Up
After green only: remove duplication, improve names, extract helpers. Keep tests green.

### Bug Fix Pattern
1. RED: Write test reproducing the bug
2. Verify RED: Confirm test fails
3. GREEN: Write minimal fix
4. Verify GREEN: Confirm test passes, no regressions
5. REFACTOR: Clean up if needed

### Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is debt. |
| "TDD will slow me down" | TDD faster than debugging. |
| "Existing code has no tests" | Add tests for existing code you're improving. |

### Red Flags - STOP
- Code before test
- Test passes immediately
- "I already manually tested it"
- Rationalizing "just this once"
