"""
Async ORM repository for Memory / Experience operations.

Provides async equivalents of the functions in core.database.memory,
using SQLAlchemy 2.0 select/update with UserMemory, UserHistoryLog,
UserMemoryCache, and UserFact models.

Usage::

    from core.orm.memory_repo import memory_repo

    content = await memory_repo.read_long_term("user-1")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import UserFact, UserHistoryLog, UserMemory, UserMemoryCache
from .session import using_session

logger = logging.getLogger(__name__)


def _fmt(dt: datetime | None) -> str | None:
    """Format datetime to string or return None."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class MemoryRepository:
    """Async ORM repository for user memory (long-term, history, cache, facts)."""

    # ── Long-term memory ─────────────────────────────────────────────────────

    async def read_long_term(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> str:
        """Read the latest long-term memory for a user (cross-session)."""
        stmt = (
            select(UserMemory.content)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.memory_type == "long_term",
            )
            .order_by(UserMemory.updated_at.desc())
            .limit(1)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.scalar_one_or_none()
            return row if row else ""

    async def write_long_term(
        self,
        user_id: str,
        content: str,
        session: AsyncSession | None = None,
    ) -> None:
        """Write (upsert) long-term memory. Fixed session_id='global'."""
        if not content:
            return
        now = datetime.now(timezone.utc)

        stmt = (
            pg_insert(UserMemory)
            .values(
                user_id=user_id,
                session_id="global",
                memory_type="long_term",
                content=content,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "session_id", "memory_type"],
                set_={
                    "content": pg_insert.excluded.content,
                    "updated_at": now,
                },
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    # ── History log ──────────────────────────────────────────────────────────

    async def append_history(
        self,
        user_id: str,
        session_id: str,
        entry: str,
        tools_used: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Append a history log entry."""
        if not entry or not entry.strip():
            return

        row = UserHistoryLog(
            user_id=user_id,
            session_id=session_id,
            entry=entry.rstrip(),
            tools_used=tools_used,
        )

        async with using_session(session) as s:
            s.add(row)

    async def get_history(
        self,
        user_id: str,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """Get recent history for a user (cross-session, newest first then reversed)."""
        stmt = (
            select(
                UserHistoryLog.entry,
                UserHistoryLog.tools_used,
                UserHistoryLog.created_at,
            )
            .where(UserHistoryLog.user_id == user_id)
            .order_by(UserHistoryLog.created_at.desc())
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            results = [
                {
                    "entry": r[0],
                    "tools_used": r[1],
                    "created_at": _fmt(r[2]),
                }
                for r in rows
            ]
            # Reverse so oldest is first
            return list(reversed(results)) if results else []

    # ── Memory cache (consolidation index) ───────────────────────────────────

    async def get_last_consolidated_index(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        """Get the last consolidation index for a user."""
        stmt = select(UserMemoryCache.last_consolidated_index).where(
            UserMemoryCache.user_id == user_id,
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one_or_none() or 0

    async def set_last_consolidated_index(
        self,
        user_id: str,
        session_id: str,
        index: int,
        session: AsyncSession | None = None,
    ) -> None:
        """Set the last consolidation index (upsert)."""
        now = datetime.now(timezone.utc)

        stmt = (
            pg_insert(UserMemoryCache)
            .values(
                user_id=user_id,
                session_id=session_id,
                last_consolidated_index=index,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "last_consolidated_index": pg_insert.excluded.last_consolidated_index,
                    "session_id": pg_insert.excluded.session_id,
                    "updated_at": now,
                },
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    # ── Session compact state ────────────────────────────────────────────────

    async def read_compact_state(
        self,
        user_id: str,
        session_id: str,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Read compact session state from PostgreSQL."""
        stmt = (
            select(UserMemory.content)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.session_id == session_id,
                UserMemory.memory_type == "session_compact",
            )
            .order_by(UserMemory.updated_at.desc())
            .limit(1)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            try:
                return json.loads(row)
            except (json.JSONDecodeError, TypeError):
                return None

    async def write_compact_state(
        self,
        user_id: str,
        session_id: str,
        state: Dict[str, Any],
        session: AsyncSession | None = None,
    ) -> None:
        """Persist compact session state (upsert)."""
        now = datetime.now(timezone.utc)
        content = json.dumps(state)

        stmt = (
            pg_insert(UserMemory)
            .values(
                user_id=user_id,
                session_id=session_id,
                memory_type="session_compact",
                content=content,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "session_id", "memory_type"],
                set_={
                    "content": pg_insert.excluded.content,
                    "updated_at": now,
                },
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    # ── Structured facts ─────────────────────────────────────────────────────

    async def read_facts(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Read user's structured facts (key-value pairs).

        Returns:
            {key: {value, confidence, source_turn}} dict
        """
        stmt = (
            select(
                UserFact.key,
                UserFact.value,
                UserFact.confidence,
                UserFact.source_turn,
            )
            .where(UserFact.user_id == user_id)
            .order_by(UserFact.updated_at.desc())
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return {
                r[0]: {
                    "value": r[1],
                    "confidence": r[2],
                    "source_turn": r[3],
                }
                for r in rows
            }

    async def write_facts(
        self,
        user_id: str,
        facts: List[Dict[str, Any]],
        session: AsyncSession | None = None,
    ) -> None:
        """Write structured facts (upsert)."""
        if not facts:
            return
        now = datetime.now(timezone.utc)

        async with using_session(session) as s:
            for fact in facts:
                key = str(fact.get("key", "")).strip()
                value = str(fact.get("value", "")).strip()
                if not key or not value:
                    continue

                stmt = (
                    pg_insert(UserFact)
                    .values(
                        user_id=user_id,
                        key=key,
                        value=value,
                        confidence=fact.get("confidence", "high"),
                        source_turn=fact.get("source_turn"),
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["user_id", "key"],
                        set_={
                            "value": pg_insert.excluded.value,
                            "confidence": pg_insert.excluded.confidence,
                            "source_turn": pg_insert.excluded.source_turn,
                            "updated_at": now,
                        },
                    )
                )
                await s.execute(stmt)


memory_repo = MemoryRepository()
