---
name: push-and-verify
description: Push to remote and wait for CI to pass. If CI fails, read logs, fix bugs, and re-push. Repeat until green.
---

## Push & Verify Workflow

This skill MUST be followed after every `git push`. A push is NOT complete until all CI workflows pass.

### Workflow

#### Step 1: Push

```bash
git push origin <branch>
```

#### Step 2: Wait for CI to trigger (10 seconds)

```bash
sleep 10
```

#### Step 3: Poll CI run status

Poll every 30 seconds until the run completes (timeout 10 minutes):

```bash
# Get the latest run ID for the push
gh run list --limit 3 --json databaseId,headBranch,name,status,conclusion

# Check status of a specific run
gh run view <RUN_ID> --json status,conclusion
```

#### Step 4: If all workflows PASS

Report success to user with workflow names and conclusion.

**Done.**

#### Step 5: If any workflow FAILS

Immediately fetch the failed logs:

```bash
gh run view <RUN_ID> --log-failed
```

Analyze the logs and classify the failure:

| Failure Type | Action |
|---|---|
| **Lint (ruff)** | Fix the reported file:line, run `ruff check .` locally to verify, commit, push |
| **Test failure** | Read the test output, reproduce locally with `pytest <test_file>::<test_func> -v`, fix, push |
| **Install failure** | Check `requirements.txt` or workflow `pip install` step, fix, push |
| **Workflow syntax** | Fix the `.github/workflows/*.yml` file, push |
| **Flaky / infra** | Re-run the failed job: `gh run rerun <RUN_ID> --failed` |

#### Step 6: After fixing, go back to Step 1

Repeat the push → poll → verify cycle until ALL workflows pass.

### Rules

1. **NEVER** consider a task done after pushing without verifying CI passes
2. **NEVER** push more than 3 times without stopping to reassess approach
3. Always report which workflows passed/failed to the user
4. If CI fails 3 times on the same push, stop and ask the user for help
5. Maximum poll timeout: 10 minutes per workflow run
6. Use `--log-failed` not `--log` to reduce noise — only read what failed

### CI Workflows to Monitor

| Workflow | Trigger | What to check |
|---|---|---|
| **CI** (`ci.yml`) | push/PR to main | lint + test + validate-json |
| **Test Suite** (`test-suite.yml`) | push/PR to main | python-tests + e2e-tests |
| **E2E Tests** (`e2e.yml`) | push to main | playwright e2e |
| **Dependency Audit** (`dependency-weekly-audit.yml`) | weekly cron | lockfile freshness (skip for daily pushes) |

### Quick Reference

```bash
# List latest runs
gh run list --limit 5

# View specific run details
gh run view <RUN_ID>

# Get failed logs only
gh run view <RUN_ID> --log-failed

# Re-run failed jobs
gh run rerun <RUN_ID> --failed

# Watch a run in real-time
gh run watch <RUN_ID>
```
