"""
私訊輔助功能（收回、隱藏等）
"""

from typing import Dict

from ..connection import get_connection
from .messaging import send_message


def send_greeting(from_user_id: str, to_user_id: str, content: str) -> Dict:
    """
    發送打招呼訊息（Pro 會員專屬，可發給非好友）
    """
    return send_message(from_user_id, to_user_id, content, message_type="greeting")


def delete_dm_message(message_id: int, user_id: str) -> Dict:
    """
    收回私訊訊息 (僅限發送者)
    不會真的刪除訊息，而是標記為已收回，讓對方看到「訊息已收回」
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查訊息是否存在且發送者是否為當前用戶
        c.execute(
            "SELECT from_user_id, message_type FROM dm_messages WHERE id = %s",
            (message_id,),
        )
        row = c.fetchone()

        if not row:
            return {"success": False, "error": "message_not_found"}

        if row[0] != user_id:
            return {"success": False, "error": "permission_denied"}

        if row[1] == "recalled":
            return {"success": False, "error": "already_recalled"}

        # 收回訊息：將 message_type 設為 'recalled'，保留原始內容但前端不顯示
        c.execute(
            """
            UPDATE dm_messages
            SET message_type = 'recalled'
            WHERE id = %s
        """,
            (message_id,),
        )
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
        c.execute("SELECT id FROM dm_messages WHERE id = %s", (message_id,))
        if not c.fetchone():
            return {"success": False, "error": "message_not_found"}

        # 插入刪除記錄（使用 ON CONFLICT 避免重複）
        c.execute(
            """
            INSERT INTO dm_message_deletions (message_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (message_id, user_id) DO NOTHING
        """,
            (message_id, user_id),
        )
        conn.commit()

        return {"success": True, "hidden": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_conversation_with_messages(
    user_id: str, other_user_id: str, limit: int = 50
) -> Dict:
    """
    一次性取得對話和訊息（優化版本，只用一個連接）
    """
    # 排序以確保唯一性
    u1, u2 = (
        (user_id, other_user_id)
        if user_id < other_user_id
        else (other_user_id, user_id)
    )

    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. 檢查或建立對話
        c.execute(
            """
            SELECT id, user1_id, user2_id, last_message_at, user1_unread_count, user2_unread_count, created_at
            FROM dm_conversations
            WHERE user1_id = %s AND user2_id = %s
        """,
            (u1, u2),
        )
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
                "is_new": False,
            }
        else:
            # 建立新對話
            c.execute(
                """
                INSERT INTO dm_conversations (user1_id, user2_id, created_at)
                VALUES (%s, %s, NOW())
                RETURNING id, created_at
            """,
                (u1, u2),
            )
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
                "is_new": True,
            }

        # 2. 取得訊息（使用同一個連接，排除被當前用戶刪除的訊息）
        c.execute(
            """
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
        """,
            (user_id, conv["id"], limit),
        )

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
                "to_username": r[10],
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
            "has_more": has_more,
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
        c.execute(
            """
            SELECT id FROM dm_conversations
            WHERE id = %s AND (user1_id = %s OR user2_id = %s)
        """,
            (conversation_id, user_id, user_id),
        )
        if not c.fetchone():
            return {"success": False, "error": "conversation_not_found"}

        # 獲取該對話中所有訊息的 ID
        c.execute(
            """
            SELECT id FROM dm_messages
            WHERE conversation_id = %s
        """,
            (conversation_id,),
        )
        message_ids = [row[0] for row in c.fetchall()]

        if not message_ids:
            # 沒有訊息，但對話存在，仍然返回成功
            return {"success": True, "hidden_count": 0}

        # 批量插入刪除記錄（使用 ON CONFLICT 避免重複）
        values = [(msg_id, user_id) for msg_id in message_ids]
        from psycopg2.extras import execute_values

        execute_values(
            c,
            """
            INSERT INTO dm_message_deletions (message_id, user_id)
            VALUES %s
            ON CONFLICT (message_id, user_id) DO NOTHING
        """,
            values,
        )

        conn.commit()

        return {"success": True, "hidden_count": len(message_ids)}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
