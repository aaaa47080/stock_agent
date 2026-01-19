import sqlite3
import os
import json
import hashlib
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_data.db")

# 追蹤資料庫是否已初始化
_db_initialized = False

def get_connection() -> sqlite3.Connection:
    """
    獲取資料庫連接，確保資料庫和表存在
    如果資料庫文件被刪除，會自動重新初始化
    """
    global _db_initialized

    # 如果資料庫文件不存在，需要重新初始化
    if not os.path.exists(DB_PATH):
        _db_initialized = False

    # 如果尚未初始化，執行初始化
    if not _db_initialized:
        init_db()
        _db_initialized = True

    return sqlite3.connect(DB_PATH)

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
    
    # 建立對話歷史表 (Conversation History)
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT DEFAULT 'default',
            user_id TEXT DEFAULT 'local_user',
            role TEXT NOT NULL,  -- 'user' or 'assistant'
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT  -- JSON String for extra info (symbol, tool_used, etc.)
        )
    ''')

    # 建立對話會話表 (Sessions) - 用於管理左側列表
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'local_user',
            title TEXT,
            is_pinned INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 建立用戶表 (Users) - 統一管理所有登入方式
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            email TEXT UNIQUE,
            auth_method TEXT DEFAULT 'password',
            pi_uid TEXT UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 遷移：為舊表添加新欄位（如果不存在）
    try:
        c.execute('ALTER TABLE users ADD COLUMN auth_method TEXT DEFAULT "password"')
    except sqlite3.OperationalError:
        pass  # 欄位已存在
    try:
        c.execute('ALTER TABLE users ADD COLUMN pi_uid TEXT UNIQUE')
    except sqlite3.OperationalError:
        pass  # 欄位已存在

    # 建立密碼重置 Token 表
    c.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 建立登入嘗試記錄表 (防暴力破解)
    c.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT,
            attempt_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
    ''')

    # Migration for existing sessions table
    try:
        c.execute('ALTER TABLE sessions ADD COLUMN is_pinned INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        # Column likely already exists
        pass
    
    conn.commit()
    conn.close()

# --- System Cache Functions ---

def set_cache(key: str, data: Any):
    """設定系統快取 (存入 DB)"""
    conn = get_connection()
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
    conn = get_connection()
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

# --- Social Trading Functions ---

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

# --- Chat History Functions (New) ---

def create_session(session_id: str, title: str = "New Chat", user_id: str = "local_user"):
    """創建新對話會話"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO sessions (session_id, user_id, title, is_pinned, created_at, updated_at)
            VALUES (?, ?, ?, 0, datetime('now'), datetime('now'))
        ''', (session_id, user_id, title))
        conn.commit()
    except Exception as e:
        print(f"Session create error: {e}")
    finally:
        conn.close()

def update_session_title(session_id: str, title: str):
    """更新對話標題"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE sessions SET title = ?, updated_at = datetime("now") WHERE session_id = ?', (title, session_id))
        conn.commit()
    finally:
        conn.close()

def toggle_session_pin(session_id: str, is_pinned: bool):
    """切換對話置頂狀態"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # Convert bool to int (0 or 1)
        pin_val = 1 if is_pinned else 0
        c.execute('UPDATE sessions SET is_pinned = ? WHERE session_id = ?', (pin_val, session_id))
        conn.commit()
    finally:
        conn.close()

def get_sessions(user_id: str = "local_user", limit: int = 20) -> List[Dict]:
    """獲取用戶的對話列表 (置頂優先)"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT session_id, title, created_at, updated_at, is_pinned
            FROM sessions 
            WHERE user_id = ? 
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT ?
        ''', (user_id, limit))
        rows = c.fetchall()
        
        sessions = []
        for row in rows:
            sessions.append({
                "id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "is_pinned": bool(row[4])
            })
        return sessions
    except Exception as e:
        print(f"Session list error: {e}")
        return []
    finally:
        conn.close()

def delete_session(session_id: str):
    """刪除對話會話及其歷史"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        c.execute('DELETE FROM conversation_history WHERE session_id = ?', (session_id,))
        conn.commit()
    finally:
        conn.close()

def save_chat_message(role: str, content: str, session_id: str = "default", user_id: str = "local_user", metadata: Optional[Dict] = None):
    """保存對話訊息，並自動更新 session 的 updated_at 和標題"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. 保存訊息
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        c.execute('''
            INSERT INTO conversation_history (session_id, user_id, role, content, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (session_id, user_id, role, content, metadata_json))

        # 2. 檢查 Session 是否存在
        c.execute('SELECT title FROM sessions WHERE session_id = ?', (session_id,))
        row = c.fetchone()

        if not row:
            # Session 不存在，創建新的
            title = content[:30] + "..." if len(content) > 30 else content
            if role == 'assistant':
                title = "AI Analysis"

            c.execute('''
                INSERT INTO sessions (session_id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
            ''', (session_id, user_id, title))
        else:
            # Session 存在，檢查是否需要更新標題
            current_title = row[0]

            # 如果標題是 "New Chat" 且這是用戶訊息，則用用戶的第一句話作為標題
            if current_title == "New Chat" and role == "user":
                new_title = content[:30] + "..." if len(content) > 30 else content
                c.execute('UPDATE sessions SET title = ?, updated_at = datetime("now") WHERE session_id = ?',
                         (new_title, session_id))
            else:
                # 只更新 updated_at
                c.execute('UPDATE sessions SET updated_at = datetime("now") WHERE session_id = ?', (session_id,))

        conn.commit()
    except Exception as e:
        print(f"Chat save error: {e}")
    finally:
        conn.close()


def get_chat_history(session_id: str = "default", limit: int = 50) -> List[Dict]:
    """獲取對話歷史"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT role, content, metadata, timestamp 
            FROM conversation_history 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
            LIMIT ?
        ''', (session_id, limit))
        rows = c.fetchall()
        
        history = []
        for row in rows:
            metadata = json.loads(row[2]) if row[2] else None
            history.append({
                "role": row[0],
                "content": row[1],
                "metadata": metadata,
                "timestamp": row[3]
            })
        return history
    except Exception as e:
        print(f"Chat history read error: {e}")
        return []
    finally:
        conn.close()

def clear_chat_history(session_id: str = "default"):
    """清除特定 session 的對話歷史"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM conversation_history WHERE session_id = ?', (session_id,))
        conn.commit()
    finally:
        conn.close()

# 初始化
init_db()

# --- User Authentication Functions ---

def hash_password(password: str) -> str:
    """使用 SHA-256 和隨機鹽值雜湊密碼"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + key.hex()

def verify_password(stored_password: str, provided_password: str) -> bool:
    """驗證密碼"""
    try:
        salt_hex, key_hex = stored_password.split(':')
        salt = bytes.fromhex(salt_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return new_key.hex() == key_hex
    except Exception:
        return False

def create_user(username: str, password: str, email: str = None) -> Dict:
    """創建新用戶"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查 email 是否已被使用
        if email:
            c.execute('SELECT user_id FROM users WHERE email = ?', (email,))
            if c.fetchone():
                raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        password_hash = hash_password(password)

        c.execute('''
            INSERT INTO users (user_id, username, password_hash, email, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (user_id, username, password_hash, email))
        conn.commit()
        return {"user_id": user_id, "username": username}
    except sqlite3.IntegrityError as e:
        if "email" in str(e).lower():
            raise ValueError("Email already registered")
        raise ValueError("Username already exists")
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict]:
    """根據用戶名獲取用戶信息（包含密碼雜湊）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, password_hash, email FROM users WHERE username = ?', (username,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "email": row[3]
            }
        return None
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict]:
    """根據 Email 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, password_hash, email FROM users WHERE email = ?', (email,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "email": row[3]
            }
        return None
    finally:
        conn.close()

def update_password(user_id: str, new_password: str) -> bool:
    """更新用戶密碼"""
    conn = get_connection()
    c = conn.cursor()
    try:
        password_hash = hash_password(new_password)
        c.execute('UPDATE users SET password_hash = ? WHERE user_id = ?', (password_hash, user_id))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Update password error: {e}")
        return False
    finally:
        conn.close()

# --- Pi Network User Functions ---

def create_or_get_pi_user(pi_uid: str, username: str) -> Dict:
    """
    創建或獲取 Pi Network 用戶
    - 如果 pi_uid 已存在，返回現有用戶
    - 如果 username 被其他用戶使用，拋出錯誤
    - 否則創建新用戶
    """
    print(f"[DEBUG] create_or_get_pi_user called: pi_uid={pi_uid}, username={username}")
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查 pi_uid 是否已存在
        c.execute('SELECT user_id, username, auth_method FROM users WHERE pi_uid = ?', (pi_uid,))
        row = c.fetchone()
        if row:
            print(f"[DEBUG] Found existing Pi user: {row}")
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "is_new": False
            }

        # 檢查 username 是否被其他用戶使用
        c.execute('SELECT user_id, auth_method FROM users WHERE username = ?', (username,))
        existing = c.fetchone()
        if existing:
            print(f"[DEBUG] Username conflict: {username} used by user_id={existing[0]}, auth_method={existing[1]}")
            raise ValueError(f"Username '{username}' is already used by another account")

        # 創建新 Pi 用戶
        print(f"[DEBUG] Creating new Pi user: pi_uid={pi_uid}, username={username}")
        user_id = pi_uid  # 使用 Pi UID 作為 user_id
        c.execute('''
            INSERT INTO users (user_id, username, password_hash, auth_method, pi_uid, created_at)
            VALUES (?, ?, NULL, 'pi_network', ?, datetime('now'))
        ''', (user_id, username, pi_uid))
        conn.commit()
        print(f"[DEBUG] Pi user created successfully: user_id={user_id}")

        return {
            "user_id": user_id,
            "username": username,
            "auth_method": "pi_network",
            "is_new": True
        }
    except ValueError:
        raise  # 重新拋出 ValueError (用戶名衝突)
    except Exception as e:
        print(f"[ERROR] create_or_get_pi_user failed: {type(e).__name__}: {e}")
        raise
    finally:
        conn.close()

def get_user_by_pi_uid(pi_uid: str) -> Optional[Dict]:
    """根據 Pi UID 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, auth_method, created_at FROM users WHERE pi_uid = ?', (pi_uid,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "created_at": row[3]
            }
        return None
    finally:
        conn.close()

def is_username_available(username: str) -> bool:
    """檢查用戶名是否可用（同時檢查 Pi 和 Email 用戶）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT 1 FROM users WHERE username = ?', (username,))
        return c.fetchone() is None
    finally:
        conn.close()

# --- Password Reset Token Functions ---

def create_reset_token(user_id: str, expires_minutes: int = 30) -> str:
    """創建密碼重置 Token（30 分鐘有效）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 先清除該用戶舊的 token
        c.execute('DELETE FROM password_reset_tokens WHERE user_id = ?', (user_id,))

        # 生成新 token
        token = str(uuid.uuid4())
        c.execute('''
            INSERT INTO password_reset_tokens (token, user_id, created_at, expires_at)
            VALUES (?, ?, datetime('now'), datetime('now', '+' || ? || ' minutes'))
        ''', (token, user_id, expires_minutes))
        conn.commit()
        return token
    except Exception as e:
        print(f"Create reset token error: {e}")
        return None
    finally:
        conn.close()

def get_reset_token(token: str) -> Optional[Dict]:
    """驗證重置 Token 並返回用戶信息（檢查是否過期）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT user_id, expires_at
            FROM password_reset_tokens
            WHERE token = ? AND expires_at > datetime('now')
        ''', (token,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "expires_at": row[1]
            }
        return None
    finally:
        conn.close()

def delete_reset_token(token: str) -> bool:
    """刪除已使用的重置 Token"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE token = ?', (token,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Delete reset token error: {e}")
        return False
    finally:
        conn.close()

def cleanup_expired_tokens():
    """清理過期的 Token（可定期執行）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE expires_at < datetime("now")')
        conn.commit()
    finally:
        conn.close()

# --- Login Attempt Functions (防暴力破解) ---

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_HOURS = 24

def record_login_attempt(username: str, success: bool, ip_address: str = None):
    """記錄登入嘗試"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO login_attempts (username, ip_address, attempt_time, success)
            VALUES (?, ?, datetime('now'), ?)
        ''', (username, ip_address, 1 if success else 0))
        conn.commit()

        # 登入成功後清除該用戶的失敗記錄
        if success:
            c.execute('''
                DELETE FROM login_attempts
                WHERE username = ? AND success = 0
            ''', (username,))
            conn.commit()
    finally:
        conn.close()

def get_failed_attempts(username: str, hours: int = LOCKOUT_HOURS) -> int:
    """獲取指定時間內的失敗登入次數"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT COUNT(*) FROM login_attempts
            WHERE username = ?
              AND success = 0
              AND attempt_time > datetime('now', '-' || ? || ' hours')
        ''', (username, hours))
        return c.fetchone()[0]
    finally:
        conn.close()

def is_account_locked(username: str) -> tuple:
    """
    檢查帳號是否被鎖定
    返回: (is_locked: bool, remaining_minutes: int)
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        failed_count = get_failed_attempts(username, LOCKOUT_HOURS)

        if failed_count >= MAX_LOGIN_ATTEMPTS:
            # 獲取最後一次失敗的時間，計算剩餘鎖定時間
            c.execute('''
                SELECT attempt_time FROM login_attempts
                WHERE username = ? AND success = 0
                ORDER BY attempt_time DESC
                LIMIT 1
            ''', (username,))
            row = c.fetchone()
            if row:
                from datetime import datetime, timedelta
                latest_attempt = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                unlock_time = latest_attempt + timedelta(hours=LOCKOUT_HOURS)
                now = datetime.utcnow()
                if now < unlock_time:
                    remaining = (unlock_time - now).total_seconds() / 60
                    return (True, int(remaining))

        return (False, 0)
    finally:
        conn.close()

def clear_login_attempts(username: str):
    """清除用戶的登入嘗試記錄（管理員用）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM login_attempts WHERE username = ?', (username,))
        conn.commit()
    finally:
        conn.close()