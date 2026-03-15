"""
Admin Notification Management
Broadcast and notification history endpoints
"""
import asyncio
import json
import uuid
import logging
from fastapi import APIRouter, Depends, Query
from psycopg2.extras import Json

from api.deps import require_admin
from core.database.connection import get_connection
from api.routers.notifications import push_notification_to_user, notification_manager
from .schemas import BroadcastRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Notifications"])


async def run_sync(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


@router.post("/notifications/broadcast")
async def broadcast_notification(
    request: BroadcastRequest,
    admin_user: dict = Depends(require_admin)
):
    """發送廣播通知給所有活躍用戶"""
    # 1. 查所有活躍用戶
    def _get_active_user_ids():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT user_id FROM users WHERE is_active = TRUE OR is_active IS NULL")
                return [row[0] for row in c.fetchall()]
        finally:
            conn.close()

    user_ids = await run_sync(_get_active_user_ids)

    if not user_ids:
        return {"success": True, "sent_count": 0, "online_count": 0}

    # 2. 批量建通知
    sent_count = 0

    def _create_notifications_batch():
        nonlocal sent_count
        conn = get_connection()
        try:
            with conn.cursor() as c:
                for uid in user_ids:
                    nid = f"notif_{uuid.uuid4().hex[:12]}"
                    c.execute("""
                        INSERT INTO notifications (id, user_id, type, title, body, data, is_read, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
                    """, (nid, uid, request.type, request.title, request.body,
                          Json({"admin_user_id": admin_user["user_id"]})))
                    sent_count += 1
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    await run_sync(_create_notifications_batch)

    # 3. WebSocket push 在線用戶
    online_count = 0
    for uid in user_ids:
        if uid in notification_manager.active_connections:
            try:
                await push_notification_to_user(uid, {
                    "type": request.type,
                    "title": request.title,
                    "body": request.body
                })
                online_count += 1
            except Exception:
                logger.debug("Broadcast websocket push failed for user %s", uid, exc_info=True)

    # 4. 寫廣播紀錄
    def _save_broadcast_record():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO admin_broadcasts (admin_user_id, title, body, type, recipient_count)
                    VALUES (%s, %s, %s, %s, %s)
                """, (admin_user["user_id"], request.title, request.body, request.type, sent_count))
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.warning(f"Failed to save broadcast record: {e}")
        finally:
            conn.close()

    await run_sync(_save_broadcast_record)

    # 5. 審計紀錄
    def _write_audit():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, ("broadcast", None,
                      json.dumps({"title": request.title, "type": request.type, "recipients": sent_count}),
                      admin_user["user_id"]))
                conn.commit()
        except Exception:
            logger.warning("Failed to write broadcast audit log", exc_info=True)
        finally:
            conn.close()

    await run_sync(_write_audit)

    return {
        "success": True,
        "sent_count": sent_count,
        "online_count": online_count
    }


@router.get("/notifications/history")
async def get_broadcast_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """獲取廣播歷史紀錄"""
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT id, admin_user_id, title, body, type, recipient_count, created_at
                    FROM admin_broadcasts
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                rows = c.fetchall()

                c.execute("SELECT COUNT(*) FROM admin_broadcasts")
                total = c.fetchone()[0]

                return {
                    "broadcasts": [{
                        "id": r[0], "admin_user_id": r[1], "title": r[2],
                        "body": r[3], "type": r[4], "recipient_count": r[5],
                        "created_at": r[6].isoformat() if r[6] else None
                    } for r in rows],
                    "total": total,
                    "page": page,
                    "limit": limit
                }
        finally:
            conn.close()

    result = await run_sync(_query)
    return {"success": True, **result}
