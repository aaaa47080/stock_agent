"""
資料庫連接管理和初始化 (PostgreSQL 版本)
使用線程安全連接池優化記憶體消耗
"""
import psycopg2
from psycopg2 import pool
import os
import threading
import time
import logging

from .schema import create_all_tables

# PostgreSQL 連接字符串
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # 嘗試從 .env 讀取 (如果 load_dotenv 未在入口處執行)
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.environ.get("DATABASE_URL")

# 允許在測試環境中延遲初始化（不立即拋出錯誤）
# 實際連接時才會驗證 DATABASE_URL 是否有效

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
                # Rollback failed, connection may be corrupted
                # Try close anyway
                pass
            try:
                self._conn.close()
                self._closed = True
            except Exception as e:
                # Log instead of just printing
                logging.warning(f"Failed to close standalone connection: {e}")
                self._closed = True  # Mark as closed even if close failed

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
                except Exception:
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

    # 驗證 DATABASE_URL 是否存在
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please set it in your .env file or environment."
        )

    # 連接池初始化重試配置
    POOL_INIT_MAX_RETRIES = 10
    POOL_INIT_RETRY_DELAY = 3  # 秒

    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
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
                except Exception:
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
                except Exception:
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
                        print("✅ 成功創建新連接繞過連接池")
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
                except Exception:
                    pass
            if attempt < MAX_RETRIES - 1:
                # 使用指數退避
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                print(f"⚠️ 連接池暫時耗盡，等待 {delay:.1f}s 後重試 (嘗試 {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(delay)

                # 連接池耗盡時，嘗試直接創建連接
                if attempt >= 2:
                    print("⚠️ 連接池持續耗盡，嘗試創建新連接...")
                    try:
                        fresh_conn = psycopg2.connect(DATABASE_URL, **CONNECTION_OPTIONS)
                        print("✅ 成功創建新連接繞過連接池")
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
                except Exception:
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
            logging.error(f"Failed to close connection pool: {e}")
        finally:
            _connection_pool = None  # Ensure pool is cleared even on error


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

    # 使用 schema 模塊創建所有表
    create_all_tables(c)

    conn.commit()
    conn.close()


# 連接池將在第一次 get_connection() 時自動初始化數據庫
# 不再需要在模塊載入時立即初始化
