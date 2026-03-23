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
    # ── Core CRUD ────────────────────────────────────────────────────────────

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

    # ── Helper: specific notification types ──────────────────────────────────

    async def notify_friend_request(
        self,
        to_user_id: str,
        from_user_id: str,
        from_username: str,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a friend request notification."""
        return await self.create_notification(
            user_id=to_user_id,
            notification_type="friend_request",
            title="好友請求",
            body=f"{from_username} 想加你為好友",
            data={"from_user_id": from_user_id, "from_username": from_username},
            session=session,
        )

    async def notify_friend_accepted(
        self,
        to_user_id: str,
        from_user_id: str,
        from_username: str,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a friend accepted notification."""
        return await self.create_notification(
            user_id=to_user_id,
            notification_type="friend_request",
            title="好友已接受",
            body=f"{from_username} 已接受你的好友請求",
            data={
                "from_user_id": from_user_id,
                "from_username": from_username,
                "action": "accepted",
            },
            session=session,
        )

    async def notify_new_message(
        self,
        to_user_id: str,
        from_user_id: str,
        from_username: str,
        message_preview: str,
        conversation_id: str,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new message notification."""
        preview = message_preview[:50]
        if len(message_preview) > 50:
            preview += "..."
        return await self.create_notification(
            user_id=to_user_id,
            notification_type="message",
            title="新消息",
            body=f"{from_username}: {preview}",
            data={
                "from_user_id": from_user_id,
                "from_username": from_username,
                "conversation_id": conversation_id,
            },
            session=session,
        )

    async def notify_post_interaction(
        self,
        to_user_id: str,
        from_username: str,
        interaction_type: str,
        post_id: int,
        post_title: str,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a post interaction notification."""
        interaction_text = {"like": "讚了", "comment": "評論了"}.get(
            interaction_type, "互動了"
        )
        title_display = post_title[:30]
        if len(post_title) > 30:
            title_display += "..."
        return await self.create_notification(
            user_id=to_user_id,
            notification_type="post_interaction",
            title="帖子互動",
            body=f"{from_username} {interaction_text}你的文章「{title_display}」",
            data={
                "post_id": post_id,
                "interaction_type": interaction_type,
                "from_username": from_username,
            },
            session=session,
        )

    async def notify_system_update(
        self,
        user_id: str,
        version: str,
        message: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a system update notification."""
        return await self.create_notification(
            user_id=user_id,
            notification_type="system_update",
            title="系統更新",
            body=message or f"新版本 {version} 可用，建議更新以獲得最佳體驗",
            data={"version": version},
            session=session,
        )

    async def notify_announcement(
        self,
        user_ids: List[str],
        title: str,
        body: str,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Create announcement notifications for multiple users in one session.

        Args:
            user_ids: List of target user IDs.
            title: Announcement title.
            body: Announcement body.
            session: Optional existing session.

        Returns:
            List of created notification dicts.
        """
        if not user_ids:
            return []

        notifications = []
        for uid in user_ids:
            notif_id = f"notif_{uuid.uuid4().hex[:12]}"
            notifications.append(
                Notification(
                    id=notif_id,
                    user_id=uid,
                    type="announcement",
                    title=title,
                    body=body,
                    is_read=False,
                )
            )

        async with using_session(session) as s:
            s.add_all(notifications)
            await s.flush()
            results = []
            for n in notifications:
                await s.refresh(n)
                results.append(_row_to_dict(n))
            return results


notifications_repo = NotificationsRepository()
