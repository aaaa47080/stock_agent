---
name: self-improvement
description: "Captures learnings, errors, and corrections for continuous improvement. Use when: (1) A command fails unexpectedly, (2) User corrects the agent, (3) User requests a missing capability, (4) An external API fails, (5) Agent knowledge is outdated, (6) A better approach is discovered. Review learnings before major tasks."
---

# Self-Improvement Skill

Log learnings and errors to markdown files. Coding agents can later process these into fixes, and important learnings get promoted to project memory.

## Quick Reference

| Situation | Action |
|-----------|--------|
| Command/operation fails | Log to `.learnings/ERRORS.md` |
| User corrects you | Log to `.learnings/LEARNINGS.md` with category `correction` |
| User wants missing feature | Log to `.learnings/FEATURE_REQUESTS.md` |
| API/external tool fails | Log to `.learnings/ERRORS.md` with integration details |
| Knowledge was outdated | Log to `.learnings/LEARNINGS.md` with category `knowledge_gap` |
| Found better approach | Log to `.learnings/LEARNINGS.md` with category `best_practice` |
| Similar to existing entry | Link with `**See Also**`, consider priority bump |
| Broadly applicable learning | Promote to `AGENTS.md` |

## Setup

Create the learnings directory in your project:
```bash
mkdir -p .learnings
```

Create log files (or copy from project root):
- `LEARNINGS.md` — corrections, knowledge gaps, best practices
- `ERRORS.md` — command failures, exceptions
- `FEATURE_REQUESTS.md` — user-requested capabilities

## Logging Format

### Learning Entry (append to `.learnings/LEARNINGS.md`)

```markdown
## [LRN-YYYYMMDD-XXX] category

**Logged**: ISO-8601 timestamp
**Priority**: low | medium | high | critical
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### Summary
One-line description of what was learned

### Details
Full context: what happened, what was wrong, what's correct

### Suggested Action
Specific fix or improvement to make

### Metadata
- Source: conversation | error | user_feedback
- Related Files: path/to/file.ext
- Tags: tag1, tag2
- See Also: LRN-20250110-001 (if related to existing entry)
```

### Error Entry (append to `.learnings/ERRORS.md`)

```markdown
## [ERR-YYYYMMDD-XXX] skill_or_command_name

**Logged**: ISO-8601 timestamp
**Priority**: high
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### Summary
Brief description of what failed

### Error
```
Actual error message or output
```

### Context
- Command/operation attempted
- Input or parameters used
- Environment details if relevant

### Suggested Fix
If identifiable, what might resolve this

### Metadata
- Reproducible: yes | no | unknown
- Related Files: path/to/file.ext
```

### Feature Request Entry (append to `.learnings/FEATURE_REQUESTS.md`)

```markdown
## [FEAT-YYYYMMDD-XXX] capability_name

**Logged**: ISO-8601 timestamp
**Priority**: medium
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### Requested Capability
What the user wanted to do

### User Context
Why they needed it, what problem they're solving

### Suggested Implementation
How this could be built, what it might extend

### Metadata
- Frequency: first_time | recurring
```

## ID Generation

Format: `TYPE-YYYYMMDD-XXX`
- TYPE: `LRN` (learning), `ERR` (error), `FEAT` (feature)
- YYYYMMDD: Current date
- XXX: Sequential number (e.g., `001`)

## Resolving Entries

When an issue is fixed, update the entry:
1. Change `**Status**: pending` → `**Status**: resolved`
2. Add resolution block:
```markdown
### Resolution
- **Resolved**: 2025-01-16T09:00:00Z
- **Commit/PR**: abc123 or #42
- **Notes**: Brief description
```

## Promoting to Project Memory

When a learning is broadly applicable (not a one-off fix), promote it to `AGENTS.md`.

### When to Promote
- Learning applies across multiple files/features
- Knowledge any contributor (human or AI) should know
- Prevents recurring mistakes

### How to Promote
1. **Distill** the learning into a concise rule or fact
2. **Add** to appropriate section in `AGENTS.md`
3. **Update** original entry: `**Status**: pending` → `**Status**: promoted

### Promotion Example

**Learning** (verbose):
> Project uses pnpm workspaces. Attempted `npm install` but failed.

**In AGENTS.md** (concise):
```markdown
## Build & Dependencies
- Package manager: pnpm (not npm) - use `pnpm install`
```

## Recurring Pattern Detection

1. **Search first**: `grep -r "keyword" .learnings/`
2. **Link entries**: Add `**See Also**: ERR-20250110-001`
3. **Bump priority** if issue keeps recurring
4. **Consider systemic fix**: Recurring issues indicate missing documentation → promote to `AGENTS.md`

## Detection Triggers

**Corrections** (→ learning with `correction` category):
- "No, that's not right..."
- "Actually, it should be..."
- "That's outdated..."

**Feature Requests** (→ feature request):
- "Can you also..."
- "I wish you could..."
- "Is there a way to..."

**Knowledge Gaps** (→ learning with `knowledge_gap` category):
- User provides information you didn't know
- Documentation you referenced is outdated

**Errors** (→ error entry):
- Command returns non-zero exit code
- Exception or stack trace
- Timeout or connection failure

## Priority Guidelines

| Priority | When to Use |
|----------|-------------|
| `critical` | Blocks core functionality, data loss risk, security issue |
| `high` | Significant impact, affects common workflows, recurring issue |
| `medium` | Moderate impact, workaround exists |
| `low` | Minor inconvenience, edge case |

## Periodic Review

Review `.learnings/` before starting major tasks or after completing features:
```bash
grep -h "Status\*\*: pending" .learnings/*.md | wc -l
grep -B5 "Priority\*\*: high" .learnings/*.md | grep "^## \["
```
