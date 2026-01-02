import sqlite3
import os
import json
from typing import List, Dict, Optional, Any
from datetime import datetime

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
    
    # 建立預測記錄表 (Social Trading)
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT, -- 用戶顯示名稱
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL, -- 'UP', 'DOWN'
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            entry_price REAL,
            status TEXT DEFAULT 'PENDING', -- 'PENDING', 'WIN', 'LOSS'
            final_pnl_pct REAL DEFAULT 0.0
        )
    ''')

    # 建立系統快取表 (System Cache)
    # 用於取代散落的 JSON 檔案，統一管理 Market Pulse, Funding Rates 等數據
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_cache (
            key TEXT PRIMARY KEY,
            value TEXT, -- JSON String
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# --- System Cache Functions ---

def set_cache(key: str, data: Any):
    """設定系統快取 (存入 DB)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        c.execute('''
            INSERT INTO system_cache (key, value, updated_at) 
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET 
                value = excluded.value,
                updated_at = excluded.updated_at
        ''', (key, json_str))
        conn.commit()
    except Exception as e:
        print(f"Cache write error: {e}")
    finally:
        conn.close()

def get_cache(key: str) -> Optional[Any]:
    """獲取系統快取 (從 DB 讀取)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT value FROM system_cache WHERE key = ?', (key,))
        row = c.fetchone()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        print(f"Cache read error: {e}")
        return None
    finally:
        conn.close()

# --- Watchlist Functions ---

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

# --- Social Trading Functions ---

def submit_prediction(user_id: str, username: str, symbol: str, direction: str, current_price: float):
    """提交用戶預測"""
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 簡單計算：勝場數最多的
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
    conn = sqlite3.connect(DB_PATH)
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

# 初始化
init_db()