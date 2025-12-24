import sqlite3
import os
from typing import List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_data.db")

def init_db():
    """初始化資料庫"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 建立自選清單資料表
    c.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id TEXT,
            symbol TEXT,
            PRIMARY KEY (user_id, symbol)
        )
    ''')
    conn.commit()
    conn.close()

def add_to_watchlist(user_id: str, symbol: str):
    """新增幣種到自選清單"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO watchlist (user_id, symbol) VALUES (?, ?)', (user_id, symbol))
        conn.commit()
    finally:
        conn.close()

def remove_from_watchlist(user_id: str, symbol: str):
    """從自選清單移除幣種"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('DELETE FROM watchlist WHERE user_id = ? AND symbol = ?', (user_id, symbol))
        conn.commit()
    finally:
        conn.close()

def get_watchlist(user_id: str) -> List[str]:
    """獲取用戶的自選清單"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT symbol FROM watchlist WHERE user_id = ?', (user_id,))
        rows = c.fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()

# 初始化
init_db()
