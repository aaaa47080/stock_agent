"""
系統快取相關資料庫操作
"""
import json
from typing import Any, Optional

from .connection import get_connection


def set_cache(key: str, data: Any):
    """設定系統快取（存入 DB）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        c.execute('''
            INSERT INTO system_cache (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT(key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
        ''', (key, json_str))
        conn.commit()
    except Exception as e:
        print(f"Cache write error: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_cache(key: str) -> Optional[Any]:
    """獲取系統快取（從 DB 讀取）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT value FROM system_cache WHERE key = %s', (key,))
        row = c.fetchone()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        print(f"Cache read error: {e}")
        return None
    finally:
        conn.close()


def delete_cache(key: str) -> bool:
    """刪除快取"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM system_cache WHERE key = %s', (key,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def clear_all_cache():
    """清除所有快取"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM system_cache')
        conn.commit()
    finally:
        conn.close()
