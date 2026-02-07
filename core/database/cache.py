"""
系統快取相關資料庫操作

Refactored to use DatabaseBase for unified CRUD operations.
"""
import json
from typing import Any, Optional

from .base import DatabaseBase


def set_cache(key: str, data: Any):
    """設定系統快取（存入 DB）"""
    json_str = json.dumps(data, ensure_ascii=False)
    DatabaseBase.execute('''
        INSERT INTO system_cache (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT(key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
    ''', (key, json_str))


def get_cache(key: str) -> Optional[Any]:
    """獲取系統快取（從 DB 讀取）"""
    result = DatabaseBase.query_one(
        'SELECT value FROM system_cache WHERE key = %s',
        (key,)
    )
    if result:
        try:
            return json.loads(result['value'])
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Cache read error: {e}")
            return None
    return None


def delete_cache(key: str) -> bool:
    """刪除快取"""
    rows_affected = DatabaseBase.execute(
        'DELETE FROM system_cache WHERE key = %s',
        (key,)
    )
    return rows_affected > 0


def clear_all_cache():
    """清除所有快取"""
    DatabaseBase.execute('DELETE FROM system_cache')
