"""
Core ORM package — SQLAlchemy 2.0 async layer.

This package coexists with the raw psycopg2 layer during the migration period.
New code should prefer the async ORM repositories.
"""

from .models import (
    Base,
    Board,
    DmConversation,
    DmMessage,
    ForumComment,
    Friendship,
    MembershipPayment,
    Notification,
    Post,
    PriceAlert,
    SystemConfig,
    Tip,
    User,
)
from .repositories import user_repo
from .session import close_async_engine, get_async_session, get_engine, using_session

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
    "using_session",
    "user_repo",
]
