"""
Core ORM package — SQLAlchemy 2.0 async layer.

This package coexists with the raw psycopg2 layer during the migration period.
New code should prefer the async ORM repositories.
"""
from .models import (
    Base,
    User,
    Board,
    Post,
    ForumComment,
    Tip,
    Friendship,
    Notification,
    DmConversation,
    DmMessage,
    SystemConfig,
    PriceAlert,
    MembershipPayment,
)
from .session import get_async_session, get_engine, close_async_engine
from .repositories import user_repo

__all__ = [
    "Base",
    "User",
    "Board",
    "Post",
    "ForumComment",
    "Tip",
    "Friendship",
    "Notification",
    "DmConversation",
    "DmMessage",
    "SystemConfig",
    "PriceAlert",
    "MembershipPayment",
    "get_async_session",
    "get_engine",
    "close_async_engine",
    "user_repo",
]
