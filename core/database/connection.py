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
from urllib.parse import quote

from .schema import (
    create_all_tables,
    format_reconcile_summary,
    reconcile_existing_tables,
)


logger = logging.getLogger(__name__)


def _load_env_file_if_needed():
    """在本地開發環境中按需讀取 .env，但不覆蓋平台已注入的變數。"""
    from dotenv import load_dotenv

    load_dotenv(override=False)


def _build_database_url_from_components(
    env: dict | os._Environ[str] | None = None,
) -> str | None:
    """
    從分離式 PostgreSQL 環境變數組裝連接字串。

    Zeabur 會提供 POSTGRESQL_HOST / USER / PASSWORD / PORT / DB。
    當密碼包含 @ 或 $ 等保留字元時，這種組裝方式比直接吃 DATABASE_URL 更安全。
    """
    env = env or os.environ

    host = env.get("POSTGRESQL_HOST")
    user = env.get("POSTGRESQL_USER")
    password = env.get("POSTGRESQL_PASSWORD")
    db_name = env.get("POSTGRESQL_DB") or env.get("POSTGRES_DB")
    port = env.get("POSTGRESQL_PORT", "5432")

    if not all([host, user, password, db_name]):
        return None

    encoded_user = quote(str(user), safe="")
    encoded_password = quote(str(password), safe="")
    encoded_db_name = quote(str(db_name), safe="")

    return (
        f"postgresql://{encoded_user}:{encoded_password}"
        f"@{host}:{port}/{encoded_db_name}"
    )


def _resolve_database_url_from_environment() -> str | None:
    """解析目前環境中的資料庫連線字串。"""
    component_url = _build_database_url_from_components()
    if component_url:
        return component_url

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    _load_env_file_if_needed()

    component_url = _build_database_url_from_components()
    if component_url:
        return component_url

    return os.environ.get("DATABASE_URL")


DATABASE_URL = _resolve_database_url_from_environment()
_INITIAL_DATABASE_URL = DATABASE_URL


def get_database_url() -> str | None:
    """
    取得目前應使用的資料庫連線字串。

    預設每次依據當前環境重新解析，避免平台重新注入變數後仍沿用舊值。
    測試若直接 patch 模組級 DATABASE_URL，這裡也會尊重該覆寫。
    """
    current_module_value = globals().get("DATABASE_URL")
    resolved_from_env = _resolve_database_url_from_environment()

    if current_module_value and current_module_value != _INITIAL_DATABASE_URL:
        return current_module_value

    globals()["DATABASE_URL"] = resolved_from_env
    return resolved_from_env


# 允許在測試環境中延遲初始化（不立即拋出錯誤）
# 實際連接時才會驗證 DATABASE_URL 是否有效

# 連接池配置 - 針對 Zeabur 優化
MIN_POOL_SIZE = int(os.getenv("DB_MIN_POOL_SIZE", "2"))
MAX_POOL_SIZE = int(os.getenv("DB_MAX_POOL_SIZE", "10"))

# 連接獲取配置
MAX_RETRIES = 5  # 重試次數
RETRY_DELAY_BASE = 0.3  # 重試延遲

# 連接參數 - 防止連接超時和斷開
CONNECTION_OPTIONS = {
    "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),

    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}

# 全局連接池
_connection_pool = None
_pool_lock = threading.Lock()
_db_initialized = False

# ✅ 效能優化：連接健康檢查頻率限制，避免每次取連線都 SELECT 1
# 只有連接超過 30 秒沒使用才重新驗證
_conn_last_verified: dict = {}  # {conn_id: timestamp}
_HEALTH_CHECK_INTERVAL = 30  # 秒


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
        if not self._closed and self._conn:
            try:
                self._conn.rollback()
            except Exception:
                pass
            try:
                self._conn.close()
                self._closed = True
            except Exception as e:
                logger.warning("Failed to close standalone connection: %s", e)
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __del__(self):
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
        if not self._returned and self._pool and self._conn:
            try:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                self._pool.putconn(self._conn)
                self._returned = True
            except Exception as e:
                try:
                    self._conn.close()
                except Exception:
                    pass
                logger.warning("Connection return to pool failed: %s", e)

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
    database_url = get_database_url()
    if not database_url:
        raise ValueError(
            "Database connection is not configured. "
            "Set DATABASE_URL or POSTGRESQL_HOST/USER/PASSWORD/DB in your environment."
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
                            database_url,
                            **CONNECTION_OPTIONS,
                        )
                        logger.info(
                            "Database connection pool initialized (min=%d, max=%d)",
                            MIN_POOL_SIZE, MAX_POOL_SIZE,
                        )
                        break
                    except psycopg2.OperationalError as e:
                        if attempt < POOL_INIT_MAX_RETRIES - 1:
                            logger.warning(
                                "Database connection failed (%s), retrying in %ds (attempt %d/%d)",
                                e, POOL_INIT_RETRY_DELAY, attempt + 1, POOL_INIT_MAX_RETRIES,
                            )
                            time.sleep(POOL_INIT_RETRY_DELAY)
                        else:
                            logger.error(
                                "Connection pool init failed after %d retries: %s",
                                POOL_INIT_MAX_RETRIES, e,
                            )
                            raise
                    except Exception as e:
                        logger.error("Connection pool init failed: %s", e)
                        raise

    return _connection_pool


