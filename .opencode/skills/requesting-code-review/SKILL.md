---
name: requesting-code-review
description: Use when completing tasks or implementing major features to verify work meets requirements before proceeding
---
## Requesting Code Review

### When
- After each task in subagent-driven development
- After completing a major feature
- Before merge to main

### How

**1. Get git SHAs:**
```bash
BASE_SHA=$(git log --oneline -2 | tail -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code-reviewer subagent:**
Use Task tool with `review` subagent_type. Provide:
- What was implemented
- Plan or requirements it should meet
- Base SHA and HEAD SHA
- Test results

**3. Act on feedback:**
- **Critical:** Fix immediately, block progress
- **Important:** Fix before proceeding to next task
- **Minor:** Note for later batch fix
- **Wrong feedback:** Push back with technical reasoning

### Integration
- **subagent-driven-development:** Review after EACH task
- **executing-plans:** Review after each batch (3 tasks)
- **Ad-hoc:** Review before merge
