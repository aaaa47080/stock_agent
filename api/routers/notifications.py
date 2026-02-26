"""
通知 API 端點
"""
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Optional, List
from pydantic import BaseModel, Field
import json
import asyncio

from core.database.notifications import (
    create_notifications_table,
    get_notifications,
    get_unread_count,
    mark_notification_as_read,
    mark_all_as_read,
    delete_notification,
    create_notification,
)
from api.utils import logger
from api.deps import get_current_user
from fastapi import Depends

router = APIRouter()

# 初始化表
try:
    create_notifications_table()
    logger.info("Notifications table initialized")
except Exception as e:
    logger.warning(f"Could not initialize notifications table: {e}")


# ============================================================================
# WebSocket 連接管理器
# ============================================================================

class NotificationConnectionManager:
    """管理通知 WebSocket 連接"""

    def __init__(self):
        # user_id -> Set[WebSocket]
        self.active_connections: dict = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        # 注意：websocket.accept() 已在 endpoint 中調用，此處只需註冊連接
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected to notification WebSocket")

    async def disconnect(self, websocket: WebSocket, user_id: str):
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected from notification WebSocket")

    async def send_to_user(self, user_id: str, data: dict):
        """發送通知給特定用戶的所有連接"""
        async with self._lock:
            connections = self.active_connections.get(user_id, set()).copy()

        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")

    def is_user_online(self, user_id: str) -> bool:
        """檢查用戶是否在線"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


# 全局連接管理器
notification_manager = NotificationConnectionManager()


# ============================================================================
# 請求模型
# ============================================================================

class CreateNotificationRequest(BaseModel):
    """創建通知請求"""
    user_id: str = Field(..., description="接收通知的用戶 ID")
    type: str = Field(..., description="通知類型")
    title: str = Field(..., description="通知標題")
    body: str = Field(..., description="通知內容")
    data: Optional[dict] = Field(None, description="額外數據")


# ============================================================================
# API 端點
# ============================================================================

@router.get("/api/notifications")
async def get_notifications_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False, description="只返回未讀通知"),
    current_user: dict = Depends(get_current_user)
):
    """
    獲取用戶的通知列表
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        notifications = get_notifications(
            user_id=user_id,
            limit=limit,
            offset=offset,
            unread_only=unread_only
        )
        unread_count = get_unread_count(user_id)

        return {
            "success": True,
            "notifications": notifications,
            "unread_count": unread_count,
            "count": len(notifications)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取通知失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取通知失敗: {str(e)}")


@router.get("/api/notifications/unread-count")
async def get_unread_count_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    獲取未讀通知數量
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        count = get_unread_count(user_id)
        return {"success": True, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取未讀數量失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取未讀數量失敗: {str(e)}")


@router.post("/api/notifications/{notification_id}/read")
async def mark_as_read_endpoint(
    notification_id: str,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    標記通知為已讀
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        success = mark_notification_as_read(notification_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="通知不存在")

        return {"success": True, "message": "已標記為已讀"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"標記已讀失敗: {e}")
        raise HTTPException(status_code=500, detail=f"標記已讀失敗: {str(e)}")


@router.post("/api/notifications/read-all")
async def mark_all_as_read_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    標記所有通知為已讀
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        count = mark_all_as_read(user_id)
        return {"success": True, "message": f"已標記 {count} 則通知為已讀", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"標記全部已讀失敗: {e}")
        raise HTTPException(status_code=500, detail=f"標記全部已讀失敗: {str(e)}")


@router.delete("/api/notifications/{notification_id}")
async def delete_notification_endpoint(
    notification_id: str,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    刪除通知
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        success = delete_notification(notification_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="通知不存在")

        return {"success": True, "message": "通知已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除通知失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除通知失敗: {str(e)}")


# ============================================================================
# WebSocket 端點
# ============================================================================

@router.websocket("/ws/notifications")
async def notification_websocket(websocket: WebSocket):
    """
    通知 WebSocket 端點

    客戶端連接後需要發送認證消息:
    {
        "type": "auth",
        "user_id": "用戶ID"
    }

    服務器會推送:
    {
        "type": "notification",
        "data": { ...通知對象... }
    }
    """
    user_id = None

    try:
        await websocket.accept()

        # 等待認證消息
        auth_message = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=10.0
        )
        auth_data = json.loads(auth_message)

        if auth_data.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            return

        user_id = auth_data.get("user_id")
        if not user_id:
            await websocket.close(code=4002, reason="User ID required")
            return

        # 註冊連接
        await notification_manager.connect(websocket, user_id)

        # 發送連接成功消息
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to notification service"
        })

        # 保持連接，處理客戶端消息（主要是心跳）
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue

    except asyncio.TimeoutError:
        await websocket.close(code=4003, reason="Authentication timeout")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Notification WebSocket error: {e}")
    finally:
        if user_id:
            await notification_manager.disconnect(websocket, user_id)


# ============================================================================
# 輔助函數（供其他模組調用）
# ============================================================================

async def push_notification_to_user(user_id: str, notification: dict):
    """
    推送通知給用戶

    Args:
        user_id: 用戶 ID
        notification: 通知對象
    """
    await notification_manager.send_to_user(user_id, {
        "type": "notification",
        "data": notification
    })


def create_and_push_notification(
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    data: Optional[dict] = None
) -> dict:
    """
    創建通知並推送（同步版本，用於非異步上下文）

    Args:
        user_id: 用戶 ID
        notification_type: 通知類型
        title: 標題
        body: 內容
        data: 額外數據

    Returns:
        創建的通知對象
    """
    notification = create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        data=data
    )

    if notification and notification_manager.is_user_online(user_id):
        # 如果用戶在線，異步推送
        asyncio.create_task(push_notification_to_user(user_id, notification))

    return notification
