"""stamp_existing_tables

Idempotent migration that ensures all tables required by the application exist.

This replaces the broken b001_baseline + b002_content_reports chain.
Those migrations used CREATE TABLE (not IF NOT EXISTS), which failed silently
on production DBs where init_db() already created the tables, leaving
alembic_version stuck at 92a35ecee1cf and causing forum/friends/notifications
to fail with "relation does not exist" errors.

Revision ID: b003_stamp_existing_tables
Revises: 92a35ecee1cf
Create Date: 2026-03-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "b003_stamp_existing_tables"
down_revision: Union[str, Sequence[str], None] = "92a35ecee1cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure all tables exist — idempotent, safe on both fresh and existing DBs."""

    conn = op.get_bind()

    # ── Helper: execute SQL, swallowing "already exists" errors ──────────────
    def safe_exec(sql: str) -> None:
        """Execute DDL, catching duplicate-object errors so this is idempotent."""
        try:
            conn.execute(sa.text(sql))
        except Exception:
            # Roll back the sub-transaction so subsequent statements still work
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT _b003"))
        finally:
            conn.execute(sa.text("SAVEPOINT _b003"))

    conn.execute(sa.text("SAVEPOINT _b003"))

    # ── users ──────────────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            auth_method TEXT DEFAULT 'password',
            pi_uid TEXT UNIQUE,
            pi_username TEXT,
            last_active_at TIMESTAMPTZ,
            membership_tier TEXT DEFAULT 'free',
            membership_expires_at TIMESTAMPTZ,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── basic tables ───────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id TEXT,
            symbol TEXT,
            PRIMARY KEY (user_id, symbol)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS system_cache (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT DEFAULT 'string',
            category TEXT DEFAULT 'general',
            description TEXT,
            is_public INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── conversation tables ────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id SERIAL PRIMARY KEY,
            session_id TEXT DEFAULT 'default',
            user_id TEXT DEFAULT 'local_user',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            metadata TEXT
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'local_user',
            title TEXT,
            is_pinned INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── user payment / admin tables ────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS membership_payments (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount NUMERIC(18,4) NOT NULL,
            months INTEGER NOT NULL,
            tx_hash TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS admin_broadcasts (
            id SERIAL PRIMARY KEY,
            admin_user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            type TEXT DEFAULT 'announcement',
            recipient_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── forum tables ───────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS boards (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            post_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            board_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            push_count INTEGER DEFAULT 0,
            boo_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            tips_total NUMERIC(18,4) DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            payment_tx_hash TEXT,
            is_pinned INTEGER DEFAULT 0,
            is_hidden INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS forum_comments (
            id SERIAL PRIMARY KEY,
            post_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            parent_id INTEGER,
            type TEXT NOT NULL,
            content TEXT,
            is_hidden INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS tips (
            id SERIAL PRIMARY KEY,
            post_id INTEGER NOT NULL,
            from_user_id TEXT NOT NULL,
            to_user_id TEXT NOT NULL,
            amount NUMERIC(18,4) NOT NULL DEFAULT 1,
            tx_hash TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            post_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS post_tags (
            post_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (post_id, tag_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_daily_comments (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            date DATE NOT NULL,
            comment_count INTEGER DEFAULT 0,
            UNIQUE (user_id, date)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_daily_posts (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            date DATE NOT NULL,
            post_count INTEGER DEFAULT 0,
            UNIQUE (user_id, date)
        )
    """)

    # ── scam tracker ───────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS scam_reports (
            id SERIAL PRIMARY KEY,
            scam_wallet_address TEXT UNIQUE NOT NULL,
            reporter_user_id TEXT NOT NULL,
            reporter_wallet_masked TEXT NOT NULL,
            scam_type TEXT NOT NULL,
            description TEXT NOT NULL,
            transaction_hash TEXT,
            verification_status TEXT DEFAULT 'pending',
            approve_count INTEGER DEFAULT 0,
            reject_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS scam_report_votes (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            vote_type TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (report_id, user_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS scam_report_comments (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            transaction_hash TEXT,
            is_hidden INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── friendships ────────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS friendships (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            friend_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, friend_id)
        )
    """)

    # ── direct messages ────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS dm_conversations (
            id SERIAL PRIMARY KEY,
            user1_id TEXT NOT NULL,
            user2_id TEXT NOT NULL,
            last_message_id INTEGER,
            last_message_at TIMESTAMPTZ,
            user1_unread_count INTEGER DEFAULT 0,
            user2_unread_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user1_id, user2_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS dm_messages (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            from_user_id TEXT NOT NULL,
            to_user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            is_read INTEGER DEFAULT 0,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS dm_message_deletions (
            id SERIAL PRIMARY KEY,
            message_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            deleted_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (message_id, user_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_message_limits (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            date DATE NOT NULL,
            message_count INTEGER DEFAULT 0,
            greeting_count INTEGER DEFAULT 0,
            greeting_month TEXT,
            UNIQUE (user_id, date)
        )
    """)

    # ── audit logs ─────────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            user_id VARCHAR(255),
            username VARCHAR(255),
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id VARCHAR(255),
            endpoint VARCHAR(255) NOT NULL,
            method VARCHAR(10) NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            request_data JSONB,
            response_code INTEGER,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT,
            duration_ms INTEGER,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── governance tables ──────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS content_reports (
            id SERIAL PRIMARY KEY,
            content_type VARCHAR(20) NOT NULL,
            content_id INTEGER NOT NULL,
            reporter_user_id VARCHAR(255) NOT NULL,
            report_type VARCHAR(50) NOT NULL,
            description TEXT,
            review_status VARCHAR(20) DEFAULT 'pending',
            violation_level VARCHAR(20),
            approve_count INTEGER DEFAULT 0,
            reject_count INTEGER DEFAULT 0,
            points_assigned INTEGER DEFAULT 0,
            action_taken VARCHAR(50),
            processed_by VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS report_review_votes (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL,
            reviewer_user_id VARCHAR(255) NOT NULL,
            vote_type VARCHAR(20) NOT NULL,
            vote_weight FLOAT DEFAULT 1.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (report_id, reviewer_user_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_violations (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            violation_level VARCHAR(20) NOT NULL,
            violation_type VARCHAR(50),
            points INTEGER DEFAULT 0,
            source_type VARCHAR(20),
            source_id INTEGER,
            action_taken VARCHAR(50),
            suspended_until TIMESTAMPTZ,
            processed_by VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_violation_points (
            user_id VARCHAR(255) PRIMARY KEY,
            points INTEGER DEFAULT 0,
            total_violations INTEGER DEFAULT 0,
            last_violation_at TIMESTAMPTZ,
            suspension_count INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS audit_reputation (
            user_id VARCHAR(255) PRIMARY KEY,
            total_reviews INTEGER DEFAULT 0,
            correct_votes INTEGER DEFAULT 0,
            accuracy_rate FLOAT DEFAULT 0.0,
            reputation_score INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_activity_logs (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            activity_type VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50),
            resource_id INTEGER,
            metadata JSONB,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── analysis / alerts / tools ──────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS analysis_reports (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(255),
            user_id VARCHAR(255),
            symbol VARCHAR(50),
            interval VARCHAR(10) DEFAULT '1d',
            report_text TEXT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            condition TEXT NOT NULL,
            target NUMERIC(18,4) NOT NULL,
            repeat INTEGER NOT NULL DEFAULT 0,
            triggered INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS tools_catalog (
            tool_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            tier_required TEXT DEFAULT 'free',
            quota_type TEXT DEFAULT 'unlimited',
            daily_limit_free INTEGER DEFAULT 0,
            daily_limit_plus INTEGER,
            daily_limit_prem INTEGER,
            source_type TEXT DEFAULT 'native',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS agent_tool_permissions (
            agent_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (agent_id, tool_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_tool_preferences (
            user_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (user_id, tool_id)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS tool_usage_log (
            user_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            used_date DATE NOT NULL DEFAULT CURRENT_DATE,
            call_count INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, tool_id, used_date)
        )
    """)

    # ── memory tables ──────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(255),
            memory_type VARCHAR(20) NOT NULL DEFAULT 'long_term',
            content TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, session_id, memory_type)
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_history_log (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(255),
            entry TEXT NOT NULL,
            tools_used TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_memory_cache (
            user_id VARCHAR(255) PRIMARY KEY,
            session_id VARCHAR(255),
            last_consolidated_index INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_facts (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            key VARCHAR(100) NOT NULL,
            value TEXT NOT NULL,
            confidence VARCHAR(10) DEFAULT 'high',
            source_turn INTEGER,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, key)
        )
    """)

    # ── notifications ──────────────────────────────────────────────────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT,
            body TEXT,
            data JSONB,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # ── task experiences (uses GENERATED column — needs raw execute) ────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS task_experiences (
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

    # ── user_api_keys (should exist from 92a35ecee1cf, ensure it) ────────────
    safe_exec("""
        CREATE TABLE IF NOT EXISTS user_api_keys (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            encrypted_key TEXT NOT NULL,
            model_selection TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_used_at TIMESTAMPTZ,
            UNIQUE (user_id, provider),
            CONSTRAINT fk_user_api_keys_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # ── content_reports: add columns from b002 (IF NOT EXISTS) ─────────────────
    safe_exec("ALTER TABLE content_reports ADD COLUMN IF NOT EXISTS points_assigned INTEGER DEFAULT 0")
    safe_exec("ALTER TABLE content_reports ADD COLUMN IF NOT EXISTS action_taken VARCHAR(50)")
    safe_exec("ALTER TABLE content_reports ADD COLUMN IF NOT EXISTS processed_by VARCHAR(255)")

    # ── Indexes (all IF NOT EXISTS) ─────────────────────────────────────────────
    safe_exec("CREATE INDEX IF NOT EXISTS idx_posts_board_id ON posts(board_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_forum_comments_post_id ON forum_comments(post_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_forum_comments_user_id ON forum_comments(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_tips_post_id ON tips(post_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_tips_from_user ON tips(from_user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_friendships_user_id ON friendships(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_friendships_friend_id ON friendships(friend_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships(status)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_dm_conversations_user1 ON dm_conversations(user1_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_dm_conversations_user2 ON dm_conversations(user2_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_dm_messages_conversation ON dm_messages(conversation_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_dm_messages_from_user ON dm_messages(from_user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at DESC)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id) WHERE is_read = FALSE")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_scam_wallet ON scam_reports(scam_wallet_address)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_scam_type ON scam_reports(scam_type)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_scam_status ON scam_reports(verification_status)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_content_reports_status ON content_reports(review_status)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_content_reports_reporter ON content_reports(reporter_user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_user_violations_user ON user_violations(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_user_activity_logs_user ON user_activity_logs(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_analysis_reports_user ON analysis_reports(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_price_alerts_user ON price_alerts(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_user_api_keys_user ON user_api_keys(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active_at DESC)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_users_membership ON users(membership_tier)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_user_facts_user ON user_facts(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_te_user_family ON task_experiences(user_id, task_family)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_te_created ON task_experiences(created_at DESC)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_user_memory_user ON user_memory(user_id)")
    safe_exec("CREATE INDEX IF NOT EXISTS idx_user_history_user ON user_history_log(user_id)")

    # Release savepoint
    conn.execute(sa.text("RELEASE SAVEPOINT _b003"))


def downgrade() -> None:
    """Downgrade is intentionally a no-op.

    This migration only creates tables IF NOT EXISTS and adds columns IF NOT EXISTS.
    Dropping everything would be destructive and is not safe to automate.
    To rollback, manually drop the tables or restore from a backup.
    """
    pass
