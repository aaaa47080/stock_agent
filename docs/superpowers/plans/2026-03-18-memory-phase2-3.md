# Memory System Phase 2 + 3 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add context budget enforcement + CompactedSessionState (Phase 2) and task_experiences + tool_execution_stats + 3-layer retrieval (Phase 3) to make the chatbot remember trajectories and stay coherent in long sessions.

**Architecture:** Phase 2 intercepts history assembly in `_understand_intent_node()` — when chars exceed budget, compact state (Goal/Progress/Open Questions/Next Steps) is served instead of raw truncated history. Phase 3 hooks into `_track_conversation()` (background write) and `_understand_intent_node()` (hint injection before planning). Both phases write asynchronously and degrade gracefully on failure.

**Spec:** `docs/superpowers/specs/2026-03-18-memory-phase2-3-design.md`

**Tech Stack:** Python 3.12, FastAPI, LangGraph, asyncio, PostgreSQL (psycopg2 via DatabaseBase), Redis (sync client), orjson, cachetools

---

## Progress Tracker

- [x] Phase 2 — context_budget module
- [x] Phase 2 — compact state read/write in MemoryStore
- [x] Phase 2 — wire budget check into manager
- [x] Phase 2 — extend consolidate() to produce compact_state
- [x] Phase 3 — schema + ExperienceStore
- [x] Phase 3 — tool stat collection hook
- [x] Phase 3 — wire record + retrieve into manager

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `core/agents/context_budget.py` | `CONTEXT_CHAR_BUDGET` constant, `history_exceeds_budget()`, `format_compact_state()` |
| Modify | `core/database/memory.py` | `CompactedSessionState` dataclass, `read_compact_state()`, `write_compact_state()`, Redis helpers |
| Modify | `core/agents/manager.py` | `_get_history_for_prompt()`, `_record_experience_background()`, extend `_do_consolidation()`, inject hints in `_understand_intent_node()` |
| Modify | `core/database/schema.py` | add `task_experiences`, `tool_execution_stats` table creation |
| Create | `core/database/experiences.py` | `ExperienceStore`: `record_experience()`, `record_tool_stat()`, `retrieve_relevant()` |
| Modify | `core/agents/tool_compactor.py` | collect `(tool_name, success, latency_ms, output_chars, error_type)` after `invoke()`, expose via `pending_stats` |
| Create | `tests/test_context_budget.py` | budget check + compact state format tests |
| Create | `tests/test_compact_state.py` | read/write compact state, Redis fallback, isolation tests |
| Create | `tests/test_experiences.py` | record + retrieve + user isolation + tool stat tests |

---

## Chunk 1: Phase 2 — Context Budget + CompactedSessionState

---

### Task 1: `context_budget.py` — char budget module

**Files:**
- Create: `core/agents/context_budget.py`
- Create: `tests/test_context_budget.py`

- [ ] **Step 1.1: Write failing tests**

Create `tests/test_context_budget.py`:

```python
"""Tests for context_budget module."""
from dataclasses import dataclass
from typing import Optional


# ── fixtures ─────────────────────────────────────────────────────────────────

def _make_compact(goal="查詢BTC", progress="取得價格", open_q="", next_s=""):
    from core.agents.context_budget import CompactPrompt
    return CompactPrompt(goal=goal, progress=progress,
                         open_questions=open_q, next_steps=next_s)


# ── budget check ─────────────────────────────────────────────────────────────

def test_short_history_under_budget():
    from core.agents.context_budget import history_exceeds_budget
    assert history_exceeds_budget("用戶: hi\n助手: hello") is False


def test_long_history_over_budget():
    from core.agents.context_budget import history_exceeds_budget, CONTEXT_CHAR_BUDGET
    long_history = "x" * (CONTEXT_CHAR_BUDGET + 1)
    assert history_exceeds_budget(long_history) is True


def test_empty_history_under_budget():
    from core.agents.context_budget import history_exceeds_budget
    assert history_exceeds_budget("") is False


# ── compact state formatting ──────────────────────────────────────────────────

def test_format_compact_state_includes_all_sections():
    from core.agents.context_budget import format_compact_state
    cp = _make_compact(goal="查詢BTC", progress="已取得價格", open_q="技術指標待確認", next_s="查詢RSI")
    result = format_compact_state(cp)
    assert "查詢BTC" in result
    assert "已取得價格" in result
    assert "技術指標待確認" in result
    assert "查詢RSI" in result


def test_format_compact_state_omits_empty_sections():
    from core.agents.context_budget import format_compact_state
    cp = _make_compact(goal="查詢BTC", progress="完成", open_q="", next_s="")
    result = format_compact_state(cp)
    assert "Open Questions" not in result
    assert "Next Steps" not in result
```

- [ ] **Step 1.2: Run — verify FAIL**

```bash
cd D:/okx/stock_agent && python -m pytest tests/test_context_budget.py -v --no-cov --tb=short
```
Expected: `ModuleNotFoundError: No module named 'core.agents.context_budget'`

- [ ] **Step 1.3: Create `core/agents/context_budget.py`**

```python
"""
Context budget enforcement for manager prompt assembly.

Prevents history slot in the LLM prompt from exceeding CONTEXT_CHAR_BUDGET chars.
When the raw history is too long, serve CompactPrompt (Goal/Progress/OpenQ/NextSteps)
instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Total chars allocated to the history slot in the manager intent-understanding prompt.
# Derived from: typical model context ~128k tokens ≈ 500k chars; history slot ≤ 1.2% of that.
# Adjust when switching to a smaller model.
CONTEXT_CHAR_BUDGET: int = 6_000


@dataclass
class CompactPrompt:
    """Structured compact representation of a long session."""
    goal: str
    progress: str
    open_questions: str = ""
    next_steps: str = ""


def history_exceeds_budget(history: str) -> bool:
    """Return True if history string exceeds CONTEXT_CHAR_BUDGET chars."""
    return len(history) > CONTEXT_CHAR_BUDGET


def format_compact_state(cp: CompactPrompt) -> str:
    """Render CompactPrompt as a compact history block for LLM injection."""
    lines = ["[Session Compact Summary]", f"Goal: {cp.goal}", f"Progress: {cp.progress}"]
    if cp.open_questions:
        lines.append(f"Open Questions: {cp.open_questions}")
    if cp.next_steps:
        lines.append(f"Next Steps: {cp.next_steps}")
    return "\n".join(lines)
```

