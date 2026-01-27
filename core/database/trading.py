"""
交易相關資料庫操作
包含：自選清單
"""
from typing import List

from .connection import get_connection


# ============================================================================
# 自選清單 (Watchlist)
# ============================================================================

def add_to_watchlist(user_id: str, symbol: str):
    """新增幣種到自選清單"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO watchlist (user_id, symbol) VALUES (?, ?)', (user_id, symbol))
        conn.commit()
    finally:
        conn.close()


def remove_from_watchlist(user_id: str, symbol: str):
    """從自選清單移除幣種"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM watchlist WHERE user_id = ? AND symbol = ?', (user_id, symbol))
        conn.commit()
    finally:
        conn.close()


def get_watchlist(user_id: str) -> List[str]:
    """獲取用戶的自選清單"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT symbol FROM watchlist WHERE user_id = ?', (user_id,))
        rows = c.fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()
