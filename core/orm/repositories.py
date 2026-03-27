"""
Async ORM repository for User operations.

This module provides async equivalents of the functions in core.database.user,
using SQLAlchemy 2.0 ORM models. It serves as the proof-of-concept for the
full ORM migration and can coexist with the raw SQL layer.

Usage::

    from core.orm.repositories import user_repo

    user = await user_repo.get_by_id("user-123")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .session import using_session

logger = logging.getLogger(__name__)


def _normalize_membership_tier(tier: Optional[str]) -> str:
    return (
        "premium"
        if (tier or "free").strip().lower() in {"premium", "plus", "pro"}
        else "free"
    )


def _user_to_dict(user: User) -> dict:
    """Convert a User ORM object to a dict matching the legacy format."""
    has_wallet = bool(user.pi_uid) or (user.auth_method == "pi_network")
    return {
        "user_id": user.user_id,
        "username": user.username,
        "auth_method": user.auth_method,
        "role": user.role or "user",
        "is_active": user.is_active if user.is_active is not None else True,
        "membership_tier": _normalize_membership_tier(user.membership_tier),
        "membership_expires_at": (
            user.membership_expires_at.isoformat()
            if user.membership_expires_at
            else None
        ),
        "created_at": (user.created_at.isoformat() if user.created_at else None),
        "is_premium": _normalize_membership_tier(user.membership_tier) == "premium",
        "pi_uid": user.pi_uid,
        "pi_username": user.pi_username,
        "has_wallet": has_wallet,
    }


class UserRepository:
    """Async repository for User entity."""

    async def get_by_id(
        self, user_id: str, session: AsyncSession | None = None
    ) -> Optional[dict]:
        """Get user by ID, returning a dict in the legacy format."""
        async with using_session(session) as s:
            result = await s.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            return _user_to_dict(user) if user else None

    async def get_by_username(
        self, username: str, session: AsyncSession | None = None
    ) -> Optional[dict]:
        """Get user by username."""
        async with using_session(session) as s:
            result = await s.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            return _user_to_dict(user) if user else None

    async def update_last_active(
        self, user_id: str, session: AsyncSession | None = None
    ) -> bool:
        """Update user's last active timestamp."""
        async with using_session(session) as s:
            result = await s.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(last_active_at=datetime.now(timezone.utc))
            )
            return result.rowcount > 0

    async def get_membership(
        self, user_id: str, session: AsyncSession | None = None
    ) -> dict:
        """Get user membership info."""
        user = await self.get_by_id(user_id, session)
        if not user:
            return {"is_premium": False, "membership_tier": "free", "days_remaining": 0}
        return {
            "is_premium": user["is_premium"],
            "membership_tier": user["membership_tier"],
            "days_remaining": self._days_remaining(user.get("membership_expires_at")),
        }

    @staticmethod
    def _days_remaining(expires_at: Optional[str]) -> int:
        if not expires_at:
            return 0
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            delta = exp - datetime.now(timezone.utc)
            return max(0, delta.days)
        except (ValueError, TypeError):
            return 0


user_repo = UserRepository()
