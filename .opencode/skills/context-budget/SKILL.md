---
name: context-budget
description: Use when session feels sluggish, output quality degrading, or after adding many skills/agents. Analyzes context window consumption
---
## Context Budget

### When to Use
- Session performance feels sluggish or output quality is degrading
- Recently added many skills or agents
- Planning to add more components and need to know if there's room
- Context utilization approaching 80%+ for large tasks

### Context Budget Rules
- **Avoid last 20% of context window** for large refactoring and multi-file features
- **Lower-sensitivity tasks** (single edits, docs, simple fixes) tolerate higher utilization
- **80% utilization** is the warning threshold for complex tasks
- **90%+** = stop and compact

### Optimization Strategies

#### 1. Strategic Compact
- After completing a milestone, before starting new work
- After exploration, before execution
- Before major context shifts

#### 2. Skill Selection
- Only load skills relevant to current task
- Don't load all skills preemptively
- Prefer specific skills over broad ones

#### 3. Agent Context
- Provide only the context each subagent needs
- Don't pass entire session history to subagents
- Extract relevant sections, not full files

#### 4. Reading Strategy
- Use `limit` and `offset` instead of reading entire files
- Use `grep` to find specific patterns before reading
- Use `glob` to locate files before reading

### Quick Check
If responses are getting shorter, less accurate, or ignoring instructions:
1. Check how many files/messages are in context
2. Compact at a logical boundary
3. Resume with focused context
