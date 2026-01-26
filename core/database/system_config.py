"""
系統配置管理模組 V2

提供從數據庫讀取和更新系統配置的功能。
包含多層快取機制（進程內 + Redis）以提高性能。

商用化設計：
- 多層快取：進程內快取(10秒) -> Redis快取(5分鐘) -> SQLite
- 配置變更審計日誌
- Redis Pub/Sub 跨進程快取失效
- 支持即時更新配置，無需重啟服務
- 分類管理（pricing, limits, general）
- 權限控制（is_public 標記）

架構圖：
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   API 請求   │ --> │ 進程內快取   │ --> │ Redis 快取  │ --> │  SQLite DB  │
└─────────────┘     │   (10秒)    │     │  (5分鐘)    │     └─────────────┘
                    └─────────────┘     └──────┬──────┘
                                               │
                                        Pub/Sub 失效通知
"""

import os
import time
import json
import threading
from typing import Any, Dict, Optional, List
from .connection import get_connection

# ============================================================================
# Redis 支持（可選依賴）
# ============================================================================

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# ============================================================================
# 配置常量
# ============================================================================

MEMORY_CACHE_TTL = 10      # 進程內快取 10 秒
REDIS_CACHE_TTL = 300      # Redis 快取 5 分鐘
CONFIG_CHANNEL = "config:updates"  # Redis Pub/Sub 頻道
REDIS_KEY_PREFIX = "config:"

# ============================================================================
# 多層快取管理器
# ============================================================================

class ConfigCacheManager:
    """
    多層快取管理器

    Layer 1: 進程內記憶體快取（10秒）- 最快，避免頻繁網絡請求
    Layer 2: Redis 快取（5分鐘）- 跨進程同步
    Layer 3: SQLite 數據庫 - 持久化存儲
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._memory_cache: Dict[str, Any] = {}
        self._memory_timestamp: float = 0
        self._redis_client: Optional[Any] = None
        self._pubsub_thread: Optional[threading.Thread] = None
        self._initialized = True

        # 初始化 Redis 連接
        self._init_redis()

    def _init_redis(self):
        """初始化 Redis 連接"""
        if not REDIS_AVAILABLE:
            print("[ConfigCache] Redis 模組未安裝，使用純記憶體快取")
            return

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("[ConfigCache] REDIS_URL 未設置，使用純記憶體快取")
            return

        try:
            self._redis_client = redis.from_url(redis_url, decode_responses=True)
            self._redis_client.ping()
            print(f"[ConfigCache] Redis 連接成功: {redis_url}")

            # 啟動 Pub/Sub 監聽線程
            self._start_pubsub_listener()

        except Exception as e:
            print(f"[ConfigCache] Redis 連接失敗，降級為純記憶體快取: {e}")
            self._redis_client = None

    def _start_pubsub_listener(self):
        """啟動 Redis Pub/Sub 監聽器"""
        if not self._redis_client:
            return

        def listener():
            try:
                pubsub = self._redis_client.pubsub()
                pubsub.subscribe(CONFIG_CHANNEL)

                for message in pubsub.listen():
                    if message['type'] == 'message':
                        # 收到失效通知，清除本地快取
                        self._memory_cache = {}
                        self._memory_timestamp = 0
                        print(f"[ConfigCache] 收到快取失效通知，已清除本地快取")
            except Exception as e:
                print(f"[ConfigCache] Pub/Sub 監聽器錯誤: {e}")

        self._pubsub_thread = threading.Thread(target=listener, daemon=True)
        self._pubsub_thread.start()
        print("[ConfigCache] Pub/Sub 監聽器已啟動")

    # ========================================================================
    # 快取讀取
    # ========================================================================

    def get_all(self) -> Dict[str, Any]:
        """
        獲取所有配置（多層快取）
        """
        # Layer 1: 進程內快取
        if self._is_memory_cache_valid():
            return self._memory_cache.copy()

        # Layer 2: Redis 快取
        redis_data = self._get_from_redis()
        if redis_data is not None:
            self._set_memory_cache(redis_data)
            return redis_data.copy()

        # Layer 3: 數據庫
        db_data = self._load_from_db()
        self._set_memory_cache(db_data)
        self._set_to_redis(db_data)
        return db_data.copy()

    def _is_memory_cache_valid(self) -> bool:
        """檢查進程內快取是否有效"""
        return (time.time() - self._memory_timestamp) < MEMORY_CACHE_TTL and bool(self._memory_cache)

    def _set_memory_cache(self, data: Dict[str, Any]):
        """設置進程內快取"""
        self._memory_cache = data.copy()
        self._memory_timestamp = time.time()

    def _get_from_redis(self) -> Optional[Dict[str, Any]]:
        """從 Redis 獲取快取"""
        if not self._redis_client:
            return None

        try:
            data = self._redis_client.get(f"{REDIS_KEY_PREFIX}all")
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"[ConfigCache] Redis 讀取失敗: {e}")
        return None

    def _set_to_redis(self, data: Dict[str, Any]):
        """設置 Redis 快取"""
        if not self._redis_client:
            return

        try:
            self._redis_client.setex(
                f"{REDIS_KEY_PREFIX}all",
                REDIS_CACHE_TTL,
                json.dumps(data)
            )
        except Exception as e:
            print(f"[ConfigCache] Redis 寫入失敗: {e}")

    def _load_from_db(self) -> Dict[str, Any]:
        """從數據庫載入所有配置"""
        conn = get_connection()
        c = conn.cursor()
        try:
            c.execute('SELECT key, value, value_type FROM system_config')
            rows = c.fetchall()

            result = {}
            for key, value, value_type in rows:
                result[key] = _parse_value(value, value_type)
            return result
        finally:
            conn.close()

    # ========================================================================
    # 快取失效
    # ========================================================================

    def invalidate(self, key: Optional[str] = None):
        """
        使快取失效

        Args:
            key: 指定 key 或 None 清除全部
        """
        # 清除進程內快取
        self._memory_cache = {}
        self._memory_timestamp = 0

        if not self._redis_client:
            return

        try:
            # 清除 Redis 快取
            if key:
                self._redis_client.delete(f"{REDIS_KEY_PREFIX}{key}")
            self._redis_client.delete(f"{REDIS_KEY_PREFIX}all")

            # 發布失效通知（讓其他進程也失效）
            self._redis_client.publish(CONFIG_CHANNEL, json.dumps({
                "action": "invalidate",
                "key": key,
                "timestamp": time.time()
            }))
            print(f"[ConfigCache] 已發布快取失效通知")

        except Exception as e:
            print(f"[ConfigCache] Redis 失效操作失敗: {e}")


# 全局快取管理器實例
_cache_manager: Optional[ConfigCacheManager] = None


def _get_cache_manager() -> ConfigCacheManager:
    """獲取快取管理器單例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ConfigCacheManager()
    return _cache_manager


