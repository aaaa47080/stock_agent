---
name: agentic-engineering
description: Use when building or debugging LangGraph multi-agent systems - eval-first execution, task decomposition, model routing by complexity, and cost discipline
---
## Agentic Engineering

For engineering workflows where AI agents perform most implementation work and humans enforce quality.

### Operating Principles
1. Define completion criteria before execution
2. Decompose work into agent-sized units (15-min rule)
3. Route model tiers by task complexity
4. Measure with evals and regression checks

### Model Routing
| Task Complexity | Model Tier | Examples |
|----------------|-----------|---------|
| Classification, boilerplate, narrow edits | Fast/cheap | Tag routing, format conversion |
| Implementation and refactors | Standard | API endpoints, DB queries, tests |
| Architecture, root-cause, multi-file invariants | Powerful | ORM design, security review, debugging |

### Task Decomposition (15-min unit rule)
- Each unit: independently verifiable, single dominant risk, clear done condition
- Closely-coupled units: same session
- Phase transitions: start fresh session

### Review Focus for AI-Generated Code
Prioritize (don't waste cycles on style):
- Invariants and edge cases
- Error boundaries and rollback
- Security and auth assumptions
- Hidden coupling and rollout risk

### Cost Discipline
Track per task: model, token estimate, retries, wall-clock, success/failure.
Escalate model tier only when lower tier fails with clear reasoning gap.

### Session Strategy
- Compact after milestone completion, not during active debugging
- Continue session for closely-coupled units
- Start fresh after major phase transitions
