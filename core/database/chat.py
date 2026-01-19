"""
對話歷史相關資料庫操作
包含：對話會話管理、對話訊息
"""
import json
from typing import List, Dict, Optional

from .connection import get_connection


# ============================================================================
# 對話會話 (Sessions)
# ============================================================================

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
        pin_val = 1 if is_pinned else 0
        c.execute('UPDATE sessions SET is_pinned = ? WHERE session_id = ?', (pin_val, session_id))
        conn.commit()
    finally:
        conn.close()


def get_sessions(user_id: str = "local_user", limit: int = 20) -> List[Dict]:
    """獲取用戶的對話列表（置頂優先）"""
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


# ============================================================================
# 對話訊息 (Chat Messages)
# ============================================================================

def save_chat_message(role: str, content: str, session_id: str = "default",
                      user_id: str = "local_user", metadata: Optional[Dict] = None):
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

            if current_title == "New Chat" and role == "user":
                new_title = content[:30] + "..." if len(content) > 30 else content
                c.execute('UPDATE sessions SET title = ?, updated_at = datetime("now") WHERE session_id = ?',
                          (new_title, session_id))
            else:
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
