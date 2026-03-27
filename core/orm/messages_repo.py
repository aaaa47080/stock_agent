"""
Async ORM repository for DM conversation and message operations.

Provides async equivalents of the functions in core.database.messages,
using SQLAlchemy 2.0 select/update/insert with ORM models.

Usage::

    from core.orm.messages_repo import messages_repo

    conv = await messages_repo.get_or_create_conversation("user1", "user2")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DmConversation, DmMessage, Friendship, User
from .session import using_session

logger = logging.getLogger(__name__)

_DEFAULT_MAX_LENGTH = 500


def _dt_iso(val: Optional[datetime]) -> Optional[str]:
    return val.isoformat() if val else None


def _conv_row_to_dict(row) -> dict:
    cols = row._mapping
    return {
        "id": cols[DmConversation.id],
        "user1_id": cols[DmConversation.user1_id],
        "user2_id": cols[DmConversation.user2_id],
        "last_message_at": _dt_iso(cols[DmConversation.last_message_at]),
        "user1_unread_count": cols[DmConversation.user1_unread_count],
        "user2_unread_count": cols[DmConversation.user2_unread_count],
        "created_at": _dt_iso(cols[DmConversation.created_at]),
    }


def _msg_row_to_dict(row) -> dict:
    cols = row._mapping
    return {
        "id": cols[DmMessage.id],
        "conversation_id": cols[DmMessage.conversation_id],
        "from_user_id": cols[DmMessage.from_user_id],
        "to_user_id": cols[DmMessage.to_user_id],
        "content": cols[DmMessage.content],
        "message_type": cols[DmMessage.message_type],
        "is_read": bool(cols[DmMessage.is_read]),
        "read_at": _dt_iso(cols[DmMessage.read_at]),
        "created_at": _dt_iso(cols[DmMessage.created_at]),
        "from_username": cols.get("_from_username"),
        "to_username": cols.get("_to_username"),
    }


class MessagesRepository:
    async def get_or_create_conversation(
        self,
        user1_id: str,
        user2_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id

        async with using_session(session) as s:
            result = await s.execute(
                select(DmConversation).where(
                    DmConversation.user1_id == user1_id,
                    DmConversation.user2_id == user2_id,
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                return {
                    "id": conv.id,
                    "user1_id": conv.user1_id,
                    "user2_id": conv.user2_id,
                    "last_message_at": _dt_iso(conv.last_message_at),
                    "user1_unread_count": conv.user1_unread_count,
                    "user2_unread_count": conv.user2_unread_count,
                    "created_at": _dt_iso(conv.created_at),
                    "is_new": False,
                }

            now = datetime.now(timezone.utc)
            conv = DmConversation(
                user1_id=user1_id,
                user2_id=user2_id,
                created_at=now,
            )
            s.add(conv)
            await s.flush()
            return {
                "id": conv.id,
                "user1_id": conv.user1_id,
                "user2_id": conv.user2_id,
                "last_message_at": None,
                "user1_unread_count": 0,
                "user2_unread_count": 0,
                "created_at": now.isoformat(),
                "is_new": True,
            }

    async def get_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        u1 = User.__table__.alias("u1")
        u2 = User.__table__.alias("u2")

        is_user1 = DmConversation.user1_id == user_id
        other_user_id_expr = case(
            (is_user1, DmConversation.user2_id),
            else_=DmConversation.user1_id,
        )
        other_username_expr = case(
            (is_user1, u2.c.username),
            else_=u1.c.username,
        )
        other_tier_expr = case(
            (is_user1, u2.c.membership_tier),
            else_=u1.c.membership_tier,
        )

        # Build two separate blocked subqueries (one for each role) to avoid
        # SQLAlchemy auto-correlation issues when using CASE in EXISTS
        blocked_by_user_as_u1 = exists(
            select(Friendship.id).where(
                Friendship.user_id == user_id,
                Friendship.friend_id == DmConversation.user1_id,
                Friendship.status == "blocked",
            )
        ).correlate(DmConversation)

        blocked_by_user_as_u2 = exists(
            select(Friendship.id).where(
                Friendship.user_id == user_id,
                Friendship.friend_id == DmConversation.user2_id,
                Friendship.status == "blocked",
            )
        ).correlate(DmConversation)

        has_visible_msg = exists(
            select(DmMessage.id).where(
                DmMessage.conversation_id == DmConversation.id,
            )
        ).correlate(DmConversation)

        stmt = (
            select(
                DmConversation.id,
                DmConversation.user1_id,
                DmConversation.user2_id,
                DmConversation.last_message_at,
                DmConversation.user1_unread_count,
                DmConversation.user2_unread_count,
                DmConversation.created_at,
                DmMessage.content.label("last_message"),
                DmMessage.from_user_id.label("last_message_from"),
                other_username_expr.label("other_username"),
                other_user_id_expr.label("other_user_id"),
                other_tier_expr.label("other_membership_tier"),
            )
            .outerjoin(
                DmMessage,
                DmMessage.id == DmConversation.last_message_id,
            )
            .outerjoin(u1, u1.c.user_id == DmConversation.user1_id)
            .outerjoin(u2, u2.c.user_id == DmConversation.user2_id)
            .where(
                or_(
                    DmConversation.user1_id == user_id,
                    DmConversation.user2_id == user_id,
                ),
                has_visible_msg,
                ~blocked_by_user_as_u1,
                ~blocked_by_user_as_u2,
            )
            .order_by(
                DmConversation.last_message_at.desc().nullslast(),
                DmConversation.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.all()
            conversations = []
            for row in rows:
                cols = row._mapping
                user1_id_val = cols[DmConversation.user1_id]
                unread_count = (
                    cols[DmConversation.user1_unread_count]
                    if user_id == user1_id_val
                    else cols[DmConversation.user2_unread_count]
                )
                conversations.append(
                    {
                        "id": cols[DmConversation.id],
                        "other_user_id": cols["other_user_id"],
                        "other_username": cols["other_username"]
                        or cols["other_user_id"],
                        "other_membership_tier": cols["other_membership_tier"]
                        or "free",
                        "last_message": cols["last_message"],
                        "last_message_from": cols["last_message_from"],
                        "last_message_at": _dt_iso(
                            cols[DmConversation.last_message_at]
                        ),
                        "unread_count": unread_count,
                        "created_at": _dt_iso(cols[DmConversation.created_at]),
                    }
                )
            return conversations

    async def get_conversation_by_id(
        self,
        conversation_id: int,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        stmt = select(DmConversation).where(
            DmConversation.id == conversation_id,
            or_(
                DmConversation.user1_id == user_id,
                DmConversation.user2_id == user_id,
            ),
        )
        async with using_session(session) as s:
            result = await s.execute(stmt)
            conv = result.scalar_one_or_none()
            if not conv:
                return None
            return {
                "id": conv.id,
                "user1_id": conv.user1_id,
                "user2_id": conv.user2_id,
                "last_message_at": _dt_iso(conv.last_message_at),
                "user1_unread_count": conv.user1_unread_count,
                "user2_unread_count": conv.user2_unread_count,
            }

    async def validate_message_send(
        self,
        from_user_id: str,
        to_user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        sender_exists_sq = (
            exists(select(User.user_id).where(User.user_id == from_user_id))
            .correlate(None)
            .label("sender_exists")
        )

        receiver_exists_sq = (
            exists(select(User.user_id).where(User.user_id == to_user_id))
            .correlate(None)
            .label("receiver_exists")
        )

        are_friends_sq = (
            exists(
                select(Friendship.id).where(
                    or_(
                        and_(
                            Friendship.user_id == from_user_id,
                            Friendship.friend_id == to_user_id,
                        ),
                        and_(
                            Friendship.user_id == to_user_id,
                            Friendship.friend_id == from_user_id,
                        ),
                    ),
                    Friendship.status == "accepted",
                )
            )
            .correlate(None)
            .label("are_friends")
        )

        is_blocked_sq = (
            exists(
                select(Friendship.id).where(
                    or_(
                        and_(
                            Friendship.user_id == from_user_id,
                            Friendship.friend_id == to_user_id,
                        ),
                        and_(
                            Friendship.user_id == to_user_id,
                            Friendship.friend_id == from_user_id,
                        ),
                    ),
                    Friendship.status == "blocked",
                )
            )
            .correlate(None)
            .label("is_blocked")
        )

        stmt = select(
            sender_exists_sq,
            receiver_exists_sq,
            are_friends_sq,
            is_blocked_sq,
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.one()
            sender_exists, receiver_exists, are_friends, is_blocked = row

            if not sender_exists:
                return {"valid": False, "error": "sender_not_found"}
            if not receiver_exists:
                return {"valid": False, "error": "receiver_not_found"}
            if is_blocked:
                return {"valid": False, "error": "blocked"}
            if not are_friends:
                return {"valid": False, "error": "not_friends"}

            return {
                "valid": True,
                "sender_exists": sender_exists,
                "receiver_exists": receiver_exists,
                "are_friends": are_friends,
                "is_blocked": is_blocked,
            }

    async def send_message(
        self,
        from_user_id: str,
        to_user_id: str,
        content: str,
        message_type: str = "text",
        session: AsyncSession | None = None,
    ) -> dict:
        if from_user_id == to_user_id:
            return {"success": False, "error": "cannot_message_self"}
        if not content or not content.strip():
            return {"success": False, "error": "empty_content"}

        max_length = await self._get_message_config(
            "limit_message_max_length", _DEFAULT_MAX_LENGTH, session
        )
        if len(content) > max_length:
            return {
                "success": False,
                "error": "message_too_long",
                "max_length": max_length,
            }

        async with using_session(session) as s:
            try:
                await s.execute(
                    update(User)
                    .where(User.user_id == from_user_id)
                    .values(last_active_at=datetime.now(timezone.utc))
                )

                user1_id, user2_id = (
                    (from_user_id, to_user_id)
                    if from_user_id < to_user_id
                    else (to_user_id, from_user_id)
                )

                result = await s.execute(
                    select(DmConversation.id, DmConversation.user1_id).where(
                        DmConversation.user1_id == user1_id,
                        DmConversation.user2_id == user2_id,
                    )
                )
                conv_row = result.one_or_none()

                if conv_row:
                    conversation_id, conv_user1_id = conv_row
                else:
                    now = datetime.now(timezone.utc)
                    conv = DmConversation(
                        user1_id=user1_id,
                        user2_id=user2_id,
                        created_at=now,
                    )
                    s.add(conv)
                    await s.flush()
                    conversation_id = conv.id
                    conv_user1_id = user1_id

                msg = DmMessage(
                    conversation_id=conversation_id,
                    from_user_id=from_user_id,
                    to_user_id=to_user_id,
                    content=content.strip(),
                    message_type=message_type,
                )
                s.add(msg)
                await s.flush()

                if conv_user1_id == to_user_id:
                    await s.execute(
                        update(DmConversation)
                        .where(DmConversation.id == conversation_id)
                        .values(
                            last_message_id=msg.id,
                            last_message_at=datetime.now(timezone.utc),
                            user1_unread_count=DmConversation.user1_unread_count + 1,
                        )
                    )
                else:
                    await s.execute(
                        update(DmConversation)
                        .where(DmConversation.id == conversation_id)
                        .values(
                            last_message_id=msg.id,
                            last_message_at=datetime.now(timezone.utc),
                            user2_unread_count=DmConversation.user2_unread_count + 1,
                        )
                    )

                await s.flush()

                from_u = User.__table__.alias("from_u")
                to_u = User.__table__.alias("to_u")
                stmt = (
                    select(
                        DmMessage.id,
                        DmMessage.conversation_id,
                        DmMessage.from_user_id,
                        DmMessage.to_user_id,
                        DmMessage.content,
                        DmMessage.message_type,
                        DmMessage.is_read,
                        DmMessage.read_at,
                        DmMessage.created_at,
                        from_u.c.username.label("_from_username"),
                        to_u.c.username.label("_to_username"),
                    )
                    .outerjoin(from_u, from_u.c.user_id == DmMessage.from_user_id)
                    .outerjoin(to_u, to_u.c.user_id == DmMessage.to_user_id)
                    .where(DmMessage.id == msg.id)
                )

                result = await s.execute(stmt)
                msg_row = result.one()

                return {
                    "success": True,
                    "message": _msg_row_to_dict(msg_row),
                }
            except Exception as e:
                logger.error("send_message error: %s", e, exc_info=True)
                return {"success": False, "error": str(e)}

    async def get_messages(
        self,
        conversation_id: int,
        user_id: str,
        limit: int = 50,
        before_id: Optional[int] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        from_u = User.__table__.alias("from_u")
        to_u = User.__table__.alias("to_u")

        verify_stmt = select(DmConversation.id).where(
            DmConversation.id == conversation_id,
            or_(
                DmConversation.user1_id == user_id,
                DmConversation.user2_id == user_id,
            ),
        )

        msg_stmt = (
            select(
                DmMessage.id,
                DmMessage.conversation_id,
                DmMessage.from_user_id,
                DmMessage.to_user_id,
                DmMessage.content,
                DmMessage.message_type,
                DmMessage.is_read,
                DmMessage.read_at,
                DmMessage.created_at,
                from_u.c.username.label("_from_username"),
                to_u.c.username.label("_to_username"),
            )
            .outerjoin(from_u, from_u.c.user_id == DmMessage.from_user_id)
            .outerjoin(to_u, to_u.c.user_id == DmMessage.to_user_id)
            .where(DmMessage.conversation_id == conversation_id)
        )

        if before_id is not None:
            msg_stmt = msg_stmt.where(DmMessage.id < before_id)

        msg_stmt = msg_stmt.order_by(
            DmMessage.created_at.desc(), DmMessage.id.desc()
        ).limit(limit)

        async with using_session(session) as s:
            verify_result = await s.execute(verify_stmt)
            if not verify_result.scalar_one_or_none():
                return {"success": False, "error": "conversation_not_found"}

            result = await s.execute(msg_stmt)
            rows = result.all()
            messages = [_msg_row_to_dict(row) for row in rows]
            messages.reverse()

            return {
                "success": True,
                "messages": messages,
                "has_more": len(rows) == limit,
            }

    async def mark_as_read(
        self,
        conversation_id: int,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        conv = await self.get_conversation_by_id(conversation_id, user_id, session)
        if not conv:
            return {"success": False, "error": "conversation_not_found"}

        async with using_session(session) as s:
            result = await s.execute(
                update(DmMessage)
                .where(
                    DmMessage.conversation_id == conversation_id,
                    DmMessage.to_user_id == user_id,
                    DmMessage.from_user_id != user_id,
                    DmMessage.is_read == 0,
                )
                .values(is_read=1, read_at=datetime.now(timezone.utc))
            )
            updated_count = result.rowcount

            if conv["user1_id"] == user_id:
                await s.execute(
                    update(DmConversation)
                    .where(DmConversation.id == conversation_id)
                    .values(user1_unread_count=0)
                )
            else:
                await s.execute(
                    update(DmConversation)
                    .where(DmConversation.id == conversation_id)
                    .values(user2_unread_count=0)
                )

            return {
                "success": True,
                "marked_count": updated_count,
            }

    async def get_unread_count(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        unread_expr = case(
            (DmConversation.user1_id == user_id, DmConversation.user1_unread_count),
            else_=DmConversation.user2_unread_count,
        )
        stmt = select(func.coalesce(func.sum(unread_expr), 0)).where(
            or_(
                DmConversation.user1_id == user_id,
                DmConversation.user2_id == user_id,
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar() or 0

    async def _get_message_config(
        self,
        key: str,
        default,
        session: AsyncSession | None = None,
    ):
        from .models import SystemConfig

        stmt = select(SystemConfig.value, SystemConfig.value_type).where(
            SystemConfig.key == key
        )
        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.one_or_none()
            if not row:
                return default
            value, value_type = row
            if value == "null" or value is None:
                return None
            if value_type == "int":
                return int(value)
            if value_type == "float":
                return float(value)
            if value_type == "bool":
                return value.lower() in ("true", "1", "yes")
            return value


messages_repo = MessagesRepository()
