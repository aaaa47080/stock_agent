"""
快取管理模組
提供查詢快取、Planning 快取和記憶體管理功能
支援 Valkey/Redis 分散式快取
"""

import hashlib
import time
import pickle
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict
from functools import wraps

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis 客戶端未安裝，將使用記憶體快取")


class LRUCache:
    """LRU (Least Recently Used) 快取實現"""

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Args:
            max_size: 最大快取條目數
            ttl: 快取有效期（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.hit_count = 0
        self.miss_count = 0

    def _is_expired(self, key: str) -> bool:
        """檢查快取是否過期"""
        if key not in self.timestamps:
            return True
        return (time.time() - self.timestamps[key]) > self.ttl

    def get(self, key: str) -> Optional[Any]:
        """獲取快取值"""
        if key not in self.cache or self._is_expired(key):
            self.miss_count += 1
            if key in self.cache:
                # 過期則刪除
                del self.cache[key]
                del self.timestamps[key]
            return None

        # 移動到最後（表示最近使用）
        self.cache.move_to_end(key)
        self.hit_count += 1
        return self.cache[key]

    def set(self, key: str, value: Any):
        """設置快取值"""
        if key in self.cache:
            # 更新現有快取
            self.cache.move_to_end(key)
            self.cache[key] = value
            self.timestamps[key] = time.time()
        else:
            # 新增快取 - 檢查是否已滿
            if len(self.cache) >= self.max_size:
                # 移除最舊的條目（第一個項目）
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]

            # 添加新項目
            self.cache[key] = value
            self.timestamps[key] = time.time()

    def clear(self):
        """清空快取"""
        self.cache.clear()
        self.timestamps.clear()
        self.hit_count = 0
        self.miss_count = 0

    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "ttl": self.ttl
        }


