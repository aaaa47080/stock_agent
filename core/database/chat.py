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
            VALUES (%s, %s, %s, 0, NOW(), NOW())
        ''', (session_id, user_id, title))
        conn.commit()
    except Exception as e:
        print(f"Session create error: {e}")
        conn.rollback()
    finally:
        conn.close()


def update_session_title(session_id: str, title: str):
    """更新對話標題"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE sessions SET title = %s, updated_at = NOW() WHERE session_id = %s', (title, session_id))
        conn.commit()
    finally:
        conn.close()


def toggle_session_pin(session_id: str, is_pinned: bool):
    """切換對話置頂狀態"""
    conn = get_connection()
    c = conn.cursor()
    try:
        pin_val = 1 if is_pinned else 0
        c.execute('UPDATE sessions SET is_pinned = %s WHERE session_id = %s', (pin_val, session_id))
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
            WHERE user_id = %s
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT %s
        ''', (user_id, limit))
        rows = c.fetchall()

        sessions = []
        for row in rows:
            created_at = row[2]
            updated_at = row[3]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            if updated_at and not isinstance(updated_at, str):
                updated_at = updated_at.strftime('%Y-%m-%d %H:%M:%S')
            sessions.append({
                "id": row[0],
                "title": row[1],
                "created_at": created_at,
                "updated_at": updated_at,
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
        c.execute('DELETE FROM sessions WHERE session_id = %s', (session_id,))
        c.execute('DELETE FROM conversation_history WHERE session_id = %s', (session_id,))
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
            VALUES (%s, %s, %s, %s, %s, NOW())
        ''', (session_id, user_id, role, content, metadata_json))

        # 2. 檢查 Session 是否存在
        c.execute('SELECT title FROM sessions WHERE session_id = %s', (session_id,))
        row = c.fetchone()

        if not row:
            # Session 不存在，創建新的
            title = content[:30] + "..." if len(content) > 30 else content
            if role == 'assistant':
                title = "AI Analysis"

            c.execute('''
                INSERT INTO sessions (session_id, user_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            ''', (session_id, user_id, title))
        else:
            # Session 存在，檢查是否需要更新標題
            current_title = row[0]

            if current_title == "New Chat" and role == "user":
                new_title = content[:30] + "..." if len(content) > 30 else content
                c.execute('UPDATE sessions SET title = %s, updated_at = NOW() WHERE session_id = %s',
                          (new_title, session_id))
            else:
                c.execute('UPDATE sessions SET updated_at = NOW() WHERE session_id = %s', (session_id,))

        conn.commit()
    except Exception as e:
        print(f"Chat save error: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_chat_history(
    session_id: str = "default",
    limit: int = 20,
    before_timestamp: str = None,
) -> List[Dict]:
    """獲取對話歷史（最新 limit 條，ASC 排序）。

    before_timestamp: 若提供，只返回比此時間更早的訊息（向上捲動載入舊訊息用）。
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        if before_timestamp:
            c.execute('''
                SELECT role, content, metadata, timestamp
                FROM conversation_history
                WHERE session_id = %s AND timestamp < %s
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (session_id, before_timestamp, limit))
        else:
            c.execute('''
                SELECT role, content, metadata, timestamp
                FROM conversation_history
                WHERE session_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (session_id, limit))

        rows = list(reversed(c.fetchall()))  # DESC 取到後反轉成 ASC

        history = []
        for row in rows:
            metadata = json.loads(row[2]) if row[2] else None
            timestamp = row[3]
            if timestamp and not isinstance(timestamp, str):
                timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            history.append({
                "role": row[0],
                "content": row[1],
                "metadata": metadata,
                "timestamp": timestamp
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
        c.execute('DELETE FROM conversation_history WHERE session_id = %s', (session_id,))
        conn.commit()
    finally:
        conn.close()