def get_connection():
    """
    Get a connection from the pool, ensuring database and tables exist.

    Features:
    - Thread-safe
    - Automatic retry with exponential backoff
    - Connection health checks
    - Hard cap on pool size (no unlimited bypass connections)
    - Raises RuntimeError when pool is exhausted

    Important: call conn.close() to return connection to pool
    """
    global _db_initialized, _connection_pool
    database_url = get_database_url()
    if not database_url:
        raise ValueError(
            "Database connection is not configured. "
            "Set DATABASE_URL or POSTGRESQL_HOST/USER/PASSWORD/DB in your environment."
        )

    # 確保連接池已初始化
    if _connection_pool is None:
        init_connection_pool()

    # 如果尚未初始化數據庫，執行初始化
    if not _db_initialized:
        init_db()
        _db_initialized = True

    # 從池中獲取連接（帶重試機制和健康檢查）
    last_error = None
    bad_conn_count = 0

    for attempt in range(MAX_RETRIES):
        raw_conn = None
        try:
            raw_conn = _connection_pool.getconn()

            if raw_conn.closed:
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except Exception:
                    pass
                raw_conn = None
                bad_conn_count += 1
                logger.debug("Closed connection detected, discarding (bad_conn_count=%d)", bad_conn_count)
                continue

            conn_id = id(raw_conn)
            now = time.time()
            needs_health_check = (
                conn_id not in _conn_last_verified
                or (now - _conn_last_verified[conn_id]) > _HEALTH_CHECK_INTERVAL
            )
            try:
                if needs_health_check:
                    test_cursor = raw_conn.cursor()
                    test_cursor.execute("SELECT 1")
                    test_cursor.fetchone()
                    test_cursor.execute(
                        "SET statement_timeout = %s",
                        (int(os.getenv("DB_STATEMENT_TIMEOUT", "30000")),),
                    )
                    test_cursor.close()
                    _conn_last_verified[conn_id] = now
            except Exception as health_error:
                logger.warning(
                    "Bad connection detected (%s), discarding (bad_conn_count=%d)",
                    type(health_error).__name__, bad_conn_count,
                )
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except Exception:
                    pass
                raw_conn = None
                bad_conn_count += 1
                last_error = health_error
                continue

            return PooledConnection(raw_conn, _connection_pool)

        except pool.PoolError as e:
            last_error = e
            if raw_conn:
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except Exception:
                    pass
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2**attempt)
                logger.warning(
                    "Connection pool exhausted, retrying in %.1fs (attempt %d/%d)",
                    delay, attempt + 1, MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Connection pool exhausted after %d retries: %s", MAX_RETRIES, e
                )
                raise RuntimeError(
                    f"Service unavailable: database connection pool exhausted "
                    f"(max={MAX_POOL_SIZE}, retries={MAX_RETRIES})"
                ) from e
        except Exception as e:
            last_error = e
            if raw_conn:
                try:
                    _connection_pool.putconn(raw_conn, close=True)
                except Exception:
                    pass
            logger.error("Failed to get connection from pool: %s", e)
            raise

    raise RuntimeError(
        f"Service unavailable: database connection pool exhausted "
        f"(max={MAX_POOL_SIZE}, retries={MAX_RETRIES}): {last_error}"
    )


def close_all_connections():
    """關閉所有連接池連接（應用關閉時調用）"""
    global _connection_pool

    if _connection_pool:
        try:
            _connection_pool.closeall()
            logger.info("All database connections closed")
        except Exception as e:
            logger.error("Failed to close connection pool: %s", e)
        finally:
            _connection_pool = None


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

    logger.info("Connection pool reset (PID: %d)", os.getpid())


def init_db():
    """
    初始化資料庫 - 建立所有資料表

    包含重試機制，適用於容器環境（如 Zeabur）中 PostgreSQL 可能尚未完全啟動的情況
    """
    # 重試配置
    INIT_MAX_RETRIES = 10
    INIT_RETRY_DELAY = 3  # 秒
    database_url = get_database_url()
    if not database_url:
        raise ValueError(
            "Database connection is not configured. "
            "Set DATABASE_URL or POSTGRESQL_HOST/USER/PASSWORD/DB in your environment."
        )

    # 直接創建連接而不是從池中獲取（避免初始化時的循環依賴）
    conn = None
    for attempt in range(INIT_MAX_RETRIES):
        try:
            conn = psycopg2.connect(database_url, **CONNECTION_OPTIONS)
            break
        except psycopg2.OperationalError as e:
            if attempt < INIT_MAX_RETRIES - 1:
                logger.warning(
                    "Database connection failed (%s), retrying in %ds (attempt %d/%d)",
                    e, INIT_RETRY_DELAY, attempt + 1, INIT_MAX_RETRIES,
                )
                time.sleep(INIT_RETRY_DELAY)
            else:
                logger.error(
                    "Database connection failed after %d retries: %s",
                    INIT_MAX_RETRIES, e,
                )
                raise

    c = conn.cursor()

    # 使用 schema 模塊創建所有表
    create_all_tables(c)
    reconcile_summary = reconcile_existing_tables(c)
    logger.info(
        "Schema reconcile completed: %s", format_reconcile_summary(reconcile_summary)
    )

    conn.commit()
    conn.close()


# 連接池將在第一次 get_connection() 時自動初始化數據庫
# 不再需要在模塊載入時立即初始化
