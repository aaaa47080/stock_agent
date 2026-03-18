from unittest.mock import patch

import orjson
import pytest


@pytest.fixture(autouse=True)
def reset_memory_cache_state():
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


def _make_store(user_id="user-test-1"):
    from core.database.memory import MemoryStore

    return MemoryStore(user_id)


def test_second_call_does_not_hit_db():
    from core.database.memory import _mem_l1_delete

    store = _make_store("user-l1-test")
    _mem_l1_delete("user-l1-test")
    db_call_count = [0]

    def fake_db_context(self, *args, **kwargs):
        db_call_count[0] += 1
        return "db result"

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch.object(type(store), "_read_from_db", fake_db_context):
            store.get_memory_context()
            store.get_memory_context()

    assert db_call_count[0] == 1


def test_write_long_term_invalidates_l1():
    from core.database.memory import _mem_l1_get, _mem_l1_set

    store = _make_store("user-inv-test")
    _mem_l1_set("user-inv-test", "stale data")
    assert _mem_l1_get("user-inv-test") == "stale data"

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_long_term("new memory")

    assert _mem_l1_get("user-inv-test") is None


def test_append_history_invalidates_l1():
    from core.database.memory import _mem_l1_get, _mem_l1_set

    store = _make_store("user-hist-test")
    _mem_l1_set("user-hist-test", "old context")

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.append_history("[2026-03-18 10:00] USER: hello")

    assert _mem_l1_get("user-hist-test") is None


def test_l2_redis_hit_skips_postgresql():
    from core.database.memory import _mem_cache_key, _mem_l1_delete

    store = _make_store("user-redis-hit")
    _mem_l1_delete("user-redis-hit")
    fake_redis = FakeRedis()
    fake_redis._store[_mem_cache_key(store.scope)] = orjson.dumps("redis cached context")

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch.object(type(store), "_read_from_db") as mock_db:
            result = store.get_memory_context()
            mock_db.assert_not_called()

    assert result == "redis cached context"


def test_l2_redis_populated_on_db_miss():
    from core.database.memory import _mem_cache_key, _mem_l1_delete

    store = _make_store("user-redis-miss")
    _mem_l1_delete("user-redis-miss")
    fake_redis = FakeRedis()

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch.object(type(store), "_read_from_db", return_value="from db"):
            store.get_memory_context()

    assert _mem_cache_key(store.scope) in fake_redis._store


def test_write_long_term_invalidates_redis():
    from core.database.memory import _mem_cache_key

    store = _make_store("user-redis-inv")
    fake_redis = FakeRedis()
    fake_redis._store[_mem_cache_key(store.scope)] = orjson.dumps("old")

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_long_term("new memory")

    assert _mem_cache_key(store.scope) not in fake_redis._store


def test_write_facts_invalidates_redis():
    from core.database.memory import _mem_cache_key

    store = _make_store("user-facts-inv")
    fake_redis = FakeRedis()
    fake_redis._store[_mem_cache_key(store.scope)] = orjson.dumps("old")

    with patch("core.database.memory._get_redis_sync", return_value=fake_redis):
        with patch("core.database.memory.DatabaseBase.execute"):
            store.write_facts([{"key": "pref", "value": "crypto", "confidence": "high", "source_turn": 1}])

    assert _mem_cache_key(store.scope) not in fake_redis._store


def test_redis_unavailable_falls_back_to_postgresql():
    from core.database.memory import _mem_l1_delete

    store = _make_store("user-fallback")
    _mem_l1_delete("user-fallback")

    with patch("core.database.memory._get_redis_sync", return_value=None):
        with patch.object(type(store), "_read_from_db", return_value="db only result"):
            result = store.get_memory_context()

    assert result == "db only result"
