"""
Async ORM repository for Notification operations.

Provides async equivalents of the functions in core.database.notifications,
using SQLAlchemy 2.0 select/update with the Notification model.

Usage::

    from core.orm.notifications_repo import notifications_repo

    notification = await notifications_repo.create_notification("user-1", "system", "Title", "Body")
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Notification
from .session import using_session

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "data": row.data,
        "is_read": row.is_read,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class NotificationsRepository:
    async def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        notification = Notification(
            id=notification_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            body=body,
            data=data,
            is_read=False,
        )

        async with using_session(session) as s:
            s.add(notification)
            await s.flush()
            await s.refresh(notification)
            return _row_to_dict(notification)

    async def get_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.scalars().all()
            return [_row_to_dict(r) for r in rows]

    async def get_unread_count(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one() or 0

    async def mark_notification_as_read(
        self,
        notification_id: str,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(is_read=True)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.rowcount > 0

    async def mark_all_as_read(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.rowcount

    async def delete_notification(
        self,
        notification_id: str,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        stmt = delete(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.rowcount > 0


notifications_repo = NotificationsRepository()