# ============================================================================
# 值解析工具
# ============================================================================

def _parse_value(value: str, value_type: str) -> Any:
    """根據類型解析配置值"""
    if value == 'null' or value is None:
        return None

    if value_type == 'int':
        return int(value)
    elif value_type == 'float':
        return float(value)
    elif value_type == 'bool':
        return value.lower() in ('true', '1', 'yes')
    elif value_type == 'json':
        return json.loads(value)
    else:
        return value


def _serialize_value(value: Any) -> str:
    """序列化配置值為字串"""
    if value is None:
        return 'null'

    if isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (dict, list)):
        return json.dumps(value)
    else:
        return str(value)


def _detect_value_type(value: Any) -> str:
    """自動檢測值類型"""
    if value is None:
        return 'string'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, (dict, list)):
        return 'json'
    return 'string'


# ============================================================================
# 向後兼容的快取函數
# ============================================================================

def invalidate_cache():
    """清除快取，強制下次讀取時重新載入（向後兼容）"""
    _get_cache_manager().invalidate()


def _refresh_cache():
    """刷新快取（向後兼容，實際由 ConfigCacheManager 處理）"""
    _get_cache_manager().invalidate()


def _is_cache_valid() -> bool:
    """檢查快取是否有效（向後兼容）"""
    return _get_cache_manager()._is_memory_cache_valid()


# ============================================================================
# 配置讀取
# ============================================================================

def get_config(key: str, default: Any = None) -> Any:
    """
    獲取單個配置值

    Args:
        key: 配置鍵名
        default: 默認值（如果配置不存在）

    Returns:
        配置值
    """
    all_configs = _get_cache_manager().get_all()
    return all_configs.get(key, default)


