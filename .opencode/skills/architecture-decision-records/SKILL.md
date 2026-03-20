---
name: architecture-decision-records
description: Use when making or recording significant architectural decisions - capture context, alternatives, and rationale as structured ADRs
---
## Architecture Decision Records

### When to Activate
- User chooses between significant alternatives (framework, DB, API design, auth strategy)
- User says "let's record this decision" or "ADR this"
- During planning phases when architectural trade-offs are discussed
- User asks "why did we choose X?"

### ADR Format
```markdown
# ADR-NNNN: [Decision Title]

**Date**: YYYY-MM-DD
**Status**: proposed | accepted | deprecated | superseded by ADR-NNNN

## Context
[2-5 sentences: the problem motivating this decision]

## Decision
[1-3 sentences: the choice made]

## Alternatives Considered
### Alternative 1: [Name]
- **Pros**: ...
- **Cons**: ...
- **Why not**: ...

## Consequences
### Positive
- ...
### Negative
- ...
```

### Workflow
1. If `docs/adr/` doesn't exist, ask user before creating
2. Extract core architectural choice
3. Document alternatives and why they were rejected
4. Assign number (increment from existing)
5. Present draft for approval before writing
6. Update `docs/adr/README.md` index

### Categories Worth Recording
| Category | Examples |
|----------|---------|
| Technology choices | Framework, database, cloud provider |
| Architecture patterns | Monolith vs microservices, event-driven |
| API design | REST vs GraphQL, auth mechanism |
| Data modeling | Schema design, caching strategy |
| Infrastructure | Deployment model, CI/CD pipeline |
| Security | Auth strategy, encryption approach |
| Testing | Test framework, coverage targets |
| Process | Branching strategy, review process |

### ADR Lifecycle
```
proposed → accepted → [deprecated | superseded by ADR-NNNN]
```

### Quick Reference
- Be specific: "Use Prisma ORM" not "use an ORM"
- Record the WHY, not just the WHAT
- Include rejected alternatives
- Keep under 2 minutes reading time
- Don't record trivial decisions
