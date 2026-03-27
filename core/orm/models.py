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
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Basic tables ────────────────────────────────────────────────────────────────


class Watchlist(Base):
    __tablename__ = "watchlist"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)


class SystemCache(Base):
    __tablename__ = "system_cache"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
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


# ── User tables ────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    auth_method: Mapped[str] = mapped_column(Text, default="password")
    pi_uid: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    pi_username: Mapped[Optional[str]] = mapped_column(Text)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    membership_tier: Mapped[str] = mapped_column(Text, default="free")
    membership_expires_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    role: Mapped[str] = mapped_column(Text, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_users_last_active", "last_active_at"),
        Index("idx_users_membership", "membership_tier"),
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
        CheckConstraint("amount > 0", name="ck_amount_positive"),
        CheckConstraint("months > 0", name="ck_months_positive"),
    )


class AdminBroadcast(Base):
    __tablename__ = "admin_broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, default="announcement")
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    admin: Mapped["User"] = relationship(foreign_keys=[admin_user_id])


class UserApiKey(Base):
    __tablename__ = "user_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_selection: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_api_key_provider"),
        Index("idx_user_api_keys_user", "user_id"),
    )


# ── Conversation tables ────────────────────────────────────────────────────────


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, default="default")
    user_id: Mapped[str] = mapped_column(Text, default="local_user")
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # Python attr is metadata_ to avoid shadowing Base.metadata
    metadata_: Mapped[Optional[str]] = mapped_column("metadata", Text)

    __table_args__ = (
        Index(
            "idx_conversation_history_session_timestamp",
            "session_id",
            "timestamp",
        ),
    )


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, default="local_user")
    title: Mapped[Optional[str]] = mapped_column(Text)
    is_pinned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
        Index("idx_sessions_updated_at", "updated_at"),
    )


# ── Forum tables ───────────────────────────────────────────────────────────────


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
        Index(
            "idx_posts_payment_tx_hash",
            "payment_tx_hash",
            unique=True,
            postgresql_where=text("payment_tx_hash IS NOT NULL"),
        ),
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
        CheckConstraint(
            "type IN ('comment', 'push', 'boo')", name="ck_forum_comment_type"
        ),
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
        CheckConstraint("amount > 0", name="ck_amount_positive"),
        Index("idx_tips_post_id", "post_id"),
        Index("idx_tips_from_user", "from_user_id"),
        Index("idx_tips_to_user", "to_user_id"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_tags_name", "name"),)


class PostTag(Base):
    __tablename__ = "post_tags"

    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id"), primary_key=True
    )


class UserDailyComment(Base):
    __tablename__ = "user_daily_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_daily_comments"),
        Index("idx_user_daily_comments_user_date", "user_id", "date"),
    )


class UserDailyPost(Base):
    __tablename__ = "user_daily_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_user_daily_posts"),)


# ── Scam tracker tables ────────────────────────────────────────────────────────


class ScamReport(Base):
    __tablename__ = "scam_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scam_wallet_address: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    reporter_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    reporter_wallet_masked: Mapped[str] = mapped_column(Text, nullable=False)
    scam_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_hash: Mapped[Optional[str]] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text, default="pending")
    approve_count: Mapped[int] = mapped_column(Integer, default=0)
    reject_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_user_id])

    __table_args__ = (
        CheckConstraint(
            "verification_status IN "
            "('pending', 'verified', 'rejected', 'investigating')",
            name="ck_verification_status_valid",
        ),
        Index("idx_scam_wallet", "scam_wallet_address"),
        Index("idx_scam_type", "scam_type"),
        Index("idx_scam_status", "verification_status"),
        Index("idx_scam_created", "created_at"),
    )


class ScamReportVote(Base):
    __tablename__ = "scam_report_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scam_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    vote_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    report: Mapped["ScamReport"] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("report_id", "user_id", name="uq_scam_vote"),
        Index("idx_vote_report", "report_id"),
        Index("idx_vote_user", "user_id"),
    )


