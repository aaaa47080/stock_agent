"""
Async ORM repository for Trading / Watchlist operations.

Provides async equivalents of the functions in core.database.trading,
using SQLAlchemy 2.0 select/delete/insert with the Watchlist model.

Usage::

    from core.orm.trading_repo import trading_repo

    await trading_repo.add_to_watchlist("user-1", "BTC")
    symbols = await trading_repo.get_watchlist("user-1")
"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Watchlist
from .session import using_session

logger = logging.getLogger(__name__)


class TradingRepository:
    """Async repository for watchlist operations."""

    async def add_to_watchlist(
        self,
        user_id: str,
        symbol: str,
        session: AsyncSession | None = None,
    ) -> None:
        """Add a symbol to the user's watchlist (no-op if already present).

        Mirrors the legacy ``INSERT ... ON CONFLICT DO NOTHING`` behaviour.
        """
        stmt = (
            pg_insert(Watchlist)
            .values(user_id=user_id, symbol=symbol)
            .on_conflict_do_nothing()
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def remove_from_watchlist(
        self,
        user_id: str,
        symbol: str,
        session: AsyncSession | None = None,
    ) -> None:
        """Remove a symbol from the user's watchlist."""
        stmt = delete(Watchlist).where(
            Watchlist.user_id == user_id,
            Watchlist.symbol == symbol,
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def get_watchlist(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> List[str]:
        """Return the list of symbols in the user's watchlist."""
        stmt = select(Watchlist.symbol).where(Watchlist.user_id == user_id)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [row[0] for row in rows]


trading_repo = TradingRepository()
