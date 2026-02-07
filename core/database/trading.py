"""
交易相關資料庫操作
包含：自選清單

Refactored to use DatabaseBase for unified CRUD operations.
"""
from typing import List

from .base import DatabaseBase


# ============================================================================
# 自選清單 (Watchlist)
# ============================================================================

def add_to_watchlist(user_id: str, symbol: str):
    """新增幣種到自選清單"""
    DatabaseBase.execute(
        'INSERT INTO watchlist (user_id, symbol) VALUES (%s, %s) ON CONFLICT DO NOTHING',
        (user_id, symbol)
    )


def remove_from_watchlist(user_id: str, symbol: str):
    """從自選清單移除幣種"""
    DatabaseBase.execute(
        'DELETE FROM watchlist WHERE user_id = %s AND symbol = %s',
        (user_id, symbol)
    )


def get_watchlist(user_id: str) -> List[str]:
    """獲取用戶的自選清單"""
    results = DatabaseBase.query_all(
        'SELECT symbol FROM watchlist WHERE user_id = %s',
        (user_id,)
    )
    return [row['symbol'] for row in results]
