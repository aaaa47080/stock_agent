"""
交易相關資料庫操作
包含：自選清單、預測、排行榜
"""
from typing import List, Dict

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


# ============================================================================
# 預測 (Social Trading)
# ============================================================================

def submit_prediction(user_id: str, username: str, symbol: str, direction: str, current_price: float):
    """提交用戶預測"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO predictions (user_id, username, symbol, direction, entry_price, timestamp)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (user_id, username, symbol, direction, current_price))
        conn.commit()
    finally:
        conn.close()


def get_leaderboard(limit: int = 10) -> List[Dict]:
    """獲取預測排行榜"""
    conn = get_connection()
    c = conn.cursor()
    try:
        query = '''
            SELECT username,
                   COUNT(*) as total_predictions,
                   SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins,
                   AVG(final_pnl_pct) as avg_pnl
            FROM predictions
            WHERE status != 'PENDING'
            GROUP BY user_id
            ORDER BY wins DESC, avg_pnl DESC
            LIMIT ?
        '''
        c.execute(query, (limit,))
        rows = c.fetchall()

        result = []
        for row in rows:
            win_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
            result.append({
                "username": row[0],
                "total_predictions": row[1],
                "wins": row[2],
                "win_rate": win_rate,
                "avg_pnl": row[3] or 0.0
            })
        return result
    finally:
        conn.close()


def get_user_predictions(user_id: str) -> List[Dict]:
    """獲取單個用戶的預測歷史"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT symbol, direction, entry_price, status, final_pnl_pct, timestamp
            FROM predictions
            WHERE user_id = ?
            ORDER BY timestamp DESC
        ''', (user_id,))
        rows = c.fetchall()
        return [
            {
                "symbol": r[0],
                "direction": r[1],
                "entry_price": r[2],
                "status": r[3],
                "pnl": r[4],
                "date": r[5]
            } for r in rows
        ]
    finally:
        conn.close()
