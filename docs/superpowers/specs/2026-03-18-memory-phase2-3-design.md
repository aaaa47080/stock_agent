# Memory System Phase 2 + 3 Design Spec

**Date:** 2026-03-18
**Status:** Approved
**Builds on:** Phase 1 (ToolResultCompactor + 3-layer MemoryStore cache, committed `f21dc4c`)
**Reference:** [ReMe](https://github.com/agentscope-ai/ReMe), [PageIndex](https://github.com/VectifyAI/PageIndex)

---

## Goal

Make the chatbot feel like it genuinely remembers you and gets smarter over time:

- **Phase 2** — Long sessions stay coherent: when context grows large, replace raw truncated history with a structured compact state (Goal / Progress / Open Questions / Next Steps) without blocking the response.
- **Phase 3** — The system learns from trajectories: after each task, record what worked and what failed; inject the most relevant past experiences before the planner decides.

Phase 4 (Daily Journal / Operator Reporting) is **deferred** — the data exists in Phase 3 tables; direct SQL queries are sufficient at current scale. See Future TODOs.

---

## Design Principles

1. **Extend, don't rewrite** — All new behaviour is added to existing hooks (`_track_conversation`, `_background_memory_consolidation`, `MemoryStore`, `_CompactingToolWrapper`).
2. **Never block the response** — All writes (compact state, experiences, tool stats) are `asyncio.create_task` fire-and-forget.
3. **Degrade gracefully** — Every new read path has a fallback: if compact state is missing, fall back to `get_compressed_history()`; if experience retrieval fails, skip injection silently.
4. **Storage in PostgreSQL** — No local file IO. All persistent data lives in PostgreSQL. Redis is the hot cache layer only.

---

## Phase 2 — CompactedSessionState + Context Budget

### Problem

`get_compressed_history(max_turns=10)` truncates each message at 200 chars and keeps 10 turns. For long sessions this loses important context; for short sessions it wastes space. There is no character budget enforcing a hard ceiling, and no structured summary of *what the session is about*.

### New Data Structure

```python
@dataclass
class CompactedSessionState:
    goal: str            # what the user is trying to achieve this session
    progress: str        # what has been resolved so far
    open_questions: str  # unresolved threads
    next_steps: str      # suggested next actions
    turn_index: int      # compacted up to this turn
    updated_at: str      # ISO timestamp
```

### Storage (reuses existing L2→L3 pattern)

| Layer | Key / Location | TTL |
|-------|---------------|-----|
| Redis (L2) | `session_compact:{user_id}:{session_id}` | 2 hr |
| PostgreSQL (L3) | `user_memory` table, `memory_type='session_compact'`, `session_id=actual_session_id` | permanent |

Read order: Redis hit → return immediately; miss → read PostgreSQL → backfill Redis.
Write: background task writes PostgreSQL first, then sets Redis.

### Context Budget

New constant: `CONTEXT_CHAR_BUDGET = 6000` (chars allocated to history slot in the manager prompt).

New module `core/agents/context_budget.py`:
- `count_history_chars(history: str) -> int`
- `history_exceeds_budget(history: str) -> bool`
- `get_history_for_prompt(manager_self) -> str`
  - if `len(raw_history) <= CONTEXT_CHAR_BUDGET` → return raw (existing behaviour)
  - else → read `compact_state`; if available → render as compact block; else → fallback to `get_compressed_history()`

### Integration Points

**`core/agents/manager.py`**
- Replace direct `get_compressed_history()` call in `_understand_intent_node()` with `_get_history_for_prompt()`
- Extend `_do_consolidation()`: LLM prompt requests an additional `compact_state` JSON field; on success, call `memory_store.write_compact_state(compact_state)`

**`core/database/memory.py`**
- Add `read_compact_state(session_id) -> Optional[CompactedSessionState]`
- Add `write_compact_state(state: CompactedSessionState, session_id) -> None` (async-safe, background)
- **session_id must be snapshotted at task creation time** (not read from `self.session_id` at write time): `sid = self.session_id; asyncio.create_task(_write(sid, state))`

**`MemoryStore.consolidate()` prompt extension**
Existing output: `{ "history_entry": "...", "memory_update": "..." }`
New output:
```json
{
  "history_entry": "...",
  "memory_update": "...",
  "compact_state": {
    "goal": "...",
    "progress": "...",
    "open_questions": "...",
    "next_steps": "..."
  }
}
```

### Success Criteria

- [ ] Sessions > `CONTEXT_CHAR_BUDGET` chars inject compact state instead of raw history
- [ ] Compact state written asynchronously; response latency unaffected
- [ ] Redis miss → PostgreSQL fallback → Redis backfill works correctly
- [ ] Server restart recovers compact state from PostgreSQL
- [ ] Budget check falls back gracefully when no compact state exists yet

---

## Phase 3 — Task/Experience Memory + Tool Memory

### Problem

The agent has no memory of past task trajectories. It cannot learn "when user asks about BTC with this phrasing, `tw_technical` always fails because market is closed" or "this tool consistently times out on large requests".

### New Tables

#### `task_experiences`
```sql
CREATE TABLE IF NOT EXISTS task_experiences (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    task_family     TEXT NOT NULL,        -- 'crypto'|'tw_stock'|'us_stock'|'forex'|'commodity'|'chat'
    query_text      TEXT NOT NULL,
    query_tsv       TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', query_text)) STORED,
    tools_used      TEXT[],               -- array of tool names
    agent_used      TEXT,
    outcome         TEXT NOT NULL,        -- 'success'|'failure'|'partial'
    quality_score   REAL,                 -- 0.0–1.0; mapped from AgentResult.quality: "pass"→1.0, "fail"→0.0, None→NULL
    failure_reason  TEXT,
    response_chars  INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_te_user_family   ON task_experiences(user_id, task_family);
CREATE INDEX idx_te_created       ON task_experiences(created_at DESC);
CREATE INDEX idx_te_tsv           ON task_experiences USING GIN(query_tsv);
```

#### `tool_execution_stats`
```sql
CREATE TABLE IF NOT EXISTS tool_execution_stats (
    id           BIGSERIAL PRIMARY KEY,
    user_id      TEXT,                    -- NULL = global stat
    tool_name    TEXT NOT NULL,
    success      BOOLEAN NOT NULL,
    latency_ms   INT,
    output_chars INT,
    error_type   TEXT,                    -- 'timeout'|'api_error'|'parse_error'|NULL
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tes_tool_created ON tool_execution_stats(tool_name, created_at DESC);
CREATE INDEX idx_tes_user_tool    ON tool_execution_stats(user_id, tool_name);
```

### Write Paths (all fire-and-forget)

**task_experiences** — hooked into `_track_conversation()` after tools_used is known:
```python
asyncio.create_task(
    self._record_experience_background(query, tools_used, agent_result)
)
```

**tool_execution_stats** — hooked into `_CompactingToolWrapper.invoke()`:
```python
# records tool_name, success, latency_ms, output_chars before returning
asyncio.create_task(_record_tool_stat_async(...))
```

Note: `_CompactingToolWrapper.invoke()` is synchronous and called from within an already-running event loop. Do NOT use `run_coroutine_threadsafe()` (that is for off-loop threads only). Instead: collect `(tool_name, success, latency_ms, output_chars, error_type)` inside `invoke()`, store them in a return-side tuple or instance-level accumulator, then let the async caller (`manager._record_experience_background`) schedule `asyncio.create_task(_record_tool_stat_async(...))` after `invoke()` returns. This is the same fire-and-forget pattern already used in `_track_conversation`.

### 3-Layer Retrieval

Called once per turn in `_understand_intent_node()`, before assembling the planner prompt. Result is injected as a compact hint block.

```
Layer 1 + 2 — Combined SQL query (~5ms total, single round-trip)
  SELECT *, ts_rank(query_tsv, plainto_tsquery('simple', $current_query)) AS rank
  FROM task_experiences
  WHERE user_id = $user_id            -- mandatory, non-nullable
    AND task_family = $detected_family
    AND user_id IS NOT NULL           -- guards against anonymous rows
  ORDER BY rank DESC, created_at DESC
  LIMIT 5

Layer 3 — LLM re-rank (optional, only if Layer 2 returns ≥ 2 candidates)
  Pass top-5 to LLM with instruction:
  "Select the 1-2 most relevant past experiences for the current query."
  → inject into planner prompt as hint block
```

Layer 3 is skipped if < 2 candidates (avoids unnecessary LLM call).

### Injection Format (minimal token footprint)

```
## 相關過去經驗（僅供參考）
- [crypto, 3天前] BTC技術分析 → 工具: get_crypto_price+technical_analysis → 成功
- [tw_stock, 1週前] 台積電查詢 → 工具: tw_price → 失敗: 盤後無K線
```

### New File

`core/database/experiences.py` — `ExperienceStore`:
- `record_experience(user_id, session_id, task_family, query, tools, agent, outcome, quality, failure_reason, response_chars)`
- `record_tool_stat(user_id, tool_name, success, latency_ms, output_chars, error_type)`
- `retrieve_relevant(user_id, task_family, query, limit=5) -> List[Dict]` — implements all 3 layers
- `_layer1_2_query()` — single combined SQL (layers 1+2 composed, one round-trip)
- `_layer3_llm_rerank()`

### Success Criteria

- [ ] task_experiences written after every agent turn, non-blocking
- [ ] tool_execution_stats written after every tool invocation
- [ ] Layer 1+2 retrieval completes in < 20ms
- [ ] Layer 3 LLM re-rank skipped when < 2 candidates
- [ ] Injection appears in planner prompt when relevant experiences exist
- [ ] Graceful fallback: retrieval failure → no injection, no error propagation
- [ ] One user's experiences not retrievable by another user (test: user_id isolation + user_id=NULL edge case)

---

## Future TODOs (not in this spec)

These items are recorded here to be actionable in future sessions.

| Item | Rationale | Trigger |
|------|-----------|---------|
| **Embedding-based retrieval** (replace Layer 2 FTS) | Better semantic matching for Phase 3 retrieval, especially cross-language queries | When false-negative rate on experience retrieval becomes noticeable |
| **Phase 4: Operator stats API** `GET /admin/stats?date=YYYY-MM-DD` | Direct PostgreSQL query over task_experiences + tool_execution_stats | When system has > 100 daily active users |
| **Phase 4: Pre-aggregated daily_stats table** | Avoid expensive real-time aggregation queries under high load | When query latency on stats endpoint > 500ms |
| **tool_execution_stats global aggregation** | Tool health dashboard across all users | When operating multiple tenants |
| **Experience decay policy** | Old/low-quality experiences should outweigh recent validated ones less | When Phase 3 retrieval quality degrades over time |

---

## File Map

| Action | Path | What changes |
|--------|------|-------------|
| Create | `core/agents/context_budget.py` | char budget constants + `get_history_for_prompt()` |
| Modify | `core/database/memory.py` | add `read_compact_state()`, `write_compact_state()` |
| Modify | `core/agents/manager.py` | wire `_get_history_for_prompt()`, `_record_experience_background()` |
| Modify | `core/agents/tool_compactor.py` | add tool stat recording hook |
| Modify | `core/database/memory.py` | extend `consolidate()` prompt + parse `compact_state` output |
| Modify | `core/database/schema.py` | add `task_experiences`, `tool_execution_stats` table creation |
| Create | `core/database/experiences.py` | `ExperienceStore` with all 3 retrieval layers |
| Create | `tests/test_context_budget.py` | budget check + compact state read/write/fallback tests |
| Create | `tests/test_experiences.py` | record + retrieve + isolation tests |
