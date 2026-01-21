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

    # 建立預測記錄表 (Social Trading)
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            entry_price REAL,
            status TEXT DEFAULT 'PENDING',
            final_pnl_pct REAL DEFAULT 0.0
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

    conn.commit()
    conn.close()


# 模組載入時初始化資料庫
init_db()