def get_all_configs(category: Optional[str] = None, public_only: bool = True) -> Dict[str, Any]:
    """
    獲取所有配置

    Args:
        category: 過濾特定分類（pricing, limits, general）
        public_only: 是否只返回公開配置

    Returns:
        配置字典
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        query = 'SELECT key, value, value_type FROM system_config WHERE 1=1'
        params = []

        if category:
            query += ' AND category = ?'
            params.append(category)

        if public_only:
            query += ' AND is_public = 1'

        c.execute(query, params)
        rows = c.fetchall()

        return {key: _parse_value(value, value_type) for key, value, value_type in rows}
    finally:
        conn.close()


def get_prices() -> Dict[str, float]:
    """
    獲取所有價格配置

    Returns:
        價格配置字典，格式與原 PI_PAYMENT_PRICES 相容
    """
    all_configs = _get_cache_manager().get_all()

    return {
        'create_post': all_configs.get('price_create_post', 1.0),
        'tip': all_configs.get('price_tip', 1.0),
        'premium': all_configs.get('price_premium', 1.0),
    }


def get_limits() -> Dict[str, Optional[int]]:
    """
    獲取所有限制配置

    Returns:
        限制配置字典，格式與原 FORUM_LIMITS 相容
    """
    all_configs = _get_cache_manager().get_all()

    return {
        'daily_post_free': all_configs.get('limit_daily_post_free', 3),
        'daily_post_premium': all_configs.get('limit_daily_post_premium'),  # None = 無限
        'daily_comment_free': all_configs.get('limit_daily_comment_free', 20),
        'daily_comment_premium': all_configs.get('limit_daily_comment_premium'),  # None = 無限
    }


# ============================================================================
# 配置更新（帶審計日誌）
# ============================================================================

def set_config(key: str, value: Any, value_type: str = 'string',
               category: str = 'general', description: str = '',
               is_public: bool = True, changed_by: str = 'system') -> bool:
    """
    設置配置值（創建或更新，帶審計日誌）

    Args:
        key: 配置鍵名
        value: 配置值
        value_type: 值類型 (string, int, float, bool, json)
        category: 分類 (pricing, limits, general)
        description: 描述
        is_public: 是否公開
        changed_by: 變更者（用戶 ID 或 'system'）

    Returns:
        是否成功
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 獲取舊值（用於審計日誌）
        c.execute('SELECT value FROM system_config WHERE key = ?', (key,))
        old_row = c.fetchone()
        old_value = old_row[0] if old_row else None

        # 自動檢測類型
        if value_type == 'string' and value is not None:
            value_type = _detect_value_type(value)

        serialized_value = _serialize_value(value)

        c.execute('''
            INSERT INTO system_config (key, value, value_type, category, description, is_public, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                value_type = excluded.value_type,
                category = excluded.category,
                description = excluded.description,
                is_public = excluded.is_public,
                updated_at = CURRENT_TIMESTAMP
        ''', (key, serialized_value, value_type, category, description, 1 if is_public else 0))

        # 寫入審計日誌
        _write_audit_log(c, key, old_value, serialized_value, changed_by)

        conn.commit()

        # 清除快取
        _get_cache_manager().invalidate()

        print(f"[Config] 配置已更新: {key} = {value} (by {changed_by})")
        return True

    except Exception as e:
        print(f"[Config] 設置配置失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def _write_audit_log(cursor, key: str, old_value: Any, new_value: Any, changed_by: str):
    """寫入配置變更審計日誌"""
    try:
        cursor.execute('''
            INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by, changed_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (key, old_value, new_value, changed_by))
    except Exception as e:
        # 審計表可能不存在，僅記錄警告
        print(f"[Config] 審計日誌寫入失敗（表可能不存在）: {e}")


def update_price(key: str, value: float, changed_by: str = 'admin') -> bool:
    """
    更新價格配置的便捷方法

    Args:
        key: 價格鍵名 (create_post, tip, premium)
        value: 新價格
        changed_by: 變更者

    Returns:
        是否成功
    """
    config_key = f'price_{key}'
    return set_config(config_key, value, 'float', 'pricing', changed_by=changed_by)


def update_limit(key: str, value: Optional[int], changed_by: str = 'admin') -> bool:
    """
    更新限制配置的便捷方法

    Args:
        key: 限制鍵名 (daily_post_free, daily_post_premium, etc.)
        value: 新限制值 (None = 無限)
        changed_by: 變更者

    Returns:
        是否成功
    """
    config_key = f'limit_{key}'
    return set_config(config_key, value, 'int', 'limits', changed_by=changed_by)


# ============================================================================
# 審計日誌查詢
# ============================================================================

def get_config_history(key: str, limit: int = 20) -> List[Dict]:
    """
    獲取配置變更歷史

    Args:
        key: 配置鍵名
        limit: 返回記錄數量

    Returns:
        變更歷史列表
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT old_value, new_value, changed_by, changed_at
            FROM config_audit_log
            WHERE config_key = ?
            ORDER BY changed_at DESC
            LIMIT ?
        ''', (key, limit))
        rows = c.fetchall()

        return [{
            'old_value': row[0],
            'new_value': row[1],
            'changed_by': row[2],
            'changed_at': row[3],
        } for row in rows]
    except Exception as e:
        print(f"[Config] 查詢審計日誌失敗: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# 批量操作
# ============================================================================

def bulk_update_configs(configs: Dict[str, Any], changed_by: str = 'admin') -> bool:
    """
    批量更新配置

    Args:
        configs: 配置字典 {key: value}
        changed_by: 變更者

    Returns:
        是否全部成功
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        for key, value in configs.items():
            # 獲取舊值
            c.execute('SELECT value FROM system_config WHERE key = ?', (key,))
            old_row = c.fetchone()
            old_value = old_row[0] if old_row else None

            serialized_value = _serialize_value(value)
            c.execute('''
                UPDATE system_config
                SET value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE key = ?
            ''', (serialized_value, key))

            # 寫入審計日誌
            _write_audit_log(c, key, old_value, serialized_value, changed_by)

        conn.commit()
        _get_cache_manager().invalidate()
        return True
    except Exception as e:
        print(f"[Config] 批量更新失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_config_metadata(key: str) -> Optional[Dict]:
    """
    獲取配置的完整元數據

    Returns:
        包含 key, value, value_type, category, description, is_public, updated_at 的字典
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        c.execute('''
            SELECT key, value, value_type, category, description, is_public, created_at, updated_at
            FROM system_config WHERE key = ?
        ''', (key,))
        row = c.fetchone()

        if row:
            return {
                'key': row[0],
                'value': _parse_value(row[1], row[2]),
                'raw_value': row[1],
                'value_type': row[2],
                'category': row[3],
                'description': row[4],
                'is_public': bool(row[5]),
                'created_at': row[6],
                'updated_at': row[7],
            }
        return None
    finally:
        conn.close()


def list_all_configs_with_metadata() -> List[Dict]:
    """
    列出所有配置及其元數據（管理後台用）

    Returns:
        配置列表
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        c.execute('''
            SELECT key, value, value_type, category, description, is_public, created_at, updated_at
            FROM system_config ORDER BY category, key
        ''')
        rows = c.fetchall()

        return [{
            'key': row[0],
            'value': _parse_value(row[1], row[2]),
            'raw_value': row[1],
            'value_type': row[2],
            'category': row[3],
            'description': row[4],
            'is_public': bool(row[5]),
            'created_at': row[6],
            'updated_at': row[7],
        } for row in rows]
    finally:
        conn.close()


# ============================================================================
# 初始化審計表
# ============================================================================

def init_audit_table():
    """初始化審計日誌表（如果不存在）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            CREATE TABLE IF NOT EXISTS config_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT NOT NULL DEFAULT 'system',
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_key ON config_audit_log(config_key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_time ON config_audit_log(changed_at)')
        conn.commit()
        print("[Config] 審計日誌表初始化完成")
    except Exception as e:
        print(f"[Config] 審計表初始化失敗: {e}")
    finally:
        conn.close()


# ============================================================================
# 模組初始化
# ============================================================================

# 自動初始化審計表
try:
    init_audit_table()
except Exception as e:
    print(f"[Config] 模組初始化時審計表創建失敗（可能是首次運行）: {e}")
