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
        c.execute('SELECT value, value_type FROM system_config WHERE key = ?', (key,))
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
            WHERE user1_id = ? AND user2_id = ?
        ''', (user1_id, user2_id))
        row = c.fetchone()

        if row:
            return {
                "id": row[0],
                "user1_id": row[1],
                "user2_id": row[2],
                "last_message_at": row[3],
                "user1_unread_count": row[4],
                "user2_unread_count": row[5],
                "created_at": row[6],
                "is_new": False
            }

        # 建立新對話
        c.execute('''
            INSERT INTO dm_conversations (user1_id, user2_id, created_at)
            VALUES (?, ?, datetime('now'))
        ''', (user1_id, user2_id))
        conn.commit()

        return {
            "id": c.lastrowid,
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
                CASE WHEN c.user1_id = ? THEN u2.username ELSE u1.username END as other_username,
                CASE WHEN c.user1_id = ? THEN u2.user_id ELSE u1.user_id END as other_user_id,
                CASE WHEN c.user1_id = ? THEN u2.membership_tier ELSE u1.membership_tier END as other_membership_tier
            FROM dm_conversations c
            LEFT JOIN dm_messages m ON m.id = c.last_message_id
            LEFT JOIN users u1 ON u1.user_id = c.user1_id
            LEFT JOIN users u2 ON u2.user_id = c.user2_id
            WHERE c.user1_id = ? OR c.user2_id = ?
            ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC
            LIMIT ? OFFSET ?
        ''', (user_id, user_id, user_id, user_id, user_id, limit, offset))

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
                "last_message_at": last_message_at,
                "unread_count": unread_count,
                "created_at": created_at
            })

        return conversations
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
            WHERE id = ? AND (user1_id = ? OR user2_id = ?)
        ''', (conversation_id, user_id, user_id))
        row = c.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user1_id": row[1],
            "user2_id": row[2],
            "last_message_at": row[3],
            "user1_unread_count": row[4],
            "user2_unread_count": row[5]
        }
    finally:
        conn.close()


# ============================================================================
# 訊息操作
# ============================================================================

def send_message(from_user_id: str, to_user_id: str, content: str, message_type: str = 'text') -> Dict:
    """
    發送訊息
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
        # 取得或建立對話
        conv = get_or_create_conversation(from_user_id, to_user_id)
        conversation_id = conv["id"]

        # 插入訊息
        c.execute('''
            INSERT INTO dm_messages (conversation_id, from_user_id, to_user_id, content, message_type, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (conversation_id, from_user_id, to_user_id, content.strip(), message_type))
        message_id = c.lastrowid

        # 更新對話的最後訊息和未讀數
        # 確定哪個用戶的未讀數要增加
        if conv["user1_id"] == to_user_id:
            unread_field = "user1_unread_count"
        else:
            unread_field = "user2_unread_count"

        c.execute(f'''
            UPDATE dm_conversations
            SET last_message_id = ?,
                last_message_at = datetime('now'),
                {unread_field} = {unread_field} + 1
            WHERE id = ?
        ''', (message_id, conversation_id))

        conn.commit()

        # 取得完整的訊息資料（包含用戶名稱）
        c.execute('''
            SELECT m.id, m.conversation_id, m.from_user_id, m.to_user_id, m.content,
                   m.message_type, m.is_read, m.read_at, m.created_at,
                   u1.username as from_username, u2.username as to_username
            FROM dm_messages m
            LEFT JOIN users u1 ON m.from_user_id = u1.user_id
            LEFT JOIN users u2 ON m.to_user_id = u2.user_id
            WHERE m.id = ?
        ''', (message_id,))
        msg_row = c.fetchone()

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
                "read_at": msg_row[7],
                "created_at": msg_row[8],
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
        # 驗證用戶是對話參與者
        conv = get_conversation_by_id(conversation_id, user_id)
        if not conv:
            return {"success": False, "error": "conversation_not_found"}

        # 查詢訊息（包含用戶名稱）
        if before_id:
            c.execute('''
                SELECT m.id, m.conversation_id, m.from_user_id, m.to_user_id, m.content,
                       m.message_type, m.is_read, m.read_at, m.created_at,
                       u1.username as from_username, u2.username as to_username
                FROM dm_messages m
                LEFT JOIN users u1 ON m.from_user_id = u1.user_id
                LEFT JOIN users u2 ON m.to_user_id = u2.user_id
                WHERE m.conversation_id = ? AND m.id < ?
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT ?
            ''', (conversation_id, before_id, limit))
        else:
            c.execute('''
                SELECT m.id, m.conversation_id, m.from_user_id, m.to_user_id, m.content,
                       m.message_type, m.is_read, m.read_at, m.created_at,
                       u1.username as from_username, u2.username as to_username
                FROM dm_messages m
                LEFT JOIN users u1 ON m.from_user_id = u1.user_id
                LEFT JOIN users u2 ON m.to_user_id = u2.user_id
                WHERE m.conversation_id = ?
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT ?
            ''', (conversation_id, limit))

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
                "read_at": row[7],
                "created_at": row[8],
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

        # 標記所有發給當前用戶的未讀訊息為已讀
        c.execute('''
            UPDATE dm_messages
            SET is_read = 1, read_at = datetime('now')
            WHERE conversation_id = ? AND to_user_id = ? AND is_read = 0
        ''', (conversation_id, user_id))
        updated_count = c.rowcount

        # 重置對話中當前用戶的未讀數
        if conv["user1_id"] == user_id:
            c.execute('UPDATE dm_conversations SET user1_unread_count = 0 WHERE id = ?', (conversation_id,))
        else:
            c.execute('UPDATE dm_conversations SET user2_unread_count = 0 WHERE id = ?', (conversation_id,))

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
                        WHEN user1_id = ? THEN user1_unread_count
                        ELSE user2_unread_count
                    END
                ), 0)
            FROM dm_conversations
            WHERE user1_id = ? OR user2_id = ?
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
            WHERE user_id = ? AND date = ?
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
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, date) DO UPDATE SET message_count = message_count + 1
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
            WHERE user_id = ? AND date = ?
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
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        row = c.fetchone()

        if row and row[0] != current_month:
            # 新月份，重置計數
            c.execute('''
                UPDATE user_message_limits
                SET greeting_count = 1, greeting_month = ?
                WHERE user_id = ? AND date = ?
            ''', (current_month, user_id, today))
        else:
            c.execute('''
                INSERT INTO user_message_limits (user_id, date, greeting_count, greeting_month)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    greeting_count = CASE
                        WHEN greeting_month = ? THEN greeting_count + 1
                        ELSE 1
                    END,
                    greeting_month = ?
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
                CASE WHEN c.user1_id = ? THEN u2.username ELSE u1.username END as other_username,
                CASE WHEN c.user1_id = ? THEN c.user2_id ELSE c.user1_id END as other_user_id
            FROM dm_messages m
            JOIN dm_conversations c ON c.id = m.conversation_id
            LEFT JOIN users u1 ON u1.user_id = c.user1_id
            LEFT JOIN users u2 ON u2.user_id = c.user2_id
            WHERE (c.user1_id = ? OR c.user2_id = ?)
            AND m.content LIKE ?
            ORDER BY m.created_at DESC
            LIMIT ?
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
                "created_at": row[6],
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
            WHERE user1_id = ? AND user2_id = ?
        ''', (u1, u2))
        row = c.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user1_id": row[1],
            "user2_id": row[2],
            "last_message_at": row[3]
        }
    finally:
        conn.close()
