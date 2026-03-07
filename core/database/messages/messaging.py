"""
私訊訊息操作
"""
from typing import Dict

from ..connection import get_connection
from .conversations import get_conversation_by_id
from .config import _get_message_config


def validate_message_send(from_user_id: str, to_user_id: str) -> Dict:
    """
    優化的訊息發送驗證（合併多個檢查到單一查詢）
    
    檢查：
    1. 發送者和接收者是否存在
    2. 是否為好友
    3. 是否被封鎖
    
    Returns:
        {
            "valid": bool,
            "error": str (如果 valid=False),
            "sender_exists": bool,
            "receiver_exists": bool,
            "are_friends": bool,
            "is_blocked": bool
        }
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 單一查詢檢查所有條件
        c.execute('''
            SELECT 
                EXISTS(SELECT 1 FROM users WHERE user_id = %s) as sender_exists,
                EXISTS(SELECT 1 FROM users WHERE user_id = %s) as receiver_exists,
                EXISTS(
                    SELECT 1 FROM friendships 
                    WHERE ((user_id = %s AND friend_id = %s) 
                           OR (user_id = %s AND friend_id = %s))
                    AND status = 'accepted'
                ) as are_friends,
                EXISTS(
                    SELECT 1 FROM friendships 
                    WHERE ((user_id = %s AND friend_id = %s) 
                           OR (user_id = %s AND friend_id = %s))
                    AND status = 'blocked'
                ) as is_blocked
        ''', (from_user_id, to_user_id, from_user_id, to_user_id, to_user_id, from_user_id, from_user_id, to_user_id, to_user_id, from_user_id))
        
        result = c.fetchone()
        sender_exists = result[0]
        receiver_exists = result[1]
        are_friends = result[2]
        is_blocked = result[3]
        
        # 驗證邏輯
        if not sender_exists:
            return {"valid": False, "error": "sender_not_found"}
        if not receiver_exists:
            return {"valid": False, "error": "receiver_not_found"}
        if is_blocked:
            return {"valid": False, "error": "blocked"}
        if not are_friends:
            return {"valid": False, "error": "not_friends"}
        
        return {
            "valid": True,
            "sender_exists": sender_exists,
            "receiver_exists": receiver_exists,
            "are_friends": are_friends,
            "is_blocked": is_blocked
        }
    finally:
        conn.close()


def send_message(from_user_id: str, to_user_id: str, content: str, message_type: str = 'text') -> Dict:
    """
    發送訊息（優化版：單一資料庫連接）
    """
    if from_user_id == to_user_id:
        return {"success": False, "error": "cannot_message_self"}

    if not content or not content.strip():
        return {"success": False, "error": "empty_content"}

    # 從資料庫讀取最大長度限制
    max_length = _get_message_config('limit_message_max_length', 500)
    if len(content) > max_length:
        return {"success": False, "error": "message_too_long", "max_length": max_length}

    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. 更新發送者最後活動時間（內聯，避免額外連接）
        c.execute('UPDATE users SET last_active_at = NOW() WHERE user_id = %s', (from_user_id,))
        
        # 2. 取得或建立對話（內聯，避免額外連接）
        # 排序確保唯一性
        user1_id, user2_id = (from_user_id, to_user_id) if from_user_id < to_user_id else (to_user_id, from_user_id)
        
        c.execute('''
            SELECT id, user1_id, user2_id
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        ''', (user1_id, user2_id))
        conv_row = c.fetchone()
        
        if conv_row:
            conversation_id = conv_row[0]
            conv_user1_id = conv_row[1]
            _ = conv_row[2]  # conv_user2_id not used
        else:
            # 建立新對話
            c.execute('''
                INSERT INTO dm_conversations (user1_id, user2_id, created_at)
                VALUES (%s, %s, NOW())
                RETURNING id
            ''', (user1_id, user2_id))
            conversation_id = c.fetchone()[0]
            conv_user1_id = user1_id
            _ = user2_id  # conv_user2_id not needed

        # 3. 插入訊息
        c.execute('''
            INSERT INTO dm_messages (conversation_id, from_user_id, to_user_id, content, message_type, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        ''', (conversation_id, from_user_id, to_user_id, content.strip(), message_type))
        message_id = c.fetchone()[0]

        # 4. 更新對話的最後訊息和未讀數
        if conv_user1_id == to_user_id:
            unread_field = "user1_unread_count"
        else:
            unread_field = "user2_unread_count"

        c.execute(f'''
            UPDATE dm_conversations
            SET last_message_id = %s,
                last_message_at = NOW(),
                {unread_field} = {unread_field} + 1
            WHERE id = %s
        ''', (message_id, conversation_id))

        # 5. 取得完整的訊息資料（包含用戶名稱）
        c.execute('''
            SELECT m.id, m.conversation_id, m.from_user_id, m.to_user_id, m.content,
                   m.message_type, m.is_read, m.read_at, m.created_at,
                   u1.username as from_username, u2.username as to_username
            FROM dm_messages m
            LEFT JOIN users u1 ON m.from_user_id = u1.user_id
            LEFT JOIN users u2 ON m.to_user_id = u2.user_id
            WHERE m.id = %s
        ''', (message_id,))
        msg_row = c.fetchone()

        conn.commit()

        return {
            "success": True,
            "message": {
                "id": msg_row[0],
                "conversation_id": msg_row[1],
                "from_user_id": msg_row[2],
                "to_user_id": msg_row[3],
                "content": msg_row[4],
                "message_type": msg_row[5],
                "is_read": bool(msg_row[6]),
                "read_at": msg_row[7].isoformat() if msg_row[7] else None,
                "created_at": msg_row[8].isoformat() if msg_row[8] else None,
                "from_username": msg_row[9],
                "to_username": msg_row[10]
            }
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_messages(conversation_id: int, user_id: str, limit: int = 50, before_id: int = None) -> Dict:
    """
    取得對話中的訊息（分頁）
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 驗證用戶是對話參與者 (內聯查詢，避免額外連接)
        c.execute('''
            SELECT id FROM dm_conversations
            WHERE id = %s AND (user1_id = %s OR user2_id = %s)
        ''', (conversation_id, user_id, user_id))
        if not c.fetchone():
            return {"success": False, "error": "conversation_not_found"}

        # 查詢訊息（包含用戶名稱，排除被當前用戶刪除的訊息）
        if before_id:
            c.execute('''
                SELECT m.id, m.conversation_id, m.from_user_id, m.to_user_id, m.content,
                       m.message_type, m.is_read, m.read_at, m.created_at,
                       u1.username as from_username, u2.username as to_username
                FROM dm_messages m
                LEFT JOIN users u1 ON m.from_user_id = u1.user_id
                LEFT JOIN users u2 ON m.to_user_id = u2.user_id
                LEFT JOIN dm_message_deletions d ON d.message_id = m.id AND d.user_id = %s
                WHERE m.conversation_id = %s AND m.id < %s AND d.id IS NULL
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT %s
            ''', (user_id, conversation_id, before_id, limit))
        else:
            c.execute('''
                SELECT m.id, m.conversation_id, m.from_user_id, m.to_user_id, m.content,
                       m.message_type, m.is_read, m.read_at, m.created_at,
                       u1.username as from_username, u2.username as to_username
                FROM dm_messages m
                LEFT JOIN users u1 ON m.from_user_id = u1.user_id
                LEFT JOIN users u2 ON m.to_user_id = u2.user_id
                LEFT JOIN dm_message_deletions d ON d.message_id = m.id AND d.user_id = %s
                WHERE m.conversation_id = %s AND d.id IS NULL
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT %s
            ''', (user_id, conversation_id, limit))

        rows = c.fetchall()

        messages = [
            {
                "id": row[0],
                "conversation_id": row[1],
                "from_user_id": row[2],
                "to_user_id": row[3],
                "content": row[4],
                "message_type": row[5],
                "is_read": bool(row[6]),
                "read_at": row[7].isoformat() if row[7] else None,
                "created_at": row[8].isoformat() if row[8] else None,
                "from_username": row[9],
                "to_username": row[10]
            }
            for row in rows
        ]

        # 反轉以按時間正序返回
        messages.reverse()

        return {
            "success": True,
            "messages": messages,
            "has_more": len(rows) == limit
        }
    finally:
        conn.close()


