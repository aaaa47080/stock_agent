"""
私訊功能 API 端點
"""

import asyncio
import json
import os
from typing import Dict, Optional, Set

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from api.deps import get_current_user, verify_token
from api.middleware.rate_limit import limiter
from api.routers.notifications import push_notification_to_user
from api.utils import logger, run_sync
from core.database import (
    check_and_increment_greeting,
    check_and_increment_message,
    check_greeting_limit,
    check_message_limit,
    delete_dm_message,
    get_conversation_by_id,
    get_conversation_with_messages,
    get_conversations,
    get_dm_messages,
    get_unread_count,
    get_user_by_id,
    get_user_membership,
    hide_conversation_for_user,
    hide_dm_message_for_user,
    increment_message_count,
    is_blocked,
    mark_as_read,
    search_messages,
    send_dm_message,
    send_greeting,
    update_last_active,
)
from core.database.notifications import notify_new_message

router = APIRouter()


# ============================================================================
# 請求模型
# ============================================================================


class SendMessageRequest(BaseModel):
    to_user_id: str = Field(..., description="接收者用戶 ID")
    content: str = Field(..., min_length=1, description="訊息內容")


class MarkReadRequest(BaseModel):
    conversation_id: int = Field(..., description="對話 ID")


# ============================================================================
# WebSocket 連接管理器
# ============================================================================