class ScamReportComment(Base):
    __tablename__ = "scam_report_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scam_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_hash: Mapped[Optional[str]] = mapped_column(Text)
    is_hidden: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    report: Mapped["ScamReport"] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_comment_report", "report_id"),
        Index("idx_comment_created", "created_at"),
    )


# ── Friendship tables ──────────────────────────────────────────────────────────


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
        UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'blocked')",
            name="ck_friendship_status",
        ),
        Index("idx_friendships_user_id", "user_id"),
        Index("idx_friendships_friend_id", "friend_id"),
        Index("idx_friendships_status", "status"),
    )


# ── DM tables ──────────────────────────────────────────────────────────────────


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
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    user1_unread_count: Mapped[int] = mapped_column(Integer, default=0)
    user2_unread_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_dm_conversation_pair"),
        Index("idx_dm_conversations_user1", "user1_id"),
        Index("idx_dm_conversations_user2", "user2_id"),
        Index("idx_dm_conversations_last_message", "last_message_at"),
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
        Index("idx_dm_messages_created", "created_at"),
        Index("idx_dm_messages_from_user", "from_user_id"),
        Index("idx_dm_messages_to_user", "to_user_id"),
    )


class DmMessageDeletion(Base):
    __tablename__ = "dm_message_deletions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dm_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    deleted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_dm_message_deletion"),
    )


class UserMessageLimit(Base):
    __tablename__ = "user_message_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    greeting_count: Mapped[int] = mapped_column(Integer, default=0)
    greeting_month: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_message_limit"),
        Index("idx_user_message_limits", "user_id", "date"),
    )


# ── Notification ───────────────────────────────────────────────────────────────


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


# ── Audit log ──────────────────────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    user_id: Mapped[Optional[str]] = mapped_column(Text)
    username: Mapped[Optional[str]] = mapped_column(Text)
    action: Mapped[Optional[str]] = mapped_column(Text)
    resource_type: Mapped[Optional[str]] = mapped_column(Text)
    resource_id: Mapped[Optional[str]] = mapped_column(Text)
    endpoint: Mapped[Optional[str]] = mapped_column(Text)
    method: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(Text)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_code: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    # Python attr is metadata_ to avoid shadowing Base.metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_endpoint", "endpoint"),
    )


# ── Governance tables ──────────────────────────────────────────────────────────


class ContentReport(Base):
    __tablename__ = "content_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reporter_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    report_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(Text, default="pending")
    violation_level: Mapped[Optional[str]] = mapped_column(Text)
    approve_count: Mapped[int] = mapped_column(Integer, default=0)
    reject_count: Mapped[int] = mapped_column(Integer, default=0)
    points_assigned: Mapped[int] = mapped_column(Integer, default=0)
    action_taken: Mapped[Optional[str]] = mapped_column(Text)
    processed_by: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'escalated')",
            name="ck_review_status_valid",
        ),
        Index("idx_content_reports_status", "review_status"),
        Index("idx_content_reports_reporter", "reporter_user_id"),
        Index("idx_content_reports_content", "content_type", "content_id"),
        Index("idx_content_reports_created", "created_at"),
    )


class ReportReviewVote(Base):
    __tablename__ = "report_review_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_reports.id"), nullable=False
    )
    reviewer_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    vote_type: Mapped[str] = mapped_column(Text, nullable=False)
    vote_weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    report: Mapped["ContentReport"] = relationship()

    __table_args__ = (
        UniqueConstraint("report_id", "reviewer_user_id", name="uq_report_review_vote"),
        CheckConstraint(
            "vote_type IN ('approve', 'reject')", name="ck_vote_type_valid"
        ),
        Index("idx_report_review_votes_report", "report_id"),
    )


class UserViolation(Base):
    __tablename__ = "user_violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    violation_level: Mapped[str] = mapped_column(Text, nullable=False)
    violation_type: Mapped[Optional[str]] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer, default=0)
    source_type: Mapped[Optional[str]] = mapped_column(Text)
    source_id: Mapped[Optional[int]] = mapped_column(Integer)
    action_taken: Mapped[Optional[str]] = mapped_column(Text)
    suspended_until: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    processed_by: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_user_violations_user", "user_id"),)


