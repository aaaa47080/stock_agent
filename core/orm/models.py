"""
SQLAlchemy 2.0 ORM declarative models.

These models mirror the existing psycopg2 schema in core/database/schema.py.
They are used for the async ORM migration and coexist with the raw SQL layer
during the transition period.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    auth_method: Mapped[str] = mapped_column(Text, default="password")
    pi_uid: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    pi_username: Mapped[Optional[str]] = mapped_column(Text)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    membership_tier: Mapped[str] = mapped_column(Text, default="free")
    membership_expires_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    role: Mapped[str] = mapped_column(Text, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class MembershipPayment(Base):
    __tablename__ = "membership_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    months: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_membership_payments_user", "user_id"),
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boards.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(Text)
    push_count: Mapped[int] = mapped_column(Integer, default=0)
    boo_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    tips_total: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    payment_tx_hash: Mapped[Optional[str]] = mapped_column(Text)
    is_pinned: Mapped[int] = mapped_column(Integer, default=0)
    is_hidden: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    board: Mapped["Board"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_posts_board_id", "board_id"),
        Index("idx_posts_user_id", "user_id"),
        Index("idx_posts_created_at", "created_at"),
        Index("idx_posts_category", "category"),
    )


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("forum_comments.id")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    is_hidden: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    post: Mapped["Post"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_forum_comments_post_id", "post_id"),
        Index("idx_forum_comments_user_id", "user_id"),
    )


class Tip(Base):
    __tablename__ = "tips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id"), nullable=False
    )
    from_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    to_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=1)
    tx_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    post: Mapped["Post"] = relationship()
    from_user: Mapped["User"] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped["User"] = relationship(foreign_keys=[to_user_id])

    __table_args__ = (
        Index("idx_tips_post_id", "post_id"),
        Index("idx_tips_from_user", "from_user_id"),
        Index("idx_tips_to_user", "to_user_id"),
    )


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    friend_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    friend: Mapped["User"] = relationship(foreign_keys=[friend_id])

    __table_args__ = (
        Index("idx_friendships_user_id", "user_id"),
        Index("idx_friendships_friend_id", "friend_id"),
        Index("idx_friendships_status", "status"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_notifications_user_created", "user_id", created_at.desc()),
        Index("idx_notifications_user_unread", "user_id"),
    )


class DmConversation(Base):
    __tablename__ = "dm_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    user2_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    last_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    user1_unread_count: Mapped[int] = mapped_column(Integer, default=0)
    user2_unread_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_dm_conversations_user1", "user1_id"),
        Index("idx_dm_conversations_user2", "user2_id"),
    )


class DmMessage(Base):
    __tablename__ = "dm_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dm_conversations.id"), nullable=False
    )
    from_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    to_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(Text, default="text")
    is_read: Mapped[int] = mapped_column(Integer, default=0)
    read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_dm_messages_conversation", "conversation_id"),
        Index("idx_dm_messages_created", created_at.desc()),
    )


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(Text, default="string")
    category: Mapped[str] = mapped_column(Text, default="general")
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_public: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    repeat: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_price_alerts_user", "user_id"),
        Index("idx_price_alerts_active", "triggered"),
    )
