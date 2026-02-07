"""
資料庫連接管理和初始化 (PostgreSQL 版本)
使用線程安全連接池優化記憶體消耗
"""
import psycopg2
from psycopg2 import pool
import os
import threading
import time
import json

# PostgreSQL 連接字符串
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # 嘗試從 .env 讀取 (如果 load_dotenv 未在入口處執行)
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

# 連接池配置 - 針對 Zeabur 優化
MIN_POOL_SIZE = 2   # 最小連接數
MAX_POOL_SIZE = 10  # 最大連接數（平衡並發需求和資源限制）

# 連接獲取配置
MAX_RETRIES = 5          # 重試次數
RETRY_DELAY_BASE = 0.3   # 重試延遲

# 連接參數 - 防止連接超時和斷開
CONNECTION_OPTIONS = {
    'connect_timeout': 10,      # 連接超時 10 秒
    'keepalives': 1,            # 啟用 TCP keepalive
    'keepalives_idle': 30,      # 空閒 30 秒後發送 keepalive
    'keepalives_interval': 10,  # keepalive 間隔 10 秒
    'keepalives_count': 3,      # 3 次失敗後斷開
}

# 全局連接池
_connection_pool = None
_pool_lock = threading.Lock()
_db_initialized = False


class _StandaloneConnection:
    """
    獨立連接包裝類 - 用於繞過連接池直接創建的連接

    當連接池中所有連接都失效時，我們會直接創建新連接。
    這個包裝類確保 close() 時真正關閉連接（而不是歸還到池中）。
    """

    def __init__(self, conn):
        self._conn = conn
        self._closed = False

    def close(self):
        """真正關閉連接"""
        if not self._closed and self._conn:
            try:
                self._conn.rollback()
            except Exception:
                pass
            try:
                self._conn.close()
                self._closed = True
            except Exception as e:
                print(f"⚠️ 關閉獨立連接失敗: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __getattr__(self, name):
        """代理所有其他屬性到原始連接"""
        return getattr(self._conn, name)

    def __del__(self):
        """析構時確保連接被關閉"""
        if not self._closed:
            self.close()


class PooledConnection:
    """
    連接池包裝類 - 確保連接正確歸還到池中

    問題：psycopg2 的 ThreadedConnectionPool 需要顯式調用 putconn() 來歸還連接，
    但調用 conn.close() 不會自動歸還，導致連接洩漏。

    解決方案：包裝原始連接，讓 close() 自動調用 putconn() 歸還連接。
    """
    
    def __init__(self, conn, pool_ref):
        self._conn = conn
        self._pool = pool_ref
        self._returned = False
    
    def close(self):
        """關閉連接（實際上是歸還到池中）"""
        if not self._returned and self._pool and self._conn:
            try:
                # 先 rollback 任何未提交的事務，避免連接狀態不一致
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                # 歸還連接到池中，而不是真正關閉
                self._pool.putconn(self._conn)
                self._returned = True
            except Exception as e:
                # 如果歸還失敗，嘗試真正關閉
                try:
                    self._conn.close()
                except:
                    pass
                print(f"⚠️ 連接歸還失敗: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    def __getattr__(self, name):
        """代理所有其他屬性到原始連接"""
        return getattr(self._conn, name)
    
    def __del__(self):
        """析構時確保連接被歸還"""
        if not self._returned:
            self.close()


def init_connection_pool():
    """
    初始化線程安全連接池（單例模式）

    包含重試機制，適用於容器環境（如 Zeabur）中 PostgreSQL 可能尚未完全啟動的情況
    """
    global _connection_pool

    # 連接池初始化重試配置
    POOL_INIT_MAX_RETRIES = 10
    POOL_INIT_RETRY_DELAY = 3  # 秒

    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                last_error = None
                for attempt in range(POOL_INIT_MAX_RETRIES):
                    try:
                        # 使用 ThreadedConnectionPool 替代 SimpleConnectionPool
                        # ThreadedConnectionPool 是線程安全的，適用於多線程環境
                        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                            MIN_POOL_SIZE,
                            MAX_POOL_SIZE,
                            DATABASE_URL,
                            **CONNECTION_OPTIONS  # 添加連接超時和 keepalive 參數
                        )
                        print(f"✅ 線程安全數據庫連接池已初始化 (min={MIN_POOL_SIZE}, max={MAX_POOL_SIZE})")
                        break
                    except psycopg2.OperationalError as e:
                        last_error = e
                        if attempt < POOL_INIT_MAX_RETRIES - 1:
                            print(f"⚠️ 資料庫連接失敗（{e}），{POOL_INIT_RETRY_DELAY} 秒後重試... (嘗試 {attempt + 1}/{POOL_INIT_MAX_RETRIES})")
                            time.sleep(POOL_INIT_RETRY_DELAY)
                        else:
                            print(f"❌ 連接池初始化失敗（已重試 {POOL_INIT_MAX_RETRIES} 次）: {e}")
                            raise
                    except Exception as e:
                        print(f"❌ 連接池初始化失敗: {e}")
                        raise

    return _connection_pool


def get_connection():
    """
    從連接池獲取連接，確保資料庫和表存在
    
    特性：
    - 線程安全
    - 自動重試機制（指數退避）
    - 連接健康檢查（防止 SSL 斷開錯誤）
    - 自動歸還連接（通過 PooledConnection 包裝）
    
    重要: 使用完畢後調用 conn.close() 會自動將連接歸還到池中
    """
    global _db_initialized, _connection_pool
    
    # 確保連接池已初始化
    if _connection_pool is None:
        init_connection_pool()

    # 如果尚未初始化數據庫，執行初始化
    if not _db_initialized:
        init_db()
        _db_initialized = True

    # 從池中獲取連接（帶重試機制和健康檢查）
    last_error = None
    bad_conn_count = 0  # 追蹤壞連接數量

    for attempt in range(MAX_RETRIES):
        raw_conn = None
        try:
            raw_conn = _connection_pool.getconn()

            # === 連接健康檢查 ===
            # 檢查 1: 連接是否已關閉
            if raw_conn.closed:
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except:
                    pass
                raw_conn = None
                bad_conn_count += 1
                continue

            # 檢查 2: 執行簡單查詢驗證連接是否真的可用（防止 SSL 斷開）
            try:
                test_cursor = raw_conn.cursor()
                test_cursor.execute("SELECT 1")
                test_cursor.fetchone()
                test_cursor.close()
            except Exception as health_error:
                # 連接已斷開（SSL 錯誤等），關閉並丟棄
                print(f"⚠️ 偵測到壞掉的連接（{type(health_error).__name__}），重新獲取...")
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except:
                    pass
                raw_conn = None
                bad_conn_count += 1

                # 如果連續遇到多個壞連接，可能整個池都壞了，創建新連接繞過池
                if bad_conn_count >= 3:
                    print(f"⚠️ 連接池可能已失效（{bad_conn_count} 個壞連接），嘗試創建新連接...")
                    try:
                        fresh_conn = psycopg2.connect(DATABASE_URL, **CONNECTION_OPTIONS)
                        # 驗證新連接
                        test_cur = fresh_conn.cursor()
                        test_cur.execute("SELECT 1")
                        test_cur.fetchone()
                        test_cur.close()
                        print(f"✅ 成功創建新連接繞過連接池")
                        # 返回一個不依賴連接池的包裝（close 時真正關閉）
                        return _StandaloneConnection(fresh_conn)
                    except Exception as new_conn_error:
                        print(f"❌ 創建新連接也失敗: {new_conn_error}")
                        last_error = new_conn_error
                continue

            # 連接健康，包裝後返回
            # PooledConnection 確保 close() 時自動調用 putconn()
            return PooledConnection(raw_conn, _connection_pool)

        except pool.PoolError as e:
            last_error = e
            if raw_conn:
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except:
                    pass
            if attempt < MAX_RETRIES - 1:
                # 使用指數退避
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"⚠️ 連接池暫時耗盡，等待 {delay:.1f}s 後重試 (嘗試 {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(delay)

                # 連接池耗盡時，嘗試直接創建連接
                if attempt >= 2:
                    print(f"⚠️ 連接池持續耗盡，嘗試創建新連接...")
                    try:
                        fresh_conn = psycopg2.connect(DATABASE_URL, **CONNECTION_OPTIONS)
                        print(f"✅ 成功創建新連接繞過連接池")
                        return _StandaloneConnection(fresh_conn)
                    except Exception as new_conn_error:
                        print(f"❌ 創建新連接也失敗: {new_conn_error}")
            else:
                print(f"❌ 無法從連接池獲取連接（已重試 {MAX_RETRIES} 次）: {e}")
                raise
        except Exception as e:
            last_error = e
            if raw_conn:
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except:
                    pass
            print(f"❌ 無法從連接池獲取連接: {e}")
            raise

    # 如果所有重試都失敗
    raise Exception(f"連接池耗盡，無法獲取連接: {last_error}")


def close_all_connections():
    """關閉所有連接池連接（應用關閉時調用）"""
    global _connection_pool

    if _connection_pool:
        try:
            _connection_pool.closeall()
            print("✅ 所有數據庫連接已關閉")
        except Exception as e:
            print(f"❌ 關閉連接池失敗: {e}")


def reset_connection_pool():
    """
    重置連接池（用於 Gunicorn worker fork 後）

    在多進程環境中（如 Gunicorn），連接池在 fork 前創建會導致所有 worker 共享
    同一個連接池，造成連接衝突。此函數用於在 fork 後重新初始化連接池。
    """
    global _connection_pool, _db_initialized

    with _pool_lock:
        if _connection_pool:
            try:
                _connection_pool.closeall()
            except Exception:
                pass
        _connection_pool = None
        _db_initialized = False

    print(f"🔄 連接池已重置 (PID: {os.getpid()})")



def init_db():
    """
    初始化資料庫 - 建立所有資料表

    包含重試機制，適用於容器環境（如 Zeabur）中 PostgreSQL 可能尚未完全啟動的情況
    """
    # 重試配置
    INIT_MAX_RETRIES = 10
    INIT_RETRY_DELAY = 3  # 秒

    # 直接創建連接而不是從池中獲取（避免初始化時的循環依賴）
    conn = None
    for attempt in range(INIT_MAX_RETRIES):
        try:
            conn = psycopg2.connect(DATABASE_URL, **CONNECTION_OPTIONS)
            break
        except psycopg2.OperationalError as e:
            if attempt < INIT_MAX_RETRIES - 1:
                print(f"⚠️ 資料庫連接失敗（{e}），{INIT_RETRY_DELAY} 秒後重試... (嘗試 {attempt + 1}/{INIT_MAX_RETRIES})")
                time.sleep(INIT_RETRY_DELAY)
            else:
                print(f"❌ 資料庫連接失敗（已重試 {INIT_MAX_RETRIES} 次）: {e}")
                raise

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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========================================================================
    # 對話相關資料表
    # ========================================================================

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
            pi_username TEXT,
            last_active_at TIMESTAMP,
            membership_tier TEXT DEFAULT 'free',
            membership_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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

    # 建立密碼重置 Token 表
    c.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
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

    # ========================================================================
    # 論壇相關資料表
    # ========================================================================

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

    # ========================================================================
    # 可疑錢包追蹤系統資料表
    # ========================================================================

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
            attachment_url TEXT,
            is_hidden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (report_id) REFERENCES scam_reports(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # ========================================================================
    # 好友功能資料表
    # ========================================================================

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

    # ========================================================================
    # 私訊功能資料表
    # ========================================================================

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

    # ========================================================================
    # 審計日誌資料表 (Security & Compliance)
    # ========================================================================
    
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
    
    # ========================================================================
    # 初始化預設數據
    # ========================================================================

    # 初始化預設看板（如果不存在）
    c.execute("SELECT COUNT(*) FROM boards WHERE slug = 'crypto'")
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
        # 可疑錢包追蹤配置
        ('scam_report_daily_limit_pro', '5', 'int', 'scam_tracker', 'PRO 用戶每日可舉報可疑錢包數量', 1),
        ('scam_comment_require_pro', 'true', 'bool', 'scam_tracker', '評論是否僅限 PRO 用戶', 1),
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

    # ========================================================================
    # 索引 (Indexes) - 優化查詢效能
    # ========================================================================
    
    # 1. AI 對話歷史索引 (Optimized for get_chat_history)
    c.execute('CREATE INDEX IF NOT EXISTS idx_conversation_history_session_timestamp ON conversation_history(session_id, timestamp)')
    
    # 2. 其他索引
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
    # 優化: 複合索引加速分頁查詢 (conversation_id + created_at)
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_conversation_created ON dm_messages(conversation_id, created_at DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_message_limits ON user_message_limits(user_id, date)')

    conn.commit()
    conn.close()


# 連接池將在第一次 get_connection() 時自動初始化數據庫
# 不再需要在模塊載入時立即初始化