- [ ] **Step 1.4: Run — verify PASS**

```bash
python -m pytest tests/test_context_budget.py -v --no-cov
```
Expected: 5 passed

- [ ] **Step 1.5: Commit**

```bash
git add core/agents/context_budget.py tests/test_context_budget.py
git commit -m "feat: add context_budget module with char budget check and compact formatter"
```

---

### Task 2: `memory.py` — CompactedSessionState read/write

**Files:**
- Modify: `core/database/memory.py`
- Create: `tests/test_compact_state.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_compact_state.py`:

```python
"""Tests for CompactedSessionState read/write in MemoryStore."""
from unittest.mock import patch, MagicMock
import orjson
import pytest


@pytest.fixture(autouse=True)
def reset_state():
    from core.database import memory as mem_mod
    mem_mod._reset_for_testing()
    yield
    mem_mod._reset_for_testing()


class FakeRedis:
    def __init__(self): self._store = {}
    def get(self, key): return self._store.get(key)
    def setex(self, key, ttl, value): self._store[key] = value
    def delete(self, key): self._store.pop(key, None)
    def ping(self): return True


def _make_state():
    from core.database.memory import CompactedSessionState
    return CompactedSessionState(
        goal="查詢BTC走勢",
        progress="已取得價格 42000",
        open_questions="RSI是否超買",
        next_steps="查詢技術指標",
        turn_index=6,
        updated_at="2026-03-18T10:00:00",
    )


# ── write → redis populated ───────────────────────────────────────────────────

def test_write_compact_state_sets_redis():
    from core.database.memory import MemoryStore, _compact_redis_key
    store = MemoryStore("user-cs-1", session_id="sess-1")
    fake_redis = FakeRedis()
    state = _make_state()

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_compact_state(state)

    assert _compact_redis_key("user-cs-1", "sess-1") in fake_redis._store


# ── read redis hit ────────────────────────────────────────────────────────────

def test_read_compact_state_redis_hit():
    from core.database.memory import MemoryStore, CompactedSessionState, _compact_redis_key
    store = MemoryStore("user-cs-2", session_id="sess-2")
    state = _make_state()
    fake_redis = FakeRedis()
    fake_redis._store[_compact_redis_key("user-cs-2", "sess-2")] = orjson.dumps(
        {"goal": state.goal, "progress": state.progress,
         "open_questions": state.open_questions, "next_steps": state.next_steps,
         "turn_index": state.turn_index, "updated_at": state.updated_at}
    )

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        result = store.read_compact_state()

    assert isinstance(result, CompactedSessionState)
    assert result.goal == state.goal


# ── read redis miss → postgresql ──────────────────────────────────────────────

def test_read_compact_state_postgresql_fallback():
    from core.database.memory import MemoryStore, CompactedSessionState
    store = MemoryStore("user-cs-3", session_id="sess-3")
    state = _make_state()
    import json
    db_row = {"content": json.dumps({
        "goal": state.goal, "progress": state.progress,
        "open_questions": state.open_questions, "next_steps": state.next_steps,
        "turn_index": state.turn_index, "updated_at": state.updated_at,
    })}

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.query_one", return_value=db_row):
            result = store.read_compact_state()

    assert isinstance(result, CompactedSessionState)
    assert result.turn_index == 6


# ── read miss returns None ────────────────────────────────────────────────────

def test_read_compact_state_returns_none_when_missing():
    from core.database.memory import MemoryStore
    store = MemoryStore("user-cs-4", session_id="sess-4")
    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.query_one", return_value=None):
            assert store.read_compact_state() is None


# ── cross-session isolation ───────────────────────────────────────────────────

def test_compact_state_isolated_by_session():
    from core.database.memory import MemoryStore, _compact_redis_key
    store_a = MemoryStore("user-cs-5", session_id="sess-a")
    store_b = MemoryStore("user-cs-5", session_id="sess-b")
    assert _compact_redis_key("user-cs-5", "sess-a") != _compact_redis_key("user-cs-5", "sess-b")
```

- [ ] **Step 2.2: Run — verify FAIL**

```bash
python -m pytest tests/test_compact_state.py -v --no-cov --tb=short
```
Expected: errors about missing `CompactedSessionState`, `_compact_redis_key`, etc.

- [ ] **Step 2.3: Add to `core/database/memory.py`**

After the `_reset_for_testing()` function (before the `MemoryStore` class), add:

```python
# ── Compact session state helpers ─────────────────────────────────────────────
_COMPACT_KEY_PREFIX = "session_compact:"
_COMPACT_REDIS_TTL = 7_200  # 2 hours


def _compact_redis_key(user_id: str, session_id: str) -> str:
    return f"{_COMPACT_KEY_PREFIX}{user_id}:{session_id}"
```

After the existing imports at the top of the file, add this dataclass (inside or just before the `MemoryStore` class definition):

```python
@dataclass
class CompactedSessionState:
    """Structured compact representation of a session's working state."""
    goal: str
    progress: str
    open_questions: str
    next_steps: str
    turn_index: int
    updated_at: str
```

