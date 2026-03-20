---
name: executing-plans
description: Use when you have a written implementation plan to execute with review checkpoints between tasks
---
## Executing Plans

### Step 1: Load and Review
1. Read plan file
2. Review critically - identify questions or concerns
3. If concerns: raise before starting
4. If clear: create TodoWrite and proceed

### Step 2: Execute Tasks
For each task:
1. Mark as in_progress
2. Follow each step exactly (plans have bite-sized steps)
3. Run verifications as specified
4. Run lint: `ruff check .`
5. Run tests: `.venv\Scripts\python.exe -m pytest --no-cov -q`
6. Mark as completed

### Step 3: Review Checkpoints
After every 3 tasks (or after complex tasks):
1. Run full test suite
2. Run `git diff` to review changes
3. Report progress to DANNY

### Step 4: Complete
After all tasks:
- Use `finishing-a-dev-branch` skill
- Verify tests, present merge/PR/keep/discard options

### When to Stop
- Hit a blocker (missing dependency, test fails, unclear instruction)
- Plan has critical gaps
- Verification fails repeatedly
- Ask for clarification rather than guessing
