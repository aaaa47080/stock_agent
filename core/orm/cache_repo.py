"""
Async ORM repository for System Cache operations.

Provides async equivalents of the DB-level functions in core.database.cache,
using SQLAlchemy 2.0 select/insert/delete with the SystemCache model.

Note: Redis-layer caching is **not** replicated here — this repo handles
only the persistent DB side (the fallback store).  Callers that need the
full Redis-first path should continue using ``core.database.cache``.

Usage::

    from core.orm.cache_repo import cache_repo

    await cache_repo.set_cache("my_key", {"data": 1})
    data = await cache_repo.get_cache("my_key")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SystemCache
from .session import using_session

logger = logging.getLogger(__name__)


def _parse_json(value: str | None) -> Any:
    """Safely parse a JSON string from the DB."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("DB cache JSON parse error: %s", exc)
        return None


class CacheRepository:
    """Async repository for the ``system_cache`` table."""

    async def set_cache(
        self,
        key: str,
        data: Any,
        session: AsyncSession | None = None,
    ) -> None:
        """Upsert a cache entry (JSON-serialised).

        Mirrors the legacy ``_db_set`` which does
        ``INSERT … ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value,
        updated_at = EXCLUDED.updated_at``.
        """
        json_str = json.dumps(data, ensure_ascii=False)
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(SystemCache)
            .values(key=key, value=json_str, updated_at=now)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": json_str, "updated_at": now},
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def get_cache(
        self,
        key: str,
        session: AsyncSession | None = None,
    ) -> Any:
        """Retrieve a cached value by key, returning the parsed JSON."""
        stmt = select(SystemCache.value).where(SystemCache.key == key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            return _parse_json(row[0]) if row else None

    async def delete_cache(
        self,
        key: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Delete a cache entry.  Returns ``True`` if a row was removed."""
        stmt = delete(SystemCache).where(SystemCache.key == key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.rowcount > 0

    async def clear_all_cache(
        self,
        session: AsyncSession | None = None,
    ) -> None:
        """Delete all entries from the cache table."""
        stmt = delete(SystemCache)

        async with using_session(session) as s:
            await s.execute(stmt)

    async def get_cache_keys(
        self,
        session: AsyncSession | None = None,
    ) -> List[str]:
        """Return all cache keys (useful for admin / debugging)."""
        stmt = select(SystemCache.key).order_by(SystemCache.key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [row[0] for row in rows]

    async def get_cache_entry(
        self,
        key: str,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        """Return the full cache row as a dict (key, value, updated_at)."""
        stmt = select(
            SystemCache.key,
            SystemCache.value,
            SystemCache.updated_at,
        ).where(SystemCache.key == key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if not row:
                return None
            return {
                "key": row[0],
                "value": _parse_json(row[1]),
                "raw_value": row[1],
                "updated_at": row[2].isoformat() if row[2] else None,
            }


cache_repo = CacheRepository()
