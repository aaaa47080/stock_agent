# Memory System Phase 1.5 - Workspace Isolation

**Date:** 2026-03-18
**Status:** In Progress

## Identity model

- `user_id`
  Canonical ownership boundary for long-term memory, facts, compacted tool results, and permission checks.
- `session_id`
  Conversation/thread boundary. Used for manager state and chat flow separation.
- `workspace_id`
  Optional higher-level collaboration boundary for future shared or delegated work contexts.

## Current runtime contract

### Memory context cache

- Memory context remains **cross-session by default**.
- Cache keys are scoped by:
  - `user_id`
  - `workspace_id` when present
- `session_id` is excluded from memory-context cache keys unless a future feature explicitly needs per-session memory views.

### Compacted tool results

- Large tool outputs are stored with owner metadata.
- Owner metadata includes:
  - `owner_id`
  - derived owner scope namespace
- Retrieval checks current requester scope before returning full data.

## Namespace rules

Shared helper: `core/memory_scope.py`

- `scope_namespace(scope, include_session=False)`
  - default: `user:{user_id}` or `user:{user_id}|workspace:{workspace_id}`
  - when `include_session=True` and no workspace:
    `user:{user_id}|session:{session_id}`

## Why this shape

- Prevent cross-user leakage immediately.
- Keep current memory semantics stable.
- Avoid baking session-specific behavior into caches that are intentionally cross-session today.
- Leave a clear upgrade path for workspace-aware collaboration later.
