from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_memory_cache_state():
    from core.database import memory as mem_mod

    mem_mod._reset_for_testing()
    yield
    mem_mod._reset_for_testing()


def test_memory_l1_cache_isolated_per_user():
    from core.database.memory import MemoryStore, _mem_l1_get

    store_a = MemoryStore("user-a")
    store_b = MemoryStore("user-b")

    with patch.object(type(store_a), "_read_from_db", return_value="context-a"):
        assert store_a.get_memory_context() == "context-a"

    with patch.object(type(store_b), "_read_from_db", return_value="context-b"):
        assert store_b.get_memory_context() == "context-b"

    assert _mem_l1_get("user-a") == "context-a"
    assert _mem_l1_get("user-b") == "context-b"


def test_memory_invalidation_only_affects_target_user():
    from core.database.memory import MemoryStore, _mem_l1_get, _mem_l1_set

    store_a = MemoryStore("user-a")
    _mem_l1_set("user-a", "context-a")
    _mem_l1_set("user-b", "context-b")

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.execute"):
            store_a.write_long_term("new memory")

    assert _mem_l1_get("user-a") is None
    assert _mem_l1_get("user-b") == "context-b"


def test_workspace_scopes_produce_distinct_memory_cache_keys():
    from core.database.memory import MemoryStore, _mem_cache_key

    store_a = MemoryStore("user-a", workspace_id="ws-1")
    store_b = MemoryStore("user-a", workspace_id="ws-2")

    assert _mem_cache_key(store_a.scope) != _mem_cache_key(store_b.scope)


def test_memory_factory_separates_same_user_by_workspace():
    from core.database.memory import get_memory_store

    store_a = get_memory_store("user-a", session_id="sess-1", workspace_id="ws-1")
    store_b = get_memory_store("user-a", session_id="sess-1", workspace_id="ws-2")

    assert store_a is not store_b
