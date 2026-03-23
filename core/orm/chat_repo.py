"""
Async ORM repository for Chat / Session operations.

Provides async equivalents of the functions in core.database.chat,
using SQLAlchemy 2.0 select/update/delete with Session and ConversationHistory models.

Usage::

    from core.orm.chat_repo import chat_repo

    await chat_repo.save_chat_message("user-1", "sess-1", "user", "hello")
    history = await chat_repo.get_chat_history("sess-1")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConversationHistory, Session
from .session import using_session

logger = logging.getLogger(__name__)


def _fmt(dt: datetime | None) -> str | None:
    """Format a datetime to ``YYYY-MM-DD HH:MM:SS`` string."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class ChatRepository:
    """Async repository for chat sessions and conversation history."""

    # ── Session management ─────────────────────────────────────────────────

    async def create_session(
        self,
        session_id: str,
        title: str = "New Chat",
        user_id: str = "local_user",
        session: AsyncSession | None = None,
    ) -> None:
        """Create a new chat session."""
        async with using_session(session) as s:
            new_session = Session(
                session_id=session_id,
                user_id=user_id,
                title=title,
                is_pinned=0,
            )
            s.add(new_session)

    async def update_session_title(
        self,
        session_id: str,
        title: str,
        session: AsyncSession | None = None,
    ) -> None:
        """Update the title of an existing session."""
        stmt = (
            text("UPDATE sessions SET title = :title, updated_at = NOW() "
                 "WHERE session_id = :session_id")
            .bindparams(title=title, session_id=session_id)
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def toggle_session_pin(
        self,
        session_id: str,
        is_pinned: bool,
        session: AsyncSession | None = None,
    ) -> None:
        """Toggle the pinned state of a session."""
        pin_val = 1 if is_pinned else 0
        stmt = (
            text("UPDATE sessions SET is_pinned = :pin_val "
                 "WHERE session_id = :session_id")
            .bindparams(pin_val=pin_val, session_id=session_id)
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def get_sessions(
        self,
        user_id: str = "local_user",
        limit: int = 20,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get sessions for a user (pinned first, then by updated_at desc)."""
        stmt = (
            text(
                "SELECT session_id, title, created_at, updated_at, is_pinned "
                "FROM sessions "
                "WHERE user_id = :user_id "
                "ORDER BY is_pinned DESC, updated_at DESC "
                "LIMIT :limit OFFSET :offset"
            )
            .bindparams(user_id=user_id, limit=limit, offset=offset)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "created_at": _fmt(row[2]),
                    "updated_at": _fmt(row[3]),
                    "is_pinned": bool(row[4]),
                }
                for row in rows
            ]

    async def delete_session(
        self,
        session_id: str,
        session: AsyncSession | None = None,
    ) -> None:
        """Delete a session and all its conversation history."""
        async with using_session(session) as s:
            await s.execute(
                delete(ConversationHistory).where(
                    ConversationHistory.session_id == session_id
                )
            )
            await s.execute(
                delete(Session).where(Session.session_id == session_id)
            )

    # ── Chat messages ──────────────────────────────────────────────────────

    async def save_chat_message(
        self,
        role: str,
        content: str,
        session_id: str = "default",
        user_id: Optional[str] = "local_user",
        metadata: Optional[dict] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Save a chat message and auto-update session title / updated_at.

        Mirrors the legacy ``save_chat_message`` logic:
        - If the session does not exist, create it with a generated title.
        - If the session title is ``"New Chat"`` and role is ``"user"``,
          update the title to a truncated version of the content.
        - Otherwise just touch ``updated_at``.
        """
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        uid = user_id or "local_user"

        async with using_session(session) as s:
            # 1. Insert the message
            msg = ConversationHistory(
                session_id=session_id,
                user_id=uid,
                role=role,
                content=content,
                metadata_=metadata_json,
            )
            s.add(msg)

            # 2. Check if session exists
            result = await s.execute(
                select(Session.title).where(Session.session_id == session_id)
            )
            row = result.fetchone()

            if not row:
                # Session does not exist — create it
                title = content[:30] + "..." if len(content) > 30 else content
                if role == "assistant":
                    title = "AI Analysis"

                new_session = Session(
                    session_id=session_id,
                    user_id=uid,
                    title=title,
                )
                s.add(new_session)
            else:
                current_title = row[0]
                if current_title == "New Chat" and role == "user":
                    new_title = (
                        content[:30] + "..." if len(content) > 30 else content
                    )
                    await s.execute(
                        text(
                            "UPDATE sessions SET title = :title, updated_at = NOW() "
                            "WHERE session_id = :session_id"
                        ).bindparams(title=new_title, session_id=session_id)
                    )
                else:
                    await s.execute(
                        text(
                            "UPDATE sessions SET updated_at = NOW() "
                            "WHERE session_id = :session_id"
                        ).bindparams(session_id=session_id)
                    )

    async def get_chat_history(
        self,
        session_id: str = "default",
        limit: int = 20,
        before_timestamp: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get chat history (latest *limit* messages, in ASC order).

        *before_timestamp*: if provided, only return messages older than this
        timestamp (for scrolling up / loading older messages).
        """
        if before_timestamp:
            stmt = text(
                "SELECT role, content, metadata, timestamp "
                "FROM conversation_history "
                "WHERE session_id = :session_id AND timestamp < :before_timestamp "
                "ORDER BY timestamp DESC "
                "LIMIT :limit"
            ).bindparams(
                session_id=session_id,
                before_timestamp=before_timestamp,
                limit=limit,
            )
        else:
            stmt = text(
                "SELECT role, content, metadata, timestamp "
                "FROM conversation_history "
                "WHERE session_id = :session_id "
                "ORDER BY timestamp DESC "
                "LIMIT :limit"
            ).bindparams(session_id=session_id, limit=limit)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = list(reversed(result.fetchall()))  # DESC → ASC

            history: List[dict] = []
            for row in rows:
                meta = row[2]
                try:
                    meta = json.loads(meta) if meta else None
                except (json.JSONDecodeError, TypeError):
                    meta = None

                history.append(
                    {
                        "role": row[0],
                        "content": row[1],
                        "metadata": meta,
                        "timestamp": _fmt(row[3]),
                    }
                )
            return history

    async def clear_chat_history(
        self,
        session_id: str = "default",
        session: AsyncSession | None = None,
    ) -> None:
        """Delete all conversation history for a given session."""
        stmt = delete(ConversationHistory).where(
            ConversationHistory.session_id == session_id
        )

        async with using_session(session) as s:
            await s.execute(stmt)


chat_repo = ChatRepository()
