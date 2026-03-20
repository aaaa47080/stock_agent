"""
Async ORM repository for forum operations.

Provides async equivalents of the functions in core.database.forum,
using SQLAlchemy 2.0 select/update with Board, Post, ForumComment, Tip, and User models.

Usage::

    from core.orm.forum_repo import forum_repo

    boards = await forum_repo.get_boards()
    post = await forum_repo.get_post_by_id(42)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Board, ForumComment, Post, Tip, User
from .session import get_async_session

logger = logging.getLogger(__name__)


def _fmt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _decimal_to_float(val) -> float:
    if isinstance(val, Decimal):
        return float(val)
    return val


class ForumRepository:

    async def get_boards(
        self,
        active_only: bool = True,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = select(
            Board.id,
            Board.name,
            Board.slug,
            Board.description,
            Board.post_count,
            Board.is_active,
        )
        if active_only:
            stmt = stmt.where(Board.is_active == 1)

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "slug": r[2],
                    "description": r[3],
                    "post_count": r[4],
                    "is_active": bool(r[5]),
                }
                for r in rows
            ]

    async def get_board_by_slug(
        self,
        slug: str,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        stmt = select(
            Board.id,
            Board.name,
            Board.slug,
            Board.description,
            Board.post_count,
            Board.is_active,
        ).where(Board.slug == slug)

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "slug": row[2],
                "description": row[3],
                "post_count": row[4],
                "is_active": bool(row[5]),
            }

    async def get_post_by_id(
        self,
        post_id: int,
        increment_view: bool = True,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        async with session or get_async_session() as s:
            if increment_view:
                await s.execute(
                    update(Post)
                    .where(Post.id == post_id)
                    .values(view_count=Post.view_count + 1)
                )

            stmt = (
                select(
                    Post.id,
                    Post.board_id,
                    Post.user_id,
                    Post.category,
                    Post.title,
                    Post.content,
                    Post.tags,
                    Post.push_count,
                    Post.boo_count,
                    Post.comment_count,
                    Post.tips_total,
                    Post.view_count,
                    Post.payment_tx_hash,
                    Post.is_pinned,
                    Post.is_hidden,
                    Post.created_at,
                    Post.updated_at,
                    User.username,
                    Board.name,
                    Board.slug,
                )
                .outerjoin(User, Post.user_id == User.user_id)
                .outerjoin(Board, Post.board_id == Board.id)
                .where(Post.id == post_id)
            )
            result = await s.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None

            tags = json.loads(row[6]) if row[6] else []
            return {
                "id": row[0],
                "board_id": row[1],
                "user_id": row[2],
                "category": row[3],
                "title": row[4],
                "content": row[5],
                "tags": tags,
                "push_count": row[7],
                "boo_count": row[8],
                "comment_count": row[9],
                "tips_total": _decimal_to_float(row[10]),
                "view_count": row[11],
                "payment_tx_hash": row[12],
                "is_pinned": bool(row[13]),
                "is_hidden": bool(row[14]),
                "created_at": _fmt(row[15]),
                "updated_at": _fmt(row[16]),
                "username": row[17],
                "board_name": row[18],
                "board_slug": row[19],
                "net_votes": row[7] - row[8],
                "viewer_vote": None,
            }

    async def get_posts(
        self,
        board_id: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = (
            select(
                Post.id,
                Post.board_id,
                Post.user_id,
                Post.category,
                Post.title,
                Post.push_count,
                Post.boo_count,
                Post.comment_count,
                Post.tips_total,
                Post.view_count,
                Post.is_pinned,
                Post.is_hidden,
                Post.created_at,
                User.username,
                Board.name,
                Board.slug,
            )
            .outerjoin(User, Post.user_id == User.user_id)
            .outerjoin(Board, Post.board_id == Board.id)
            .where(Post.is_hidden == 0)
            .order_by(Post.is_pinned.desc(), Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if board_id is not None:
            stmt = stmt.where(Post.board_id == board_id)
        if category is not None:
            stmt = stmt.where(Post.category == category)

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "board_id": r[1],
                    "user_id": r[2],
                    "category": r[3],
                    "title": r[4],
                    "push_count": r[5],
                    "boo_count": r[6],
                    "comment_count": r[7],
                    "tips_total": _decimal_to_float(r[8]),
                    "view_count": r[9],
                    "is_pinned": bool(r[10]),
                    "is_hidden": bool(r[11]),
                    "created_at": _fmt(r[12]),
                    "username": r[13],
                    "board_name": r[14],
                    "board_slug": r[15],
                    "net_votes": r[5] - r[6],
                }
                for r in rows
            ]

    async def create_post(
        self,
        board_id: int,
        user_id: str,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        payment_tx_hash: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        MAX_TITLE_LENGTH = 200
        MAX_CONTENT_LENGTH = 10000
        MAX_TAGS_PER_POST = 5

        if not title or len(title.strip()) == 0:
            return {"success": False, "error": "title_required"}
        if len(title) > MAX_TITLE_LENGTH:
            return {
                "success": False,
                "error": "title_too_long",
                "max_length": MAX_TITLE_LENGTH,
                "current_length": len(title),
            }
        if not content or len(content.strip()) == 0:
            return {"success": False, "error": "content_required"}
        if len(content) > MAX_CONTENT_LENGTH:
            return {
                "success": False,
                "error": "content_too_long",
                "max_length": MAX_CONTENT_LENGTH,
                "current_length": len(content),
            }
        if tags and len(tags) > MAX_TAGS_PER_POST:
            return {
                "success": False,
                "error": "too_many_tags",
                "max_tags": MAX_TAGS_PER_POST,
                "provided": len(tags),
            }

        now = datetime.now(timezone.utc)
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        new_post = Post(
            board_id=board_id,
            user_id=user_id,
            category=category,
            title=title,
            content=content,
            tags=tags_json,
            payment_tx_hash=payment_tx_hash,
            created_at=now,
            updated_at=now,
        )

        async with session or get_async_session() as s:
            s.add(new_post)
            await s.flush()
            post_id = new_post.id

            await s.execute(
                update(Board)
                .where(Board.id == board_id)
                .values(post_count=Board.post_count + 1)
            )

            return {"success": True, "post_id": post_id}

    async def update_post(
        self,
        post_id: int,
        user_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> bool:
        values = {"updated_at": datetime.now(timezone.utc)}
        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        if category is not None:
            values["category"] = category

        if len(values) == 1:
            return False

        stmt = (
            update(Post)
            .where(Post.id == post_id, Post.user_id == user_id)
            .values(**values)
        )

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            return result.rowcount > 0

    async def delete_post(
        self,
        post_id: int,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        stmt = (
            update(Post)
            .where(Post.id == post_id, Post.user_id == user_id)
            .values(is_hidden=1)
        )

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            return result.rowcount > 0

    async def add_comment(
        self,
        post_id: int,
        user_id: str,
        comment_type: str,
        content: Optional[str] = None,
        parent_id: Optional[int] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        new_comment = ForumComment(
            post_id=post_id,
            user_id=user_id,
            parent_id=parent_id,
            type=comment_type,
            content=content,
            created_at=now,
        )

        async with session or get_async_session() as s:
            s.add(new_comment)
            await s.flush()

            if comment_type == "push":
                await s.execute(
                    update(Post)
                    .where(Post.id == post_id)
                    .values(push_count=Post.push_count + 1)
                )
            elif comment_type == "boo":
                await s.execute(
                    update(Post)
                    .where(Post.id == post_id)
                    .values(boo_count=Post.boo_count + 1)
                )
            else:
                await s.execute(
                    update(Post)
                    .where(Post.id == post_id)
                    .values(comment_count=Post.comment_count + 1)
                )

            return {"success": True, "comment_id": new_comment.id}

    async def get_comments(
        self,
        post_id: int,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        stmt = (
            select(
                ForumComment.id,
                ForumComment.post_id,
                ForumComment.user_id,
                ForumComment.parent_id,
                ForumComment.type,
                ForumComment.content,
                ForumComment.is_hidden,
                ForumComment.created_at,
                User.username,
            )
            .outerjoin(User, ForumComment.user_id == User.user_id)
            .where(ForumComment.post_id == post_id, ForumComment.is_hidden == 0)
            .order_by(ForumComment.created_at.asc())
            .limit(limit)
            .offset(offset)
        )

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "post_id": r[1],
                    "user_id": r[2],
                    "parent_id": r[3],
                    "type": r[4],
                    "content": r[5],
                    "is_hidden": bool(r[6]),
                    "created_at": _fmt(r[7]),
                    "username": r[8],
                }
                for r in rows
            ]

    async def create_tip(
        self,
        post_id: int,
        from_user_id: str,
        to_user_id: str,
        amount: float,
        tx_hash: str,
        session: AsyncSession | None = None,
    ) -> int:
        now = datetime.now(timezone.utc)
        new_tip = Tip(
            post_id=post_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount=amount,
            tx_hash=tx_hash,
            created_at=now,
        )

        async with session or get_async_session() as s:
            s.add(new_tip)
            await s.flush()

            await s.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(tips_total=Post.tips_total + amount)
            )

            return new_tip.id

    async def get_tips_sent(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        to_user = User
        stmt = (
            select(
                Tip.id,
                Tip.post_id,
                Tip.to_user_id,
                Tip.amount,
                Tip.tx_hash,
                Tip.created_at,
                Post.title,
                to_user.username,
            )
            .outerjoin(Post, Tip.post_id == Post.id)
            .outerjoin(to_user, Tip.to_user_id == to_user.user_id)
            .where(Tip.from_user_id == user_id)
            .order_by(Tip.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "post_id": r[1],
                    "to_user_id": r[2],
                    "amount": _decimal_to_float(r[3]),
                    "tx_hash": r[4],
                    "created_at": _fmt(r[5]),
                    "post_title": r[6],
                    "to_username": r[7],
                }
                for r in rows
            ]

    async def get_tips_received(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        from_user = User
        stmt = (
            select(
                Tip.id,
                Tip.post_id,
                Tip.from_user_id,
                Tip.amount,
                Tip.tx_hash,
                Tip.created_at,
                Post.title,
                from_user.username,
            )
            .outerjoin(Post, Tip.post_id == Post.id)
            .outerjoin(from_user, Tip.from_user_id == from_user.user_id)
            .where(Tip.to_user_id == user_id)
            .order_by(Tip.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        async with session or get_async_session() as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "post_id": r[1],
                    "from_user_id": r[2],
                    "amount": _decimal_to_float(r[3]),
                    "tx_hash": r[4],
                    "created_at": _fmt(r[5]),
                    "post_title": r[6],
                    "from_username": r[7],
                }
                for r in rows
            ]


forum_repo = ForumRepository()
