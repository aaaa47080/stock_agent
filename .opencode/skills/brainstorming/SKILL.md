---
name: brainstorming
description: Use before any creative work - creating features, building components, modifying behavior. Explores intent, requirements and design before implementation
---
## Brainstorming Ideas Into Designs

### Hard Gate
Do NOT write any code, scaffold any project, or take any implementation action until design is approved.

### Checklist
1. **Explore project context** - check files, docs, recent commits
2. **Ask clarifying questions** - one at a time, understand purpose/constraints/success criteria
3. **Propose 2-3 approaches** - with trade-offs and recommendation
4. **Present design** - in sections scaled to complexity, get approval after each
5. **Write design doc** - save to `docs/specs/YYYY-MM-DD-<topic>-design.md`

### Process
- Check current project state first
- If request covers multiple independent subsystems, flag and decompose first
- Ask questions one at a time, prefer multiple choice
- Focus on: purpose, constraints, success criteria
- Propose 2-3 approaches, lead with recommendation
- Present design in sections, approve each before moving on
- Cover: architecture, components, data flow, error handling, testing

### Design Principles
- Break into smaller units with one clear purpose each
- Well-defined interfaces between units
- Each unit independently understandable and testable
- Can you change internals without breaking consumers?

### Working in Existing Codebases
- Explore current structure before proposing changes
- Follow existing patterns
- Include targeted improvements only where they affect the work
- Don't propose unrelated refactoring

### Key Principles
- One question at a time
- YAGNI ruthlessly
- Explore alternatives before settling
- Incremental validation - approve before moving on
