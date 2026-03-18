# Memory System Phase 1 — Design Spec

**Date:** 2026-03-18
**Status:** Approved
**Scope:** ToolResultCompactor + MemoryStore Redis Cache

---

## Problem Statement

This platform serves multiple concurrent users. Two bottlenecks exist today:

1. **Context window overflow** — `create_react_agent` accumulates tool results directly in LangGraph message state. A single yfinance K-line fetch (200 rows) ≈ 4,000 tokens. With multi-tool ReAct loops, context blows up fast.

2. **PostgreSQL write pressure** — `MemoryStore.get_memory_context()` hits PostgreSQL on every agent turn (intent understanding + response generation = 2× per request). Under concurrent load this creates DB contention.

---

## Solution Overview

### Part A: ToolResultCompactor

Wrap every LangChain tool handler before it is registered with `create_react_agent`. Large outputs are stored in Redis and replaced with a compact summary + UUID reference in the message stream.

```
tool.invoke(args)
    │
    ▼
output = raw result (any size)
    │
    ├─ len(output) ≤ 2000 chars? → return as-is
    │
    └─ len(output) > 2000 chars?
           │
           ├─ generate compact summary (first 500 chars + stats line)
           ├─ store full output → Redis  key="tr:{uuid}"  TTL=3600s
           └─ return "[COMPACTED:{uuid}]\n{summary}\n[Full data stored. Key: {uuid}]"
```

**Attach point:** `BaseReActAgent._get_tool_metas()` — for each `ToolMetadata` in the result, create a **new** `ToolMetadata` (via `dataclasses.replace`) with a wrapped handler. The registry's original object is never mutated, preventing double-wrapping on repeated calls.

**Retrieval:** A new `tool_result_retrieve` LangChain tool is registered for all agents. The LLM can call it with a UUID to fetch full data if needed. This is optional — most analysis tasks only need the summary.

### Part B: MemoryStore Redis Cache

Add a 3-layer cache to `MemoryStore`, mirroring the existing pattern in `core/database/system_config.py`.

```
get_memory_context(user_id)
    │
    ├─ L1: TTLCache[30s] (in-process)   → hit → return
    │
    ├─ L2: Redis  key="mem:{user_id}"  TTL=120s  → hit → warm L1 → return
    │
    └─ L3: PostgreSQL (user_memory + user_facts)  → warm L1+L2 → return

write_long_term / write_facts / append_history
    └─ after DB write → invalidate L1+L2 for this user_id
```

**Redis client:** **synchronous** (`redis.from_url`) — MemoryStore methods are called from both async endpoints and thread executors; a sync client avoids event-loop conflicts. Same pattern as `core/database/system_config.py`.
**Serialization:** `orjson` — already a dependency.
**Key namespace:** `mem:` — distinct from `mkt:` (market cache) and `config:` (system config).

---

## Files Affected

| Action | File | Purpose |
|--------|------|---------|
| Create | `core/agents/tool_compactor.py` | Compactor logic + Redis store/retrieve |
| Modify | `core/agents/base_react_agent.py` | Wrap tools in `_get_tool_metas()` |
| Modify | `core/agents/bootstrap.py` | Register `tool_result_retrieve` tool for all agents |
| Modify | `core/database/memory.py` | Add L1+L2 cache to read/write methods |
| Create | `tests/test_tool_compactor.py` | Unit tests for compactor |
| Create | `tests/test_memory_cache.py` | Unit tests for memory cache layer |

---

## Constraints

- **No new dependencies** — uses `redis`, `cachetools`, `orjson` already in requirements.txt
- **Graceful degradation** — if Redis is unavailable, compactor skips storage (returns full output), memory falls back to PostgreSQL direct read
- **Backward compatibility** — existing tool return shapes are unchanged for outputs ≤ 2000 chars
- **Multi-user safe** — Redis keys are namespaced by `user_id` for memory; tool results use random UUIDs

---

## Success Criteria

- Tool outputs > 2000 chars replaced by compact reference in LangGraph messages
- `get_memory_context()` served from Redis on second call within 120s
- All existing agent tests pass
- New unit tests ≥ 80% coverage for both modules
