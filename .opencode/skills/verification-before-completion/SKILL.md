---
name: verification-before-completion
description: Use before claiming work is complete, fixed, or passing. Requires running verification commands and confirming output before any success claims
---
## Verification Before Completion

### The Iron Law
```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

### The Gate Function
Before claiming any status:
1. **IDENTIFY** - What command proves this claim?
2. **RUN** - Execute the FULL command (fresh, complete)
3. **READ** - Full output, check exit code, count failures
4. **VERIFY** - Does output confirm the claim?
5. **ONLY THEN** - Make the claim

### Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Requirements met | Line-by-line checklist | Tests passing |

### Red Flags - STOP
- Using "should", "probably", "seems to"
- Expressing satisfaction before verification
- About to commit/push without verification
- Trusting agent success reports without checking
- ANY wording implying success without having run verification

### Patterns
```
Tests:
  [Run test command] [See: 34/34 pass] -> "All tests pass"
  "Should pass now" / "Looks correct"  -> WRONG

Build:
  [Run build] [See: exit 0] -> "Build passes"
  "Linter passed"               -> WRONG (linter != compiler)

Requirements:
  Re-read plan -> Create checklist -> Verify each -> Report gaps or completion
  "Tests pass, phase complete"   -> WRONG
```

Run the command. Read the output. THEN claim the result. Non-negotiable.
