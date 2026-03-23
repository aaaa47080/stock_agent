"""
Async ORM repository for Price Alert operations.

Provides async equivalents of the functions in core.database.price_alerts,
using SQLAlchemy 2.0 select/update with the PriceAlert model.

Usage::

    from core.orm.alerts_repo import alerts_repo

    alerts = await alerts_repo.get_user_alerts("user-1")
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PriceAlert
from .session import using_session

logger = logging.getLogger(__name__)

VALID_MARKETS = {"crypto", "tw_stock", "us_stock"}
VALID_CONDITIONS = {"above", "below", "change_pct_up", "change_pct_down"}
MAX_ALERTS_PER_USER = 20


def _to_dict(alert: PriceAlert) -> Dict[str, Any]:
    """Convert a PriceAlert ORM object to the dict format expected by routes."""
    return {
        "id": alert.id,
        "user_id": alert.user_id,
        "symbol": alert.symbol,
        "market": alert.market,
        "condition": alert.condition,
        "target": float(alert.target),
        "repeat": alert.repeat,
        "triggered": alert.triggered,
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
    }


class AlertsRepository:
    """Async ORM repository for price alert CRUD and background-task queries."""

    async def create_alert(
        self,
        user_id: str,
        symbol: str,
        market: str,
        condition: str,
        target: float,
        repeat: bool = False,
        max_alerts: int = MAX_ALERTS_PER_USER,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Create a new price alert.

        Raises:
            ValueError: On invalid market/condition or if the user has reached max_alerts.
        """
        if market not in VALID_MARKETS:
            raise ValueError(
                f"Invalid market '{market}'. Must be one of {VALID_MARKETS}"
            )
        if condition not in VALID_CONDITIONS:
            raise ValueError(
                f"Invalid condition '{condition}'. Must be one of {VALID_CONDITIONS}"
            )

        alert_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        repeat_int = 1 if repeat else 0

        async with using_session(session) as s:
            # Count existing alerts (same transaction to prevent races)
            count_stmt = (
                select(func.count())
                .select_from(PriceAlert)
                .where(PriceAlert.user_id == user_id)
            )
            count_result = await s.execute(count_stmt)
            count = count_result.scalar_one() or 0

            if count >= max_alerts:
                raise ValueError(
                    f"已達警報上限（最多 {max_alerts} 個），請刪除舊警報後再試。"
                )

            new_alert = PriceAlert(
                id=alert_id,
                user_id=user_id,
                symbol=symbol.upper(),
                market=market,
                condition=condition,
                target=target,
                repeat=repeat_int,
                triggered=0,
                created_at=created_at,
            )
            s.add(new_alert)
            await s.flush()

        return {
            "id": alert_id,
            "user_id": user_id,
            "symbol": symbol.upper(),
            "market": market,
            "condition": condition,
            "target": target,
            "repeat": repeat_int,
            "triggered": 0,
            "created_at": created_at.isoformat(),
        }

    async def get_user_alerts(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """Return all alerts for a user, ordered by created_at DESC."""
        stmt = (
            select(PriceAlert)
            .where(PriceAlert.user_id == user_id)
            .order_by(PriceAlert.created_at.desc())
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.scalars().all()
            return [_to_dict(r) for r in rows]

    async def delete_alert(
        self,
        alert_id: str,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Delete an alert. Returns True if deleted, False if not found/unauthorized."""
        stmt = delete(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == user_id,
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.rowcount > 0

    async def get_active_alerts(
        self,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """Return all alerts that have not been permanently deactivated (for background task)."""
        stmt = select(PriceAlert).where(
            (PriceAlert.triggered == 0) | (PriceAlert.repeat == 1),
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.scalars().all()
            return [_to_dict(r) for r in rows]

    async def mark_alert_triggered(
        self,
        alert_id: str,
        repeat: bool,
        session: AsyncSession | None = None,
    ) -> None:
        """Handle triggered alert.

        - repeat=False (one-shot): delete the alert
        - repeat=True (persistent): set triggered=1 to prevent immediate re-trigger
        """
        if not repeat:
            stmt = delete(PriceAlert).where(PriceAlert.id == alert_id)
        else:
            stmt = (
                update(PriceAlert)
                .where(PriceAlert.id == alert_id)
                .values(triggered=1)
            )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def count_user_alerts(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        """Count total alerts for a user (for limit enforcement)."""
        stmt = (
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.user_id == user_id)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one() or 0


alerts_repo = AlertsRepository()