class MessageConnectionManager:
    """管理 WebSocket 連接"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        async with self.lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(
            f"用戶 {user_id} WebSocket 連接，當前連接數: {sum(len(v) for v in self.active_connections.values())}"
        )

    async def disconnect(self, websocket: WebSocket, user_id: str):
        async with self.lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        logger.info(f"用戶 {user_id} WebSocket 斷開")

    async def send_to_user(self, user_id: str, data: dict):
        """發送訊息給特定用戶的所有連接"""
        async with self.lock:
            connections = self.active_connections.get(user_id, set()).copy()

        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"發送訊息給用戶 {user_id} 失敗: {e}")

    def is_user_online(self, user_id: str) -> bool:
        """檢查用戶是否在線"""
        return (
            user_id in self.active_connections
            and len(self.active_connections[user_id]) > 0
        )


message_manager = MessageConnectionManager()


# ============================================================================
# API 端點
# ============================================================================


@router.get("/api/messages/conversations")
async def get_conversations_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    取得對話列表
    """
    try:
        user_id = current_user["user_id"]
        conversations = await run_sync(
            lambda: get_conversations(user_id, limit=limit, offset=offset)
        )
        total_unread = await run_sync(get_unread_count, user_id)

        return {
            "success": True,
            "conversations": conversations,
            "count": len(conversations),
            "total_unread": total_unread,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得對話列表失敗: {e}")
        raise HTTPException(status_code=500, detail="取得對話列表失敗，請稍後再試")


@router.get("/api/messages/conversation/{conversation_id}")
async def get_messages_endpoint(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(None, description="取得此 ID 之前的訊息"),
    current_user: dict = Depends(get_current_user),
):
    """
    取得對話中的訊息
    """
    try:
        user_id = current_user["user_id"]
        result = await run_sync(
            lambda: get_dm_messages(
                conversation_id, user_id, limit=limit, before_id=before_id
            )
        )

        if not result["success"]:
            raise HTTPException(status_code=404, detail="對話不存在或無權限")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得訊息失敗: {e}")
        raise HTTPException(status_code=500, detail="取得訊息失敗，請稍後再試")


@router.get("/api/messages/with/{other_user_id}")
async def get_conversation_with_user_endpoint(
    other_user_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    取得與特定用戶的對話和訊息（優化版：單一數據庫連接）
    """
    try:
        user_id = current_user["user_id"]
        result = await run_sync(
            get_conversation_with_messages, user_id, other_user_id, limit
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500, detail=result.get("error", "取得對話失敗")
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得對話失敗: {e}")
        raise HTTPException(status_code=500, detail="取得對話失敗，請稍後再試")


@router.post("/api/messages/send")
@limiter.limit("30/minute")
async def send_message_endpoint(
    request: Request,
    body: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    發送訊息（僅限好友）- 優化版本
    """
    try:
        user_id = current_user["user_id"]
        from core.database import validate_message_send

        validation = await run_sync(validate_message_send, user_id, body.to_user_id)

        if not validation["valid"]:
            error = validation["error"]
            if error == "sender_not_found":
                raise HTTPException(status_code=401, detail="用戶不存在")
            elif error == "receiver_not_found":
                raise HTTPException(status_code=404, detail="接收者不存在")
            elif error == "blocked":
                raise HTTPException(status_code=403, detail="無法發送訊息給此用戶")
            elif error == "not_friends":
                raise HTTPException(status_code=403, detail="只能發送訊息給好友")
            else:
                raise HTTPException(status_code=400, detail="驗證失敗")

        membership = await run_sync(get_user_membership, user_id)
        is_premium = membership.get("is_premium", False)
        limit_check = await run_sync(
            lambda: check_and_increment_message(user_id, is_premium)
        )

        if not limit_check["can_send"]:
            await run_sync(increment_message_count, user_id)
            raise HTTPException(
                status_code=429,
                detail=f"已達每日訊息上限 ({limit_check['limit']} 條)，升級 Premium 會員可無限發送",
            )

        result = await run_sync(send_dm_message, user_id, body.to_user_id, body.content)

        if not result["success"]:
            await run_sync(increment_message_count, user_id)
            raise HTTPException(status_code=400, detail=result.get("error", "發送失敗"))

        if not is_premium:
            pass  # Already incremented atomically above

        await message_manager.send_to_user(
            body.to_user_id, {"type": "new_message", "message": result["message"]}
        )

        await message_manager.send_to_user(
            user_id, {"type": "message_sent", "message": result["message"]}
        )

        try:
            msg = result["message"]
            notification = await run_sync(
                notify_new_message,
                body.to_user_id,
                user_id,
                msg.get("from_username", user_id),
                msg["content"],
                str(msg["conversation_id"]),
            )
            if notification:
                await push_notification_to_user(body.to_user_id, notification)
        except Exception as notify_error:
            logger.warning(f"Failed to send message notification: {notify_error}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"發送訊息失敗: {e}")
        raise HTTPException(status_code=500, detail="發送訊息失敗，請稍後再試")


@router.post("/api/messages/read")
async def mark_read_endpoint(
    request: MarkReadRequest, current_user: dict = Depends(get_current_user)
):
    """
    標記對話為已讀
    """
    try:
        user_id = current_user["user_id"]
        result = await run_sync(mark_as_read, request.conversation_id, user_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail="對話不存在")

        conv = await run_sync(get_conversation_by_id, request.conversation_id, user_id)
        if conv:
            other_user_id = (
                conv["user2_id"] if conv["user1_id"] == user_id else conv["user1_id"]
            )

            other_membership = await run_sync(get_user_membership, other_user_id)
            is_other_premium = other_membership.get("is_premium", False)
            if is_other_premium:
                await message_manager.send_to_user(
                    other_user_id,
                    {
                        "type": "read_receipt",
                        "conversation_id": request.conversation_id,
                        "read_by": user_id,
                    },
                )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"標記已讀失敗: {e}")
        raise HTTPException(status_code=500, detail="標記已讀失敗，請稍後再試")


@router.post("/api/messages/greeting")
@limiter.limit("5/minute")
async def send_greeting_endpoint(
    request: Request,
    body: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    發送打招呼訊息（Premium 會員專屬，可發給非好友）
    """
    try:
        user_id = current_user["user_id"]
        sender_exists = await run_sync(get_user_by_id, user_id)
        if not sender_exists:
            raise HTTPException(status_code=401, detail="用戶不存在")

        receiver_exists = await run_sync(get_user_by_id, body.to_user_id)
        if not receiver_exists:
            raise HTTPException(status_code=404, detail="接收者不存在")

        membership = await run_sync(get_user_membership, user_id)
        if not membership.get("is_premium", False):
            raise HTTPException(
                status_code=403, detail="打招呼功能僅限 Premium 會員使用"
            )

        blocked = await run_sync(is_blocked, user_id, body.to_user_id)
        if blocked:
            raise HTTPException(status_code=403, detail="無法發送訊息給此用戶")

        is_premium = membership.get("is_premium", False)
        limit_check = await run_sync(
            lambda: check_and_increment_greeting(user_id, is_premium)
        )
        if not limit_check["can_send"]:
            raise HTTPException(
                status_code=429,
                detail=f"已達每月打招呼上限 ({limit_check['limit']} 條)",
            )

        result = await run_sync(send_greeting, user_id, body.to_user_id, body.content)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "發送失敗"))

        pass  # Already incremented atomically above

        await message_manager.send_to_user(
            body.to_user_id, {"type": "new_message", "message": result["message"]}
        )

        try:
            msg = result["message"]
            notification = await run_sync(
                notify_new_message,
                body.to_user_id,
                user_id,
                msg.get("from_username", user_id),
                msg["content"],
                str(msg["conversation_id"]),
            )
            if notification:
                await push_notification_to_user(body.to_user_id, notification)
        except Exception as notify_error:
            logger.warning(f"Failed to send greeting notification: {notify_error}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"發送打招呼失敗: {e}")
        raise HTTPException(status_code=500, detail="發送打招呼失敗，請稍後再試")


@router.get("/api/messages/search")
async def search_messages_endpoint(
    q: str = Query(..., min_length=1, max_length=100, description="搜尋關鍵字"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    搜尋訊息（Premium 會員專屬）
    """
    try:
        user_id = current_user["user_id"]
        membership = await run_sync(get_user_membership, user_id)
        if not membership.get("is_premium", False):
            raise HTTPException(
                status_code=403, detail="訊息搜尋功能僅限 Premium 會員使用"
            )

        results = await run_sync(lambda: search_messages(user_id, q, limit=limit))

        return {"success": True, "results": results, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜尋訊息失敗: {e}")
        raise HTTPException(status_code=500, detail="搜尋訊息失敗，請稍後再試")


@router.get("/api/messages/unread-count")
async def get_unread_count_endpoint(current_user: dict = Depends(get_current_user)):
    """
    取得未讀訊息數量
    """
    try:
        user_id = current_user["user_id"]
        count = await run_sync(get_unread_count, user_id)
        return {"success": True, "unread_count": count}
    except Exception as e:
        logger.error(f"取得未讀數量失敗: {e}")
        raise HTTPException(status_code=500, detail="取得未讀數量失敗，請稍後再試")


@router.get("/api/messages/limits")
async def get_message_limits_endpoint(current_user: dict = Depends(get_current_user)):
    """
    取得用戶的訊息限制狀態
    """
    try:
        user_id = current_user["user_id"]
        from core.database import get_config

        membership = await run_sync(get_user_membership, user_id)
        is_premium = membership.get("is_premium", False)

        message_limit = await run_sync(lambda: check_message_limit(user_id, is_premium))
        greeting_limit = await run_sync(
            lambda: check_greeting_limit(user_id, is_premium)
        )
        max_length = await run_sync(lambda: get_config("limit_message_max_length", 500))
        return {
            "success": True,
            "is_premium": is_premium,
            "message_limit": message_limit,
            "greeting_limit": greeting_limit,
            "max_length": max_length,
        }
    except Exception as e:
        logger.error(f"取得限制狀態失敗: {e}")
        raise HTTPException(status_code=500, detail="取得限制狀態失敗，請稍後再試")


@router.delete("/api/messages/{message_id}")
async def delete_message_endpoint(
    message_id: int, current_user: dict = Depends(get_current_user)
):
    """
    刪除訊息
    """
    try:
        user_id = current_user["user_id"]
        result = await run_sync(delete_dm_message, message_id, user_id)

        if not result["success"]:
            error = result.get("error", "")
            if error == "message_not_found":
                raise HTTPException(status_code=404, detail="訊息不存在")
            elif error == "permission_denied":
                raise HTTPException(status_code=403, detail="無權刪除此訊息")
            else:
                raise HTTPException(status_code=400, detail=f"刪除失敗: {error}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除訊息失敗: {e}")
        raise HTTPException(status_code=500, detail="刪除訊息失敗，請稍後再試")


@router.post("/api/messages/{message_id}/hide")
async def hide_message_endpoint(
    message_id: int, current_user: dict = Depends(get_current_user)
):
    """
    隱藏訊息（只對自己隱藏，不影響對方）
    類似 WhatsApp 的「為我刪除」功能
    """
    try:
        user_id = current_user["user_id"]
        result = await run_sync(hide_dm_message_for_user, message_id, user_id)

        if not result["success"]:
            error = result.get("error", "")
            if error == "message_not_found":
                raise HTTPException(status_code=404, detail="訊息不存在")
            else:
                raise HTTPException(status_code=400, detail=f"隱藏失敗: {error}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"隱藏訊息失敗: {e}")
        raise HTTPException(status_code=500, detail="隱藏訊息失敗，請稍後再試")


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: int, current_user: dict = Depends(get_current_user)
):
    """
    刪除對話（隱藏整段對話，只對自己隱藏）
    類似 WhatsApp 的「刪除對話」功能
    """
    try:
        user_id = current_user["user_id"]
        result = await run_sync(hide_conversation_for_user, conversation_id, user_id)

        logger.info(f"刪除對話結果: {result}")

        if not result["success"]:
            error = result.get("error", "")
            if error == "conversation_not_found":
                raise HTTPException(status_code=404, detail="對話不存在")
            else:
                raise HTTPException(status_code=400, detail=f"刪除對話失敗: {error}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除對話失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="刪除對話失敗，請稍後再試")


# ============================================================================
# WebSocket 端點
# ============================================================================


@router.websocket("/ws/messages")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端點 - 即時訊息推送

    客戶端訊息格式:
    {"action": "auth", "user_id": "xxx"}  - 認證
    {"action": "ping"}                     - 心跳
    """
    user_id = None

    try:
        await websocket.accept()

        try:
            auth_data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            auth_message = json.loads(auth_data)

            token = auth_message.get("token") or auth_message.get("access_token")

            if not token:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Authentication required (Missing Token)",
                    }
                )
                await websocket.close()
                return

            if os.getenv("TEST_MODE") == "True" and token.startswith("test-"):
                user_id = token
                logger.info(f"WebSocket Dev Auth: {user_id}")
            else:
                try:
                    payload = verify_token(token)
                    user_id = payload.get("sub")
                    if not user_id:
                        raise HTTPException(
                            status_code=401, detail="Invalid token payload"
                        )
                except Exception as e:
                    logger.warning(f"WebSocket auth failed: {e}")
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid Token"}
                    )
                    await websocket.close()
                    return

            if auth_message.get("user_id") and auth_message["user_id"] != user_id:
                logger.warning(
                    f"WebSocket auth mismatch: Token user {user_id} != Claimed {auth_message['user_id']}"
                )
                await websocket.send_json(
                    {"type": "error", "message": "User ID mismatch"}
                )
                await websocket.close()
                return

            user_exists = await run_sync(get_user_by_id, user_id)
            if not user_exists:
                await websocket.send_json({"type": "error", "message": "用戶不存在"})
                await websocket.close()
                return

        except asyncio.TimeoutError:
            await websocket.send_json({"type": "error", "message": "認證超時"})
            await websocket.close()
            return

        async with message_manager.lock:
            if user_id not in message_manager.active_connections:
                message_manager.active_connections[user_id] = set()
            message_manager.active_connections[user_id].add(websocket)

        logger.info(f"用戶 {user_id} WebSocket 認證成功")

        await run_sync(update_last_active, user_id)

        unread_count = await run_sync(get_unread_count, user_id)
        await websocket.send_json(
            {"type": "authenticated", "user_id": user_id, "unread_count": unread_count}
        )

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"用戶 {user_id} WebSocket 主動斷開")
    except Exception as e:
        logger.error(f"WebSocket 錯誤: {e}")
    finally:
        if user_id:
            await message_manager.disconnect(websocket, user_id)
