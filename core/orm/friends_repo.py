"""
Async ORM repository for Friendship operations.

Provides async equivalents of the functions in core.database.friends,
using SQLAlchemy 2.0 select/update with Friendship and User models.

Usage::

    from core.orm.friends_repo import friends_repo

    result = await friends_repo.send_friend_request("user-1", "user-2")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Friendship, Post, User
from .session import using_session

logger = logging.getLogger(__name__)


def _fmt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class FriendsRepository:
    async def search_users(
        self,
        query: str,
        limit: int = 20,
        exclude_user_id: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = (
            select(
                User.user_id,
                User.username,
                User.pi_username,
                User.membership_tier,
                User.created_at,
            )
            .where(User.username.ilike(f"%{query.replace('%', r'\%').replace('_', r'\_')}%", escape='\\'))
            .order_by(User.username.asc())
            .limit(limit)
        )
        if exclude_user_id:
            stmt = stmt.where(User.user_id != exclude_user_id)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "pi_username": r[2],
                    "membership_tier": r[3] or "free",
                    "member_since": _fmt(r[4]),
                }
                for r in rows
            ]

    async def get_friends_list(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        friend_alias = User
        stmt = (
            select(
                friend_alias.user_id,
                friend_alias.username,
                friend_alias.pi_username,
                friend_alias.membership_tier,
                Friendship.updated_at,
                friend_alias.last_active_at,
            )
            .join(
                friend_alias,
                or_(
                    (Friendship.user_id == user_id)
                    & (Friendship.friend_id == friend_alias.user_id),
                    (Friendship.friend_id == user_id)
                    & (Friendship.user_id == friend_alias.user_id),
                ),
            )
            .where(
                or_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id == user_id,
                ),
                Friendship.status == "accepted",
                friend_alias.user_id != user_id,
            )
            .order_by(Friendship.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "pi_username": r[2],
                    "membership_tier": r[3] or "free",
                    "friends_since": _fmt(r[4]),
                    "last_active_at": _fmt(r[5]),
                }
                for r in rows
            ]

    async def get_friendship_status(
        self,
        user_id: str,
        other_user_id: str,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        stmt = select(Friendship).where(
            or_(
                (Friendship.user_id == user_id)
                & (Friendship.friend_id == other_user_id),
                (Friendship.user_id == other_user_id)
                & (Friendship.friend_id == user_id),
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "id": row.id,
                "requester_id": row.user_id,
                "target_id": row.friend_id,
                "status": row.status,
                "created_at": _fmt(row.created_at),
                "updated_at": _fmt(row.updated_at),
                "is_requester": row.user_id == user_id,
            }

    async def send_friend_request(
        self,
        from_user_id: str,
        to_user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        if from_user_id == to_user_id:
            return {"success": False, "error": "cannot_add_self"}

        async with using_session(session) as s:
            stmt = select(Friendship).where(
                or_(
                    (Friendship.user_id == from_user_id)
                    & (Friendship.friend_id == to_user_id),
                    (Friendship.user_id == to_user_id)
                    & (Friendship.friend_id == from_user_id),
                )
            ).with_for_update()
            result = await s.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                if existing.status == "accepted":
                    return {"success": False, "error": "already_friends"}
                if existing.status == "pending":
                    if existing.user_id == to_user_id:
                        await s.execute(
                            update(Friendship)
                            .where(
                                Friendship.user_id == to_user_id,
                                Friendship.friend_id == from_user_id,
                            )
                            .values(
                                status="accepted",
                                updated_at=datetime.now(timezone.utc),
                            )
                        )
                        return {
                            "success": True,
                            "message": "friend_added",
                            "auto_accepted": True,
                        }
                    return {"success": False, "error": "request_pending"}
                if existing.status == "blocked":
                    if existing.user_id == to_user_id:
                        return {"success": False, "error": "user_blocked_you"}
                    return {"success": False, "error": "you_blocked_user"}
                if existing.status == "rejected":
                    await s.execute(
                        update(Friendship)
                        .where(
                            Friendship.user_id == from_user_id,
                            Friendship.friend_id == to_user_id,
                        )
                        .values(
                            status="pending",
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                    return {
                        "success": True,
                        "message": "request_resent",
                        "request_id": existing.id,
                    }

            now = datetime.now(timezone.utc)
            new_friendship = Friendship(
                user_id=from_user_id,
                friend_id=to_user_id,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            s.add(new_friendship)
            await s.flush()
            return {
                "success": True,
                "message": "request_sent",
                "request_id": new_friendship.id,
            }

    async def accept_friend_request(
        self,
        user_id: str,
        requester_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        stmt = (
            update(Friendship)
            .where(
                Friendship.user_id == requester_id,
                Friendship.friend_id == user_id,
                Friendship.status == "pending",
            )
            .values(status="accepted", updated_at=datetime.now(timezone.utc))
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                return {"success": False, "error": "request_not_found"}
            return {"success": True, "message": "friend_added"}

    async def reject_friend_request(
        self,
        user_id: str,
        requester_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        stmt = (
            update(Friendship)
            .where(
                Friendship.user_id == requester_id,
                Friendship.friend_id == user_id,
                Friendship.status == "pending",
            )
            .values(status="rejected", updated_at=datetime.now(timezone.utc))
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                return {"success": False, "error": "request_not_found"}
            return {"success": True, "message": "request_rejected"}

    async def remove_friend(
        self,
        user_id: str,
        friend_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        stmt = delete(Friendship).where(
            or_(
                (Friendship.user_id == user_id) & (Friendship.friend_id == friend_id),
                (Friendship.user_id == friend_id) & (Friendship.friend_id == user_id),
            ),
            Friendship.status == "accepted",
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                return {"success": False, "error": "not_friends"}
            return {"success": True, "message": "friend_removed"}

    async def block_user(
        self,
        user_id: str,
        blocked_user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        if user_id == blocked_user_id:
            return {"success": False, "error": "cannot_block_self"}

        async with using_session(session) as s:
            await s.execute(
                delete(Friendship).where(
                    or_(
                        (Friendship.user_id == user_id)
                        & (Friendship.friend_id == blocked_user_id),
                        (Friendship.user_id == blocked_user_id)
                        & (Friendship.friend_id == user_id),
                    )
                )
            )

            now = datetime.now(timezone.utc)
            new_block = Friendship(
                user_id=user_id,
                friend_id=blocked_user_id,
                status="blocked",
                created_at=now,
                updated_at=now,
            )
            s.add(new_block)
            return {"success": True, "message": "user_blocked"}

    async def unblock_user(
        self,
        user_id: str,
        blocked_user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        stmt = delete(Friendship).where(
            Friendship.user_id == user_id,
            Friendship.friend_id == blocked_user_id,
            Friendship.status == "blocked",
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                return {"success": False, "error": "user_not_blocked"}
            return {"success": True, "message": "user_unblocked"}

    async def get_blocked_users(
        self,
        user_id: str,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = (
            select(
                User.user_id,
                User.username,
                User.pi_username,
                Friendship.created_at,
            )
            .join(User, Friendship.friend_id == User.user_id)
            .where(
                Friendship.user_id == user_id,
                Friendship.status == "blocked",
            )
            .order_by(Friendship.created_at.desc())
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "pi_username": r[2],
                    "blocked_at": _fmt(r[3]),
                }
                for r in rows
            ]

    async def is_friend(
        self,
        user_id: str,
        other_user_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        stmt = (
            select(Friendship.id)
            .where(
                or_(
                    (Friendship.user_id == user_id)
                    & (Friendship.friend_id == other_user_id),
                    (Friendship.user_id == other_user_id)
                    & (Friendship.friend_id == user_id),
                ),
                Friendship.status == "accepted",
            )
            .limit(1)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def is_blocked(
        self,
        user_id: str,
        other_user_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        stmt = (
            select(Friendship.id)
            .where(
                or_(
                    (Friendship.user_id == user_id)
                    & (Friendship.friend_id == other_user_id),
                    (Friendship.user_id == other_user_id)
                    & (Friendship.friend_id == user_id),
                ),
                Friendship.status == "blocked",
            )
            .limit(1)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_friends_count(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Friendship)
            .where(
                or_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id == user_id,
                ),
                Friendship.status == "accepted",
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one() or 0

    async def get_pending_count(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Friendship)
            .where(
                Friendship.friend_id == user_id,
                Friendship.status == "pending",
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar_one() or 0

    async def cancel_friend_request(
        self,
        user_id: str,
        target_user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        stmt = delete(Friendship).where(
            Friendship.user_id == user_id,
            Friendship.friend_id == target_user_id,
            Friendship.status == "pending",
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                return {"success": False, "error": "request_not_found"}
            return {"success": True, "message": "request_cancelled"}

    async def get_pending_requests_received(
        self,
        user_id: str,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = (
            select(
                User.user_id,
                User.username,
                User.pi_username,
                User.membership_tier,
                Friendship.id,
                Friendship.created_at,
            )
            .join(User, Friendship.user_id == User.user_id)
            .where(
                Friendship.friend_id == user_id,
                Friendship.status == "pending",
            )
            .order_by(Friendship.created_at.desc())
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "pi_username": r[2],
                    "membership_tier": r[3] or "free",
                    "request_id": r[4],
                    "requested_at": _fmt(r[5]),
                }
                for r in rows
            ]

    async def get_pending_requests_sent(
        self,
        user_id: str,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = (
            select(
                User.user_id,
                User.username,
                User.pi_username,
                User.membership_tier,
                Friendship.id,
                Friendship.created_at,
            )
            .join(User, Friendship.friend_id == User.user_id)
            .where(
                Friendship.user_id == user_id,
                Friendship.status == "pending",
            )
            .order_by(Friendship.created_at.desc())
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "pi_username": r[2],
                    "membership_tier": r[3] or "free",
                    "request_id": r[4],
                    "sent_at": _fmt(r[5]),
                }
                for r in rows
            ]

    async def get_bulk_friendship_status(
        self,
        user_id: str,
        other_user_ids: List[str],
        session: AsyncSession | None = None,
    ) -> dict:
        if not other_user_ids:
            return {}

        stmt = select(
            Friendship.id,
            Friendship.user_id,
            Friendship.friend_id,
            Friendship.status,
            Friendship.created_at,
            Friendship.updated_at,
        ).where(
            or_(
                (Friendship.user_id == user_id)
                & (Friendship.friend_id.in_(other_user_ids)),
                (Friendship.friend_id == user_id)
                & (Friendship.user_id.in_(other_user_ids)),
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            result_map = {uid: None for uid in other_user_ids}

            for row in rows:
                uid1, uid2 = row[1], row[2]
                other = uid2 if uid1 == user_id else uid1
                result_map[other] = {
                    "id": row[0],
                    "requester_id": row[1],
                    "target_id": row[2],
                    "status": row[3],
                    "created_at": _fmt(row[4]),
                    "updated_at": _fmt(row[5]),
                    "is_requester": row[1] == user_id,
                }

            return result_map

    async def get_public_user_profile(
        self,
        target_user_id: str,
        viewer_user_id: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        friendship_subq = None
        if viewer_user_id and viewer_user_id != target_user_id:
            friendship_subq = (
                select(
                    Friendship.id,
                    Friendship.user_id,
                    Friendship.friend_id,
                    Friendship.status,
                    Friendship.created_at,
                    Friendship.updated_at,
                )
                .where(
                    or_(
                        (Friendship.user_id == viewer_user_id)
                        & (Friendship.friend_id == target_user_id),
                        (Friendship.user_id == target_user_id)
                        & (Friendship.friend_id == viewer_user_id),
                    )
                )
                .limit(1)
                .subquery()
            )

        post_count_sq = (
            select(func.count())
            .select_from(Post)
            .where(Post.user_id == target_user_id, Post.is_hidden == 0)
            .correlate(None)
            .scalar_subquery()
        )

        total_pushes_sq = (
            select(func.coalesce(func.sum(Post.push_count), 0))
            .where(Post.user_id == target_user_id)
            .correlate(None)
            .scalar_subquery()
        )

        friends_count_sq = (
            select(func.count())
            .select_from(Friendship)
            .where(
                or_(
                    Friendship.user_id == target_user_id,
                    Friendship.friend_id == target_user_id,
                ),
                Friendship.status == "accepted",
            )
            .correlate(None)
            .scalar_subquery()
        )

        stmt = select(
            User.user_id,
            User.username,
            User.pi_username,
            User.membership_tier,
            User.created_at,
            post_count_sq.label("post_count"),
            total_pushes_sq.label("total_pushes"),
            friends_count_sq.label("friends_count"),
        ).where(User.user_id == target_user_id)

        if friendship_subq is not None:
            stmt = stmt.add_columns(
                friendship_subq.c.id.label("f_id"),
                friendship_subq.c.user_id.label("f_user_id"),
                friendship_subq.c.friend_id.label("f_friend_id"),
                friendship_subq.c.status.label("f_status"),
                friendship_subq.c.created_at.label("f_created_at"),
                friendship_subq.c.updated_at.label("f_updated_at"),
            )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None

            profile = {
                "user_id": row[0],
                "username": row[1],
                "pi_username": row[2],
                "membership_tier": row[3] or "free",
                "member_since": _fmt(row[4]),
                "post_count": row[5] or 0,
                "total_pushes": row[6] or 0,
                "friends_count": row[7] or 0,
                "is_friend": False,
                "friend_status": None,
                "is_requester": False,
            }

            if friendship_subq is not None:
                f_status = row[11]
                f_user_id = row[9]
                profile["friend_status"] = f_status
                profile["is_friend"] = f_status == "accepted" if f_status else False
                profile["is_requester"] = f_user_id == viewer_user_id

            return profile


friends_repo = FriendsRepository()
