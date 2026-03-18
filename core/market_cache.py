"""
Unified async market-data cache.

Architecture (hot → cold):
  L1  TTLCache (in-process, ~10 s)   — zero network latency, absorbs burst traffic
  L2  Redis async (shared across workers, per-key TTL)
  L3  caller re-fetches from yfinance / TWSE on cache miss

Graceful degradation:
  If Redis is not configured or unreachable, falls back to L1-only.
  L1 still protects against duplicate yfinance calls within the same process.

No new dependencies — uses packages already in requirements.txt:
  cachetools==6.2.2   (TTLCache)
  redis==7.3.0        (redis.asyncio)
  orjson==3.11.6      (fast JSON)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import orjson
from cachetools import TTLCache

from core.redis_url import resolve_redis_url

logger = logging.getLogger(__name__)

# ── L1 configuration ─────────────────────────────────────────────────────────
_L1_MAX = 1024  # max entries in the in-process cache
_L1_TTL = 10  # seconds — catches burst traffic without a Redis round-trip

# ── Redis key prefix ──────────────────────────────────────────────────────────
_KEY_PREFIX = "mkt:"  # distinct from "config:" used by system_config

# ── Module-level state ────────────────────────────────────────────────────────
_l1: TTLCache = TTLCache(maxsize=_L1_MAX, ttl=_L1_TTL)
_redis: Optional[Any] = None  # redis.asyncio.Redis or None
_redis_checked: bool = False  # lazy-init flag


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _get_redis() -> Optional[Any]:
    """Return a live async Redis client, or None if unavailable."""
    global _redis, _redis_checked
    if _redis_checked:
        return _redis

    _redis_checked = True
    redis_url, source = resolve_redis_url()
    if not redis_url:
        logger.info("[MarketCache] No Redis configured — L1-only mode")
        return None

    try:
        import redis.asyncio as aioredis  # noqa: PLC0415

        client = aioredis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await client.ping()
        _redis = client
        logger.info("[MarketCache] Redis async connected via %s", source)
    except Exception as exc:
        logger.warning("[MarketCache] Redis unavailable — L1-only mode: %s", exc)
        _redis = None

    return _redis


def _full(key: str) -> str:
    return _KEY_PREFIX + key


# ── Public API ────────────────────────────────────────────────────────────────


async def get(key: str) -> Optional[Any]:
    """Return cached value, or None on miss."""
    fk = _full(key)

    # L1 hit (zero latency)
    hit = _l1.get(fk)
    if hit is not None:
        return hit

    # L2 Redis
    r = await _get_redis()
    if r:
        try:
            raw = await r.get(fk)
            if raw is not None:
                value = orjson.loads(raw)
                _l1[fk] = value  # warm L1 for next burst
                return value
        except Exception as exc:
            logger.debug("[MarketCache] Redis get(%s) error: %s", key, exc)

    return None


async def set(key: str, data: Any, ttl: int = 300) -> None:
    """Store value in L1 (10 s) and L2 Redis (ttl seconds)."""
    fk = _full(key)
    _l1[fk] = data

    r = await _get_redis()
    if r:
        try:
            await r.setex(fk, ttl, orjson.dumps(data))
        except Exception as exc:
            logger.debug("[MarketCache] Redis set(%s) error: %s", key, exc)


async def delete(key: str) -> None:
    """Invalidate a specific cache entry."""
    fk = _full(key)
    _l1.pop(fk, None)

    r = await _get_redis()
    if r:
        try:
            await r.delete(fk)
        except Exception as exc:
            logger.debug("[MarketCache] Redis delete(%s) error: %s", key, exc)


async def reset_connection() -> None:
    """Force reconnection to Redis (useful after network recovery)."""
    global _redis, _redis_checked
    _redis = None
    _redis_checked = False
    await _get_redis()
