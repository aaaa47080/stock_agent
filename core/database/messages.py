"""
私訊功能資料庫操作
包含：對話管理、訊息發送、已讀狀態、訊息限制
"""
from typing import List, Dict, Optional
from datetime import date, datetime

from .connection import get_connection


# ============================================================================
# 配置讀取輔助函數
# ============================================================================

def _get_message_config(key: str, default: any = None):
    """從 system_config 表讀取配置值"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT value, value_type FROM system_config WHERE key = %s', (key,))
        row = c.fetchone()
        if not row:
            return default

        value, value_type = row
        if value == 'null' or value is None:
            return None

        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        return value
    except Exception:
        return default
    finally:
        conn.close()


# ============================================================================
# 對話管理
# ============================================================================

def get_or_create_conversation(user1_id: str, user2_id: str) -> Dict:
    """
    取得或建立兩人之間的對話
    為確保唯一性，user1_id 和 user2_id 會被排序
    """
    # 排序以確保唯一性
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id

    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查是否已存在
        c.execute('''
            SELECT id, user1_id, user2_id, last_message_at, user1_unread_count, user2_unread_count, created_at
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        ''', (user1_id, user2_id))
        row = c.fetchone()

        if row:
            return {
                "id": row[0],
                "user1_id": row[1],
                "user2_id": row[2],
                "last_message_at": row[3].isoformat() if row[3] else None,
                "user1_unread_count": row[4],
                "user2_unread_count": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "is_new": False
            }

        # 建立新對話
        c.execute('''
            INSERT INTO dm_conversations (user1_id, user2_id, created_at)
            VALUES (%s, %s, NOW())
            RETURNING id
        ''', (user1_id, user2_id))
        conv_id = c.fetchone()[0]
        conn.commit()

        return {
            "id": conv_id,
            "user1_id": user1_id,
            "user2_id": user2_id,
            "last_message_at": None,
            "user1_unread_count": 0,
            "user2_unread_count": 0,
            "created_at": datetime.now().isoformat(),
            "is_new": True
        }
    finally:
        conn.close()


def get_conversations(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
    """
    取得用戶的對話列表，按最後訊息時間排序
    排除所有訊息都已被用戶刪除的對話
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT
                c.id,
                c.user1_id,
                c.user2_id,
                c.last_message_at,
                c.user1_unread_count,
                c.user2_unread_count,
                c.created_at,
                m.content as last_message,
                m.from_user_id as last_message_from,
                CASE WHEN c.user1_id = %s THEN u2.username ELSE u1.username END as other_username,
                CASE WHEN c.user1_id = %s THEN u2.user_id ELSE u1.user_id END as other_user_id,
                CASE WHEN c.user1_id = %s THEN u2.membership_tier ELSE u1.membership_tier END as other_membership_tier
            FROM dm_conversations c
            LEFT JOIN dm_messages m ON m.id = c.last_message_id
            LEFT JOIN users u1 ON u1.user_id = c.user1_id
            LEFT JOIN users u2 ON u2.user_id = c.user2_id
            WHERE (c.user1_id = %s OR c.user2_id = %s)
            -- 排除所有訊息都被刪除的對話
            AND EXISTS (
                SELECT 1 FROM dm_messages msg
                LEFT JOIN dm_message_deletions del ON del.message_id = msg.id AND del.user_id = %s
                WHERE msg.conversation_id = c.id AND del.id IS NULL
            )
            ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC
            LIMIT %s OFFSET %s
        ''', (user_id, user_id, user_id, user_id, user_id, user_id, limit, offset))

        rows = c.fetchall()
        conversations = []

        for row in rows:
            conv_id, user1_id, user2_id, last_message_at, user1_unread, user2_unread, created_at, last_message, last_message_from, other_username, other_user_id, other_membership_tier = row

            # 根據當前用戶決定未讀數
            unread_count = user1_unread if user_id == user1_id else user2_unread

            conversations.append({
                "id": conv_id,
                "other_user_id": other_user_id,
                "other_username": other_username or other_user_id,
                "other_membership_tier": other_membership_tier or 'free',
                "last_message": last_message,
                "last_message_from": last_message_from,
                "last_message_at": last_message_at.isoformat() if last_message_at else None,
                "unread_count": unread_count,
                "created_at": created_at.isoformat() if created_at else None
            })

        return conversations
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"get_conversations error for user {user_id}: {str(e)}", exc_info=True)
        raise
    finally:
        conn.close()


def get_conversation_by_id(conversation_id: int, user_id: str) -> Optional[Dict]:
    """
    取得特定對話（驗證用戶是參與者）
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT id, user1_id, user2_id, last_message_at, user1_unread_count, user2_unread_count
            FROM dm_conversations
            WHERE id = %s AND (user1_id = %s OR user2_id = %s)
        ''', (conversation_id, user_id, user_id))
        row = c.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user1_id": row[1],
            "user2_id": row[2],
            "last_message_at": row[3].isoformat() if row[3] else None,
            "user1_unread_count": row[4],
            "user2_unread_count": row[5]
        }
    finally:
        conn.close()


