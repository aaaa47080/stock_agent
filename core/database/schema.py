"""
Database Schema Definitions
Contains all DDL statements for table creation
"""
import json


def create_basic_tables(c):
    """Create basic tables (watchlist, system_cache, system_config)"""
    # 建立自選清單資料表
    c.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id TEXT,
            symbol TEXT,
            PRIMARY KEY (user_id, symbol)
        )
    ''')

    # 建立系統快取表 (System Cache)
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_cache (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 建立系統配置表 (System Config)
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT DEFAULT 'string',
            category TEXT DEFAULT 'general',
            description TEXT,
            is_public INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def create_conversation_tables(c):
    """Create conversation tables (conversation_history, sessions)"""
    # 建立對話歷史表 (Conversation History)
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id SERIAL PRIMARY KEY,
            session_id TEXT DEFAULT 'default',
            user_id TEXT DEFAULT 'local_user',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    ''')

    # 建立對話會話表 (Sessions)
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'local_user',
            title TEXT,
            is_pinned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def create_user_tables(c):
    """Create user-related tables (users, membership_payments, admin_broadcasts, login_attempts)"""
    # 建立用戶表 (Users)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            email TEXT UNIQUE,
            auth_method TEXT DEFAULT 'password',
            pi_uid TEXT UNIQUE,
            pi_username TEXT,
            last_active_at TIMESTAMP,
            membership_tier TEXT DEFAULT 'free',
            membership_expires_at TIMESTAMP,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration: add role and is_active columns if missing
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")

    # 建立會員支付記錄表 (Membership Payments)
    c.execute('''
        CREATE TABLE IF NOT EXISTS membership_payments (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            months INTEGER NOT NULL,
            tx_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 管理員廣播紀錄表 (Admin Broadcasts)
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_broadcasts (
            id SERIAL PRIMARY KEY,
            admin_user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            type TEXT DEFAULT 'announcement',
            recipient_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    # 建立登入嘗試記錄表 (防暴力破解)
    c.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            ip_address TEXT,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
    ''')

    # 建立用戶 API Keys 表 (BYOK - Bring Your Own Key)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_api_keys (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            encrypted_key TEXT NOT NULL,
            model_selection TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP,
            UNIQUE(user_id, provider),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    ''')


def create_forum_tables(c):
    """Create forum-related tables (boards, posts, forum_comments, tips, tags, post_tags, daily counts)"""
    # 看板表
    c.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id              SERIAL PRIMARY KEY,
            name            TEXT NOT NULL,
            slug            TEXT NOT NULL UNIQUE,
            description     TEXT,
            post_count      INTEGER DEFAULT 0,
            is_active       INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 文章表
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id              SERIAL PRIMARY KEY,
            board_id        INTEGER NOT NULL,
            user_id         TEXT NOT NULL,
            category        TEXT NOT NULL,
            title           TEXT NOT NULL,
            content         TEXT NOT NULL,
            tags            TEXT,

            push_count      INTEGER DEFAULT 0,
            boo_count       INTEGER DEFAULT 0,
            comment_count   INTEGER DEFAULT 0,
            tips_total      REAL DEFAULT 0,
            view_count      INTEGER DEFAULT 0,

            payment_tx_hash TEXT,

            is_pinned       INTEGER DEFAULT 0,
            is_hidden       INTEGER DEFAULT 0,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (board_id) REFERENCES boards(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 回覆表
    c.execute('''
        CREATE TABLE IF NOT EXISTS forum_comments (
            id              SERIAL PRIMARY KEY,
            post_id         INTEGER NOT NULL,
            user_id         TEXT NOT NULL,
            parent_id       INTEGER,
            type            TEXT NOT NULL,
            content         TEXT,

            is_hidden       INTEGER DEFAULT 0,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (parent_id) REFERENCES forum_comments(id)
        )
    ''')

    # 打賞記錄表
    c.execute('''
        CREATE TABLE IF NOT EXISTS tips (
            id              SERIAL PRIMARY KEY,
            post_id         INTEGER NOT NULL,
            from_user_id    TEXT NOT NULL,
            to_user_id      TEXT NOT NULL,
            amount          REAL NOT NULL DEFAULT 1,
            tx_hash         TEXT NOT NULL,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (from_user_id) REFERENCES users(user_id),
            FOREIGN KEY (to_user_id) REFERENCES users(user_id)
        )
    ''')

    # 標籤統計表
    c.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id              SERIAL PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE,
            post_count      INTEGER DEFAULT 0,
            last_used_at    TIMESTAMP,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 文章標籤關聯表
    c.execute('''
        CREATE TABLE IF NOT EXISTS post_tags (
            post_id         INTEGER NOT NULL,
            tag_id          INTEGER NOT NULL,

            PRIMARY KEY (post_id, tag_id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
    ''')

    # 用戶每日回覆計數表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_daily_comments (
            id              SERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            date            DATE NOT NULL,
            comment_count   INTEGER DEFAULT 0,

            UNIQUE (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 用戶每日發文計數表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_daily_posts (
            id              SERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            date            DATE NOT NULL,
            post_count      INTEGER DEFAULT 0,

            UNIQUE (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')


def create_scam_tracker_tables(c):
    """Create scam tracker tables (scam_reports, votes, comments)"""
    # 詐騙舉報表
    c.execute('''
        CREATE TABLE IF NOT EXISTS scam_reports (
            id SERIAL PRIMARY KEY,

            -- 錢包資訊
            scam_wallet_address TEXT NOT NULL UNIQUE,
            blockchain_type TEXT DEFAULT 'pi_network',

            -- 舉報者資訊
            reporter_user_id TEXT NOT NULL,
            reporter_wallet_address TEXT NOT NULL,
            reporter_wallet_masked TEXT NOT NULL,

            -- 詐騙資訊
            scam_type TEXT NOT NULL,
            description TEXT NOT NULL,
            transaction_hash TEXT,

            -- 驗證狀態
            verification_status TEXT DEFAULT 'pending',

            -- 社群投票統計
            approve_count INTEGER DEFAULT 0,
            reject_count INTEGER DEFAULT 0,

            -- 元數據
            comment_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,

            -- 時間戳
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- 外鍵
            FOREIGN KEY (reporter_user_id) REFERENCES users(user_id)
        )
    ''')

    # 投票表
    c.execute('''
        CREATE TABLE IF NOT EXISTS scam_report_votes (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            vote_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(report_id, user_id),
            FOREIGN KEY (report_id) REFERENCES scam_reports(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 評論表
    c.execute('''
        CREATE TABLE IF NOT EXISTS scam_report_comments (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            transaction_hash TEXT,
            is_hidden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (report_id) REFERENCES scam_reports(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Migration: drop unused columns
    c.execute("ALTER TABLE scam_report_comments DROP COLUMN IF EXISTS attachment_url")


def create_friendship_tables(c):
    """Create friendship tables"""
    # 好友關係表
    c.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            id              SERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            friend_id       TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (friend_id) REFERENCES users(user_id),
            UNIQUE (user_id, friend_id)
        )
    ''')


def create_dm_tables(c):
    """Create direct message tables"""
    # 對話表（兩人之間的對話）
    c.execute('''
        CREATE TABLE IF NOT EXISTS dm_conversations (
            id                  SERIAL PRIMARY KEY,
            user1_id            TEXT NOT NULL,
            user2_id            TEXT NOT NULL,
            last_message_id     INTEGER,
            last_message_at     TIMESTAMP,
            user1_unread_count  INTEGER DEFAULT 0,
            user2_unread_count  INTEGER DEFAULT 0,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (user1_id, user2_id),
            FOREIGN KEY (user1_id) REFERENCES users(user_id),
            FOREIGN KEY (user2_id) REFERENCES users(user_id)
        )
    ''')

    # 私訊訊息表
    c.execute('''
        CREATE TABLE IF NOT EXISTS dm_messages (
            id              SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            from_user_id    TEXT NOT NULL,
            to_user_id      TEXT NOT NULL,
            content         TEXT NOT NULL,
            message_type    TEXT DEFAULT 'text',
            is_read         INTEGER DEFAULT 0,
            read_at         TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (conversation_id) REFERENCES dm_conversations(id),
            FOREIGN KEY (from_user_id) REFERENCES users(user_id),
            FOREIGN KEY (to_user_id) REFERENCES users(user_id)
        )
    ''')

    # 私訊刪除記錄表（只對自己隱藏，不影響對方）
    c.execute('''
        CREATE TABLE IF NOT EXISTS dm_message_deletions (
            id              SERIAL PRIMARY KEY,
            message_id      INTEGER NOT NULL,
            user_id         TEXT NOT NULL,
            deleted_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (message_id, user_id),
            FOREIGN KEY (message_id) REFERENCES dm_messages(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 用戶訊息限制追蹤表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_message_limits (
            id              SERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            date            DATE NOT NULL,
            message_count   INTEGER DEFAULT 0,
            greeting_count  INTEGER DEFAULT 0,
            greeting_month  TEXT,

            UNIQUE (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')


def create_audit_log_tables(c):
    """Create audit log tables"""
    # 審計日誌主表 - 記錄所有安全敏感操作
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            -- User information
            user_id VARCHAR(255),
            username VARCHAR(255),

            -- Action details
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id VARCHAR(255),

            -- Request details
            endpoint VARCHAR(255) NOT NULL,
            method VARCHAR(10) NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,

            -- Request/Response data
            request_data JSONB,
            response_code INTEGER,

            -- Status
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT,

            -- Performance
            duration_ms INTEGER,

            -- Additional metadata
            metadata JSONB,

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    ''')

    # 審計日誌索引 - 優化查詢性能
    c.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_endpoint ON audit_logs(endpoint)')


def create_governance_tables(c):
    """Create community governance tables"""
    # 內容檢舉表
    c.execute('''
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
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    # 檢舉審核投票表
    c.execute('''
        CREATE TABLE IF NOT EXISTS report_review_votes (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL REFERENCES content_reports(id),
            reviewer_user_id VARCHAR(255) NOT NULL,
            vote_type VARCHAR(20) NOT NULL,
            vote_weight FLOAT DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(report_id, reviewer_user_id)
        )
    ''')

    # 用戶違規記錄表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_violations (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            violation_level VARCHAR(20) NOT NULL,
            violation_type VARCHAR(50),
            points INTEGER DEFAULT 0,
            source_type VARCHAR(20),
            source_id INTEGER,
            action_taken VARCHAR(50),
            suspended_until TIMESTAMP,
            processed_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    # 用戶違規點數表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_violation_points (
            user_id VARCHAR(255) PRIMARY KEY,
            points INTEGER DEFAULT 0,
            total_violations INTEGER DEFAULT 0,
            last_violation_at TIMESTAMP,
            suspension_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    # 審核信譽表
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_reputation (
            user_id VARCHAR(255) PRIMARY KEY,
            total_reviews INTEGER DEFAULT 0,
            correct_votes INTEGER DEFAULT 0,
            accuracy_rate FLOAT DEFAULT 0.0,
            reputation_score INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    # 用戶活動日誌表
    c.execute('''
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
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')


def create_analysis_tables(c):
    """Create analysis report tables"""
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis_reports (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(255),
            user_id VARCHAR(255),
            symbol VARCHAR(50),
            interval VARCHAR(10) DEFAULT '1d',
            report_text TEXT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_analysis_reports_session ON analysis_reports(session_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_analysis_reports_user ON analysis_reports(user_id)')


def create_tool_tables(c):
    """Create tool system tables"""
    # 工具目錄：所有可用工具的 Metadata
    c.execute('''
        CREATE TABLE IF NOT EXISTS tools_catalog (
            tool_id          TEXT PRIMARY KEY,
            display_name     TEXT NOT NULL,
            description      TEXT,
            category         TEXT NOT NULL,
            tier_required    TEXT DEFAULT 'free',
            quota_type       TEXT DEFAULT 'unlimited',
            daily_limit_free INTEGER DEFAULT 0,
            daily_limit_plus INTEGER,
            daily_limit_prem INTEGER,
            source_type      TEXT DEFAULT 'native',
            is_active        BOOLEAN DEFAULT TRUE,
            created_at       TIMESTAMP DEFAULT NOW()
        )
    ''')
    c.execute("ALTER TABLE tools_catalog ADD COLUMN IF NOT EXISTS daily_limit_plus INTEGER")

    # Agent 可用工具設定（Admin 層控制）
    c.execute('''
        CREATE TABLE IF NOT EXISTS agent_tool_permissions (
            agent_id    TEXT NOT NULL,
            tool_id     TEXT NOT NULL,
            is_enabled  BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (agent_id, tool_id)
        )
    ''')

    # 用戶工具偏好（用戶層個人化，Premium 才可改）
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_tool_preferences (
            user_id     TEXT NOT NULL,
            tool_id     TEXT NOT NULL,
            is_enabled  BOOLEAN DEFAULT TRUE,
            updated_at  TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (user_id, tool_id)
        )
    ''')

    # 工具每日使用量追蹤（Rate Limiting）
    c.execute('''
        CREATE TABLE IF NOT EXISTS tool_usage_log (
            user_id     TEXT NOT NULL,
            tool_id     TEXT NOT NULL,
            used_date   DATE NOT NULL DEFAULT CURRENT_DATE,
            call_count  INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, tool_id, used_date)
        )
    ''')


def create_indexes(c):
    """Create all indexes for optimization"""
    # AI 對話歷史索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_conversation_history_session_timestamp ON conversation_history(session_id, timestamp)')
    # ✅ 效能修復：sessions 表缺少 user_id index，導致 get_sessions() 全表掃描
    c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)')
    # ✅ 效能修復：users 表常用查詢欄位補 index
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_membership ON users(membership_tier)')
    # ✅ 效能修復：membership_payments 補 user_id index
    c.execute('CREATE INDEX IF NOT EXISTS idx_membership_payments_user ON membership_payments(user_id)')
    # ✅ 效能修復：login_attempts 補 username + attempt_time index（表結構沒有 user_id 和 created_at）
    c.execute('CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(attempt_time DESC)')
    # ✅ user_api_keys 索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_api_keys_user ON user_api_keys(user_id)')

    # 論壇索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_board_id ON posts(board_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_forum_comments_post_id ON forum_comments(post_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_forum_comments_user_id ON forum_comments(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tips_post_id ON tips(post_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tips_from_user ON tips(from_user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tips_to_user ON tips(to_user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_daily_comments_user_date ON user_daily_comments(user_id, date)')

    # 可疑錢包追蹤系統索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_scam_wallet ON scam_reports(scam_wallet_address)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_scam_type ON scam_reports(scam_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_scam_status ON scam_reports(verification_status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_scam_created ON scam_reports(created_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vote_report ON scam_report_votes(report_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vote_user ON scam_report_votes(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_comment_report ON scam_report_comments(report_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_comment_created ON scam_report_comments(created_at DESC)')

    # 社群治理系統索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_content_reports_status ON content_reports(review_status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_content_reports_reporter ON content_reports(reporter_user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_content_reports_content ON content_reports(content_type, content_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_content_reports_created ON content_reports(created_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_report_review_votes_report ON report_review_votes(report_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_violations_user ON user_violations(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_logs_user ON user_activity_logs(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_logs_type ON user_activity_logs(activity_type)')

    # 好友功能索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_friendships_user_id ON friendships(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_friendships_friend_id ON friendships(friend_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships(status)')

    # 私訊功能索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_conversations_user1 ON dm_conversations(user1_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_conversations_user2 ON dm_conversations(user2_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_conversations_last_message ON dm_conversations(last_message_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_conversation ON dm_messages(conversation_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_created ON dm_messages(created_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_from_user ON dm_messages(from_user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_to_user ON dm_messages(to_user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_conversation_created ON dm_messages(conversation_id, created_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_message_limits ON user_message_limits(user_id, date)')

    # 工具系統索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_tools_catalog_category ON tools_catalog(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tools_catalog_tier ON tools_catalog(tier_required)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_agent_tool_agent ON agent_tool_permissions(agent_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_tool_prefs_user ON user_tool_preferences(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tool_usage_user_date ON tool_usage_log(user_id, used_date)')

    # 記憶系統索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_memory_user ON user_memory(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_memory_session ON user_memory(session_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_memory_type ON user_memory(memory_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_history_user ON user_history_log(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_history_session ON user_history_log(session_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_history_created ON user_history_log(created_at DESC)')


def init_default_data(c):
    """Initialize default data (boards, system config)"""
    from core.config import PI_PAYMENT_PRICES, FORUM_LIMITS

    # 初始化預設看板（如果不存在）
    c.execute("SELECT COUNT(*) FROM boards WHERE slug = 'crypto'")
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO boards (name, slug, description, is_active)
            VALUES ('加密貨幣', 'crypto', '加密貨幣相關討論', 1)
        ''')

    # 初始化系統配置（如果不存在）
    default_configs = [
        # 價格配置
        ('price_create_post', str(PI_PAYMENT_PRICES.get('create_post', 1.0)), 'float', 'pricing', '發文費用 (Pi)', 1),
        ('price_tip', str(PI_PAYMENT_PRICES.get('tip', 1.0)), 'float', 'pricing', '打賞費用 (Pi)', 1),
        ('price_premium', str(PI_PAYMENT_PRICES.get('premium', 1.0)), 'float', 'pricing', 'Premium 會員費用 (Pi)', 1),
        # 論壇限制配置
        ('limit_daily_post_free', str(FORUM_LIMITS.get('daily_post_free', 3)), 'int', 'limits', '一般會員每日發文上限', 1),
        ('limit_daily_post_premium', 'null', 'int', 'limits', 'Premium 會員每日發文上限 (null=無限)', 1),
        ('limit_daily_comment_free', str(FORUM_LIMITS.get('daily_comment_free', 20)), 'int', 'limits', '一般會員每日回覆上限', 1),
        ('limit_daily_comment_premium', 'null', 'int', 'limits', 'Premium 會員每日回覆上限 (null=無限)', 1),
        # 私訊限制配置
        ('limit_daily_message_free', '20', 'int', 'limits', '一般會員每日私訊上限', 1),
        ('limit_daily_message_premium', 'null', 'int', 'limits', 'Premium 會員每日私訊上限 (null=無限)', 1),
        ('limit_monthly_greeting', '5', 'int', 'limits', 'Premium 會員每月打招呼上限', 1),
        ('limit_message_max_length', '500', 'int', 'limits', '單則訊息最大字數', 1),
        # 可疑錢包追蹤配置
        ('scam_report_daily_limit_pro', '5', 'int', 'scam_tracker', 'Premium 用戶每日可舉報可疑錢包數量', 1),
        ('scam_comment_require_pro', 'true', 'bool', 'scam_tracker', '評論是否僅限 Premium 用戶', 1),
        ('scam_verification_vote_threshold', '10', 'int', 'scam_tracker', '達到「已驗證」所需的最低總投票數', 1),
        ('scam_verification_approve_rate', '0.7', 'float', 'scam_tracker', '達到「已驗證」所需的贊同率（0-1）', 1),
        ('scam_wallet_mask_length', '4', 'int', 'scam_tracker', '錢包地址遮罩顯示長度（前後各保留字符數）', 1),
        ('scam_list_page_size', '20', 'int', 'scam_tracker', '列表每頁顯示數量', 1),
    ]

    # 詐騙類型配置（JSON）
    scam_types_config = json.dumps([
        {'id': 'fake_official', 'name': '假冒官方', 'icon': '🎭'},
        {'id': 'investment_scam', 'name': '投資詐騙', 'icon': '💰'},
        {'id': 'fake_airdrop', 'name': '空投詐騙', 'icon': '🎁'},
        {'id': 'trading_fraud', 'name': '交易詐騙', 'icon': '🔄'},
        {'id': 'gambling', 'name': '賭博騙局', 'icon': '🎰'},
        {'id': 'phishing', 'name': '釣魚網站', 'icon': '🎣'},
        {'id': 'other', 'name': '其他詐騙', 'icon': '⚠️'}
    ], ensure_ascii=False)

    default_configs.append((
        'scam_types', scam_types_config, 'json', 'scam_tracker',
        '詐騙類型列表（可動態新增）', 1
    ))

    for key, value, value_type, category, description, is_public in default_configs:
        c.execute('SELECT COUNT(*) FROM system_config WHERE key = %s', (key,))
        if c.fetchone()[0] == 0:
            c.execute('''
                INSERT INTO system_config (key, value, value_type, category, description, is_public)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (key, value, value_type, category, description, is_public))


def create_memory_tables(c):
    """Create user memory tables for persistent agent memory"""
    # 用戶長期記憶表 (MEMORY.md equivalent)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(255),
            memory_type VARCHAR(20) NOT NULL DEFAULT 'long_term',
            content TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            UNIQUE(user_id, session_id, memory_type)
        )
    ''')

    # 用戶對話歷史日誌表 (HISTORY.md equivalent)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_history_log (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(255),
            entry TEXT NOT NULL,
            tools_used TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    ''')

    # 用戶記憶快取表 (for fast access)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_memory_cache (
            user_id VARCHAR(255) PRIMARY KEY,
            session_id VARCHAR(255),
            long_term_memory TEXT,
            last_consolidated_index INTEGER DEFAULT 0,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    ''')


def create_user_facts_table(c):
    """Create user_facts table for nanoclaw-style structured fact extraction"""
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_facts (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            key VARCHAR(100) NOT NULL,
            value TEXT NOT NULL,
            confidence VARCHAR(10) DEFAULT 'high',
            source_turn INTEGER,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            UNIQUE(user_id, key)
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_facts_user ON user_facts(user_id)')


def create_all_tables(c):
    """Create all database tables"""
    create_basic_tables(c)
    create_conversation_tables(c)
    create_user_tables(c)
    create_forum_tables(c)
    create_scam_tracker_tables(c)
    create_friendship_tables(c)
    create_dm_tables(c)
    create_audit_log_tables(c)
    create_governance_tables(c)
    create_analysis_tables(c)
    create_tool_tables(c)
    create_memory_tables(c)
    create_user_facts_table(c)
    create_indexes(c)
    init_default_data(c)