class UserViolationPoints(Base):
    __tablename__ = "user_violation_points"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    total_violations: Mapped[int] = mapped_column(Integer, default=0)
    last_violation_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    suspension_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditReputation(Base):
    __tablename__ = "audit_reputation"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    correct_votes: Mapped[int] = mapped_column(Integer, default=0)
    accuracy_rate: Mapped[float] = mapped_column(Float, default=0.0)
    reputation_score: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(Text)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)
    # Python attr is metadata_ to avoid shadowing Base.metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(Text)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_activity_logs_user", "user_id"),
        Index("idx_user_activity_logs_type", "activity_type"),
    )


# ── Analysis tables ────────────────────────────────────────────────────────────


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[str]] = mapped_column(Text)
    symbol: Mapped[Optional[str]] = mapped_column(Text)
    interval: Mapped[str] = mapped_column(Text, default="1d")
    report_text: Mapped[Optional[str]] = mapped_column(Text)
    # Python attr is metadata_ to avoid shadowing Base.metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_analysis_reports_session", "session_id"),
        Index("idx_analysis_reports_user", "user_id"),
    )


# ── Price alerts ───────────────────────────────────────────────────────────────


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
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        CheckConstraint("target > 0", name="ck_target_positive"),
        Index("idx_price_alerts_user", "user_id"),
        Index("idx_price_alerts_active", "triggered"),
    )


# ── Tool tables ────────────────────────────────────────────────────────────────


class ToolsCatalog(Base):
    __tablename__ = "tools_catalog"

    tool_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    tier_required: Mapped[str] = mapped_column(Text, default="free")
    quota_type: Mapped[str] = mapped_column(Text, default="unlimited")
    daily_limit_free: Mapped[Optional[int]] = mapped_column(Integer)
    daily_limit_plus: Mapped[Optional[int]] = mapped_column(Integer)
    daily_limit_prem: Mapped[Optional[int]] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(Text, default="native")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_tools_catalog_category", "category"),
        Index("idx_tools_catalog_tier", "tier_required"),
    )


class AgentToolPermission(Base):
    __tablename__ = "agent_tool_permissions"

    agent_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tool_id: Mapped[str] = mapped_column(Text, primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("idx_agent_tool_agent", "agent_id"),)


class UserToolPreference(Base):
    __tablename__ = "user_tool_preferences"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tool_id: Mapped[str] = mapped_column(Text, primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_user_tool_prefs_user", "user_id"),)


class ToolUsageLog(Base):
    __tablename__ = "tool_usage_log"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tool_id: Mapped[str] = mapped_column(Text, primary_key=True)
    used_date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    call_count: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (Index("idx_tool_usage_user_date", "user_id", "used_date"),)


# ── Memory tables ──────────────────────────────────────────────────────────────


class UserMemory(Base):
    __tablename__ = "user_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(Text, default="long_term")
    content: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "session_id", "memory_type", name="uq_user_memory"),
        Index("idx_user_memory_user", "user_id"),
        Index("idx_user_memory_session", "session_id"),
        Index("idx_user_memory_type", "memory_type"),
    )


class UserHistoryLog(Base):
    __tablename__ = "user_history_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(Text)
    entry: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_history_user", "user_id"),
        Index("idx_user_history_session", "session_id"),
        Index("idx_user_history_created", "created_at"),
    )


class UserMemoryCache(Base):
    __tablename__ = "user_memory_cache"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text)
    last_consolidated_index: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserFact(Base):
    __tablename__ = "user_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, default="high")
    source_turn: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_fact"),
        Index("idx_user_facts_user", "user_id"),
    )


# ── Experience tables ──────────────────────────────────────────────────────────


class TaskExperience(Base):
    __tablename__ = "task_experiences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    task_family: Mapped[str] = mapped_column(Text, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    agent_used: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    response_chars: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # Generated column — persisted TSVECTOR for full-text search
    query_tsv = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', query_text)", persisted=True),
    )

    __table_args__ = (
        Index("idx_te_user_family", "user_id", "task_family"),
        Index("idx_te_created", "created_at"),
        Index("idx_te_tsv", "query_tsv", postgresql_using="gin"),
    )