# ============================================================================
# 訊息操作
# ============================================================================

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
            conv_user2_id = conv_row[2]
        else:
            # 建立新對話
            c.execute('''
                INSERT INTO dm_conversations (user1_id, user2_id, created_at)
                VALUES (%s, %s, NOW())
                RETURNING id
            ''', (user1_id, user2_id))
            conversation_id = c.fetchone()[0]
            conv_user1_id = user1_id
            conv_user2_id = user2_id

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


# ============================================================================
# 訊息限制
# ============================================================================

def check_message_limit(user_id: str, is_pro: bool) -> Dict:
    """
    檢查用戶是否超過每日訊息限制
    返回: {"can_send": bool, "remaining": int, "limit": int}
    """
    # Pro 會員：檢查是否有限制
    if is_pro:
        pro_limit = _get_message_config('limit_daily_message_premium', None)
        if pro_limit is None:
            return {"can_send": True, "remaining": -1, "limit": -1}  # -1 表示無限

    # 從資料庫讀取限制配置
    daily_limit = _get_message_config('limit_daily_message_free', 20)
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT message_count FROM user_message_limits
            WHERE user_id = %s AND date = %s
        ''', (user_id, today))
        row = c.fetchone()

        current_count = row[0] if row else 0
        remaining = daily_limit - current_count

        return {
            "can_send": remaining > 0,
            "remaining": max(0, remaining),
            "limit": daily_limit,
            "used": current_count
        }
    finally:
        conn.close()


def increment_message_count(user_id: str) -> None:
    """
    增加用戶的每日訊息計數
    """
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO user_message_limits (user_id, date, message_count)
            VALUES (%s, %s, 1)
            ON CONFLICT(user_id, date) DO UPDATE SET message_count = user_message_limits.message_count + 1
        ''', (user_id, today))
        conn.commit()
    finally:
        conn.close()


