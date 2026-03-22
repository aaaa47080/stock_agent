"""
系統快取 — Redis-first with DB fallback

Read path:  Redis → DB fallback
Write path: Redis (async best-effort) + DB (always)
Delete:     Redis + DB

When Redis is unavailable every operation silently degrades to DB-only,
so existing callers are never disrupted.
"""

import json
import logging
from typing import Any, Optional

from .base import DatabaseBase

logger = logging.getLogger(__name__)

# ── Redis connection ────────────────────────────────────────────────────────────
_KEY_PREFIX = "stock_agent:"
_redis_client = None
_redis_available = False


def _init_redis() -> None:
    """Try to connect to Redis; set ``_redis_available`` flag."""
    global _redis_client, _redis_available
    if _redis_available:
        return  # already connected

    try:
        import redis as redis_lib
    except ImportError:
        logger.debug("redis package not installed — DB-only cache")
        return

    # Reuse the project-wide URL resolver
    from core.redis_url import resolve_redis_url

    redis_url, source = resolve_redis_url()
    if not redis_url:
        logger.debug("REDIS_URL not set — DB-only cache")
        return

    try:
        _redis_client = redis_lib.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info("Cache Redis connected (%s): %s", source, redis_url)
    except Exception as exc:
        logger.warning("Cache Redis connection failed, using DB fallback: %s", exc)
        _redis_client = None
        _redis_available = False


def _redis_key(key: str) -> str:
    """Namespace a bare cache key for Redis."""
    return f"{_KEY_PREFIX}{key}"


# ── Internal Redis helpers (never raise) ────────────────────────────────────────


def _redis_get(key: str) -> Optional[Any]:
    if not _redis_available:
        return None
    try:
        val = _redis_client.get(_redis_key(key))
        if val is not None:
            return json.loads(val)
    except Exception as exc:
        logger.warning("Redis GET failed for %s: %s", key, exc)
    return None


def _redis_set(key: str, data: Any, ttl: Optional[int] = None) -> bool:
    if not _redis_available:
        return False
    try:
        val = json.dumps(data, ensure_ascii=False)
        rk = _redis_key(key)
        if ttl is not None and ttl > 0:
            _redis_client.setex(rk, ttl, val)
        else:
            _redis_client.set(rk, val)
        return True
    except Exception as exc:
        logger.warning("Redis SET failed for %s: %s", key, exc)
        return False


def _redis_delete(key: str) -> bool:
    if not _redis_available:
        return False
    try:
        return bool(_redis_client.delete(_redis_key(key)))
    except Exception as exc:
        logger.warning("Redis DEL failed for %s: %s", key, exc)
        return False


def _redis_clear() -> bool:
    if not _redis_available:
        return False
    try:
        # Use SCAN to avoid blocking on large keyspaces
        cursor = 0
        while True:
            cursor, keys = _redis_client.scan(
                cursor, match=f"{_KEY_PREFIX}*", count=100
            )
            if keys:
                _redis_client.delete(*keys)
            if cursor == 0:
                break
        return True
    except Exception as exc:
        logger.warning("Redis SCAN/DEL failed: %s", exc)
        return False


# ── Internal DB helpers (original implementation) ───────────────────────────────


def _db_set(key: str, data: Any) -> None:
    """Write cache entry to system_cache table (upsert)."""
    json_str = json.dumps(data, ensure_ascii=False)
    DatabaseBase.execute(
        """
        INSERT INTO system_cache (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT(key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
    """,
        (key, json_str),
    )


def _db_get(key: str) -> Optional[Any]:
    """Read cache entry from system_cache table."""
    result = DatabaseBase.query_one(
        "SELECT value FROM system_cache WHERE key = %s",
        (key,),
    )
    if result:
        try:
            return json.loads(result["value"])
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("DB cache read error for %s: %s", key, exc)
            return None
    return None


def _db_delete(key: str) -> bool:
    """Delete cache entry from system_cache table."""
    rows_affected = DatabaseBase.execute(
        "DELETE FROM system_cache WHERE key = %s",
        (key,),
    )
    return rows_affected > 0


def _db_clear() -> None:
    """Delete all entries from system_cache table."""
    DatabaseBase.execute("DELETE FROM system_cache")


# ── Public API (backward-compatible) ───────────────────────────────────────────


def set_cache(key: str, data: Any, ttl: Optional[int] = None) -> None:
    """
    Store *data* under *key*.

    Writes to Redis (with optional TTL) **and** DB (always).
    The DB write acts as the persistent fallback so data survives
    Redis restarts.
    """
    _init_redis()
    _redis_set(key, data, ttl=ttl)
    # DB is always written for durability
    _db_set(key, data)


def get_cache(key: str) -> Optional[Any]:
    """
    Retrieve cached data for *key*.

    Tries Redis first; falls back to DB on miss or Redis failure.
    """
    _init_redis()
    result = _redis_get(key)
    if result is not None:
        return result
    # Fallback to DB
    return _db_get(key)


def delete_cache(key: str) -> bool:
    """
    Remove *key* from both Redis and DB.

    Returns ``True`` if the key existed in at least one store.
    """
    _init_redis()
    redis_ok = _redis_delete(key)
    db_ok = _db_delete(key)
    return redis_ok or db_ok


def clear_all_cache() -> None:
    """
    Remove **all** cache entries from both Redis and DB.

    Redis keys are scoped to the ``stock_agent:`` prefix so
    other tenants sharing the same Redis instance are unaffected.
    """
    _init_redis()
    _redis_clear()
    _db_clear()