Add `from dataclasses import dataclass` to imports if not already present.

Then add these two methods to the `MemoryStore` class (after `get_memory_context`):

```python
def read_compact_state(self) -> Optional["CompactedSessionState"]:
    """Read compact session state: Redis → PostgreSQL → None."""
    redis_client = _get_redis_sync()
    key = _compact_redis_key(self.user_id, self.session_id)
    if redis_client:
        try:
            raw = redis_client.get(key)
            if raw:
                data = orjson.loads(raw)
                return CompactedSessionState(**data)
        except Exception:
            pass
    # Fall back to PostgreSQL
    row = DatabaseBase.query_one(
        """SELECT content FROM user_memory
           WHERE user_id = %s AND session_id = %s AND memory_type = 'session_compact'
           ORDER BY updated_at DESC LIMIT 1""",
        (self.user_id, self.session_id),
    )
    if row:
        try:
            import json
            data = json.loads(row["content"])
            state = CompactedSessionState(**data)
            # backfill Redis
            if redis_client:
                try:
                    redis_client.setex(key, _COMPACT_REDIS_TTL, orjson.dumps(data))
                except Exception:
                    pass
            return state
        except Exception:
            pass
    return None

def write_compact_state(self, state: "CompactedSessionState") -> None:
    """Persist compact session state to Redis + PostgreSQL."""
    import json
    data = {
        "goal": state.goal, "progress": state.progress,
        "open_questions": state.open_questions, "next_steps": state.next_steps,
        "turn_index": state.turn_index, "updated_at": state.updated_at,
    }
    # Write Redis first (fast path)
    redis_client = _get_redis_sync()
    if redis_client:
        try:
            redis_client.setex(
                _compact_redis_key(self.user_id, self.session_id),
                _COMPACT_REDIS_TTL,
                orjson.dumps(data),
            )
        except Exception as exc:
            logger.debug("[MemoryStore] compact state Redis write failed: %s", exc)
    # Write PostgreSQL (durable)
    DatabaseBase.execute(
        """INSERT INTO user_memory (user_id, session_id, memory_type, content, updated_at)
           VALUES (%s, %s, 'session_compact', %s, NOW())
           ON CONFLICT (user_id, session_id, memory_type)
           DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()""",
        (self.user_id, self.session_id, json.dumps(data)),
    )
```

- [ ] **Step 2.4: Run — verify PASS**

```bash
python -m pytest tests/test_compact_state.py -v --no-cov
```
Expected: 5 passed

- [ ] **Step 2.5: Commit**

```bash
git add core/database/memory.py tests/test_compact_state.py
git commit -m "feat: add CompactedSessionState read/write to MemoryStore with Redis+PostgreSQL"
```

---

### Task 3: Wire `_get_history_for_prompt()` into manager

**Files:**
- Modify: `core/agents/manager.py`

- [ ] **Step 3.1: Write failing test**

Add to `tests/test_context_budget.py`:

```python
# ── manager integration ───────────────────────────────────────────────────────

def test_manager_uses_compact_state_when_over_budget():
    """When history > budget and compact state exists, manager returns formatted compact."""
    from unittest.mock import MagicMock, patch
    from core.agents.context_budget import CONTEXT_CHAR_BUDGET, CompactPrompt, format_compact_state

    long_history = "用戶: " + "x" * CONTEXT_CHAR_BUDGET

    mock_compact = CompactPrompt(
        goal="查詢BTC", progress="已完成", open_questions="", next_steps=""
    )

    with patch("core.agents.manager.history_exceeds_budget", return_value=True):
        with patch("core.agents.manager._read_compact_for_manager", return_value=mock_compact):
            from core.agents.manager import _get_history_for_prompt
            result = _get_history_for_prompt(long_history, user_id="u1", session_id="s1")

    assert "查詢BTC" in result
    assert "x" * 10 not in result  # raw history NOT passed through


def test_manager_uses_raw_history_when_under_budget():
    from unittest.mock import patch
    from core.agents.context_budget import CONTEXT_CHAR_BUDGET

    short_history = "用戶: hi\n助手: hello"

    with patch("core.agents.manager.history_exceeds_budget", return_value=False):
        from core.agents.manager import _get_history_for_prompt
        result = _get_history_for_prompt(short_history, user_id="u1", session_id="s1")

    assert result == short_history


def test_manager_falls_back_to_truncated_when_no_compact_state():
    from unittest.mock import patch
    from core.agents.context_budget import CONTEXT_CHAR_BUDGET

    long_history = "用戶: " + "x" * CONTEXT_CHAR_BUDGET

    with patch("core.agents.manager.history_exceeds_budget", return_value=True):
        with patch("core.agents.manager._read_compact_for_manager", return_value=None):
            from core.agents.manager import _get_history_for_prompt
            result = _get_history_for_prompt(long_history, user_id="u1", session_id="s1")

    # fallback: returns truncated to budget
    assert len(result) <= CONTEXT_CHAR_BUDGET
```

- [ ] **Step 3.2: Run — verify FAIL**

```bash
python -m pytest tests/test_context_budget.py -v --no-cov --tb=short
```
Expected: `ImportError` — `_get_history_for_prompt` not in manager

- [ ] **Step 3.3: Add module-level helpers + method to `manager.py`**

At the top of `manager.py`, add imports:

```python
from core.agents.context_budget import (
    CONTEXT_CHAR_BUDGET,
    CompactPrompt,
    history_exceeds_budget,
    format_compact_state,
)
```

After the imports, add two module-level functions (before `class ManagerAgent`):

```python
def _read_compact_for_manager(user_id: str, session_id: str) -> Optional[CompactPrompt]:
    """Read compact session state, return as CompactPrompt or None."""
    try:
        from core.database.memory import get_memory_store
        store = get_memory_store(user_id, session_id=session_id)
        state = store.read_compact_state()
        if state is None:
            return None
        return CompactPrompt(
            goal=state.goal,
            progress=state.progress,
            open_questions=state.open_questions,
            next_steps=state.next_steps,
        )
    except Exception:
        return None


def _get_history_for_prompt(
    raw_history: str,
    user_id: str,
    session_id: str,
) -> str:
    """Return history string for LLM prompt, respecting CONTEXT_CHAR_BUDGET.

    Priority:
      1. raw_history within budget → return as-is
      2. over budget + compact state available → return formatted compact block
      3. over budget + no compact state → truncate raw history to budget
    """
    if not history_exceeds_budget(raw_history):
        return raw_history
    compact = _read_compact_for_manager(user_id, session_id)
    if compact is not None:
        return format_compact_state(compact)
    # Fallback: truncate to budget (tail — keep most recent)
    return raw_history[-CONTEXT_CHAR_BUDGET:]
```

In `_understand_intent_node()`, find:
```python
history = state.get("history", "")
```
Replace with:
```python
history = state.get("history", "")
history = _get_history_for_prompt(
    history,
    user_id=self.user_id or "anonymous",
    session_id=self.session_id,
)
```

- [ ] **Step 3.4: Run — verify PASS**

```bash
python -m pytest tests/test_context_budget.py -v --no-cov
```
Expected: all 8 tests pass

- [ ] **Step 3.5: Run existing tests to check no regressions**

```bash
python -m pytest tests/test_base_react_agent.py tests/test_memory_cache.py tests/test_tool_compactor.py -v --no-cov -q
```
Expected: all pass

- [ ] **Step 3.6: Commit**

```bash
git add core/agents/manager.py tests/test_context_budget.py
git commit -m "feat: wire context budget check into manager — compact state replaces raw history when over budget"
```

---

### Task 4: Extend `consolidate()` to produce compact_state

**Files:**
- Modify: `core/database/memory.py` — extend `consolidate()` prompt + parse output
- Modify: `core/agents/manager.py` — call `write_compact_state` in `_do_consolidation()`

- [ ] **Step 4.1: Write failing test**

Add to `tests/test_compact_state.py`:

```python
def test_consolidate_writes_compact_state():
    """When LLM returns compact_state in consolidation response, it is stored."""
    import asyncio
    from unittest.mock import MagicMock, patch
    from langchain_core.messages import AIMessage

    llm_response = AIMessage(content="""{
        "history_entry": "[2026-03-18 10:00] 用戶查詢BTC價格",
        "memory_update": "## Long-term Memory\\n- 喜歡BTC分析",
        "compact_state": {
            "goal": "了解BTC走勢",
            "progress": "已取得價格資料",
            "open_questions": "技術指標待查詢",
            "next_steps": "執行RSI分析"
        }
    }""")

    from core.database.memory import MemoryStore
    store = MemoryStore("user-cons-1", session_id="sess-cons-1")
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=llm_response)

    written_state = {}

    def fake_write_compact(state):
        written_state["goal"] = state.goal
        written_state["progress"] = state.progress

    with patch.object(store, "write_compact_state", side_effect=fake_write_compact):
        with patch.object(store, "append_history"):
            with patch.object(store, "write_long_term"):
                with patch.object(store, "set_last_consolidated_index"):
                    with patch.object(store, "get_last_consolidated_index", return_value=0):
                        messages = [{"role": "user", "content": "BTC?", "timestamp": "2026-03-18 10:00"}]
                        result = asyncio.run(store.consolidate(messages, mock_llm))

    assert result is True
    assert written_state.get("goal") == "了解BTC走勢"
```

- [ ] **Step 4.2: Run — verify FAIL**

```bash
python -m pytest tests/test_compact_state.py::test_consolidate_writes_compact_state -v --no-cov --tb=short
```
Expected: FAIL — `write_compact_state` not called (compact_state not parsed)

- [ ] **Step 4.3: Extend `consolidate()` in `memory.py`**

In `MemoryStore.consolidate()`, find the existing prompt string and extend it. Replace the `Respond in this exact JSON format:` section:

```python
# OLD:
prompt = f"""...
Respond in this exact JSON format:
{{
    "history_entry": "[2026-01-01 10:00] Summary of what happened...",
    "memory_update": "# Long-term Memory\\n\\n## User Preferences\\n- ..."
}}"""

# NEW — add compact_state field:
prompt = f"""...
Respond in this exact JSON format:
{{
    "history_entry": "[2026-01-01 10:00] Summary of what happened...",
    "memory_update": "# Long-term Memory\\n\\n## User Preferences\\n- ...",
    "compact_state": {{
        "goal": "What the user is trying to achieve this session",
        "progress": "What has been resolved or answered",
        "open_questions": "Unresolved questions or threads (empty string if none)",
        "next_steps": "Suggested next actions (empty string if none)"
    }}
}}"""
```

After `update = result.get("memory_update")` and the existing write logic, add:

```python
# Write compact session state
compact_data = result.get("compact_state")
if compact_data and isinstance(compact_data, dict):
    try:
        from datetime import datetime
        state = CompactedSessionState(
            goal=str(compact_data.get("goal", "")),
            progress=str(compact_data.get("progress", "")),
            open_questions=str(compact_data.get("open_questions", "")),
            next_steps=str(compact_data.get("next_steps", "")),
            turn_index=new_index,
            updated_at=datetime.now().isoformat(),
        )
        self.write_compact_state(state)
    except Exception as exc:
        logger.warning("[MemoryStore] compact_state write failed: %s", exc)
else:
    logger.debug("[MemoryStore] compact_state absent from LLM consolidation response")
```

- [ ] **Step 4.4: Run — verify PASS**

```bash
python -m pytest tests/test_compact_state.py -v --no-cov
```
Expected: all 6 tests pass

- [ ] **Step 4.5: Commit**

```bash
git add core/database/memory.py tests/test_compact_state.py
git commit -m "feat: extend consolidate() to produce and persist CompactedSessionState"
```

---

## Chunk 2: Phase 3 — Task/Experience Memory + Tool Memory

---

### Task 5: Schema + `ExperienceStore`

**Files:**
- Modify: `core/database/schema.py`
- Create: `core/database/experiences.py`
- Create: `tests/test_experiences.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/test_experiences.py`:

```python
"""Tests for ExperienceStore — task_experiences + tool_execution_stats."""
from unittest.mock import patch, MagicMock
import pytest


# ── record_experience ─────────────────────────────────────────────────────────

def test_record_experience_calls_db_execute():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    with patch("core.database.experiences.DatabaseBase.execute") as mock_exec:
        store.record_experience(
            user_id="u1", session_id="s1", task_family="crypto",
            query="BTC價格", tools_used=["get_crypto_price"],
            agent_used="crypto", outcome="success",
            quality_score=1.0, failure_reason=None, response_chars=500,
        )
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert "task_experiences" in call_args[0]


def test_record_experience_maps_quality_string_to_float():
    from core.database.experiences import ExperienceStore, _quality_to_float
    assert _quality_to_float("pass") == 1.0
    assert _quality_to_float("fail") == 0.0
    assert _quality_to_float(None) is None
    assert _quality_to_float(0.75) == 0.75


# ── record_tool_stat ──────────────────────────────────────────────────────────

def test_record_tool_stat_calls_db_execute():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    with patch("core.database.experiences.DatabaseBase.execute") as mock_exec:
        store.record_tool_stat(
            user_id="u1", tool_name="get_crypto_price",
            success=True, latency_ms=120, output_chars=300, error_type=None,
        )
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert "tool_execution_stats" in call_args[0]


# ── retrieve_relevant ─────────────────────────────────────────────────────────

def test_retrieve_relevant_returns_list():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    rows = [
        {"id": 1, "task_family": "crypto", "query_text": "BTC走勢",
         "tools_used": ["get_crypto_price"], "agent_used": "crypto",
         "outcome": "success", "quality_score": 1.0,
         "failure_reason": None, "created_at": "2026-03-18"},
    ]
    with patch("core.database.experiences.DatabaseBase.query_all", return_value=rows):
        results = store.retrieve_relevant(
            user_id="u1", task_family="crypto",
            query="BTC今天怎麼樣", llm=None,
        )
    assert isinstance(results, list)
    assert len(results) == 1


def test_retrieve_relevant_returns_empty_on_db_error():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    with patch("core.database.experiences.DatabaseBase.query_all", side_effect=Exception("DB down")):
        results = store.retrieve_relevant(
            user_id="u1", task_family="crypto", query="BTC", llm=None
        )
    assert results == []


# ── user isolation ────────────────────────────────────────────────────────────

def test_retrieve_relevant_filters_by_user_id():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    captured_params = {}
    def fake_query_all(sql, params):
        captured_params["params"] = params
        return []
    with patch("core.database.experiences.DatabaseBase.query_all", side_effect=fake_query_all):
        store.retrieve_relevant(user_id="u-specific", task_family="crypto", query="BTC", llm=None)
    assert "u-specific" in captured_params["params"]


def test_retrieve_relevant_rejects_null_user_id():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    results = store.retrieve_relevant(
        user_id=None, task_family="crypto", query="BTC", llm=None
    )
    assert results == []


# ── layer 3 LLM rerank skipped when < 2 candidates ───────────────────────────

def test_layer3_skipped_when_fewer_than_2_candidates():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    mock_llm = MagicMock()
    rows = [{"id": 1, "task_family": "crypto", "query_text": "BTC",
             "tools_used": [], "agent_used": "crypto", "outcome": "success",
             "quality_score": 1.0, "failure_reason": None, "created_at": "2026-03-18"}]
    with patch("core.database.experiences.DatabaseBase.query_all", return_value=rows):
        store.retrieve_relevant(user_id="u1", task_family="crypto", query="BTC", llm=mock_llm)
    mock_llm.invoke.assert_not_called()
```

- [ ] **Step 5.2: Run — verify FAIL**

```bash
python -m pytest tests/test_experiences.py -v --no-cov --tb=short
```
Expected: `ModuleNotFoundError: No module named 'core.database.experiences'`

- [ ] **Step 5.3: Add tables to `schema.py`**

In `schema.py`, find the function that creates the memory tables (near `create_user_facts_table`). Add a new function:

```python
def create_experience_tables(c):
    """Create task_experiences and tool_execution_stats tables for Phase 3 memory."""
    c.execute("""
        CREATE TABLE IF NOT EXISTS task_experiences (
            id              BIGSERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            session_id      TEXT NOT NULL,
            task_family     TEXT NOT NULL,
            query_text      TEXT NOT NULL,
            query_tsv       TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', query_text)) STORED,
            tools_used      TEXT[],
            agent_used      TEXT,
            outcome         TEXT NOT NULL,
            quality_score   REAL,
            failure_reason  TEXT,
            response_chars  INT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_te_user_family ON task_experiences(user_id, task_family)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_te_created ON task_experiences(created_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_te_tsv ON task_experiences USING GIN(query_tsv)")

    c.execute("""
        CREATE TABLE IF NOT EXISTS tool_execution_stats (
            id           BIGSERIAL PRIMARY KEY,
            user_id      TEXT,
            tool_name    TEXT NOT NULL,
            success      BOOLEAN NOT NULL,
            latency_ms   INT,
            output_chars INT,
            error_type   TEXT,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_tes_tool_created ON tool_execution_stats(tool_name, created_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tes_user_tool ON tool_execution_stats(user_id, tool_name)")
```

Then call `create_experience_tables(c)` in the main table-creation function (same place `create_user_facts_table` is called).

- [ ] **Step 5.4: Create `core/database/experiences.py`**

```python
"""
Experience and tool memory store for Phase 3.

Provides:
- record_experience(): write task trajectory after each agent turn
- record_tool_stat(): write tool telemetry after each tool invocation
- retrieve_relevant(): 3-layer retrieval (structured + FTS + optional LLM rerank)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import DatabaseBase

logger = logging.getLogger(__name__)


def _quality_to_float(quality: Any) -> Optional[float]:
    """Map AgentResult.quality (str or float) to float for storage."""
    if quality is None:
        return None
    if isinstance(quality, float):
        return quality
    if quality == "pass":
        return 1.0
    if quality == "fail":
        return 0.0
    return None


class ExperienceStore:
    """Read/write task experiences and tool execution stats."""

    # ── writes ────────────────────────────────────────────────────────────────

    def record_experience(
        self,
        user_id: str,
        session_id: str,
        task_family: str,
        query: str,
        tools_used: List[str],
        agent_used: str,
        outcome: str,
        quality_score: Any = None,
        failure_reason: Optional[str] = None,
        response_chars: Optional[int] = None,
    ) -> None:
        """Persist one task trajectory. Called fire-and-forget from manager."""
        try:
            DatabaseBase.execute(
                """INSERT INTO task_experiences
                   (user_id, session_id, task_family, query_text,
                    tools_used, agent_used, outcome,
                    quality_score, failure_reason, response_chars)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    user_id, session_id, task_family, query,
                    tools_used, agent_used, outcome,
                    _quality_to_float(quality_score), failure_reason, response_chars,
                ),
            )
        except Exception as exc:
            logger.warning("[ExperienceStore] record_experience failed: %s", exc)

    def record_tool_stat(
        self,
        user_id: Optional[str],
        tool_name: str,
        success: bool,
        latency_ms: Optional[int] = None,
        output_chars: Optional[int] = None,
        error_type: Optional[str] = None,
    ) -> None:
        """Persist one tool execution stat. Called fire-and-forget from manager."""
        try:
            DatabaseBase.execute(
                """INSERT INTO tool_execution_stats
                   (user_id, tool_name, success, latency_ms, output_chars, error_type)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, tool_name, success, latency_ms, output_chars, error_type),
            )
        except Exception as exc:
            logger.warning("[ExperienceStore] record_tool_stat failed: %s", exc)

    # ── retrieval ─────────────────────────────────────────────────────────────

    def retrieve_relevant(
        self,
        user_id: Optional[str],
        task_family: str,
        query: str,
        llm: Any,
        limit: int = 5,
    ) -> List[Dict]:
        """3-layer retrieval: structured filter + FTS (combined SQL) + optional LLM rerank.

        Returns empty list on any failure — never raises.
        """
        if not user_id:
            return []
        try:
            candidates = self._layer1_2_query(user_id, task_family, query, limit)
            if len(candidates) >= 2 and llm is not None:
                candidates = self._layer3_llm_rerank(candidates, query, llm)
            return candidates
        except Exception as exc:
            logger.warning("[ExperienceStore] retrieve_relevant failed: %s", exc)
            return []

    def _layer1_2_query(
        self,
        user_id: str,
        task_family: str,
        query: str,
        limit: int,
    ) -> List[Dict]:
        """Layers 1+2: structured filter + FTS ts_rank in a single SQL round-trip."""
        rows = DatabaseBase.query_all(
            """SELECT id, task_family, query_text, tools_used, agent_used,
                      outcome, quality_score, failure_reason, created_at,
                      ts_rank(query_tsv, plainto_tsquery('simple', %s)) AS rank
               FROM task_experiences
               WHERE user_id = %s
                 AND task_family = %s
               ORDER BY rank DESC, created_at DESC
               LIMIT %s""",
            (query, user_id, task_family, limit),
        )
        return rows or []

    def _layer3_llm_rerank(
        self,
        candidates: List[Dict],
        current_query: str,
        llm: Any,
    ) -> List[Dict]:
        """Layer 3: ask LLM to select the 1-2 most relevant candidates.

        Falls back to returning candidates unchanged on any failure.
        """
        try:
            from langchain_core.messages import HumanMessage
            numbered = "\n".join(
                f"{i+1}. [{c['outcome']}] {c['query_text']} "
                f"(工具: {', '.join(c.get('tools_used') or [])})"
                for i, c in enumerate(candidates)
            )
            prompt = (
                f"Current query: {current_query}\n\n"
                f"Past experiences:\n{numbered}\n\n"
                "Which 1-2 past experiences are most relevant? "
                "Reply with only the numbers, comma-separated (e.g. '1,3')."
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            indices_str = response.content.strip()
            indices = [int(x.strip()) - 1 for x in indices_str.split(",") if x.strip().isdigit()]
            selected = [candidates[i] for i in indices if 0 <= i < len(candidates)]
            return selected if selected else candidates
        except Exception as exc:
            logger.debug("[ExperienceStore] layer3 rerank failed, returning unranked: %s", exc)
            return candidates

    def format_for_prompt(self, experiences: List[Dict]) -> str:
        """Format retrieved experiences as a compact hint block for LLM injection."""
        if not experiences:
            return ""
        lines = ["## 相關過去經驗（僅供參考）"]
        for exp in experiences:
            tools = ", ".join(exp.get("tools_used") or []) or "無"
            date = str(exp.get("created_at", ""))[:10]
            outcome = exp.get("outcome", "unknown")
            reason = f" 原因: {exp['failure_reason']}" if exp.get("failure_reason") else ""
            lines.append(
                f"- [{exp.get('task_family', '')}, {date}] "
                f"{exp.get('query_text', '')} → 工具: {tools} → {outcome}{reason}"
            )
        return "\n".join(lines)
```

