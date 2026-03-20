"""baseline_schema

Create all existing tables as the initial Alembic baseline.

Revision ID: b001_baseline
Revises:
Create Date: 2026-03-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "b001_baseline"
down_revision: Union[str, Sequence[str], None] = "92a35ecee1cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("username", sa.Text(), unique=True, nullable=False),
        sa.Column("auth_method", sa.Text(), server_default="password"),
        sa.Column("pi_uid", sa.Text(), unique=True),
        sa.Column("pi_username", sa.Text()),
        sa.Column("last_active_at", TIMESTAMP(timezone=True)),
        sa.Column("membership_tier", sa.Text(), server_default="free"),
        sa.Column("membership_expires_at", TIMESTAMP(timezone=True)),
        sa.Column("role", sa.Text(), server_default="user"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # ── basic tables ──────────────────────────────────────────────
    op.create_table(
        "watchlist",
        sa.Column("user_id", sa.Text()),
        sa.Column("symbol", sa.Text()),
        sa.PrimaryKeyConstraint("user_id", "symbol"),
    )
    op.create_table(
        "system_cache",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "system_config",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.Text(), server_default="string"),
        sa.Column("category", sa.Text(), server_default="general"),
        sa.Column("description", sa.Text()),
        sa.Column("is_public", sa.Integer(), server_default="1"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # ── conversation tables ───────────────────────────────────────
    op.create_table(
        "conversation_history",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("session_id", sa.Text(), server_default="default"),
        sa.Column("user_id", sa.Text(), server_default="local_user"),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", sa.Text()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), server_default="local_user"),
        sa.Column("title", sa.Text()),
        sa.Column("is_pinned", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )

    # ── user tables ───────────────────────────────────────────────
    op.create_table(
        "membership_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.Text(), unique=True, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.CheckConstraint("amount > 0", name="ck_amount_positive"),
        sa.CheckConstraint("months > 0", name="ck_months_positive"),
    )
    op.create_table(
        "admin_broadcasts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("admin_user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), server_default="announcement"),
        sa.Column("recipient_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.user_id"]),
    )
    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("model_selection", sa.Text()),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("user_id", "provider"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )

    # ── forum tables ──────────────────────────────────────────────
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("post_count", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Integer(), server_default="1"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text()),
        sa.Column("push_count", sa.Integer(), server_default="0"),
        sa.Column("boo_count", sa.Integer(), server_default="0"),
        sa.Column("comment_count", sa.Integer(), server_default="0"),
        sa.Column("tips_total", sa.Numeric(18, 4), server_default="0"),
        sa.Column("view_count", sa.Integer(), server_default="0"),
        sa.Column("payment_tx_hash", sa.Text()),
        sa.Column("is_pinned", sa.Integer(), server_default="0"),
        sa.Column("is_hidden", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "forum_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Integer()),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("is_hidden", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["forum_comments.id"]),
        sa.CheckConstraint("type IN ('comment', 'reply')", name="ck_type_valid"),
    )
    op.create_table(
        "tips",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Text(), nullable=False),
        sa.Column("to_user_id", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="1"),
        sa.Column("tx_hash", sa.Text(), unique=True, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.user_id"]),
        sa.CheckConstraint("amount > 0", name="ck_amount_positive"),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
        sa.Column("post_count", sa.Integer(), server_default="0"),
        sa.Column("last_used_at", TIMESTAMP(timezone=True)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "post_tags",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("post_id", "tag_id"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]),
    )
    op.create_table(
        "user_daily_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("comment_count", sa.Integer(), server_default="0"),
        sa.UniqueConstraint("user_id", "date"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "user_daily_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("post_count", sa.Integer(), server_default="0"),
        sa.UniqueConstraint("user_id", "date"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )

    # ── scam tracker tables ───────────────────────────────────────
    op.create_table(
        "scam_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("scam_wallet_address", sa.Text(), unique=True, nullable=False),
        sa.Column("reporter_user_id", sa.Text(), nullable=False),
        sa.Column("reporter_wallet_masked", sa.Text(), nullable=False),
        sa.Column("scam_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("transaction_hash", sa.Text()),
        sa.Column("verification_status", sa.Text(), server_default="pending"),
        sa.Column("approve_count", sa.Integer(), server_default="0"),
        sa.Column("reject_count", sa.Integer(), server_default="0"),
        sa.Column("comment_count", sa.Integer(), server_default="0"),
        sa.Column("view_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.user_id"]),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected', 'investigating')",
            name="ck_verification_status_valid",
        ),
    )
    op.create_table(
        "scam_report_votes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("vote_type", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("report_id", "user_id"),
        sa.ForeignKeyConstraint(["report_id"], ["scam_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "scam_report_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("transaction_hash", sa.Text()),
        sa.Column("is_hidden", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["report_id"], ["scam_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )

    # ── friendships ───────────────────────────────────────────────
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("friend_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "friend_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["friend_id"], ["users.user_id"]),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'blocked')", name="ck_status_valid"
        ),
    )

    # ── direct messages ───────────────────────────────────────────
    op.create_table(
        "dm_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user1_id", sa.Text(), nullable=False),
        sa.Column("user2_id", sa.Text(), nullable=False),
        sa.Column("last_message_id", sa.Integer()),
        sa.Column("last_message_at", TIMESTAMP(timezone=True)),
        sa.Column("user1_unread_count", sa.Integer(), server_default="0"),
        sa.Column("user2_unread_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user1_id", "user2_id"),
        sa.ForeignKeyConstraint(["user1_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["user2_id"], ["users.user_id"]),
    )
    op.create_table(
        "dm_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Text(), nullable=False),
        sa.Column("to_user_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.Text(), server_default="text"),
        sa.Column("is_read", sa.Integer(), server_default="0"),
        sa.Column("read_at", TIMESTAMP(timezone=True)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["conversation_id"], ["dm_conversations.id"]),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.user_id"]),
    )
    op.create_table(
        "dm_message_deletions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("message_id", "user_id"),
        sa.ForeignKeyConstraint(["message_id"], ["dm_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "user_message_limits",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("greeting_count", sa.Integer(), server_default="0"),
        sa.Column("greeting_month", sa.Text()),
        sa.UniqueConstraint("user_id", "date"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )

    # ── audit logs ────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("timestamp", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("user_id", sa.String(255)),
        sa.Column("username", sa.String(255)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("request_data", JSONB()),
        sa.Column("response_code", sa.Integer()),
        sa.Column("success", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("error_message", sa.Text()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("metadata", JSONB()),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # ── governance tables ─────────────────────────────────────────
    op.create_table(
        "content_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("review_status", sa.String(20), server_default="pending"),
        sa.Column("violation_level", sa.String(20)),
        sa.Column("approve_count", sa.Integer(), server_default="0"),
        sa.Column("reject_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'escalated')",
            name="ck_review_status_valid",
        ),
    )
    op.create_table(
        "report_review_votes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.String(255), nullable=False),
        sa.Column("vote_type", sa.String(20), nullable=False),
        sa.Column("vote_weight", sa.Float(), server_default="1.0"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("report_id", "reviewer_user_id"),
        sa.ForeignKeyConstraint(["report_id"], ["content_reports.id"]),
        sa.CheckConstraint(
            "vote_type IN ('approve', 'reject')", name="ck_vote_type_valid"
        ),
    )
    op.create_table(
        "user_violations",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("violation_level", sa.String(20), nullable=False),
        sa.Column("violation_type", sa.String(50)),
        sa.Column("points", sa.Integer(), server_default="0"),
        sa.Column("source_type", sa.String(20)),
        sa.Column("source_id", sa.Integer()),
        sa.Column("action_taken", sa.String(50)),
        sa.Column("suspended_until", TIMESTAMP(timezone=True)),
        sa.Column("processed_by", sa.String(255)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "user_violation_points",
        sa.Column("user_id", sa.String(255), primary_key=True),
        sa.Column("points", sa.Integer(), server_default="0"),
        sa.Column("total_violations", sa.Integer(), server_default="0"),
        sa.Column("last_violation_at", TIMESTAMP(timezone=True)),
        sa.Column("suspension_count", sa.Integer(), server_default="0"),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "audit_reputation",
        sa.Column("user_id", sa.String(255), primary_key=True),
        sa.Column("total_reviews", sa.Integer(), server_default="0"),
        sa.Column("correct_votes", sa.Integer(), server_default="0"),
        sa.Column("accuracy_rate", sa.Float(), server_default="0.0"),
        sa.Column("reputation_score", sa.Integer(), server_default="0"),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "user_activity_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("activity_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.Integer()),
        sa.Column("metadata", JSONB()),
        sa.Column("success", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("error_message", sa.Text()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )

    # ── analysis reports ──────────────────────────────────────────
    op.create_table(
        "analysis_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("session_id", sa.String(255)),
        sa.Column("user_id", sa.String(255)),
        sa.Column("symbol", sa.String(50)),
        sa.Column("interval", sa.String(10), server_default="1d"),
        sa.Column("report_text", sa.Text()),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # ── price alerts ──────────────────────────────────────────────
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("target", sa.Numeric(18, 4), nullable=False),
        sa.Column("repeat", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], ondelete="CASCADE", name="fk_alert_user"
        ),
        sa.CheckConstraint("target > 0", name="ck_target_positive"),
    )

    # ── tool system ───────────────────────────────────────────────
    op.create_table(
        "tools_catalog",
        sa.Column("tool_id", sa.Text(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("tier_required", sa.Text(), server_default="free"),
        sa.Column("quota_type", sa.Text(), server_default="unlimited"),
        sa.Column("daily_limit_free", sa.Integer(), server_default="0"),
        sa.Column("daily_limit_plus", sa.Integer()),
        sa.Column("daily_limit_prem", sa.Integer()),
        sa.Column("source_type", sa.Text(), server_default="native"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "agent_tool_permissions",
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("tool_id", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.PrimaryKeyConstraint("agent_id", "tool_id"),
    )
    op.create_table(
        "user_tool_preferences",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("tool_id", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "tool_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_table(
        "tool_usage_log",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("tool_id", sa.Text(), nullable=False),
        sa.Column(
            "used_date",
            sa.Date(),
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.Column("call_count", sa.Integer(), server_default="1"),
        sa.PrimaryKeyConstraint("user_id", "tool_id", "used_date"),
    )

    # ── memory system ─────────────────────────────────────────────
    op.create_table(
        "user_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("session_id", sa.String(255)),
        sa.Column(
            "memory_type", sa.String(20), nullable=False, server_default="long_term"
        ),
        sa.Column("content", sa.Text()),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "session_id", "memory_type"),
    )
    op.create_table(
        "user_history_log",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("session_id", sa.String(255)),
        sa.Column("entry", sa.Text(), nullable=False),
        sa.Column("tools_used", sa.Text()),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "user_memory_cache",
        sa.Column("user_id", sa.String(255), primary_key=True),
        sa.Column("session_id", sa.String(255)),
        sa.Column("last_consolidated_index", sa.Integer(), server_default="0"),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # ── user facts ────────────────────────────────────────────────
    op.create_table(
        "user_facts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(10), server_default="high"),
        sa.Column("source_turn", sa.Integer()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "key"),
    )

    # ── notifications ─────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("body", sa.Text()),
        sa.Column("data", JSONB()),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], ondelete="CASCADE", name="fk_user"
        ),
    )

    # ── task experiences ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE task_experiences (
            id              BIGSERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            session_id      TEXT NOT NULL,
            task_family     TEXT NOT NULL,
            query_text      TEXT NOT NULL,
            query_tsv       TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', query_text)) STORED,
            tools_used      TEXT[],
            agent_used      TEXT,
            outcome         TEXT NOT NULL,
            quality_score   REAL,
            failure_reason  TEXT,
            response_chars  INT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── indexes ───────────────────────────────────────────────────
    # conversation / sessions
    op.create_index(
        "idx_conversation_history_session_timestamp",
        "conversation_history",
        ["session_id", "timestamp"],
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_updated_at", "sessions", [sa.text("updated_at DESC")])
    # users
    op.create_index("idx_users_last_active", "users", [sa.text("last_active_at DESC")])
    op.create_index("idx_users_membership", "users", ["membership_tier"])
    # membership_payments
    op.create_index("idx_membership_payments_user", "membership_payments", ["user_id"])
    # user_api_keys
    op.create_index("idx_user_api_keys_user", "user_api_keys", ["user_id"])
    # forum
    op.create_index("idx_posts_board_id", "posts", ["board_id"])
    op.create_index("idx_posts_user_id", "posts", ["user_id"])
    op.create_index("idx_posts_created_at", "posts", ["created_at"])
    op.create_index("idx_posts_category", "posts", ["category"])
    op.create_index("idx_forum_comments_post_id", "forum_comments", ["post_id"])
    op.create_index("idx_forum_comments_user_id", "forum_comments", ["user_id"])
    op.create_index("idx_tips_post_id", "tips", ["post_id"])
    op.create_index("idx_tips_from_user", "tips", ["from_user_id"])
    op.create_index("idx_tips_to_user", "tips", ["to_user_id"])
    op.create_index("idx_tags_name", "tags", ["name"])
    op.create_index(
        "idx_user_daily_comments_user_date", "user_daily_comments", ["user_id", "date"]
    )
    # posts partial unique on payment_tx_hash
    op.execute(
        "CREATE UNIQUE INDEX idx_posts_payment_tx_hash "
        "ON posts(payment_tx_hash) WHERE payment_tx_hash IS NOT NULL"
    )
    # scam tracker
    op.create_index("idx_scam_wallet", "scam_reports", ["scam_wallet_address"])
    op.create_index("idx_scam_type", "scam_reports", ["scam_type"])
    op.create_index("idx_scam_status", "scam_reports", ["verification_status"])
    op.create_index("idx_scam_created", "scam_reports", [sa.text("created_at DESC")])
    op.create_index("idx_vote_report", "scam_report_votes", ["report_id"])
    op.create_index("idx_vote_user", "scam_report_votes", ["user_id"])
    op.create_index("idx_comment_report", "scam_report_comments", ["report_id"])
    op.create_index(
        "idx_comment_created", "scam_report_comments", [sa.text("created_at DESC")]
    )
    # governance
    op.create_index("idx_content_reports_status", "content_reports", ["review_status"])
    op.create_index(
        "idx_content_reports_reporter", "content_reports", ["reporter_user_id"]
    )
    op.create_index(
        "idx_content_reports_content", "content_reports", ["content_type", "content_id"]
    )
    op.create_index(
        "idx_content_reports_created", "content_reports", [sa.text("created_at DESC")]
    )
    op.create_index(
        "idx_report_review_votes_report", "report_review_votes", ["report_id"]
    )
    op.create_index("idx_user_violations_user", "user_violations", ["user_id"])
    op.create_index("idx_user_activity_logs_user", "user_activity_logs", ["user_id"])
    op.create_index(
        "idx_user_activity_logs_type", "user_activity_logs", ["activity_type"]
    )
    # friendships
    op.create_index("idx_friendships_user_id", "friendships", ["user_id"])
    op.create_index("idx_friendships_friend_id", "friendships", ["friend_id"])
    op.create_index("idx_friendships_status", "friendships", ["status"])
    # direct messages
    op.create_index("idx_dm_conversations_user1", "dm_conversations", ["user1_id"])
    op.create_index("idx_dm_conversations_user2", "dm_conversations", ["user2_id"])
    op.create_index(
        "idx_dm_conversations_last_message",
        "dm_conversations",
        [sa.text("last_message_at DESC")],
    )
    op.create_index("idx_dm_messages_conversation", "dm_messages", ["conversation_id"])
    op.create_index(
        "idx_dm_messages_created", "dm_messages", [sa.text("created_at DESC")]
    )
    op.create_index("idx_dm_messages_from_user", "dm_messages", ["from_user_id"])
    op.create_index("idx_dm_messages_to_user", "dm_messages", ["to_user_id"])
    op.create_index(
        "idx_dm_messages_conversation_created",
        "dm_messages",
        ["conversation_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_user_message_limits", "user_message_limits", ["user_id", "date"]
    )
    # audit logs
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index(
        "idx_audit_logs_timestamp", "audit_logs", [sa.text("timestamp DESC")]
    )
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_endpoint", "audit_logs", ["endpoint"])
    # analysis reports
    op.create_index("idx_analysis_reports_session", "analysis_reports", ["session_id"])
    op.create_index("idx_analysis_reports_user", "analysis_reports", ["user_id"])
    # price alerts
    op.create_index("idx_price_alerts_user", "price_alerts", ["user_id"])
    op.execute(
        "CREATE INDEX idx_price_alerts_active ON price_alerts(triggered) WHERE triggered = 0"
    )
    # tool system
    op.create_index("idx_tools_catalog_category", "tools_catalog", ["category"])
    op.create_index("idx_tools_catalog_tier", "tools_catalog", ["tier_required"])
    op.create_index("idx_agent_tool_agent", "agent_tool_permissions", ["agent_id"])
    op.create_index("idx_user_tool_prefs_user", "user_tool_preferences", ["user_id"])
    op.create_index(
        "idx_tool_usage_user_date", "tool_usage_log", ["user_id", "used_date"]
    )
    # memory system
    op.create_index("idx_user_memory_user", "user_memory", ["user_id"])
    op.create_index("idx_user_memory_session", "user_memory", ["session_id"])
    op.create_index("idx_user_memory_type", "user_memory", ["memory_type"])
    op.create_index("idx_user_history_user", "user_history_log", ["user_id"])
    op.create_index("idx_user_history_session", "user_history_log", ["session_id"])
    op.create_index(
        "idx_user_history_created", "user_history_log", [sa.text("created_at DESC")]
    )
    # user facts
    op.create_index("idx_user_facts_user", "user_facts", ["user_id"])
    # notifications
    op.create_index(
        "idx_notifications_user_created",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
    )
    op.execute(
        "CREATE INDEX idx_notifications_user_unread ON notifications(user_id) WHERE is_read = FALSE"
    )
    # task experiences
    op.create_index(
        "idx_te_user_family", "task_experiences", ["user_id", "task_family"]
    )
    op.create_index("idx_te_created", "task_experiences", [sa.text("created_at DESC")])
    op.execute("CREATE INDEX idx_te_tsv ON task_experiences USING GIN(query_tsv)")


def downgrade() -> None:
    # ── indexes ───────────────────────────────────────────────────
    op.drop_index("idx_te_tsv", table_name="task_experiences")
    op.drop_index("idx_te_created", table_name="task_experiences")
    op.drop_index("idx_te_user_family", table_name="task_experiences")
    op.drop_index("idx_notifications_user_unread", table_name="notifications")
    op.drop_index("idx_notifications_user_created", table_name="notifications")
    op.drop_index("idx_user_facts_user", table_name="user_facts")
    op.drop_index("idx_user_history_created", table_name="user_history_log")
    op.drop_index("idx_user_history_session", table_name="user_history_log")
    op.drop_index("idx_user_history_user", table_name="user_history_log")
    op.drop_index("idx_user_memory_type", table_name="user_memory")
    op.drop_index("idx_user_memory_session", table_name="user_memory")
    op.drop_index("idx_user_memory_user", table_name="user_memory")
    op.drop_index("idx_tool_usage_user_date", table_name="tool_usage_log")
    op.drop_index("idx_user_tool_prefs_user", table_name="user_tool_preferences")
    op.drop_index("idx_agent_tool_agent", table_name="agent_tool_permissions")
    op.drop_index("idx_tools_catalog_tier", table_name="tools_catalog")
    op.drop_index("idx_tools_catalog_category", table_name="tools_catalog")
    op.drop_index("idx_price_alerts_active", table_name="price_alerts")
    op.drop_index("idx_price_alerts_user", table_name="price_alerts")
    op.drop_index("idx_analysis_reports_user", table_name="analysis_reports")
    op.drop_index("idx_analysis_reports_session", table_name="analysis_reports")
    op.drop_index("idx_audit_logs_endpoint", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("idx_user_message_limits", table_name="user_message_limits")
    op.drop_index("idx_dm_messages_conversation_created", table_name="dm_messages")
    op.drop_index("idx_dm_messages_to_user", table_name="dm_messages")
    op.drop_index("idx_dm_messages_from_user", table_name="dm_messages")
    op.drop_index("idx_dm_messages_created", table_name="dm_messages")
    op.drop_index("idx_dm_messages_conversation", table_name="dm_messages")
    op.drop_index("idx_dm_conversations_last_message", table_name="dm_conversations")
    op.drop_index("idx_dm_conversations_user2", table_name="dm_conversations")
    op.drop_index("idx_dm_conversations_user1", table_name="dm_conversations")
    op.drop_index("idx_friendships_status", table_name="friendships")
    op.drop_index("idx_friendships_friend_id", table_name="friendships")
    op.drop_index("idx_friendships_user_id", table_name="friendships")
    op.drop_index("idx_user_activity_logs_type", table_name="user_activity_logs")
    op.drop_index("idx_user_activity_logs_user", table_name="user_activity_logs")
    op.drop_index("idx_user_violations_user", table_name="user_violations")
    op.drop_index("idx_report_review_votes_report", table_name="report_review_votes")
    op.drop_index("idx_content_reports_created", table_name="content_reports")
    op.drop_index("idx_content_reports_content", table_name="content_reports")
    op.drop_index("idx_content_reports_reporter", table_name="content_reports")
    op.drop_index("idx_content_reports_status", table_name="content_reports")
    op.drop_index("idx_comment_created", table_name="scam_report_comments")
    op.drop_index("idx_comment_report", table_name="scam_report_comments")
    op.drop_index("idx_vote_user", table_name="scam_report_votes")
    op.drop_index("idx_vote_report", table_name="scam_report_votes")
    op.drop_index("idx_scam_created", table_name="scam_reports")
    op.drop_index("idx_scam_status", table_name="scam_reports")
    op.drop_index("idx_scam_type", table_name="scam_reports")
    op.drop_index("idx_scam_wallet", table_name="scam_reports")
    op.drop_index("idx_posts_payment_tx_hash", table_name="posts")
    op.drop_index("idx_user_daily_comments_user_date", table_name="user_daily_comments")
    op.drop_index("idx_tags_name", table_name="tags")
    op.drop_index("idx_tips_to_user", table_name="tips")
    op.drop_index("idx_tips_from_user", table_name="tips")
    op.drop_index("idx_tips_post_id", table_name="tips")
    op.drop_index("idx_forum_comments_user_id", table_name="forum_comments")
    op.drop_index("idx_forum_comments_post_id", table_name="forum_comments")
    op.drop_index("idx_posts_category", table_name="posts")
    op.drop_index("idx_posts_created_at", table_name="posts")
    op.drop_index("idx_posts_user_id", table_name="posts")
    op.drop_index("idx_posts_board_id", table_name="posts")
    op.drop_index("idx_user_api_keys_user", table_name="user_api_keys")
    op.drop_index("idx_membership_payments_user", table_name="membership_payments")
    op.drop_index("idx_users_membership", table_name="users")
    op.drop_index("idx_users_last_active", table_name="users")
    op.drop_index("idx_sessions_updated_at", table_name="sessions")
    op.drop_index("idx_sessions_user_id", table_name="sessions")
    op.drop_index(
        "idx_conversation_history_session_timestamp", table_name="conversation_history"
    )

    # ── tables (reverse dependency order) ─────────────────────────
    op.execute("DROP TABLE IF EXISTS task_experiences CASCADE")
    op.drop_table("notifications")
    op.drop_table("user_facts")
    op.drop_table("user_memory_cache")
    op.drop_table("user_history_log")
    op.drop_table("user_memory")
    op.drop_table("tool_usage_log")
    op.drop_table("user_tool_preferences")
    op.drop_table("agent_tool_permissions")
    op.drop_table("tools_catalog")
    op.drop_table("price_alerts")
    op.drop_table("analysis_reports")
    op.drop_table("user_activity_logs")
    op.drop_table("audit_reputation")
    op.drop_table("user_violation_points")
    op.drop_table("user_violations")
    op.drop_table("report_review_votes")
    op.drop_table("content_reports")
    op.drop_table("audit_logs")
    op.drop_table("user_message_limits")
    op.drop_table("dm_message_deletions")
    op.drop_table("dm_messages")
    op.drop_table("dm_conversations")
    op.drop_table("friendships")
    op.drop_table("scam_report_comments")
    op.drop_table("scam_report_votes")
    op.drop_table("scam_reports")
    op.drop_table("user_daily_posts")
    op.drop_table("user_daily_comments")
    op.drop_table("post_tags")
    op.drop_table("tags")
    op.drop_table("tips")
    op.drop_table("forum_comments")
    op.drop_table("posts")
    op.drop_table("boards")
    op.drop_table("user_api_keys")
    op.drop_table("admin_broadcasts")
    op.drop_table("membership_payments")
    op.drop_table("sessions")
    op.drop_table("conversation_history")
    op.drop_table("system_config")
    op.drop_table("system_cache")
    op.drop_table("watchlist")
    op.drop_table("users")
