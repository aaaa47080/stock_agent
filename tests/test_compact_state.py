"""Tests for CompactedSessionState read/write in MemoryStore."""

from unittest.mock import patch

import orjson
import pytest


@pytest.fixture(autouse=True)
def reset_state():
    from core.database import memory as mem_mod

    mem_mod._reset_for_testing()
    yield
    mem_mod._reset_for_testing()


class FakeRedis:
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
    from core.database.memory import (
        CompactedSessionState,
        MemoryStore,
        _compact_redis_key,
    )

    store = MemoryStore("user-cs-2", session_id="sess-2")
    state = _make_state()
    fake_redis = FakeRedis()
    fake_redis._store[_compact_redis_key("user-cs-2", "sess-2")] = orjson.dumps(
        {
            "goal": state.goal,
            "progress": state.progress,
            "open_questions": state.open_questions,
            "next_steps": state.next_steps,
            "turn_index": state.turn_index,
            "updated_at": state.updated_at,
        }
    )

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        result = store.read_compact_state()

    assert isinstance(result, CompactedSessionState)
    assert result.goal == state.goal


# ── read redis miss → postgresql ──────────────────────────────────────────────


def test_read_compact_state_postgresql_fallback():
    from core.database.memory import CompactedSessionState, MemoryStore

    store = MemoryStore("user-cs-3", session_id="sess-3")
    state = _make_state()
    import json

    db_row = {
        "content": json.dumps(
            {
                "goal": state.goal,
                "progress": state.progress,
                "open_questions": state.open_questions,
                "next_steps": state.next_steps,
                "turn_index": state.turn_index,
                "updated_at": state.updated_at,
            }
        )
    }

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

    _store_a = MemoryStore("user-cs-5", session_id="sess-a")
    _store_b = MemoryStore("user-cs-5", session_id="sess-b")
    assert _compact_redis_key("user-cs-5", "sess-a") != _compact_redis_key(
        "user-cs-5", "sess-b"
    )


# ── consolidate writes compact state ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_consolidate_writes_compact_state():
    """When LLM returns compact_state in consolidation response, it is stored."""
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    llm_response = AIMessage(
        content="""{
        "history_entry": "[2026-03-18 10:00] 用戶查詢BTC價格",
        "memory_update": "## Long-term Memory\\n- 喜歡BTC分析",
        "compact_state": {
            "goal": "了解BTC走勢",
            "progress": "已取得價格資料",
            "open_questions": "技術指標待查詢",
            "next_steps": "執行RSI分析"
        }
    }"""
    )

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
                with patch.object(store, "read_long_term", return_value=""):
                    with patch.object(store, "set_last_consolidated_index"):
                        with patch.object(
                            store, "get_last_consolidated_index", return_value=0
                        ):
                            messages = [
                                {
                                    "role": "user",
                                    "content": "BTC?",
                                    "timestamp": "2026-03-18 10:00",
                                }
                            ]
                            result = await store.consolidate(
                                messages, mock_llm, archive_all=True
                            )

    assert result is True
    assert written_state.get("goal") == "了解BTC走勢"