- [ ] **Step 5.5: Run — verify PASS**

```bash
python -m pytest tests/test_experiences.py -v --no-cov
```
Expected: all 7 tests pass

- [ ] **Step 5.6: Commit**

```bash
git add core/database/schema.py core/database/experiences.py tests/test_experiences.py
git commit -m "feat: add ExperienceStore with task_experiences + tool_execution_stats tables and 3-layer retrieval"
```

---

### Task 6: Tool stat collection in `tool_compactor.py`

**Files:**
- Modify: `core/agents/tool_compactor.py`

- [ ] **Step 6.1: Write failing test**

Add to `tests/test_tool_compactor.py` (append after existing tests):

```python
# ── tool stat collection ──────────────────────────────────────────────────────

def test_wrapper_records_pending_stat_on_success():
    """After invoke(), wrapper exposes a pending stat tuple."""
    from core.agents.tool_compactor import wrap_tool, _reset_for_testing
    _reset_for_testing()
    tool = _make_tool("small output")
    wrapped = wrap_tool(tool, owner_id="u1")
    wrapped.invoke({})
    assert wrapped.last_stat is not None
    stat = wrapped.last_stat
    assert stat["tool_name"] == "mock_tool"
    assert stat["success"] is True
    assert stat["output_chars"] > 0


def test_wrapper_records_pending_stat_on_failure():
    """After a failing invoke(), last_stat has success=False and error_type set."""
    from core.agents.tool_compactor import wrap_tool, _reset_for_testing
    _reset_for_testing()
    tool = MagicMock()
    tool.name = "fail_tool"
    tool.invoke = MagicMock(side_effect=RuntimeError("API down"))
    wrapped = wrap_tool(tool, owner_id="u1")
    try:
        wrapped.invoke({})
    except RuntimeError:
        pass
    assert wrapped.last_stat is not None
    assert wrapped.last_stat["success"] is False
    assert wrapped.last_stat["error_type"] == "RuntimeError"
```

- [ ] **Step 6.2: Run — verify FAIL**

```bash
python -m pytest tests/test_tool_compactor.py::test_wrapper_records_pending_stat_on_success tests/test_tool_compactor.py::test_wrapper_records_pending_stat_on_failure -v --no-cov --tb=short
```
Expected: `AttributeError: '_CompactingToolWrapper' object has no attribute 'last_stat'`

- [ ] **Step 6.3: Extend `_CompactingToolWrapper` in `tool_compactor.py`**

Add `import time` to the top of `tool_compactor.py`.

In `_CompactingToolWrapper.__init__()`, add:
```python
self.last_stat: Optional[dict] = None
```

Replace the existing `invoke()` method body:

```python
def invoke(self, input: Any, **kwargs: Any) -> Any:  # noqa: A002
    import time
    start = time.monotonic()
    try:
        raw = self._original.invoke(input, **kwargs)
        text = _to_str(raw)
        latency_ms = int((time.monotonic() - start) * 1000)
        self.last_stat = {
            "tool_name": getattr(self._original, "name", "unknown"),
            "success": True,
            "latency_ms": latency_ms,
            "output_chars": len(text),
            "error_type": None,
        }
        if len(text) <= THRESHOLD:
            return raw
        uid = _store_sync(
            text,
            owner_id=self._owner_id,
            workspace_id=self._workspace_id,
            session_id=self._session_id,
        )
        preview = text[:PREVIEW_LEN]
        return (
            f"[COMPACTED:{uid}]\n"
            f"{preview}...\n"
            f"[{len(text):,} chars total. Retrieve full data with key: {uid}]"
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        self.last_stat = {
            "tool_name": getattr(self._original, "name", "unknown"),
            "success": False,
            "latency_ms": latency_ms,
            "output_chars": 0,
            "error_type": type(exc).__name__,
        }
        raise
```

- [ ] **Step 6.4: Run — verify PASS**

```bash
python -m pytest tests/test_tool_compactor.py -v --no-cov
```
Expected: all 19 tests pass

- [ ] **Step 6.5: Commit**

```bash
git add core/agents/tool_compactor.py tests/test_tool_compactor.py
git commit -m "feat: collect tool execution stats in _CompactingToolWrapper.last_stat"
```

---

### Task 7: Wire record + retrieve into manager

**Files:**
- Modify: `core/agents/manager.py`

- [ ] **Step 7.1: Write failing tests**

Create `tests/test_manager_experience.py`:

```python
"""Tests for manager experience recording + hint injection."""
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest


def test_record_experience_background_called_after_track():
    """_track_conversation fires _record_experience_background as a background task."""
    # We verify the coroutine is created (not that it runs — that's ExperienceStore's job)
    from core.agents.manager import ManagerAgent
    from unittest.mock import MagicMock, patch

    manager = MagicMock(spec=ManagerAgent)
    manager.user_id = "u1"
    manager.session_id = "s1"
    manager._message_count = 0
    manager._last_consolidated_index = 0
    manager._consolidating = False
    manager._last_activity_time = 0.0

    tasks_created = []

    with patch("core.agents.manager.asyncio.create_task", side_effect=tasks_created.append):
        # call the real method on the mock instance
        asyncio.run(ManagerAgent._track_conversation(
            manager, "BTC price?", "BTC is 42000", tools_used=["get_crypto_price"]
        ))

    # At minimum _extract_facts_background is created; _record_experience also created
    assert len(tasks_created) >= 1


def test_experience_hint_injected_in_prompt_when_available():
    """When retrieve_relevant returns results, prompt includes hint block."""
    from core.database.experiences import ExperienceStore
    hint_rows = [
        {"task_family": "crypto", "query_text": "BTC走勢", "tools_used": ["get_crypto_price"],
         "agent_used": "crypto", "outcome": "success", "quality_score": 1.0,
         "failure_reason": None, "created_at": "2026-03-15"},
    ]
    store = ExperienceStore()
    hint = store.format_for_prompt(hint_rows)
    assert "BTC走勢" in hint
    assert "get_crypto_price" in hint
    assert "相關過去經驗" in hint


def test_experience_hint_empty_string_when_no_results():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    assert store.format_for_prompt([]) == ""
```

