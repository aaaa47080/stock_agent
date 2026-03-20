---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Creates bite-sized implementation plans
---
## Writing Plans

Write implementation plans assuming the engineer has zero context for the codebase. Document everything: which files, code, testing, how to verify. Bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

### File Structure
Before defining tasks, map out which files will be created/modified and what each is responsible for. Design units with clear boundaries and well-defined interfaces.

### Bite-Sized Task Granularity
Each step is one action (2-5 minutes):
- "Write the failing test"
- "Run it to make sure it fails"
- "Implement the minimal code to make the test pass"
- "Run the tests and make sure they pass"
- "Commit"

### Task Template
````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**
```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

### Rules
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits
