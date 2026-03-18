# Memory System Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ToolResultCompactor and 3-layer MemoryStore cache to prevent context window overflow and reduce PostgreSQL read pressure under multi-user load.

**Architecture:** Wrap LangChain tool handlers (non-mutating wrapper class) to compress outputs > 2000 chars into Redis-backed references; add TTLCache → Redis → PostgreSQL layered reads to MemoryStore with invalidation on every write (including `append_history`). Both features degrade gracefully if Redis is unavailable.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, redis (sync, for thread-safe tool invocation), cachetools.TTLCache, orjson, PostgreSQL

**Spec:** `docs/superpowers/specs/2026-03-18-memory-phase1-design.md`

---

## Progress Tracker

- [x] Roadmap priority realigned for multi-user architecture
- [x] Phase 1 implemented: ToolResultCompactor
- [x] Phase 1 implemented: MemoryStore cache
- [x] Phase 1 integrated: BaseReActAgent tool wrapping + bootstrap retrieval tool
- [x] Phase 1 verified: targeted pytest suite + parse/import smoke checks
- [x] Phase 1.5 implemented: Workspace isolation hardening
- [ ] Phase 2 planned: Context compaction + async background summary
- [ ] Phase 3 planned: Task/Experience Memory + Tool Memory
- [ ] Phase 4 planned: Daily journal / operator reporting

**Status note:** Phase 1 and Phase 1.5 are implemented for the current architecture. Shared scope helpers, workspace-aware manager/memory wiring, ownership-checked tool-result retrieval, and cross-user/workspace tests are all in place.

---

## Roadmap Alignment Update (Multi-user Priority Order)

This file originally scoped only **Phase 1**. The platform direction is now explicitly **multi-user**, so priority must be based on:

1. risk of cross-user leakage
2. context/token pressure under concurrent load
3. DB / Redis cost under repeated reads and summaries
4. whether the feature creates reusable infrastructure for later memory types

### Recommended implementation order

| Priority | Capability | Why it moves earlier/later now |
|----------|------------|--------------------------------|
| P0 | Workspace isolation | Before adding richer memory, every cache key, compacted payload, memory row, and summary artifact must be tenant-scoped to avoid cross-user leakage. This becomes a prerequisite in a real multi-user platform. |
| P0 | ToolResultCompactor | Biggest immediate protection against context blow-up from yfinance / TWSE / long tool outputs. Also reduces repeated token replay across agents. |
| P0 | MemoryStore cache | Directly reduces repeated PostgreSQL reads on every turn. Highest infra ROI once multiple users are active. |
| P1 | Context Compaction | After output compaction + memory caching, compress the prompt state itself into Goal / Progress / Next Steps so long trajectories stay usable. |
| P1 | Async background summary | Important once compaction/summarisation exists, but should be built after state boundaries and invalidation rules are clear. |
| P2 | Task / Experience Memory | High product value, but should sit on top of isolated storage and compacted context; otherwise it amplifies noisy or unsafe memory. |
| P2 | Tool Memory | Useful for agent/tool selection and cost control, but depends on stable tool instrumentation and persisted execution traces first. |
| P3 | Daily journal | Nice-to-have reporting layer; overlaps with episodic/session summary and should not block the core memory architecture. |

### Why `Workspace isolation` moves up

The earlier comparison ranked workspace isolation low because the system is effectively single-user today. That ranking does **not** hold once this platform is intended for many users.

If we add Task Memory / Tool Memory / background summaries first, then later retrofit tenant isolation, we will need to:

- migrate Redis key layouts
- backfill or repartition stored artifacts
- re-audit every retrieval path for cross-user contamination
- retest every memory read/write/invalidation path

That retrofit is more expensive than introducing isolation boundaries first.

### Delivery phases after this document

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| Phase 1 | ToolResultCompactor + MemoryStore cache | Long tool results stop flooding context; repeated memory reads hit L1/L2 cache before PostgreSQL. |
| Phase 1.5 | Workspace isolation hardening | All memory/tool-result/cache artifacts are namespaced by `user_id` and, where needed, `session_id` / `workspace_id`; retrieval APIs cannot cross tenant boundaries. |
| Phase 2 | Context Compaction + Async background summary | Long-running sessions preserve only compact state (`Goal`, `Progress`, `Open Questions`, `Next Steps`) and summary writes no longer block the foreground turn. |
| Phase 3 | Task/Experience Memory + Tool Memory | The system learns from successful/failed trajectories and tool execution telemetry for better routing, retries, and cost control. |
| Phase 4 | Daily journal / operator reporting | Human-readable daily rollups built from existing episodic/task memory, without becoming a new source of truth. |

### Concrete recommendation

Do **not** treat the table's original "low value" label for workspace isolation as the final roadmap decision.

For this platform, the right sequence is:

1. Finish Phase 1 in this file.
2. Immediately harden workspace / tenant isolation.
3. Then build context compaction and async summary infrastructure.
4. Only after those foundations are stable, add Task/Experience Memory and Tool Memory.
5. Leave Daily journal for the end.

---

## Phase 1.5 Plan: Workspace Isolation Hardening

**Goal:** Make every memory and compaction artifact tenant-safe before higher-level memory features are added.

**Why now:** Once the platform is multi-user, isolation is no longer a low-priority enhancement. It is a safety prerequisite for every later memory capability.

### Success criteria

- [x] Every Redis key for memory and compaction now uses a shared tenant namespace helper.
- [x] Current summary / consolidation paths were audited; no separate Redis summary store exists yet.
- [x] Retrieval APIs verify ownership before returning stored artifacts.
- [x] `user_id`, `session_id`, and future `workspace_id` semantics are documented and consistent.
- [x] Tests prove one user's artifacts cannot be read by another user.

### Recommended scope

- [ ] Define canonical identity model:
  `user_id` = owner of long-term memory and facts
  `session_id` = conversation/thread scope
  `workspace_id` = future shared or delegated work context, if introduced
- [x] Update key patterns:
  memory cache and compacted tool-result ownership now use shared scope namespace helpers
- [x] Update compacted tool-result store:
  retrieval should validate caller ownership, not just UUID existence
- [x] Audit all write/read paths in:
  `core/database/memory.py`, `core/agents/tool_compactor.py`, `core/agents/bootstrap.py`, API retrieval routes, and any background summary workers
- [x] Add multi-user tests:
  cross-user read denial, cache separation, invalidation separation

### Suggested deliverables

- [x] Design spec: `docs/superpowers/specs/2026-03-18-memory-phase1_5-workspace-isolation.md`
- [x] Test file: `tests/test_memory_isolation.py`
- [x] Code changes in memory + compactor retrieval path

---

## Phase 2 Plan: Context Compaction + Async Background Summary

**Goal:** Keep long-running agent sessions usable by preserving only compact working state and moving summarisation off the request critical path.

### Success criteria

- [ ] Prompt context is reduced into stable sections: `Goal`, `Progress`, `Open Questions`, `Next Steps`.
- [ ] Long trajectories compact automatically based on token/character budget.
- [ ] Summary generation does not block user-facing response latency.
- [ ] Compaction output is deterministic enough to support later Task Memory extraction.

### Recommended implementation order

- [ ] Add a context budget contract:
  define thresholds for raw tool output, message history, and summary replacement
- [ ] Introduce compacted session state object:
  current goal, resolved symbols/markets, completed subtasks, pending next actions, important evidence
- [ ] Trigger compaction on budget breach or after N tool turns
- [ ] Add async summary writer:
  enqueue summary work after response finalisation instead of performing it inline
- [ ] Add recovery path:
  if async summary fails, foreground path still works with raw state fallback

### Suggested deliverables

- [ ] Design spec: `docs/superpowers/specs/2026-03-18-memory-phase2-context-compaction.md`
- [ ] Core module for session compaction
- [ ] Background task / queue integration
- [ ] Tests for budget-triggered compaction and summary fallback

---

## Phase 3 Plan: Task/Experience Memory + Tool Memory

**Goal:** Convert trajectories and tool usage into reusable learning signals without polluting the live prompt.

### Success criteria

- [ ] Successful and failed task trajectories can be retrieved by pattern, not only raw session log.
- [ ] Tool telemetry tracks success/failure, latency, output size, and approximate token cost.
- [ ] Agents can consume summarized experience/tool hints without loading raw historical transcripts.
- [ ] Memory writes are filtered so low-quality or one-off noise does not become durable policy.

### Recommended implementation order

- [ ] Task / Experience Memory first:
  store problem pattern, chosen tools, outcome quality, failure reason, retry guidance
- [ ] Add retrieval contract:
  fetch only top-N relevant experience snippets for current task type
- [ ] Then add Tool Memory:
  success rate, latency percentile, token/output size, common bad parameter combinations
- [ ] Expose tool hints to planner / manager layer:
  use as ranking signal, not as a hardcoded rule engine

### Suggested schema directions

- [ ] `task_experiences`
  keyed by tenant + task family + market/query attributes
- [ ] `tool_execution_stats`
  keyed by tenant/global scope + tool name + normalized parameter signature
- [ ] retention / decay policy
  recent and validated experience should outweigh stale or low-confidence entries

### Suggested deliverables

- [ ] Design spec: `docs/superpowers/specs/2026-03-18-memory-phase3-experience-and-tool-memory.md`
- [ ] Retrieval API for top relevant experiences
- [ ] Telemetry ingestion path for tool executions
- [ ] Tests for ranking, decay, and noise filtering

---

## Phase 4 Plan: Daily Journal / Operator Reporting

**Goal:** Generate human-readable daily summaries for operators without creating another source of truth.

### Success criteria

- [ ] Daily rollups are derived from task/experience/session summaries, not separate ad hoc notes.
- [ ] Journal entries are segmented by tenant/workspace when needed.
- [ ] Operators can inspect major failures, common tool issues, and notable user requests for a given day.

### Recommended scope

- [ ] Generate one daily markdown artifact per date and tenant/workspace
- [ ] Include:
  top task categories, repeated failures, tool anomalies, major memory updates
- [ ] Keep journal read-only / derived:
  no downstream feature should depend on journal text as canonical memory

### Suggested deliverables

- [ ] Design spec: `docs/superpowers/specs/2026-03-18-memory-phase4-daily-journal.md`
- [ ] Scheduled summariser job
- [ ] Markdown writer for `YYYY-MM-DD.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `core/agents/tool_compactor.py` | Non-mutating tool wrapper; compact large outputs; Redis store/retrieve |
| Modify | `core/agents/base_react_agent.py` | Apply `wrap_tool()` in `_get_tool_metas()` (returns new handler) |
| Modify | `core/agents/bootstrap.py` | Register `tool_result_retrieve` tool for all agents |
| Modify | `core/database/memory.py` | L1+L2 cache for read operations; invalidate on all write paths |
| Create | `tests/test_tool_compactor.py` | Unit tests — compactor + base_react_agent integration |
| Create | `tests/test_memory_cache.py` | Unit tests — memory cache layers |

---

## Task 1: ToolResultCompactor — core module

**Files:**
- Create: `core/agents/tool_compactor.py`
- Create: `tests/test_tool_compactor.py`

- [ ] **Step 1.1: Write failing tests**

Create `tests/test_tool_compactor.py`:

```python
"""Tests for ToolResultCompactor."""
from unittest.mock import MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_tool(return_value, name="mock_tool"):
    """Return a mock LangChain tool whose .invoke() returns return_value."""
    tool = MagicMock()
    tool.name = name
    tool.invoke = MagicMock(return_value=return_value)
    return tool


# ── threshold / passthrough ───────────────────────────────────────────────────

def test_small_output_passes_through():
    """Outputs ≤ THRESHOLD chars must be returned unchanged."""
    from core.agents.tool_compactor import wrap_tool
    tool = _make_tool({"price": 100})
    wrapped = wrap_tool(tool)
    result = wrapped.invoke({})
    assert result == {"price": 100}


def test_large_string_output_is_compacted():
    """Outputs > THRESHOLD chars must be replaced with [COMPACTED:uuid] reference."""
    from core.agents.tool_compactor import wrap_tool, THRESHOLD
    big_output = "x" * (THRESHOLD + 1)
    tool = _make_tool(big_output)

    with patch("core.agents.tool_compactor._store_sync", return_value="test-uuid-123"):
        wrapped = wrap_tool(tool)
        result = wrapped.invoke({})

    assert isinstance(result, str)
    assert "[COMPACTED:test-uuid-123]" in result


def test_large_dict_output_is_compacted():
    """Large dict outputs must also be compacted (serialised before size check)."""
    from core.agents.tool_compactor import wrap_tool, THRESHOLD
    big_dict = {"rows": ["row"] * 300}   # JSON > 2000 chars
    tool = _make_tool(big_dict)

    with patch("core.agents.tool_compactor._store_sync", return_value="uuid-abc"):
        wrapped = wrap_tool(tool)
        result = wrapped.invoke({})

    assert "[COMPACTED:uuid-abc]" in result


def test_compact_summary_contains_preview():
    """Compact output must include a text preview of the original content."""
    from core.agents.tool_compactor import wrap_tool, THRESHOLD
    original = "PREVIEW_MARKER" + "A" * (THRESHOLD + 500)
    tool = _make_tool(original)

    with patch("core.agents.tool_compactor._store_sync", return_value="uid"):
        wrapped = wrap_tool(tool)
        result = wrapped.invoke({})

    assert "PREVIEW_MARKER" in result


def test_tool_name_preserved():
    """Wrapped tool must keep the original tool's .name attribute."""
    from core.agents.tool_compactor import wrap_tool
    tool = _make_tool("small output", name="tw_stock_price")
    wrapped = wrap_tool(tool)
    assert wrapped.name == "tw_stock_price"


def test_wrap_tool_does_not_mutate_original():
    """wrap_tool must return a NEW object; the original tool must be unchanged."""
    from core.agents.tool_compactor import wrap_tool, THRESHOLD
    big_output = "x" * (THRESHOLD + 100)
    tool = _make_tool(big_output)
    original_invoke = tool.invoke   # save reference

    with patch("core.agents.tool_compactor._store_sync", return_value="uid"):
        wrapped = wrap_tool(tool)

    # Original invoke must be the same object
    assert tool.invoke is original_invoke
    # Wrapped must be a different object
    assert wrapped is not tool


def test_multiple_wraps_do_not_stack():
    """Wrapping the same tool twice must not double-compact the output."""
    from core.agents.tool_compactor import wrap_tool, THRESHOLD
    big_output = "x" * (THRESHOLD + 100)
    tool = _make_tool(big_output)

    store_calls = []
    def fake_store(data):
        store_calls.append(data)
        return f"uid-{len(store_calls)}"

    with patch("core.agents.tool_compactor._store_sync", side_effect=fake_store):
        wrapped1 = wrap_tool(tool)
        wrapped2 = wrap_tool(tool)   # wrap original again (not the already-wrapped)
        wrapped1.invoke({})
        wrapped2.invoke({})

    # Each wrap of the ORIGINAL tool stores once — 2 separate calls, 1 store each
    assert len(store_calls) == 2


# ── store/retrieve helpers ────────────────────────────────────────────────────

def test_store_sync_returns_uuid_string():
    """_store_sync must return a non-empty string UUID."""
    from core.agents.tool_compactor import _store_sync
    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        uid = _store_sync("some data")
    assert isinstance(uid, str) and len(uid) > 0


def test_retrieve_sync_returns_none_for_unknown_key():
    """_retrieve_sync must return None when key is absent from all stores."""
    from core.agents.tool_compactor import _retrieve_sync
    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        with patch("core.agents.tool_compactor._local_store", {}):
            result = _retrieve_sync("nonexistent-uuid")
    assert result is None


def test_retrieve_tool_result_error_message():
    """retrieve_tool_result must return an [ERROR] string for unknown UUIDs."""
    from core.agents.tool_compactor import retrieve_tool_result
    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        with patch("core.agents.tool_compactor._local_store", {}):
            result = retrieve_tool_result("bad-key")
    assert "[ERROR]" in result


def test_retrieve_tool_result_returns_stored_data():
    """retrieve_tool_result must return the exact data previously stored."""
    from core.agents.tool_compactor import retrieve_tool_result
    with patch("core.agents.tool_compactor._local_store", {"my-uid": "full content here"}):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            result = retrieve_tool_result("my-uid")
    assert result == "full content here"