def check_greeting_limit(user_id: str, is_pro: bool) -> Dict:
    """
    檢查 Pro 用戶的每月打招呼限制
    返回: {"can_send": bool, "remaining": int, "limit": int}
    """
    if not is_pro:
        return {"can_send": False, "remaining": 0, "limit": 0, "error": "pro_only"}

    # 從資料庫讀取限制配置
    monthly_limit = _get_message_config('limit_monthly_greeting', 5)
    current_month = date.today().strftime('%Y-%m')

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT greeting_count, greeting_month FROM user_message_limits
            WHERE user_id = %s AND date = %s
        ''', (user_id, date.today().isoformat()))
        row = c.fetchone()

        if row and row[1] == current_month:
            current_count = row[0]
        else:
            current_count = 0

        remaining = monthly_limit - current_count

        return {
            "can_send": remaining > 0,
            "remaining": max(0, remaining),
            "limit": monthly_limit,
            "used": current_count
        }
    finally:
        conn.close()


def increment_greeting_count(user_id: str) -> None:
    """
    增加用戶的每月打招呼計數
    """
    today = date.today().isoformat()
    current_month = date.today().strftime('%Y-%m')

    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查是否需要重置（新月份）
        c.execute('''
            SELECT greeting_month FROM user_message_limits
            WHERE user_id = %s AND date = %s
        ''', (user_id, today))
        row = c.fetchone()

        if row and row[0] != current_month:
            # 新月份，重置計數
            c.execute('''
                UPDATE user_message_limits
                SET greeting_count = 1, greeting_month = %s
                WHERE user_id = %s AND date = %s
            ''', (current_month, user_id, today))
        else:
            c.execute('''
                INSERT INTO user_message_limits (user_id, date, greeting_count, greeting_month)
                VALUES (%s, %s, 1, %s)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    greeting_count = CASE
                        WHEN user_message_limits.greeting_month = %s THEN user_message_limits.greeting_count + 1
                        ELSE 1
                    END,
                    greeting_month = %s
            ''', (user_id, today, current_month, current_month, current_month))

        conn.commit()
    finally:
        conn.close()


# ============================================================================
# 打招呼功能（Pro 專屬：發給非好友）
# ============================================================================

def send_greeting(from_user_id: str, to_user_id: str, content: str) -> Dict:
    """
    發送打招呼訊息（Pro 會員專屬，可發給非好友）
    """
    return send_message(from_user_id, to_user_id, content, message_type='greeting')


# ============================================================================
# 訊息搜尋（Pro 專屬）
# ============================================================================

def search_messages(user_id: str, query: str, limit: int = 50) -> List[Dict]:
    """
    搜尋用戶的訊息內容
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT
                m.id, m.conversation_id, m.from_user_id, m.to_user_id,
                m.content, m.message_type, m.created_at,
                CASE WHEN c.user1_id = %s THEN u2.username ELSE u1.username END as other_username,
                CASE WHEN c.user1_id = %s THEN c.user2_id ELSE c.user1_id END as other_user_id
            FROM dm_messages m
            JOIN dm_conversations c ON c.id = m.conversation_id
            LEFT JOIN users u1 ON u1.user_id = c.user1_id
            LEFT JOIN users u2 ON u2.user_id = c.user2_id
            WHERE (c.user1_id = %s OR c.user2_id = %s)
            AND m.content LIKE %s
            ORDER BY m.created_at DESC
            LIMIT %s
        ''', (user_id, user_id, user_id, user_id, f'%{query}%', limit))

        rows = c.fetchall()

        return [
            {
                "id": row[0],
                "conversation_id": row[1],
                "from_user_id": row[2],
                "to_user_id": row[3],
                "content": row[4],
                "message_type": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "other_username": row[7],
                "other_user_id": row[8]
            }
            for row in rows
        ]
    finally:
        conn.close()


# ============================================================================
# 輔助函數
# ============================================================================