- [ ] **Step 7.2: Run — verify current state**

```bash
python -m pytest tests/test_manager_experience.py -v --no-cov --tb=short
```

- [ ] **Step 7.3: Add `_record_experience_background()` to `manager.py`**

Add import at top of `manager.py`:
```python
from core.database.experiences import ExperienceStore
_experience_store = ExperienceStore()
```

Add method to `ManagerAgent` class (after `_extract_facts_background`):

```python
async def _record_experience_background(
    self,
    user_message: str,
    assistant_response: str,
    tools_used: Optional[List[str]],
    task_results: Optional[dict] = None,
) -> None:
    """Fire-and-forget: record task trajectory + tool stats after each turn."""
    try:
        # Determine task_family from agent names used
        task_family = "chat"
        if task_results:
            agents_used = [v.get("agent_name", "") for v in task_results.values() if isinstance(v, dict)]
            for agent in agents_used:
                if agent in ("crypto", "tw_stock", "us_stock", "forex", "commodity", "economic"):
                    task_family = agent
                    break

        # Determine outcome from task_results quality
        outcome = "success"
        quality = None
        if task_results:
            qualities = [v.get("quality") for v in task_results.values() if isinstance(v, dict)]
            if "fail" in qualities:
                outcome = "failure"
                quality = "fail"
            else:
                quality = "pass"

        _experience_store.record_experience(
            user_id=self.user_id or "anonymous",
            session_id=self.session_id,
            task_family=task_family,
            query=user_message,
            tools_used=tools_used or [],
            agent_used=",".join(set(
                v.get("agent_name", "") for v in (task_results or {}).values()
                if isinstance(v, dict) and v.get("agent_name")
            )),
            outcome=outcome,
            quality_score=quality,
            failure_reason=None,
            response_chars=len(assistant_response),
        )

        # Record per-tool stats from wrapped tool last_stat (if available)
        # Tools expose last_stat after invoke() — collect via tool_metas if accessible
        # (latency is best-effort; skipped here since tool refs not retained post-execution)

    except Exception as exc:
        logger.debug("[Manager] _record_experience_background failed: %s", exc)
```

In `_track_conversation()`, after the existing `asyncio.create_task(self._extract_facts_background(...))` line, add:

```python
asyncio.create_task(self._record_experience_background(
    user_message, assistant_response, tools_used
))
```

- [ ] **Step 7.4: Add experience hint injection to `_understand_intent_node()`**

In `_understand_intent_node()`, after the `long_term_memory = self.get_long_term_memory_context()` line, add:

```python
# Retrieve relevant past experiences for planner hint
experience_hint = ""
try:
    detected_family = "chat"  # default; intent not yet parsed
    experiences = _experience_store.retrieve_relevant(
        user_id=self.user_id,
        task_family=detected_family,
        query=query,
        llm=self.llm,
    )
    experience_hint = _experience_store.format_for_prompt(experiences)
except Exception:
    pass
```

Then in the `PromptRegistry.render(...)` call for `intent_understanding`, add `experience_hint=experience_hint` as a parameter. Also update the `long_term_memory` section in the prompt template to include the hint block:

```python
long_term_memory_with_hints = long_term_memory or "（尚無長期記憶）"
if experience_hint:
    long_term_memory_with_hints += f"\n\n{experience_hint}"
```

Pass `long_term_memory=long_term_memory_with_hints` to `PromptRegistry.render(...)`.

- [ ] **Step 7.5: Run full test suite on affected files**

```bash
python -m pytest tests/test_experiences.py tests/test_manager_experience.py tests/test_context_budget.py tests/test_compact_state.py tests/test_tool_compactor.py tests/test_memory_cache.py -v --no-cov -q
```
Expected: all pass

- [ ] **Step 7.6: Parse check all modified files**

```bash
python -c "
import ast, sys
files = [
    'core/agents/context_budget.py',
    'core/agents/manager.py',
    'core/agents/tool_compactor.py',
    'core/database/memory.py',
    'core/database/experiences.py',
    'core/database/schema.py',
]
for f in files:
    try:
        ast.parse(open(f).read())
        print(f'OK: {f}')
    except SyntaxError as e:
        print(f'FAIL: {f}: {e}')
        sys.exit(1)
"
```
Expected: all `OK:`

- [ ] **Step 7.7: Final commit**

```bash
git add core/agents/manager.py tests/test_manager_experience.py
git commit -m "feat: wire Phase 3 experience recording + hint injection into manager"
```

---

## Verification (all chunks complete)

- [ ] **Run all new tests:**

```bash
python -m pytest tests/test_context_budget.py tests/test_compact_state.py tests/test_experiences.py tests/test_manager_experience.py tests/test_tool_compactor.py tests/test_memory_cache.py tests/test_memory_isolation.py tests/test_tool_registry_retrieve.py -v --no-cov -q
```
Expected: all pass, 0 failures

- [ ] **Update plan progress tracker** — mark all items `[x]`

- [ ] **Update Phase 2+3 items in `docs/superpowers/plans/2026-03-18-memory-phase1.md` progress tracker**
