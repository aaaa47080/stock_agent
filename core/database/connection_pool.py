"""
優化的數據庫連接管理 - 使用線程安全連接池
替換原本的 core/database/connection.py
"""
import psycopg2
from psycopg2 import pool
import os
import threading
import time

# PostgreSQL 連接字符串
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

# 連接池配置 - 增加最大連接數以支持並發任務
MIN_POOL_SIZE = 2   # 最小連接數
MAX_POOL_SIZE = 20  # 最大連接數（增加以支持並發 screener 任務）

# 連接獲取配置
MAX_RETRIES = 3          # 最大重試次數
RETRY_DELAY_BASE = 0.5   # 重試延遲基數（秒），使用指數退避

# 全局連接池
_connection_pool = None
_pool_lock = threading.Lock()
_db_initialized = False


def init_connection_pool():
    """初始化線程安全連接池（單例模式）"""
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                try:
                    # 使用 ThreadedConnectionPool 替代 SimpleConnectionPool
                    # ThreadedConnectionPool 是線程安全的，適用於多線程環境
                    _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                        MIN_POOL_SIZE,
                        MAX_POOL_SIZE,
                        DATABASE_URL
                    )
                    print(f"✅ 線程安全數據庫連接池已初始化 (min={MIN_POOL_SIZE}, max={MAX_POOL_SIZE})")
                except Exception as e:
                    print(f"❌ 連接池初始化失敗: {e}")
                    raise
    
    return _connection_pool


def get_connection():
    """
    從連接池獲取連接
    
    特性：
    - 線程安全
    - 自動重試機制（指數退避）
    - 連接健康檢查（防止 SSL 斷開錯誤）
    - 自動重新建立壞掉的連接
    
    記住要調用 conn.close() 來將連接歸還到池中（不是真正關閉）
    """
    global _db_initialized, _connection_pool
    
    # 確保連接池已初始化
    if _connection_pool is None:
        init_connection_pool()
    
    # 如果數據庫還沒初始化，先初始化
    if not _db_initialized:
        init_db()
        _db_initialized = True
    
    # 從池中獲取連接（帶重試機制和健康檢查）
    last_error = None
    for attempt in range(MAX_RETRIES):
        conn = None
        try:
            conn = _connection_pool.getconn()
            
            # === 連接健康檢查 ===
            # 檢查 1: 連接是否已關閉
            if conn.closed:
                try:
                    _connection_pool.putconn(conn, close=True)
                except:
                    pass
                conn = None
                continue
            
            # 檢查 2: 執行簡單查詢驗證連接是否真的可用（防止 SSL 斷開）
            try:
                test_cursor = conn.cursor()
                test_cursor.execute("SELECT 1")
                test_cursor.fetchone()
                test_cursor.close()
            except Exception as health_error:
                # 連接已斷開（SSL 錯誤等），關閉並丟棄
                print(f"⚠️ 偵測到壞掉的連接（{type(health_error).__name__}），重新獲取...")
                try:
                    _connection_pool.putconn(conn, close=True)
                except:
                    pass
                conn = None
                continue
            
            # 連接健康，可以返回
            return conn
            
        except pool.PoolError as e:
            last_error = e
            if conn:
                try:
                    _connection_pool.putconn(conn, close=True)
                except:
                    pass
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"⚠️ 連接池暫時耗盡，等待 {delay:.1f}s 後重試 (嘗試 {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(delay)
            else:
                print(f"❌ 無法從連接池獲取連接（已重試 {MAX_RETRIES} 次）: {e}")
                raise
        except Exception as e:
            last_error = e
            if conn:
                try:
                    _connection_pool.putconn(conn, close=True)
                except:
                    pass
            print(f"❌ 無法從連接池獲取連接: {e}")
            raise
    
    raise Exception(f"連接池耗盡，無法獲取連接: {last_error}")


def return_connection(conn):
    """
    將連接歸還到池中
    
    注意: 使用 conn.close() 也會自動歸還，這個函數是為了語義清晰
    """
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            print(f"⚠️ 歸還連接失敗: {e}")


def close_all_connections():
    """關閉所有連接池連接（應用關閉時調用）"""
    global _connection_pool
    
    if _connection_pool:
        try:
            _connection_pool.closeall()
            print("✅ 所有數據庫連接已關閉")
        except Exception as e:
            print(f"❌ 關閉連接池失敗: {e}")


def init_db():
    """初始化資料庫 - 建立所有資料表"""
    # 直接創建連接而不是從池中獲取（避免循環）
    conn = psycopg2.connect(DATABASE_URL)
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

    # 建立系統快取表
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_cache (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 建立系統配置表
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

    # ...  (其餘表創建代碼保持不變)
    # 為了簡潔，這裡省略了其他表的創建代碼
    # 實際使用時，請從原 connection.py 複製所有表創建代碼

    conn.commit()
    conn.close()
    print("✅ 數據庫表初始化完成")


# 使用示例和最佳實踐
"""
正確的使用方式:

# 方式1: 手動管理
conn = get_connection()
try:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    result = cursor.fetchall()
    cursor.close()
finally:
    conn.close()  # 將連接歸還到池中

# 方式2: 使用上下文管理器（推薦）
from contextlib import contextmanager

@contextmanager
def get_db_cursor():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# 使用
with get_db_cursor() as cursor:
    cursor.execute("SELECT * FROM users")
    result = cursor.fetchall()
"""
