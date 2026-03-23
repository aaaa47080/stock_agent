"""
Async ORM repository for System Config operations.

Provides async equivalents of the DB-level functions in
``core.database.system_config``, using SQLAlchemy 2.0 select/insert/update/delete
with the ``SystemConfig`` model.

Note: the multi-layer caching (in-memory + Redis Pub/Sub) from the legacy module
is **not** replicated here — this repo handles only the DB side.  Callers that
need the full cached path should continue using ``core.database.system_config``.

Usage::

    from core.orm.config_repo import config_repo

    value = await config_repo.get_config("price_tip", default=1.0)
    all_cfg = await config_repo.get_all_configs()
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SystemConfig
from .session import using_session

logger = logging.getLogger(__name__)


# ── Value parsing / serialisation helpers (mirrors legacy helpers) ──────────


def _parse_value(value: str, value_type: str) -> Any:
    """Parse a config value string according to its declared type."""
    if value == "null" or value is None:
        return None
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        return value.lower() in ("true", "1", "yes")
    if value_type == "json":
        return json.loads(value)
    return value


def _serialize_value(value: Any) -> str:
    """Serialise a config value to its string representation."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _detect_value_type(value: Any) -> str:
    """Auto-detect the type of a config value."""
    if value is None:
        return "string"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict, list)):
        return "json"
    return "string"


def _fmt_iso(dt: datetime | None) -> str | None:
    """Format a datetime to ISO string."""
    if dt is None:
        return None
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


# ── Audit log writer (raw SQL, same as legacy) ────────────────────────────


async def _write_audit_log(
    session: AsyncSession,
    key: str,
    old_value: Any,
    new_value: Any,
    changed_by: str,
) -> None:
    """Write a config-change audit entry.  Silently ignores if table missing."""
    try:
        await session.execute(
            text(
                "INSERT INTO config_audit_log "
                "(config_key, old_value, new_value, changed_by, changed_at) "
                "VALUES (:key, :old, :new, :who, CURRENT_TIMESTAMP)"
            ).bindparams(key=key, old=old_value, new=new_value, who=changed_by)
        )
    except Exception as exc:
        # Audit table may not exist — just log a warning.
        logger.warning("Audit log write failed (table may not exist): %s", exc)


# ── Repository ────────────────────────────────────────────────────────────


