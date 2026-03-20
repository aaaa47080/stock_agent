---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks - dispatch fresh subagent per task with two-stage review
---
## Subagent-Driven Development

Execute plan by dispatching fresh subagent per task, with two-stage review after each: spec compliance first, then code quality.

### Core Principle
Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration

### The Process
1. Read plan, extract all tasks with full text, create todo list
2. For each task:
   a. Dispatch implementer subagent with full task text + context
   b. Handle implementer status (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED)
   c. Dispatch spec reviewer - does code match spec?
   d. If issues -> implementer fixes -> re-review
   e. Dispatch code quality reviewer - is implementation well-built?
   f. If issues -> implementer fixes -> re-review
   g. Mark task complete
3. After all tasks: dispatch final code reviewer for entire implementation

### Implementer Status Handling
- **DONE**: Proceed to spec review
- **DONE_WITH_CONCERNS**: Read concerns, address if correctness-related, note observations
- **NEEDS_CONTEXT**: Provide missing context, re-dispatch
- **BLOCKED**: Assess - context problem? Re-dispatch. Too large? Break up. Plan wrong? Escalate to human.

### Red Flags - Never
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Let implementer self-review replace actual review
- Start code quality review before spec compliance passes
- Move to next task while either review has open issues

### Model Selection
- Mechanical tasks (1-2 files, clear spec) -> fast, cheap model
- Integration/judgment tasks (multi-file, debugging) -> standard model
- Architecture/design/review tasks -> most capable model
