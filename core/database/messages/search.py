"""
私訊搜尋功能
"""

from typing import Dict, List

from ..connection import get_connection


def search_messages(user_id: str, query: str, limit: int = 50) -> List[Dict]:
    """
    搜尋用戶的訊息內容
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
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
        """,
            (user_id, user_id, user_id, user_id, f"%{query}%", limit),
        )

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
                "other_user_id": row[8],
            }
            for row in rows
        ]
    finally:
        conn.close()
