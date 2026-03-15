"""
通知 API 端點
"""
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Optional
from pydantic import BaseModel, Field
import json
import asyncio
import os

from core.database.notifications import (
    get_notifications,
    get_unread_count,
    mark_notification_as_read,
    mark_all_as_read,
    delete_notification,
)
from core.database.user import get_user_by_id
from api.utils import logger
from api.deps import get_current_user, verify_token
from fastapi import Depends

router = APIRouter()


async def run_sync(fn, *args):
    """Run a synchronous DB function in the thread executor."""
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


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
    """獲取用戶的通知列表"""
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        notifications = await run_sync(
            lambda: get_notifications(user_id=user_id, limit=limit, offset=offset, unread_only=unread_only)
        )
        unread_count = await run_sync(get_unread_count, user_id)

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
        raise HTTPException(status_code=500, detail="獲取通知失敗，請稍後再試")


@router.get("/api/notifications/unread-count")
async def get_unread_count_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """獲取未讀通知數量"""
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        count = await run_sync(get_unread_count, user_id)
        return {"success": True, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取未讀數量失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取未讀數量失敗，請稍後再試")


@router.post("/api/notifications/{notification_id}/read")
async def mark_as_read_endpoint(
    notification_id: str,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """標記通知為已讀"""
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        success = await run_sync(mark_notification_as_read, notification_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="通知不存在")

        return {"success": True, "message": "已標記為已讀"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"標記已讀失敗: {e}")
        raise HTTPException(status_code=500, detail="標記已讀失敗，請稍後再試")


@router.post("/api/notifications/read-all")
async def mark_all_as_read_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """標記所有通知為已讀"""
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        count = await run_sync(mark_all_as_read, user_id)
        return {"success": True, "message": f"已標記 {count} 則通知為已讀", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"標記全部已讀失敗: {e}")
        raise HTTPException(status_code=500, detail="標記全部已讀失敗，請稍後再試")


@router.delete("/api/notifications/{notification_id}")
async def delete_notification_endpoint(
    notification_id: str,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """刪除通知"""
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        success = await run_sync(delete_notification, notification_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="通知不存在")

        return {"success": True, "message": "通知已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除通知失敗: {e}")
        raise HTTPException(status_code=500, detail="刪除通知失敗，請稍後再試")


# ============================================================================
# WebSocket 端點
# ============================================================================

@router.websocket("/ws/notifications")
async def notification_websocket(websocket: WebSocket):
    """
    通知 WebSocket 端點
    客戶端連接後需發送認證消息: {"type": "auth", "token": "JWT_TOKEN"}
    """
    user_id = None

    try:
        await websocket.accept()

        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        auth_data = json.loads(auth_message)

        if auth_data.get("type") != "auth":
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close(code=4001, reason="Authentication required")
            return

        token = auth_data.get("token") or auth_data.get("access_token")
        if not token:
            await websocket.send_json({"type": "error", "message": "JWT Token required"})
            await websocket.close(code=4002, reason="JWT Token required")
            return

        if os.getenv("TEST_MODE") == "True" and token.startswith("test-"):
            user_id = token
            logger.info(f"Notification WebSocket Dev Auth: {user_id}")
        else:
            try:
                payload = verify_token(token)
                user_id = payload.get("sub")
                if not user_id:
                    raise HTTPException(status_code=401, detail="Invalid token payload")
            except Exception as e:
                logger.warning(f"Notification WebSocket auth failed: {e}")
                await websocket.send_json({"type": "error", "message": "Invalid Token"})
                await websocket.close(code=4003, reason="Invalid Token")
                return

        claimed_user_id = auth_data.get("user_id")
        if claimed_user_id and claimed_user_id != user_id:
            logger.warning(f"Notification WebSocket auth mismatch: Token user {user_id} != Claimed {claimed_user_id}")
            await websocket.send_json({"type": "error", "message": "User ID mismatch"})
            await websocket.close(code=4004, reason="User ID mismatch")
            return

        user_exists = await run_sync(get_user_by_id, user_id)
        if not user_exists:
            await websocket.send_json({"type": "error", "message": "User not found"})
            await websocket.close(code=4005, reason="User not found")
            return

        await notification_manager.connect(websocket, user_id)
        logger.info(f"User {user_id} authenticated successfully via notification WebSocket")

        await websocket.send_json({
            "type": "connected",
            "message": "Connected to notification service",
            "user_id": user_id
        })

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
    """推送通知給用戶（WebSocket 即時推送）"""
    await notification_manager.send_to_user(user_id, {
        "type": "notification",
        "data": notification
    })
