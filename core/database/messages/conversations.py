"""
私訊對話管理
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..connection import get_connection


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
        c.execute(
            """
            SELECT id, user1_id, user2_id, last_message_at, user1_unread_count, user2_unread_count, created_at
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        """,
            (user1_id, user2_id),
        )
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
                "is_new": False,
            }

        # 建立新對話
        c.execute(
            """
            INSERT INTO dm_conversations (user1_id, user2_id, created_at)
            VALUES (%s, %s, NOW())
            RETURNING id
        """,
            (user1_id, user2_id),
        )
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
            "is_new": True,
        }
    finally:
        conn.close()


def get_conversations(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
    """
    取得用戶的對話列表，按最後訊息時間排序
    排除所有訊息都已被用戶刪除的對話
    排除當前用戶已封鎖的對話（LINE 模式：封鎖後對話從列表隱藏，解除封鎖後恢復）
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
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
            -- 排除當前用戶已封鎖的對話（LINE 模式）
            AND NOT EXISTS (
                SELECT 1 FROM friendships f
                WHERE f.user_id = %s
                AND f.friend_id = CASE WHEN c.user1_id = %s THEN c.user2_id ELSE c.user1_id END
                AND f.status = 'blocked'
            )
            ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC
            LIMIT %s OFFSET %s
        """,
            (
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
                limit,
                offset,
            ),
        )

        rows = c.fetchall()
        conversations = []

        for row in rows:
            (
                conv_id,
                user1_id,
                user2_id,
                last_message_at,
                user1_unread,
                user2_unread,
                created_at,
                last_message,
                last_message_from,
                other_username,
                other_user_id,
                other_membership_tier,
            ) = row

            # 根據當前用戶決定未讀數
            unread_count = user1_unread if user_id == user1_id else user2_unread

            conversations.append(
                {
                    "id": conv_id,
                    "other_user_id": other_user_id,
                    "other_username": other_username or other_user_id,
                    "other_membership_tier": other_membership_tier or "free",
                    "last_message": last_message,
                    "last_message_from": last_message_from,
                    "last_message_at": last_message_at.isoformat()
                    if last_message_at
                    else None,
                    "unread_count": unread_count,
                    "created_at": created_at.isoformat() if created_at else None,
                }
            )

        return conversations
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"get_conversations error for user {user_id}: {str(e)}", exc_info=True
        )
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
        c.execute(
            """
            SELECT id, user1_id, user2_id, last_message_at, user1_unread_count, user2_unread_count
            FROM dm_conversations
            WHERE id = %s AND (user1_id = %s OR user2_id = %s)
        """,
            (conversation_id, user_id, user_id),
        )
        row = c.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user1_id": row[1],
            "user2_id": row[2],
            "last_message_at": row[3].isoformat() if row[3] else None,
            "user1_unread_count": row[4],
            "user2_unread_count": row[5],
        }
    finally:
        conn.close()


def get_conversation_with_user(user_id: str, other_user_id: str) -> Optional[Dict]:
    """
    取得與特定用戶的對話
    """
    # 排序以匹配資料庫中的儲存方式
    u1, u2 = (
        (user_id, other_user_id)
        if user_id < other_user_id
        else (other_user_id, user_id)
    )

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            SELECT id, user1_id, user2_id, last_message_at
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        """,
            (u1, u2),
        )
        row = c.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user1_id": row[1],
            "user2_id": row[2],
            "last_message_at": row[3].isoformat() if row[3] else None,
        }
    finally:
        conn.close()