class ValkeyCache:
    """Valkey/Redis 分散式快取實現"""

    def __init__(self, host: str = "localhost", port: int = 6380, db: int = 0,
                 password: Optional[str] = None, ttl: int = 3600, prefix: str = "cache"):
        """
        Args:
            host: Valkey/Redis 主機
            port: Valkey/Redis 端口
            db: 資料庫編號
            password: 密碼（可選）
            ttl: 快取有效期（秒）
            prefix: 鍵前綴（用於區分不同類型的快取）
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis 客戶端未安裝，請執行: pip install redis")

        self.ttl = ttl
        self.prefix = prefix
        self.hit_count = 0
        self.miss_count = 0

        # 連接 Valkey/Redis
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False,  # 不自動解碼，我們使用 pickle
            socket_connect_timeout=5,
            socket_timeout=5
        )

        # 測試連接
        try:
            self.client.ping()
            print(f"✅ 已連接到 Valkey/Redis: {host}:{port} (DB {db})")
        except Exception as e:
            print(f"❌ 無法連接到 Valkey/Redis: {e}")
            raise

    def _make_key(self, key: str) -> str:
        """生成完整的鍵名"""
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """獲取快取值"""
        try:
            full_key = self._make_key(key)
            value = self.client.get(full_key)

            if value is None:
                self.miss_count += 1
                return None

            self.hit_count += 1
            # 使用 pickle 反序列化
            return pickle.loads(value)

        except Exception as e:
            print(f"⚠️ Valkey get 錯誤: {e}")
            self.miss_count += 1
            return None

    def set(self, key: str, value: Any):
        """設置快取值"""
        try:
            full_key = self._make_key(key)
            # 使用 pickle 序列化（支援複雜 Python 物件）
            serialized = pickle.dumps(value)
            self.client.setex(full_key, self.ttl, serialized)

        except Exception as e:
            print(f"⚠️ Valkey set 錯誤: {e}")

    def clear(self):
        """清空快取（只清除當前 prefix 的鍵）"""
        try:
            # 使用 SCAN 來避免阻塞
            cursor = 0
            pattern = f"{self.prefix}:*"
            deleted_count = 0

            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=100)
                if keys:
                    self.client.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break

            self.hit_count = 0
            self.miss_count = 0
            print(f"🗑️ 已清空 {deleted_count} 個快取鍵（prefix: {self.prefix}）")

        except Exception as e:
            print(f"⚠️ Valkey clear 錯誤: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

        try:
            # 獲取當前 prefix 的鍵數量
            cursor = 0
            pattern = f"{self.prefix}:*"
            size = 0

            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=100)
                size += len(keys)
                if cursor == 0:
                    break

        except Exception:
            size = -1  # 錯誤時返回 -1

        return {
            "size": size,
            "max_size": "unlimited",
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "ttl": self.ttl,
            "prefix": self.prefix
        }


class CacheManager:
    """統一的快取管理器"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 快取配置字典
        """
        self.config = config

        # 決定使用哪種快取實現
        use_valkey = config.get('use_valkey', False)
        valkey_config = config.get('valkey', {})

        def _create_cache(cache_type: str, enabled_key: str, ttl_key: str, size_key: str = None, default_ttl: int = 3600):
            """創建快取實例的輔助函數"""
            if not config.get(enabled_key, True):
                return None

            if use_valkey and REDIS_AVAILABLE:
                try:
                    return ValkeyCache(
                        host=valkey_config.get('host', 'localhost'),
                        port=valkey_config.get('port', 6380),
                        db=valkey_config.get('db', 0),
                        password=valkey_config.get('password'),
                        ttl=config.get(ttl_key, default_ttl),
                        prefix=f"{cache_type}"
                    )
                except Exception as e:
                    print(f"⚠️ Valkey 連接失敗，回退到記憶體快取: {e}")
                    # 回退到 LRUCache
                    return LRUCache(
                        max_size=config.get(size_key, 100) if size_key else 100,
                        ttl=config.get(ttl_key, default_ttl)
                    )
            else:
                return LRUCache(
                    max_size=config.get(size_key, 100) if size_key else 100,
                    ttl=config.get(ttl_key, default_ttl)
                )

        # 查詢快取（相似查詢的最終答案）
        self.query_cache = _create_cache(
            'query_cache',
            'enable_query_cache',
            'query_cache_ttl',
            'query_cache_size',
            3600
        )

        # Planning 結果快取
        self.planning_cache = _create_cache(
            'planning_cache',
            'enable_planning_cache',
            'planning_cache_ttl',
            'planning_cache_size',
            7200
        )

        # 檢索結果快取
        self.retrieval_cache = _create_cache(
            'retrieval_cache',
            'enable_retrieval_cache',
            'retrieval_cache_ttl',
            'retrieval_cache_size',
            1800
        )

        cache_backend = "Valkey/Redis" if use_valkey and REDIS_AVAILABLE else "記憶體 (LRU)"
        print(f"✅ CacheManager 初始化完成（後端: {cache_backend}）")
        if self.query_cache:
            stats = self.query_cache.get_stats()
            print(f"   - 查詢快取: ttl={stats['ttl']}s")
        if self.planning_cache:
            stats = self.planning_cache.get_stats()
            print(f"   - Planning 快取: ttl={stats['ttl']}s")
        if self.retrieval_cache:
            stats = self.retrieval_cache.get_stats()
            print(f"   - 檢索快取: ttl={stats['ttl']}s")

    @staticmethod
    def generate_key(*args, **kwargs) -> str:
        """生成快取鍵（基於參數的 hash）"""
        # 將參數轉換為字串
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_str = "|".join(key_parts)

        # 生成 MD5 hash
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def get_query_cache(self, query: str, user_id: str = "") -> Optional[Any]:
        """獲取查詢快取"""
        if not self.query_cache:
            return None

        key = self.generate_key(query, user_id)
        return self.query_cache.get(key)

    def set_query_cache(self, query: str, result: Any, user_id: str = ""):
        """設置查詢快取"""
        if not self.query_cache:
            return

        key = self.generate_key(query, user_id)
        self.query_cache.set(key, result)

    def get_planning_cache(self, query: str, context: str = "", user_id: str = "") -> Optional[Any]:
        """
        獲取 Planning 快取

        🔒 隱私優先策略：
        - 總是使用 user_id 隔離不同用戶（避免主問題中的個人信息泄露）
        """
        if not self.planning_cache:
            return None

        # 🔒 強制包含 user_id，避免主問題跨用戶共享
        key = self.generate_key(query, context, user_id)
        return self.planning_cache.get(key)

    def set_planning_cache(self, query: str, result: Any, context: str = "", user_id: str = ""):
        """
        設置 Planning 快取

        🔒 隱私優先策略：
        - 總是使用 user_id 隔離不同用戶（避免主問題中的個人信息泄露）
        """
        if not self.planning_cache:
            return

        # 🔒 強制包含 user_id，避免主問題跨用戶共享
        key = self.generate_key(query, context, user_id)
        self.planning_cache.set(key, result)

    def get_retrieval_cache(self, query: str, datasource_ids: list = None) -> Optional[Any]:
        """獲取檢索快取"""
        if not self.retrieval_cache:
            return None

        datasource_key = ",".join(sorted(datasource_ids)) if datasource_ids else "default"
        key = self.generate_key(query, datasource_key)
        return self.retrieval_cache.get(key)

    def set_retrieval_cache(self, query: str, result: Any, datasource_ids: list = None):
        """設置檢索快取"""
        if not self.retrieval_cache:
            return

        datasource_key = ",".join(sorted(datasource_ids)) if datasource_ids else "default"
        key = self.generate_key(query, datasource_key)
        self.retrieval_cache.set(key, result)

    def clear_all(self):
        """清空所有快取"""
        if self.query_cache:
            self.query_cache.clear()
        if self.planning_cache:
            self.planning_cache.clear()
        if self.retrieval_cache:
            self.retrieval_cache.clear()
        print("🗑️ 已清空所有快取")

    def get_stats(self) -> Dict[str, Any]:
        """獲取所有快取統計"""
        stats = {}

        if self.query_cache:
            stats['query_cache'] = self.query_cache.get_stats()

        if self.planning_cache:
            stats['planning_cache'] = self.planning_cache.get_stats()

        if self.retrieval_cache:
            stats['retrieval_cache'] = self.retrieval_cache.get_stats()

        return stats

    def print_stats(self):
        """打印快取統計"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📊 快取統計")
        print("="*60)

        for cache_name, cache_stats in stats.items():
            print(f"\n【{cache_name}】")
            print(f"  大小: {cache_stats['size']}/{cache_stats['max_size']}")
            print(f"  命中次數: {cache_stats['hit_count']}")
            print(f"  未命中次數: {cache_stats['miss_count']}")
            print(f"  命中率: {cache_stats['hit_rate']:.2%}")
            print(f"  TTL: {cache_stats['ttl']}s")

        print("="*60 + "\n")