class ConfigRepository:
    """Async repository for the ``system_config`` table."""

    # ── Read operations ───────────────────────────────────────────────────

    async def get_config(
        self,
        key: str,
        default: Any = None,
        session: AsyncSession | None = None,
    ) -> Any:
        """Get a single config value, parsed according to its ``value_type``."""
        stmt = select(
            SystemConfig.value,
            SystemConfig.value_type,
        ).where(SystemConfig.key == key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if row is None:
                return default
            return _parse_value(row[0], row[1])

    async def get_all_configs(
        self,
        category: Optional[str] = None,
        public_only: bool = True,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Get all config values as a dict (optionally filtered)."""
        stmt = select(
            SystemConfig.key,
            SystemConfig.value,
            SystemConfig.value_type,
        )
        if category:
            stmt = stmt.where(SystemConfig.category == category)
        if public_only:
            stmt = stmt.where(SystemConfig.is_public == 1)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return {
                key: _parse_value(value, vtype) for key, value, vtype in rows
            }

    async def get_prices(
        self,
        session: AsyncSession | None = None,
    ) -> Dict[str, float]:
        """Get all pricing configs in the legacy ``PI_PAYMENT_PRICES`` format."""
        all_configs = await self.get_all_configs(session=session)
        return {
            "create_post": all_configs.get("price_create_post", 1.0),
            "tip": all_configs.get("price_tip", 1.0),
            "premium": all_configs.get("price_premium", 1.0),
        }

    async def get_limits(
        self,
        session: AsyncSession | None = None,
    ) -> Dict[str, Optional[int]]:
        """Get all limit configs in the legacy ``FORUM_LIMITS`` format."""
        all_configs = await self.get_all_configs(session=session)
        return {
            "daily_post_free": all_configs.get("limit_daily_post_free", 3),
            "daily_post_premium": all_configs.get("limit_daily_post_premium"),
            "daily_comment_free": all_configs.get("limit_daily_comment_free", 20),
            "daily_comment_premium": all_configs.get("limit_daily_comment_premium"),
        }

    # ── Write operations ──────────────────────────────────────────────────

    async def set_config(
        self,
        key: str,
        value: Any,
        value_type: str = "string",
        category: str = "general",
        description: str = "",
        is_public: bool = True,
        changed_by: str = "system",
        session: AsyncSession | None = None,
    ) -> bool:
        """Set a config value (create or update) with audit logging."""
        async with using_session(session) as s:
            # Fetch old value for audit
            old_result = await s.execute(
                select(SystemConfig.value).where(SystemConfig.key == key)
            )
            old_row = old_result.fetchone()
            old_value = old_row[0] if old_row else None

            # Auto-detect type if not explicitly provided
            if value_type == "string" and value is not None:
                value_type = _detect_value_type(value)

            serialized = _serialize_value(value)

            stmt = (
                pg_insert(SystemConfig)
                .values(
                    key=key,
                    value=serialized,
                    value_type=value_type,
                    category=category,
                    description=description,
                    is_public=1 if is_public else 0,
                    updated_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "value": serialized,
                        "value_type": value_type,
                        "category": category,
                        "description": description,
                        "is_public": 1 if is_public else 0,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            )
            await s.execute(stmt)

            # Write audit log
            await _write_audit_log(s, key, old_value, serialized, changed_by)

            logger.info("Config updated: %s = %s (by %s)", key, value, changed_by)
            return True

    async def update_price(
        self,
        key: str,
        value: float,
        changed_by: str = "admin",
        session: AsyncSession | None = None,
    ) -> bool:
        """Convenience method to update a pricing config."""
        config_key = f"price_{key}"
        return await self.set_config(
            config_key, value, "float", "pricing", changed_by=changed_by,
            session=session,
        )

    async def update_limit(
        self,
        key: str,
        value: Optional[int],
        changed_by: str = "admin",
        session: AsyncSession | None = None,
    ) -> bool:
        """Convenience method to update a limit config."""
        config_key = f"limit_{key}"
        return await self.set_config(
            config_key, value, "int", "limits", changed_by=changed_by,
            session=session,
        )

    async def bulk_update_configs(
        self,
        configs: Dict[str, Any],
        changed_by: str = "admin",
        session: AsyncSession | None = None,
    ) -> bool:
        """Update multiple configs in a single transaction."""
        async with using_session(session) as s:
            for key, value in configs.items():
                # Fetch old value for audit
                old_result = await s.execute(
                    select(SystemConfig.value).where(SystemConfig.key == key)
                )
                old_row = old_result.fetchone()
                old_value = old_row[0] if old_row else None

                serialized = _serialize_value(value)
                await s.execute(
                    update(SystemConfig)
                    .where(SystemConfig.key == key)
                    .values(value=serialized, updated_at=datetime.now(timezone.utc))
                )

                await _write_audit_log(s, key, old_value, serialized, changed_by)

            logger.info("Bulk config update: %d keys (by %s)", len(configs), changed_by)
            return True

    # ── Metadata / History ────────────────────────────────────────────────

    async def get_config_metadata(
        self,
        key: str,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        """Get full metadata for a single config entry."""
        stmt = select(
            SystemConfig.key,
            SystemConfig.value,
            SystemConfig.value_type,
            SystemConfig.category,
            SystemConfig.description,
            SystemConfig.is_public,
            SystemConfig.created_at,
            SystemConfig.updated_at,
        ).where(SystemConfig.key == key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return {
                "key": row[0],
                "value": _parse_value(row[1], row[2]),
                "raw_value": row[1],
                "value_type": row[2],
                "category": row[3],
                "description": row[4],
                "is_public": bool(row[5]),
                "created_at": _fmt_iso(row[6]),
                "updated_at": _fmt_iso(row[7]),
            }

    async def list_all_configs_with_metadata(
        self,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """List all configs with full metadata (admin panel use)."""
        stmt = select(
            SystemConfig.key,
            SystemConfig.value,
            SystemConfig.value_type,
            SystemConfig.category,
            SystemConfig.description,
            SystemConfig.is_public,
            SystemConfig.created_at,
            SystemConfig.updated_at,
        ).order_by(SystemConfig.category, SystemConfig.key)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "key": row[0],
                    "value": _parse_value(row[1], row[2]),
                    "raw_value": row[1],
                    "value_type": row[2],
                    "category": row[3],
                    "description": row[4],
                    "is_public": bool(row[5]),
                    "created_at": _fmt_iso(row[6]),
                    "updated_at": _fmt_iso(row[7]),
                }
                for row in rows
            ]

    async def get_config_history(
        self,
        key: str,
        limit: int = 20,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get the audit-log history for a config key."""
        stmt = text(
            "SELECT old_value, new_value, changed_by, changed_at "
            "FROM config_audit_log "
            "WHERE config_key = :key "
            "ORDER BY changed_at DESC "
            "LIMIT :limit"
        ).bindparams(key=key, limit=limit)

        async with using_session(session) as s:
            try:
                result = await s.execute(stmt)
                rows = result.fetchall()
                return [
                    {
                        "old_value": row[0],
                        "new_value": row[1],
                        "changed_by": row[2],
                        "changed_at": row[3].isoformat() if row[3] else None,
                    }
                    for row in rows
                ]
            except Exception as exc:
                logger.warning("Audit log query failed: %s", exc)
                return []

    async def get_config_count(
        self,
        session: AsyncSession | None = None,
    ) -> int:
        """Return the total number of config entries."""
        stmt = select(func.count()).select_from(SystemConfig)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one() or 0


config_repo = ConfigRepository()
