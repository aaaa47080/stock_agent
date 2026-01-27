"""
資料庫連接管理和初始化
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user_data.db")

# 追蹤資料庫是否已初始化
_db_initialized = False


def get_connection() -> sqlite3.Connection:
    """
    獲取資料庫連接，確保資料庫和表存在
    如果資料庫文件被刪除，會自動重新初始化
    """
    global _db_initialized

    # 如果資料庫文件不存在，需要重新初始化
    if not os.path.exists(DB_PATH):
        _db_initialized = False

    # 如果尚未初始化，執行初始化
    if not _db_initialized:
        init_db()
        _db_initialized = True

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化資料庫 - 建立所有資料表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ========================================================================
    # 基礎資料表
    # ========================================================================

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
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========================================================================
    # 系統配置資料表 (商用化配置管理)
    # ========================================================================

    # 建立系統配置表 (System Config)
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT DEFAULT 'string',
            category TEXT DEFAULT 'general',
            description TEXT,
            is_public INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========================================================================
    # 對話相關資料表
    # ========================================================================

    # 建立對話歷史表 (Conversation History)
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT DEFAULT 'default',
            user_id TEXT DEFAULT 'local_user',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========================================================================
    # 用戶相關資料表
    # ========================================================================

    # 建立用戶表 (Users)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            email TEXT UNIQUE,
            auth_method TEXT DEFAULT 'password',
            pi_uid TEXT UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 建立會員支付記錄表 (Membership Payments)
    c.execute('''
        CREATE TABLE IF NOT EXISTS membership_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            months INTEGER NOT NULL,
            tx_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 遷移：為舊表添加新欄位
    try:
        c.execute('ALTER TABLE users ADD COLUMN auth_method TEXT DEFAULT "password"')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN pi_uid TEXT UNIQUE')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN pi_username TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN last_active_at TIMESTAMP')
    except sqlite3.OperationalError:
        pass

    # 建立密碼重置 Token 表
    c.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 建立登入嘗試記錄表 (防暴力破解)
    c.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT,
            attempt_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
    ''')

    # Migration for existing sessions table
    try:
        c.execute('ALTER TABLE sessions ADD COLUMN is_pinned INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    # ========================================================================
    # 論壇相關資料表
    # ========================================================================

    # 看板表
    c.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            date            DATE NOT NULL,
            post_count      INTEGER DEFAULT 0,

            UNIQUE (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # ========================================================================
    # 好友功能資料表
    # ========================================================================

    # 好友關係表
    c.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # ========================================================================
    # 私訊功能資料表
    # ========================================================================

    # 對話表（兩人之間的對話）
    c.execute('''
        CREATE TABLE IF NOT EXISTS dm_conversations (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # 用戶訊息限制追蹤表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_message_limits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            date            DATE NOT NULL,
            message_count   INTEGER DEFAULT 0,
            greeting_count  INTEGER DEFAULT 0,
            greeting_month  TEXT,

            UNIQUE (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Migration: 為 users 表添加會員等級欄位
    try:
        c.execute('ALTER TABLE users ADD COLUMN membership_tier TEXT DEFAULT "free"')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN membership_expires_at TIMESTAMP')
    except sqlite3.OperationalError:
        pass

    # 初始化預設看板（如果不存在）
    c.execute('SELECT COUNT(*) FROM boards WHERE slug = "crypto"')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO boards (name, slug, description, is_active)
            VALUES ('加密貨幣', 'crypto', '加密貨幣相關討論', 1)
        ''')

    # 初始化系統配置（如果不存在）
    # 從 core/config.py 獲取預設值
    from core.config import PI_PAYMENT_PRICES, FORUM_LIMITS

    default_configs = [
        # 價格配置
        ('price_create_post', str(PI_PAYMENT_PRICES.get('create_post', 1.0)), 'float', 'pricing', '發文費用 (Pi)', 1),
        ('price_tip', str(PI_PAYMENT_PRICES.get('tip', 1.0)), 'float', 'pricing', '打賞費用 (Pi)', 1),
        ('price_premium', str(PI_PAYMENT_PRICES.get('premium', 1.0)), 'float', 'pricing', '高級會員費用 (Pi)', 1),
        # 論壇限制配置
        ('limit_daily_post_free', str(FORUM_LIMITS.get('daily_post_free', 3)), 'int', 'limits', '一般會員每日發文上限', 1),
        ('limit_daily_post_premium', 'null', 'int', 'limits', '高級會員每日發文上限 (null=無限)', 1),
        ('limit_daily_comment_free', str(FORUM_LIMITS.get('daily_comment_free', 20)), 'int', 'limits', '一般會員每日回覆上限', 1),
        ('limit_daily_comment_premium', 'null', 'int', 'limits', '高級會員每日回覆上限 (null=無限)', 1),
        # 私訊限制配置
        ('limit_daily_message_free', '20', 'int', 'limits', '一般會員每日私訊上限', 1),
        ('limit_daily_message_premium', 'null', 'int', 'limits', '高級會員每日私訊上限 (null=無限)', 1),
        ('limit_monthly_greeting', '5', 'int', 'limits', '高級會員每月打招呼上限', 1),
        ('limit_message_max_length', '500', 'int', 'limits', '單則訊息最大字數', 1),
    ]

    for key, value, value_type, category, description, is_public in default_configs:
        c.execute('SELECT COUNT(*) FROM system_config WHERE key = ?', (key,))
        if c.fetchone()[0] == 0:
            c.execute('''
                INSERT INTO system_config (key, value, value_type, category, description, is_public)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (key, value, value_type, category, description, is_public))

    # ========================================================================
    # 索引
    # ========================================================================
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
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_message_limits ON user_message_limits(user_id, date)')

    conn.commit()
    conn.close()


# 模組載入時初始化資料庫
init_db()