def delete_dm_message(message_id: int, user_id: str) -> Dict:
    """
    收回私訊訊息 (僅限發送者)
    不會真的刪除訊息，而是標記為已收回，讓對方看到「訊息已收回」
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查訊息是否存在且發送者是否為當前用戶
        c.execute('SELECT from_user_id, message_type FROM dm_messages WHERE id = %s', (message_id,))
        row = c.fetchone()

        if not row:
            return {"success": False, "error": "message_not_found"}

        if row[0] != user_id:
            return {"success": False, "error": "permission_denied"}

        if row[1] == 'recalled':
            return {"success": False, "error": "already_recalled"}

        # 收回訊息：將 message_type 設為 'recalled'，保留原始內容但前端不顯示
        c.execute('''
            UPDATE dm_messages
            SET message_type = 'recalled'
            WHERE id = %s
        ''', (message_id,))
        conn.commit()

        return {"success": True, "recalled": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def hide_dm_message_for_user(message_id: int, user_id: str) -> Dict:
    """
    隱藏私訊訊息（只對自己隱藏，不影響對方）
    類似 WhatsApp 的「為我刪除」功能
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查訊息是否存在
        c.execute('SELECT id FROM dm_messages WHERE id = %s', (message_id,))
        if not c.fetchone():
            return {"success": False, "error": "message_not_found"}

        # 插入刪除記錄（使用 ON CONFLICT 避免重複）
        c.execute('''
            INSERT INTO dm_message_deletions (message_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (message_id, user_id) DO NOTHING
        ''', (message_id, user_id))
        conn.commit()

        return {"success": True, "hidden": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_conversation_with_user(user_id: str, other_user_id: str) -> Optional[Dict]:
    """
    取得與特定用戶的對話
    """
    # 排序以匹配資料庫中的儲存方式
    u1, u2 = (user_id, other_user_id) if user_id < other_user_id else (other_user_id, user_id)

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT id, user1_id, user2_id, last_message_at
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        ''', (u1, u2))
        row = c.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user1_id": row[1],
            "user2_id": row[2],
            "last_message_at": row[3].isoformat() if row[3] else None
        }
    finally:
        conn.close()


def get_conversation_with_messages(user_id: str, other_user_id: str, limit: int = 50) -> Dict:
    """
    一次性取得對話和訊息（優化版本，只用一個連接）
    """
    # 排序以確保唯一性
    u1, u2 = (user_id, other_user_id) if user_id < other_user_id else (other_user_id, user_id)

    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. 檢查或建立對話
        c.execute('''
            SELECT id, user1_id, user2_id, last_message_at, user1_unread_count, user2_unread_count, created_at
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        ''', (u1, u2))
        row = c.fetchone()

        if row:
            conv = {
                "id": row[0],
                "user1_id": row[1],
                "user2_id": row[2],
                "last_message_at": row[3].isoformat() if row[3] else None,
                "user1_unread_count": row[4],
                "user2_unread_count": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "is_new": False
            }
        else:
            # 建立新對話
            c.execute('''
                INSERT INTO dm_conversations (user1_id, user2_id, created_at)
                VALUES (%s, %s, NOW())
                RETURNING id, created_at
            ''', (u1, u2))
            new_row = c.fetchone()
            conn.commit()
            conv = {
                "id": new_row[0],
                "user1_id": u1,
                "user2_id": u2,
                "last_message_at": None,
                "user1_unread_count": 0,
                "user2_unread_count": 0,
                "created_at": new_row[1].isoformat() if new_row[1] else None,
                "is_new": True
            }

        # 2. 取得訊息（使用同一個連接，排除被當前用戶刪除的訊息）
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
        ''', (user_id, conv["id"], limit))

        rows = c.fetchall()
        messages = [
            {
                "id": r[0],
                "conversation_id": r[1],
                "from_user_id": r[2],
                "to_user_id": r[3],
                "content": r[4],
                "message_type": r[5],
                "is_read": bool(r[6]),
                "read_at": r[7].isoformat() if r[7] else None,
                "created_at": r[8].isoformat() if r[8] else None,
                "from_username": r[9],
                "to_username": r[10]
            }
            for r in rows
        ]
        messages.reverse()  # 按時間正序

        # 檢查是否有更多
        has_more = len(rows) >= limit

        return {
            "success": True,
            "conversation": conv,
            "messages": messages,
            "has_more": has_more
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def hide_conversation_for_user(conversation_id: int, user_id: str) -> Dict:
    """
    隱藏整段對話（刪除對話，只對自己隱藏所有訊息）
    類似 WhatsApp 的「刪除對話」功能
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 驗證用戶是對話參與者
        c.execute('''
            SELECT id FROM dm_conversations
            WHERE id = %s AND (user1_id = %s OR user2_id = %s)
        ''', (conversation_id, user_id, user_id))
        if not c.fetchone():
            return {"success": False, "error": "conversation_not_found"}

        # 獲取該對話中所有訊息的 ID
        c.execute('''
            SELECT id FROM dm_messages
            WHERE conversation_id = %s
        ''', (conversation_id,))
        message_ids = [row[0] for row in c.fetchall()]

        if not message_ids:
            # 沒有訊息，但對話存在，仍然返回成功
            return {"success": True, "hidden_count": 0}

        # 批量插入刪除記錄（使用 ON CONFLICT 避免重複）
        values = [(msg_id, user_id) for msg_id in message_ids]
        from psycopg2.extras import execute_values
        execute_values(c, '''
            INSERT INTO dm_message_deletions (message_id, user_id)
            VALUES %s
            ON CONFLICT (message_id, user_id) DO NOTHING
        ''', values)
        
        conn.commit()

        return {"success": True, "hidden_count": len(message_ids)}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
