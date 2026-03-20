---
name: receiving-code-review
description: Use when receiving code review feedback - verify before implementing, ask before assuming, technical correctness over social comfort
---
## Receiving Code Review

### Response Pattern
```
1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS project?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

### Forbidden
- "You're absolutely right!" (performative)
- "Great point!" / "Thanks!" (gratitude expressions)
- "Let me implement that now" (before verification)

### Instead
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

### Unclear Feedback
If ANY item is unclear: STOP. Ask for clarification on ALL unclear items before implementing.
Partial understanding = wrong implementation.

### Implementation Order
1. Clarify anything unclear FIRST
2. Blocking issues (breaks, security)
3. Simple fixes (typos, imports)
4. Complex fixes (refactoring, logic)
5. Test each fix individually

### When to Push Back
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Conflicts with DANNY's prior decisions

### If You Were Wrong
"Verified this and you're correct. Fixing now."
State factually and move on. No apologies.