# 🆕 全域快取管理器實例（單例模式）
_global_cache_manager = None

def get_cache_manager():
    """獲取全域唯一的快取管理器實例"""
    global _global_cache_manager
    if _global_cache_manager is None:
        from core.config import CACHE_CONFIG
        if CACHE_CONFIG.get('enabled', True):
            _global_cache_manager = CacheManager(CACHE_CONFIG)
    return _global_cache_manager


# ===== 裝飾器：自動快取函數結果 =====

def cached_async(cache_manager: CacheManager, cache_type: str = "query"):
    """
    異步函數快取裝飾器

    Args:
        cache_manager: CacheManager 實例
        cache_type: 快取類型 ("query", "planning", "retrieval")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = CacheManager.generate_key(*args, **kwargs)

            # 嘗試從快取獲取
            cache = None
            if cache_type == "query":
                cache = cache_manager.query_cache
            elif cache_type == "planning":
                cache = cache_manager.planning_cache
            elif cache_type == "retrieval":
                cache = cache_manager.retrieval_cache

            if cache:
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    print(f"✅ 使用快取結果 ({cache_type}): {func.__name__}")
                    return cached_result

            # 執行函數
            result = await func(*args, **kwargs)

            # 存入快取
            if cache:
                cache.set(cache_key, result)

            return result

        return wrapper
    return decorator


# ===== 記憶體管理工具 =====

class MemoryManager:
    """記憶體管理器（對話歷史管理）"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 記憶體管理配置
        """
        self.max_history_turns = config.get('max_history_turns', 50)
        self.keep_recent_turns = config.get('keep_recent_turns', 30)
        self.auto_cleanup = config.get('auto_cleanup', True)

        print(f"✅ MemoryManager 初始化完成")
        print(f"   - 最大歷史輪數: {self.max_history_turns}")
        print(f"   - 保留最近輪數: {self.keep_recent_turns}")
        print(f"   - 自動清理: {self.auto_cleanup}")

    def should_cleanup(self, conversation_history: list) -> bool:
        """判斷是否需要清理"""
        return self.auto_cleanup and len(conversation_history) > self.max_history_turns

    def cleanup(self, conversation_history: list) -> Tuple[list, int]:
        """
        清理對話歷史

        Returns:
            (清理後的歷史, 清理的條目數)
        """
        if not self.should_cleanup(conversation_history):
            return conversation_history, 0

        original_len = len(conversation_history)
        cleaned = conversation_history[-self.keep_recent_turns:]
        removed = original_len - len(cleaned)

        print(f"🗑️ 自動清理對話歷史: 移除 {removed} 輪，保留最近 {len(cleaned)} 輪")

        return cleaned, removed

    def get_memory_info(self, conversation_history: list) -> Dict[str, Any]:
        """獲取記憶體使用資訊"""
        import sys

        memory_bytes = sys.getsizeof(conversation_history)

        # 計算所有對話內容的大小
        for query, answer in conversation_history:
            memory_bytes += sys.getsizeof(query) + sys.getsizeof(answer)

        return {
            "turns": len(conversation_history),
            "max_turns": self.max_history_turns,
            "memory_bytes": memory_bytes,
            "memory_mb": memory_bytes / (1024 * 1024),
            "usage_percent": len(conversation_history) / self.max_history_turns * 100
        }

    def print_memory_info(self, conversation_history: list):
        """打印記憶體資訊"""
        info = self.get_memory_info(conversation_history)

        print(f"\n📊 對話歷史記憶體資訊:")
        print(f"   -當前輪數: {info['turns']}/{info['max_turns']}")
        print(f"   - 記憶體使用: {info['memory_mb']:.2f} MB")
        print(f"   - 使用率: {info['usage_percent']:.1f}%\n")