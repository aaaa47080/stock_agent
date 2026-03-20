---
name: writing-skills
description: Use when creating new skills or editing existing skills - follow TDD for documentation
---
## Writing Skills

Skills are reusable technique guides in `.opencode/skills/<name>/SKILL.md`.

### SKILL.md Structure
```markdown
---
name: skill-name-with-hyphens
description: Use when [specific triggering conditions, not workflow summary]
---
## Overview
Core principle in 1-2 sentences.

## When to Use
Symptoms and use cases. When NOT to use.

## Core Pattern
Before/after or step-by-step.

## Quick Reference
Table for scanning common operations.

## Common Mistakes
What goes wrong + fixes.
```

### Naming
- Use letters, numbers, hyphens only
- Verb-first, gerunds work well: `using-git-worktrees`, `executing-plans`
- Description starts with "Use when..." and includes specific triggers

### Description = When to Use (NOT What It Does)
```yaml
# BAD: summarizes workflow
description: Dispatch subagent per task with review between tasks

# GOOD: triggering conditions only
description: Use when executing implementation plans with independent tasks
```

### Key Principles
- **One excellent example** beats many mediocre ones
- **Keep concise**: <500 words for most skills
- **No narrative storytelling** - techniques and patterns only
- **Project-specific** > generic (reference AGENTS.md, our commands, our conventions)
- **Cross-reference** other skills instead of repeating

### Checklist
- [ ] Name: letters, numbers, hyphens only
- [ ] Frontmatter: name + description (max 1024 chars)
- [ ] Description: "Use when..." + specific triggers
- [ ] Overview: core principle
- [ ] Quick reference table
- [ ] Common mistakes section
- [ ] No narrative/storytelling
