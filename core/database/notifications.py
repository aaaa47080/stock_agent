"""
通知資料庫操作模組
"""
from .connection import get_connection
from typing import Optional, List, Dict, Any
from datetime import datetime
from psycopg2.extras import Json
import uuid


def create_notifications_table():
    """創建通知表（如果不存在）"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT,
                    body TEXT,
                    data JSONB,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),

                    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                -- 索引優化查詢
                CREATE INDEX IF NOT EXISTS idx_notifications_user_created
                    ON notifications(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
                    ON notifications(user_id) WHERE is_read = FALSE;
            """)
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    創建新通知

    Args:
        user_id: 接收通知的用戶 ID
        notification_type: 通知類型 (friend_request, message, post_interaction, system_update, announcement)
        title: 通知標題
        body: 通知內容
        data: 額外數據

    Returns:
        創建的通知對象
    """
    notification_id = f"notif_{uuid.uuid4().hex[:12]}"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO notifications (id, user_id, type, title, body, data, is_read, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
                RETURNING id, user_id, type, title, body, data, is_read, created_at
            """, (notification_id, user_id, notification_type, title, body, Json(data) if data else None))

            row = cur.fetchone()
            conn.commit()

            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "type": row[2],
                    "title": row[3],
                    "body": row[4],
                    "data": row[5],
                    "is_read": row[6],
                    "created_at": row[7].isoformat() if row[7] else None
                }
            return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_notifications(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False
) -> List[Dict[str, Any]]:
    """
    獲取用戶的通知列表

    Args:
        user_id: 用戶 ID
        limit: 返回數量限制
        offset: 偏移量
        unread_only: 是否只返回未讀通知

    Returns:
        通知列表
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if unread_only:
                cur.execute("""
                    SELECT id, user_id, type, title, body, data, is_read, created_at
                    FROM notifications
                    WHERE user_id = %s AND is_read = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, limit, offset))
            else:
                cur.execute("""
                    SELECT id, user_id, type, title, body, data, is_read, created_at
                    FROM notifications
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, limit, offset))

            rows = cur.fetchall()
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "type": row[2],
                    "title": row[3],
                    "body": row[4],
                    "data": row[5],
                    "is_read": row[6],
                    "created_at": row[7].isoformat() if row[7] else None
                }
                for row in rows
            ]
    finally:
        conn.close()


def get_unread_count(user_id: str) -> int:
    """
    獲取用戶未讀通知數量

    Args:
        user_id: 用戶 ID

    Returns:
        未讀通知數量
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM notifications
                WHERE user_id = %s AND is_read = FALSE
            """, (user_id,))

            result = cur.fetchone()
            return result[0] if result else 0
    finally:
        conn.close()


def mark_notification_as_read(notification_id: str, user_id: str) -> bool:
    """
    標記通知為已讀

    Args:
        notification_id: 通知 ID
        user_id: 用戶 ID（用於驗證權限）

    Returns:
        是否成功
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE notifications
                SET is_read = TRUE
                WHERE id = %s AND user_id = %s
            """, (notification_id, user_id))

            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def mark_all_as_read(user_id: str) -> int:
    """
    標記用戶所有通知為已讀

    Args:
        user_id: 用戶 ID

    Returns:
        更新的通知數量
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE notifications
                SET is_read = TRUE
                WHERE user_id = %s AND is_read = FALSE
            """, (user_id,))

            conn.commit()
            return cur.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def delete_notification(notification_id: str, user_id: str) -> bool:
    """
    刪除通知

    Args:
        notification_id: 通知 ID
        user_id: 用戶 ID（用於驗證權限）

    Returns:
        是否成功
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM notifications
                WHERE id = %s AND user_id = %s
            """, (notification_id, user_id))

            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ============================================================================
# 輔助函數：創建特定類型的通知
# ============================================================================

def notify_friend_request(to_user_id: str, from_user_id: str, from_username: str) -> Dict[str, Any]:
    """創建好友請求通知"""
    return create_notification(
        user_id=to_user_id,
        notification_type="friend_request",
        title="好友請求",
        body=f"{from_username} 想加你為好友",
        data={
            "from_user_id": from_user_id,
            "from_username": from_username
        }
    )


def notify_friend_accepted(to_user_id: str, from_user_id: str, from_username: str) -> Dict[str, Any]:
    """創建好友接受通知"""
    return create_notification(
        user_id=to_user_id,
        notification_type="friend_request",
        title="好友已接受",
        body=f"{from_username} 已接受你的好友請求",
        data={
            "from_user_id": from_user_id,
            "from_username": from_username,
            "action": "accepted"
        }
    )


def notify_new_message(to_user_id: str, from_user_id: str, from_username: str, message_preview: str, conversation_id: str) -> Dict[str, Any]:
    """創建新消息通知"""
    return create_notification(
        user_id=to_user_id,
        notification_type="message",
        title="新消息",
        body=f"{from_username}: {message_preview[:50]}{'...' if len(message_preview) > 50 else ''}",
        data={
            "from_user_id": from_user_id,
            "from_username": from_username,
            "conversation_id": conversation_id
        }
    )


def notify_post_interaction(to_user_id: str, from_username: str, interaction_type: str, post_id: int, post_title: str) -> Dict[str, Any]:
    """創建帖子互動通知"""
    interaction_text = {
        "like": "讚了",
        "comment": "評論了"
    }.get(interaction_type, "互動了")

    return create_notification(
        user_id=to_user_id,
        notification_type="post_interaction",
        title="帖子互動",
        body=f"{from_username} {interaction_text}你的文章「{post_title[:30]}{'...' if len(post_title) > 30 else ''}」",
        data={
            "post_id": post_id,
            "interaction_type": interaction_type,
            "from_username": from_username
        }
    )


def notify_system_update(user_id: str, version: str, message: str = None) -> Dict[str, Any]:
    """創建系統更新通知"""
    return create_notification(
        user_id=user_id,
        notification_type="system_update",
        title="系統更新",
        body=message or f"新版本 {version} 可用，建議更新以獲得最佳體驗",
        data={
            "version": version
        }
    )


def notify_announcement(user_ids: List[str], title: str, body: str) -> List[Dict[str, Any]]:
    """創建系統公告（批量）"""
    notifications = []
    for user_id in user_ids:
        notification = create_notification(
            user_id=user_id,
            notification_type="announcement",
            title=title,
            body=body,
            data={}
        )
        if notification:
            notifications.append(notification)
    return notifications