def mark_as_read(conversation_id: int, user_id: str) -> Dict:
    """
    標記對話中所有收到的訊息為已讀
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 驗證用戶是對話參與者
        conv = get_conversation_by_id(conversation_id, user_id)
        if not conv:
            return {"success": False, "error": "conversation_not_found"}

        c.execute('''
            UPDATE dm_messages
            SET is_read = 1, read_at = NOW()
            WHERE conversation_id = %s AND to_user_id = %s AND from_user_id != %s AND is_read = 0
        ''', (conversation_id, user_id, user_id))
        updated_count = c.rowcount

        # 重置對話中當前用戶的未讀數
        if conv["user1_id"] == user_id:
            c.execute('UPDATE dm_conversations SET user1_unread_count = 0 WHERE id = %s', (conversation_id,))
        else:
            c.execute('UPDATE dm_conversations SET user2_unread_count = 0 WHERE id = %s', (conversation_id,))

        conn.commit()

        return {
            "success": True,
            "marked_count": updated_count
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_unread_count(user_id: str) -> int:
    """
    取得用戶的總未讀訊息數
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT
                COALESCE(SUM(
                    CASE
                        WHEN user1_id = %s THEN user1_unread_count
                        ELSE user2_unread_count
                    END
                ), 0)
            FROM dm_conversations
            WHERE user1_id = %s OR user2_id = %s
        ''', (user_id, user_id, user_id))
        return c.fetchone()[0]
    finally:
        conn.close()