```

- [ ] **Step 1.2: Run tests — verify they all FAIL**

```bash
cd /Users/a1031737/agent_stock/stock_agent
.venv/bin/pytest tests/test_tool_compactor.py -v 2>&1 | head -40
```

Expected: `ModuleNotFoundError: No module named 'core.agents.tool_compactor'`

- [ ] **Step 1.3: Add `_reset_for_testing()` helper and implement `core/agents/tool_compactor.py`**

The module uses lazy-init globals. Expose a reset function so tests can isolate state:

```python
def _reset_for_testing() -> None:
    """Reset module-level Redis state. For use in tests only."""
    global _redis_client, _redis_init_attempted
    _redis_client = None
    _redis_init_attempted = False
```

Full implementation of `core/agents/tool_compactor.py`:

```python
"""
ToolResultCompactor
===================
Wraps LangChain tool handlers to prevent large outputs from flooding
LangGraph message state and consuming the context window.

Design
------
- wrap_tool() returns a NEW wrapper object — it does NOT mutate the original.
- Large outputs (> THRESHOLD chars) are stored in Redis and replaced with a
  compact reference string containing a UUID.
- Falls back to an in-process dict if Redis is unavailable.
- Wrapping the same original tool multiple times produces independent wrappers
  that each store once — no double-compaction.

No new dependencies — uses redis (sync, thread-safe for tool threads),
orjson, uuid from stdlib.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import orjson

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
THRESHOLD = 2_000        # chars; outputs longer than this get compacted
PREVIEW_LEN = 500        # chars of original shown in compact summary
REDIS_TTL = 3_600        # seconds — 1 hour retention
_KEY_PREFIX = "tr:"      # distinct from "mkt:" and "mem:"

# ── In-process fallback (lost on restart — acceptable for transient cache) ────
_local_store: dict[str, str] = {}

# ── Redis sync client (lazy-init, reused across threads) ─────────────────────
_redis_client: Optional[Any] = None
_redis_init_attempted = False


def _get_redis_sync() -> Optional[Any]:
    """Return a synchronous Redis client, or None if unavailable."""
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    try:
        import redis as _r
        from core.redis_url import resolve_redis_url
        url, _ = resolve_redis_url()
        if not url:
            return None
        client = _r.from_url(url, decode_responses=True,
                              socket_connect_timeout=2,
                              socket_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("[ToolCompactor] Redis sync client connected")
    except Exception as exc:
        logger.warning("[ToolCompactor] Redis unavailable — in-process fallback: %s", exc)
        _redis_client = None
    return _redis_client


# ── Storage helpers ───────────────────────────────────────────────────────────

def _store_sync(data: str) -> str:
    """Persist full tool output; return the UUID key."""
    uid = str(uuid.uuid4())
    r = _get_redis_sync()
    if r:
        try:
            r.setex(_KEY_PREFIX + uid, REDIS_TTL, data)
            return uid
        except Exception as exc:
            logger.debug("[ToolCompactor] Redis store error: %s", exc)
    _local_store[uid] = data
    return uid


def _retrieve_sync(uid: str) -> Optional[str]:
    """Retrieve stored tool output by UUID. Returns None if not found."""
    r = _get_redis_sync()
    if r:
        try:
            val = r.get(_KEY_PREFIX + uid)
            if val is not None:
                return val
        except Exception as exc:
            logger.debug("[ToolCompactor] Redis retrieve error: %s", exc)
    return _local_store.get(uid)


# ── Serialisation ─────────────────────────────────────────────────────────────

def _to_str(output: Any) -> str:
    if isinstance(output, str):
        return output
    try:
        return orjson.dumps(output).decode()
    except Exception:
        return json.dumps(output, ensure_ascii=False, default=str)


# ── Wrapper class (non-mutating) ──────────────────────────────────────────────

class _CompactingToolWrapper:
    """
    Thin proxy around a LangChain tool that intercepts large invoke() outputs.

    Attributes other than .invoke are delegated to the original tool so that
    LangChain's introspection (name, description, args_schema …) still works.
    """

    def __init__(self, original: Any) -> None:
        self._original = original

    def __getattr__(self, item: str) -> Any:
        return getattr(self._original, item)

    def invoke(self, input: Any, **kwargs: Any) -> Any:  # noqa: A002
        raw = self._original.invoke(input, **kwargs)
        text = _to_str(raw)
        if len(text) <= THRESHOLD:
            return raw          # fast path — no compaction needed

        uid = _store_sync(text)
        preview = text[:PREVIEW_LEN]
        compact = (
            f"[COMPACTED:{uid}]\n"
            f"{preview}...\n"
            f"[{len(text):,} chars total. Retrieve full data with key: {uid}]"
        )
        logger.debug("[ToolCompactor] tool=%s size=%d uid=%s",
                     getattr(self._original, "name", "?"), len(text), uid)
        return compact


# ── Public API ────────────────────────────────────────────────────────────────

def wrap_tool(tool: Any) -> _CompactingToolWrapper:
    """
    Return a new _CompactingToolWrapper around the given tool.

    The original tool object is NOT modified.
    Small outputs pass through unchanged; large outputs are stored in Redis
    and replaced with a compact summary + UUID reference.
    """
    return _CompactingToolWrapper(tool)


def retrieve_tool_result(uid: str) -> str:
    """
    Retrieve a previously compacted tool result by its UUID.
    Returns the full stored string, or an [ERROR] message if not found/expired.
    """
    data = _retrieve_sync(uid)
    if data is None:
        return f"[ERROR] Tool result '{uid}' not found or expired."
    return data


def _reset_for_testing() -> None:
    """Reset module-level Redis state. For use in tests only."""
    global _redis_client, _redis_init_attempted
    _redis_client = None
    _redis_init_attempted = False
```

- [ ] **Step 1.4: Run tests — verify they all PASS**

```bash
.venv/bin/pytest tests/test_tool_compactor.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 1.5: Commit**

```bash
git add core/agents/tool_compactor.py tests/test_tool_compactor.py
git commit -m "feat: add ToolResultCompactor to prevent context window overflow"
```

---

## Task 2: Wire compactor into BaseReActAgent

**Files:**
- Modify: `core/agents/base_react_agent.py`

- [ ] **Step 2.1: Write failing tests** (add to `tests/test_tool_compactor.py`)

```python
import pytest

@pytest.fixture(autouse=True)
def reset_compactor_redis():
    """Ensure Redis lazy-init state is clean before each test."""
    from core.agents import tool_compactor
    tool_compactor._reset_for_testing()
    yield
    tool_compactor._reset_for_testing()


def test_base_react_agent_wraps_tools_non_mutating():
    """_get_tool_metas() must return new ToolMetadata objects; registry copy unchanged."""
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.tool_compactor import THRESHOLD, _CompactingToolWrapper
    from core.agents.tool_registry import ToolMetadata

    class DummyAgent(BaseReActAgent):
        name = "dummy"

    big_tool = _make_tool("x" * (THRESHOLD + 100), name="big_tool")
    original_invoke = big_tool.invoke   # save reference

    registry_meta = ToolMetadata(
        name="big_tool",
        description="test",
        input_schema={},
        handler=big_tool,
        allowed_agents=[],
        required_tier="free",
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]

    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry)

    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        metas = agent._get_tool_metas()

    # Returned handler must be a wrapper
    assert isinstance(metas[0].handler, _CompactingToolWrapper)
    # Registry's original object must NOT be mutated
    assert big_tool.invoke is original_invoke
    assert registry_meta.handler is big_tool


def test_repeated_get_tool_metas_does_not_double_wrap():
    """Calling _get_tool_metas() twice must not stack-wrap the handler."""
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.tool_compactor import THRESHOLD, _CompactingToolWrapper
    from core.agents.tool_registry import ToolMetadata

    class DummyAgent(BaseReActAgent):
        name = "dummy"

    tool = _make_tool("small output")
    registry_meta = ToolMetadata(
        name="t", description="", input_schema={}, handler=tool, allowed_agents=[]
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]
    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry)

    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        metas1 = agent._get_tool_metas()
        metas2 = agent._get_tool_metas()

    # Each call wraps the REGISTRY original (unchanged), not the previous wrapper
    # Both returned handlers must wrap the same original tool
    assert metas1[0].handler._original is tool
    assert metas2[0].handler._original is tool


def test_required_tool_path_compacts_large_output():
    """_execute_with_required_tool invokes through the compactor for large outputs."""
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.tool_compactor import THRESHOLD
    from core.agents.tool_registry import ToolMetadata
    from core.agents.models import SubTask

    class DummyAgent(BaseReActAgent):
        name = "dummy"

    big_tool = _make_tool("x" * (THRESHOLD + 100), name="forced_tool")
    registry_meta = ToolMetadata(
        name="forced_tool", description="test",
        input_schema={}, handler=big_tool, allowed_agents=[], required_tier="free",
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]

    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry)

    captured = {}
    def fake_summarize(self, task, meta, tool_result, language):
        captured["tool_result"] = tool_result
        from core.agents.models import AgentResult
        return AgentResult(success=True, message="ok", agent_name="dummy")

    task = SubTask(step=1, description="test", agent="dummy")

    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        with patch("core.agents.tool_compactor._store_sync", return_value="forced-uid"):
            with patch.object(
                type(agent), "_summarize_required_tool_result", fake_summarize
            ):
                with patch.object(type(agent), "_select_required_tool",
                                  return_value=registry_meta):
                    with patch.object(type(agent), "_requires_tool_execution",
                                      return_value=True):
                        agent._get_tool_metas()   # apply wrapping
                        agent._execute_with_required_tool(task, [registry_meta], "zh-TW")

    # The tool result passed to summarize must be the compact reference
    assert "[COMPACTED:forced-uid]" in str(captured.get("tool_result", ""))
```

- [ ] **Step 2.2: Run tests — verify they FAIL**

```bash
.venv/bin/pytest tests/test_tool_compactor.py::test_base_react_agent_wraps_tools_non_mutating \
                 tests/test_tool_compactor.py::test_base_react_agent_required_tool_path_also_compacts -v
```

Expected: FAIL — tools are not yet wrapped.

- [ ] **Step 2.3: Modify `_get_tool_metas` in `base_react_agent.py`**

At top of file, add imports:
```python
import dataclasses
from core.agents.tool_compactor import wrap_tool
```

Inside `_get_tool_metas()`, AFTER all existing filtering logic and BEFORE the `return`,
replace the final return statement with:

```python
    # Build new ToolMetadata objects with wrapped handlers.
    # Uses dataclasses.replace() so the registry's original objects are never mutated —
    # preventing double-wrapping if _get_tool_metas() is called multiple times.
    return [
        dataclasses.replace(meta, handler=wrap_tool(meta.handler))
        for meta in filtered_metas
    ]
```

Do NOT do `meta.handler = wrap_tool(meta.handler)` — that mutates the registry object.
Both `_execute_with_agent` and `_execute_with_required_tool` consume the returned list,
so both code paths are covered by this single change.

- [ ] **Step 2.4: Run tests — verify they PASS**

```bash
.venv/bin/pytest tests/test_tool_compactor.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add core/agents/base_react_agent.py tests/test_tool_compactor.py
git commit -m "feat: wire ToolResultCompactor into BaseReActAgent — both ReAct and forced-tool paths"
```

---

## Task 3: Register `tool_result_retrieve` in bootstrap

**Files:**
- Modify: `core/agents/bootstrap.py`
- Create: `tests/test_tool_registry_retrieve.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_tool_registry_retrieve.py`:

```python
"""Tests for tool_result_retrieve registration in bootstrap."""
from unittest.mock import patch


def test_retrieve_tool_result_returns_stored():
    """retrieve_tool_result returns stored content by UUID."""
    from core.agents.tool_compactor import retrieve_tool_result
    with patch("core.agents.tool_compactor._local_store", {"abc-123": "full data here"}):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            result = retrieve_tool_result("abc-123")
    assert result == "full data here"


def test_retrieve_tool_result_unknown_key():
    """retrieve_tool_result returns [ERROR] for unknown UUID."""
    from core.agents.tool_compactor import retrieve_tool_result
    with patch("core.agents.tool_compactor._local_store", {}):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            result = retrieve_tool_result("nonexistent-key")
    assert "[ERROR]" in result


def test_tool_result_retrieve_registered_in_bootstrap():
    """bootstrap() must register tool_result_retrieve in the ToolRegistry it returns."""
    # Patch DB and OKX so bootstrap doesn't need real infrastructure
    with patch("core.database.tools.get_allowed_tools", return_value=None), \
         patch("core.agents.bootstrap.OKXAPIConnector", side_effect=Exception("no okx")), \
         patch("core.database.base.DatabaseBase.query_one", return_value=None), \
         patch("core.database.base.DatabaseBase.query_all", return_value=[]):

        from core.agents.bootstrap import bootstrap
        from unittest.mock import MagicMock

        fake_llm = MagicMock()
        fake_llm.invoke = MagicMock(return_value=MagicMock(content="ok"))

        manager = bootstrap(fake_llm, user_tier="free", user_id="test-user")

    # The registry on the manager must contain tool_result_retrieve
    tool = manager.tool_registry.get("tool_result_retrieve")
    assert tool is not None, "tool_result_retrieve must be registered in bootstrap()"
```

- [ ] **Step 3.2: Run tests — verify first two PASS, third may PASS (registry test is self-contained)**

```bash
.venv/bin/pytest tests/test_tool_registry_retrieve.py -v
```

- [ ] **Step 3.3: Add registration to `bootstrap.py`**

Near the end of `bootstrap()`, after all other `tool_registry.register()` calls, add:

```python
# ── Register ToolResultCompactor retrieval tool ──
from langchain_core.tools import tool as lc_tool
from core.agents.tool_compactor import retrieve_tool_result as _retrieve_fn

@lc_tool
def tool_result_retrieve(uuid: str) -> str:
    """Retrieve the full content of a previously compacted tool result by its UUID key."""
    return _retrieve_fn(uuid)

tool_registry.register(ToolMetadata(
    name="tool_result_retrieve",
    description="Retrieve the full content of a previously compacted tool result by its UUID key.",
    input_schema={"uuid": "str"},
    handler=tool_result_retrieve,
    allowed_agents=[],   # [] = available to all agents
    required_tier="free",
))
```

- [ ] **Step 3.4: Run all compactor tests**

```bash
.venv/bin/pytest tests/test_tool_compactor.py tests/test_tool_registry_retrieve.py -v
```

Expected: all tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add core/agents/bootstrap.py tests/test_tool_registry_retrieve.py
git commit -m "feat: register tool_result_retrieve tool in bootstrap for all agents"
```

---

## Task 4: MemoryStore Redis cache

**Files:**
- Modify: `core/database/memory.py`
- Create: `tests/test_memory_cache.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_memory_cache.py`:

```python
"""Tests for MemoryStore 3-layer cache (L1 TTLCache → L2 Redis → L3 PostgreSQL)."""
import pytest
from unittest.mock import MagicMock, patch, call
import orjson


@pytest.fixture(autouse=True)
def reset_memory_redis():
    """Reset Redis lazy-init globals before each test to prevent cross-test leakage."""
    from core.database import memory as mem_mod
    mem_mod._reset_for_testing()
    yield
    mem_mod._reset_for_testing()


class FakeRedis:
    """Minimal synchronous Redis stub for testing."""
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def setex(self, key, ttl, value):
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)

    def ping(self):
        return True


def _make_store(user_id="user-test-1"):
    from core.database.memory import MemoryStore
    return MemoryStore(user_id)


# ── L1 in-process cache ───────────────────────────────────────────────────────

def test_second_call_does_not_hit_db():
    """L1: second get_memory_context call within TTL must skip PostgreSQL."""
    from core.database.memory import _mem_l1_delete
    store = _make_store("user-l1-test")
    _mem_l1_delete("user-l1-test")   # clear L1 before test

    db_call_count = [0]
    def fake_db_context(self, *a, **kw):
        db_call_count[0] += 1
        return "db result"

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch.object(type(store), "_read_from_db", fake_db_context):
            store.get_memory_context()   # first call — hits DB
            store.get_memory_context()   # second call — must use L1

    assert db_call_count[0] == 1, "DB must be hit only once within L1 TTL"


def test_write_long_term_invalidates_l1():
    """Writing long-term memory must clear the L1 entry for this user."""
    from core.database.memory import _mem_l1_set, _mem_l1_get, _mem_l1_delete
    store = _make_store("user-inv-test")
    _mem_l1_delete("user-inv-test")

    # Seed L1
    _mem_l1_set("user-inv-test", "stale data")
    assert _mem_l1_get("user-inv-test") == "stale data"

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_long_term("new memory")

    assert _mem_l1_get("user-inv-test") is None   # must be evicted


def test_append_history_invalidates_l1():
    """append_history must also invalidate the L1 cache (history is part of context)."""
    from core.database.memory import _mem_l1_set, _mem_l1_get, _mem_l1_delete
    store = _make_store("user-hist-test")
    _mem_l1_delete("user-hist-test")

    _mem_l1_set("user-hist-test", "old context")

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.append_history("[2026-03-18 10:00] USER: hello")

    assert _mem_l1_get("user-hist-test") is None


# ── L2 Redis cache ────────────────────────────────────────────────────────────

def test_l2_redis_hit_skips_postgresql():
    """L2: when Redis has the key, PostgreSQL must not be called."""
    store = _make_store("user-redis-hit")
    fake_redis = FakeRedis()
    cached_payload = "redis cached context"
    fake_redis._store[f"mem:user-redis-hit"] = orjson.dumps(cached_payload)

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch.object(type(store), "_read_from_db") as mock_db:
            result = store.get_memory_context()
            mock_db.assert_not_called()

    assert result == cached_payload


def test_l2_redis_populated_on_db_miss():
    """L3 → L2: after a DB read, the result must be written to Redis."""
    from core.database.memory import _mem_l1_delete
    store = _make_store("user-redis-miss")
    _mem_l1_delete("user-redis-miss")
    fake_redis = FakeRedis()

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch.object(type(store), "_read_from_db", return_value="from db"):
            store.get_memory_context()

    assert "mem:user-redis-miss" in fake_redis._store


def test_write_long_term_invalidates_redis():
    """write_long_term must delete the Redis key for this user."""
    store = _make_store("user-redis-inv")
    fake_redis = FakeRedis()
    fake_redis._store["mem:user-redis-inv"] = orjson.dumps("old")

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_long_term("new memory")

    assert "mem:user-redis-inv" not in fake_redis._store


def test_write_facts_invalidates_redis():
    """write_facts must also delete the Redis key for this user."""
    store = _make_store("user-facts-inv")
    fake_redis = FakeRedis()
    fake_redis._store["mem:user-facts-inv"] = orjson.dumps("old")

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_facts([{"key": "pref", "value": "crypto",
                                "confidence": "high", "source_turn": 1}])

    assert "mem:user-facts-inv" not in fake_redis._store


# ── Fallback ──────────────────────────────────────────────────────────────────

def test_redis_unavailable_falls_back_to_postgresql():
    """When Redis is None, get_memory_context must work via PostgreSQL only."""
    from core.database.memory import _mem_l1_delete
    store = _make_store("user-fallback")
    _mem_l1_delete("user-fallback")

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch.object(type(store), "_read_from_db", return_value="db only result"):
            result = store.get_memory_context()

    assert result == "db only result"
```

- [ ] **Step 4.2: Run tests — verify they FAIL**

```bash
.venv/bin/pytest tests/test_memory_cache.py -v 2>&1 | head -50
```

Expected: failures because `_mem_l1_delete`, `_read_from_db`, `_get_redis_sync` don't exist yet.

- [ ] **Step 4.3: Add cache infrastructure to `core/database/memory.py`**

After the existing imports, add (include `_reset_for_testing` for test isolation):

```python
import orjson
from cachetools import TTLCache

# ── Memory context cache (L1 in-process → L2 Redis → L3 PostgreSQL) ──────────
_MEM_L1: TTLCache = TTLCache(maxsize=512, ttl=30)   # 30 s in-process
_MEM_REDIS_TTL = 120                                  # 2 min Redis TTL
_MEM_KEY_PREFIX = "mem:"

_mem_redis_client = None
_mem_redis_init = False


def _get_redis_sync():
    global _mem_redis_client, _mem_redis_init
    if _mem_redis_init:
        return _mem_redis_client
    _mem_redis_init = True
    try:
        import redis as _r
        from core.redis_url import resolve_redis_url
        url, _ = resolve_redis_url()
        if not url:
            return None
        client = _r.from_url(url, decode_responses=False,
                              socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        _mem_redis_client = client
        logger.info("[MemoryCache] Redis connected")
    except Exception as exc:
        logger.warning("[MemoryCache] Redis unavailable: %s", exc)
        _mem_redis_client = None
    return _mem_redis_client


def _mem_cache_key(user_id: str) -> str:
    return _MEM_KEY_PREFIX + user_id


def _mem_l1_get(user_id: str):
    return _MEM_L1.get(_mem_cache_key(user_id))


def _mem_l1_set(user_id: str, data) -> None:
    _MEM_L1[_mem_cache_key(user_id)] = data


def _mem_l1_delete(user_id: str) -> None:
    try:
        del _MEM_L1[_mem_cache_key(user_id)]
    except KeyError:
        pass   # already evicted or never set — safe to ignore


def _mem_redis_get(user_id: str):
    r = _get_redis_sync()
    if not r:
        return None
    try:
        raw = r.get(_mem_cache_key(user_id))
        return orjson.loads(raw) if raw else None
    except Exception:
        return None


def _mem_redis_set(user_id: str, data) -> None:
    r = _get_redis_sync()
    if not r:
        return
    try:
        r.setex(_mem_cache_key(user_id), _MEM_REDIS_TTL, orjson.dumps(data))
    except Exception:
        pass


def _mem_redis_delete(user_id: str) -> None:
    r = _get_redis_sync()
    if not r:
        return
    try:
        r.delete(_mem_cache_key(user_id))
    except Exception:
        pass


def _invalidate_memory_cache(user_id: str) -> None:
    """Invalidate both L1 and L2 cache for a user."""
    _mem_l1_delete(user_id)
    _mem_redis_delete(user_id)


def _reset_for_testing() -> None:
    """Reset Redis lazy-init state. For use in tests only."""
    global _mem_redis_client, _mem_redis_init
    _mem_redis_client = None
    _mem_redis_init = False
```

- [ ] **Step 4.4: Refactor `get_memory_context()` and extract `_read_from_db()`**

In `MemoryStore`, rename the existing body of `get_memory_context()` to `_read_from_db()`,
then replace `get_memory_context()` with the cache-layered version:

```python
def _read_from_db(self, include_history: bool = True, history_limit: int = 10) -> str:
    """Actual PostgreSQL read — moved from get_memory_context()."""
    # ← paste the EXISTING body of get_memory_context() here, unchanged ←
    parts = []
    facts_text = self.facts_to_text()
    if facts_text and facts_text != "（尚無已知事實）":
        parts.append(f"## 已知用戶事實\n{facts_text}")
    long_term = self.read_long_term()
    if long_term:
        parts.append(f"## Long-term Memory\n{long_term}")
    if not parts:
        return ""
    context = "\n\n".join(parts)
    if include_history:
        history = self.get_history(limit=history_limit)
        if history:
            history_text = "\n\n".join([h.get('entry', '') for h in history if h.get('entry')])
            if history_text:
                context += f"\n\n## Recent History\n{history_text}"
    return context


def get_memory_context(self, include_history: bool = True, history_limit: int = 10) -> str:
    """Return memory context with L1 → L2 → L3 cache layering."""
    # L1
    cached = _mem_l1_get(self.user_id)
    if cached is not None:
        return cached
    # L2
    redis_hit = _mem_redis_get(self.user_id)
    if redis_hit is not None:
        _mem_l1_set(self.user_id, redis_hit)
        return redis_hit
    # L3
    result = self._read_from_db(include_history, history_limit)
    _mem_l1_set(self.user_id, result)
    _mem_redis_set(self.user_id, result)
    return result
```

- [ ] **Step 4.5: Add `_invalidate_memory_cache` call to all write methods**

In `write_long_term()`, at the very end (after `DatabaseBase.execute` call):
```python
    _invalidate_memory_cache(self.user_id)
```

In `write_facts()`, after the for-loop that calls `DatabaseBase.execute`:
```python
    _invalidate_memory_cache(self.user_id)
```

In `append_history()`, after `DatabaseBase.execute`:
```python
    _invalidate_memory_cache(self.user_id)
```

- [ ] **Step 4.6: Run tests — verify they PASS**

```bash
.venv/bin/pytest tests/test_memory_cache.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 4.7: Run full test suite to check for regressions**

```bash
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: no new failures beyond pre-existing ones.

- [ ] **Step 4.8: Commit**

```bash
git add core/database/memory.py tests/test_memory_cache.py
git commit -m "feat: add 3-layer Redis cache to MemoryStore — L1 TTLCache + L2 Redis + L3 PostgreSQL"
```

---

## Task 5: Verification

- [ ] **Step 5.1: Parse-check all modified files**

```bash
cd /Users/a1031737/agent_stock/stock_agent
.venv/bin/python -c "
import ast, sys
files = [
    'core/agents/tool_compactor.py',
    'core/agents/base_react_agent.py',
    'core/agents/bootstrap.py',
    'core/database/memory.py',
]
ok = True
for f in files:
    try:
        ast.parse(open(f).read())
        print(f'OK  {f}')
    except SyntaxError as e:
        print(f'ERR {f}: {e}')
        ok = False
sys.exit(0 if ok else 1)
"
```

Expected: all `OK`.

- [ ] **Step 5.2: Import smoke test**

```bash
.venv/bin/python -c "
from core.agents.tool_compactor import wrap_tool, retrieve_tool_result, _CompactingToolWrapper
from core.database.memory import MemoryStore, _get_redis_sync, _mem_l1_delete
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 5.3: Full test run**

```bash
.venv/bin/pytest tests/test_tool_compactor.py tests/test_tool_registry_retrieve.py tests/test_memory_cache.py -v
```

Expected: all tests PASS, no errors.

- [ ] **Step 5.4: Final commit**

```bash
git add .
git status   # review before committing
git commit -m "chore: verify all memory phase 1 imports and tests"
```

---

## Rollback Plan

**ToolResultCompactor:**
Remove `meta.handler = wrap_tool(meta.handler)` from `_get_tool_metas()` in `base_react_agent.py`. On next process restart, all tools revert to raw output. The `_CompactingToolWrapper` class does not mutate originals, so no other cleanup needed. **Requires process restart** — in-flight wrapped tool calls complete normally.

**MemoryStore cache:**
Redis unavailability is handled automatically — `_get_redis_sync()` returns None and code falls through to PostgreSQL. To fully disable the L1 cache, set `TTLCache(maxsize=0)` or set `_MEM_L1 = {}` at runtime. The `_read_from_db()` path is always available as the ground truth. **No DB migration required. No config change required.**
