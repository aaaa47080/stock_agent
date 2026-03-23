"""
Admin Notification Management
Broadcast and notification history endpoints
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text

from api.deps import require_admin
from api.routers.notifications import notification_manager, push_notification_to_user
from core.orm import AdminBroadcast, Notification
from core.orm.config_repo import _write_audit_log
from core.orm.session import get_session_factory

from .schemas import BroadcastRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Notifications"])


@router.post("/notifications/broadcast")
async def broadcast_notification(
    request: BroadcastRequest, admin_user: dict = Depends(require_admin)
):
    """發送廣播通知給所有活躍用戶"""

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT user_id FROM users WHERE is_active = TRUE OR is_active IS NULL")
        )
        user_ids = [row[0] for row in result.fetchall()]

    if not user_ids:
        return {"success": True, "sent_count": 0, "online_count": 0}

    sent_count = 0

    factory = get_session_factory()
    async with factory() as session:
        for uid in user_ids:
            nid = f"notif_{uuid.uuid4().hex[:12]}"
            notification = Notification(
                id=nid,
                user_id=uid,
                type=request.type,
                title=request.title,
                body=request.body,
                data={"admin_user_id": admin_user["user_id"]},
                is_read=False,
            )
            session.add(notification)
            sent_count += 1
        await session.flush()

    online_count = 0
    for uid in user_ids:
        if uid in notification_manager.active_connections:
            try:
                await push_notification_to_user(
                    uid,
                    {
                        "type": request.type,
                        "title": request.title,
                        "body": request.body,
                    },
                )
                online_count += 1
            except Exception:
                logger.debug(
                    "Broadcast websocket push failed for user %s", uid, exc_info=True
                )

    factory = get_session_factory()
    async with factory() as session:
        broadcast = AdminBroadcast(
            admin_user_id=admin_user["user_id"],
            title=request.title,
            body=request.body,
            type=request.type,
            recipient_count=sent_count,
        )
        session.add(broadcast)
        await _write_audit_log(
            session,
            "broadcast",
            None,
            json.dumps(
                {
                    "title": request.title,
                    "type": request.type,
                    "recipients": sent_count,
                }
            ),
            admin_user["user_id"],
        )

    return {"success": True, "sent_count": sent_count, "online_count": online_count}


@router.get("/notifications/history")
async def get_broadcast_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin),
):
    """獲取廣播歷史紀錄"""
    offset = (page - 1) * limit

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(
                AdminBroadcast.id,
                AdminBroadcast.admin_user_id,
                AdminBroadcast.title,
                AdminBroadcast.body,
                AdminBroadcast.type,
                AdminBroadcast.recipient_count,
                AdminBroadcast.created_at,
            )
            .order_by(AdminBroadcast.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = result.fetchall()

        total_result = await session.execute(
            select(func.count()).select_from(AdminBroadcast)
        )
        total = total_result.scalar()

        return {
            "success": True,
            "broadcasts": [
                {
                    "id": r[0],
                    "admin_user_id": r[1],
                    "title": r[2],
                    "body": r[3],
                    "type": r[4],
                    "recipient_count": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ],
            "total": total,
            "page": page,
            "limit": limit,
        }
