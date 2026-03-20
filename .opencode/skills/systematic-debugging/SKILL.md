---
name: systematic-debugging
description: Use when encountering any bug, test failure, build error, or unexpected behavior - 4-phase root cause process before proposing fixes
---
## Systematic Debugging

### The Iron Law
```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

### Phase 1: Root Cause Investigation
1. **Read error messages carefully** - stack traces, line numbers, error codes
2. **Reproduce consistently** - exact steps, every time?
3. **Check recent changes** - `git diff`, recent commits, new dependencies
4. **Gather evidence in multi-component systems** - log data at each component boundary (API -> service -> DB)
5. **Trace data flow backward** - where does bad value originate? Keep tracing up until source

### Phase 2: Pattern Analysis
1. Find working examples in codebase - what works that's similar?
2. Compare against references - read reference implementation COMPLETELY
3. Identify differences - list EVERY difference, however small
4. Understand dependencies - what settings, config, environment?

### Phase 3: Hypothesis and Testing
1. Form single hypothesis: "I think X is the root cause because Y"
2. Test minimally - ONE variable at a time
3. Verify - did it work? No -> form NEW hypothesis
4. Don't pretend to know - say "I don't understand X" and research more

### Phase 4: Implementation
1. **Create failing test case first** - simplest reproduction, automated if possible
2. Implement single fix - ONE change, no "while I'm here" improvements
3. Verify - test passes? No other tests broken? Issue resolved?
4. **If 3+ fixes failed** - STOP. Question architecture. Discuss with human.

### Red Flags - STOP
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- Proposing solutions before tracing data flow
- Each fix reveals new problem in different place

### Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| 1. Root Cause | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY |
| 2. Pattern | Find working examples, compare | Identify differences |
| 3. Hypothesis | Form theory, test minimally | Confirmed or new hypothesis |
| 4. Implementation | Create test, fix, verify | Bug resolved, tests pass |
