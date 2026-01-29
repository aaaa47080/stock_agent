"""
私訊功能 API 端點
"""
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Optional, Set, Dict
from pydantic import BaseModel, Field
import json

import asyncio
from functools import partial

from core.database import (
    get_or_create_conversation,
    get_conversations,
    get_conversation_by_id,
    get_conversation_with_user,
    send_dm_message,
    get_dm_messages,
    mark_as_read,
    get_unread_count,
    check_message_limit,
    increment_message_count,
    check_greeting_limit,
    increment_greeting_count,
    send_greeting,
    search_messages,
    is_friend,
    is_blocked,
    get_user_by_id,
    get_user_membership,
    update_last_active,
)
from fastapi import Depends
from api.deps import get_current_user, verify_token
from api.utils import logger

router = APIRouter()


# ============================================================================
# 請求模型
# ============================================================================

class SendMessageRequest(BaseModel):
    """發送訊息請求"""
    to_user_id: str = Field(..., description="接收者用戶 ID")
    content: str = Field(..., min_length=1, description="訊息內容")  # max_length 由資料庫配置控制



class MarkReadRequest(BaseModel):
    """標記已讀請求"""
    conversation_id: int = Field(..., description="對話 ID")


# ============================================================================
# WebSocket 連接管理器
# ============================================================================

class MessageConnectionManager:
    """管理 WebSocket 連接"""

    def __init__(self):
        # user_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        async with self.lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(f"用戶 {user_id} WebSocket 連接，當前連接數: {sum(len(v) for v in self.active_connections.values())}")

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
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


# 全局連接管理器
message_manager = MessageConnectionManager()


# ============================================================================
# 輔助函數
# ============================================================================

def _check_user_is_pro(user_id: str) -> bool:
    """檢查用戶是否為 Pro 會員"""
    membership = get_user_membership(user_id)
    return membership.get("is_pro", False)


# ============================================================================
# API 端點
# ============================================================================

@router.get("/api/messages/conversations")
async def get_conversations_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),

    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    取得對話列表
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        # 驗證用戶存在
        loop = asyncio.get_running_loop()
        user_exists = await loop.run_in_executor(None, get_user_by_id, user_id)
        if not user_exists:
            raise HTTPException(status_code=401, detail="用戶不存在")

        conversations = await loop.run_in_executor(
            None, 
            partial(get_conversations, user_id, limit=limit, offset=offset)
        )
        total_unread = await loop.run_in_executor(None, get_unread_count, user_id)

        return {
            "success": True,
            "conversations": conversations,
            "count": len(conversations),
            "total_unread": total_unread
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得對話列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得對話列表失敗: {str(e)}")


@router.get("/api/messages/conversation/{conversation_id}")
async def get_messages_endpoint(
    conversation_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(None, description="取得此 ID 之前的訊息"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得對話中的訊息
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(get_dm_messages, conversation_id, user_id, limit=limit, before_id=before_id)
        )

        if not result["success"]:
            raise HTTPException(status_code=404, detail="對話不存在或無權限")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得訊息失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得訊息失敗: {str(e)}")


@router.get("/api/messages/with/{other_user_id}")
async def get_conversation_with_user_endpoint(
    other_user_id: str,
    user_id: str = Query(..., description="當前用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    取得與特定用戶的對話和訊息
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        loop = asyncio.get_running_loop()
        
        # 取得或建立對話
        conv = await loop.run_in_executor(
            None,
            partial(get_or_create_conversation, user_id, other_user_id)
        )

        # 取得訊息
        result = await loop.run_in_executor(
            None,
            partial(get_dm_messages, conv["id"], user_id, limit=limit)
        )

        return {
            "success": True,
            "conversation": conv,
            "messages": result.get("messages", []),
            "has_more": result.get("has_more", False)
        }
    except Exception as e:
        logger.error(f"取得對話失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得對話失敗: {str(e)}")


@router.post("/api/messages/send")
async def send_message_endpoint(
    request: SendMessageRequest,
    user_id: str = Query(..., description="發送者用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    發送訊息（僅限好友）
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        # 驗證用戶存在
        loop = asyncio.get_running_loop()
        sender_exists = await loop.run_in_executor(None, get_user_by_id, user_id)
        if not sender_exists:
            raise HTTPException(status_code=401, detail="用戶不存在")
            
        receiver_exists = await loop.run_in_executor(None, get_user_by_id, request.to_user_id)
        if not receiver_exists:
            raise HTTPException(status_code=404, detail="接收者不存在")

        # 檢查是否被封鎖
        blocked = await loop.run_in_executor(None, partial(is_blocked, user_id, request.to_user_id))
        if blocked:
            raise HTTPException(status_code=403, detail="無法發送訊息給此用戶")

        # 檢查是否為好友
        friend = await loop.run_in_executor(None, partial(is_friend, user_id, request.to_user_id))
        if not friend:
            raise HTTPException(status_code=403, detail="只能發送訊息給好友")

        # 更新用戶最後活動時間
        await loop.run_in_executor(None, update_last_active, user_id)

        # 檢查訊息限制
        is_pro = _check_user_is_pro(user_id)
        limit_check = await loop.run_in_executor(None, partial(check_message_limit, user_id, is_pro))

        if not limit_check["can_send"]:
            raise HTTPException(
                status_code=429,
                detail=f"已達每日訊息上限 ({limit_check['limit']} 條)，升級 Pro 會員可無限發送"
            )

        # 發送訊息
        result = await loop.run_in_executor(
            None,
            partial(send_dm_message, user_id, request.to_user_id, request.content)
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "發送失敗"))

        # 增加訊息計數（非 Pro 用戶）
        if not is_pro:
            await loop.run_in_executor(None, increment_message_count, user_id)

        # 透過 WebSocket 推送給接收者
        await message_manager.send_to_user(request.to_user_id, {
            "type": "new_message",
            "message": result["message"]
        })

        # 也推送給發送者（其他設備）
        await message_manager.send_to_user(user_id, {
            "type": "message_sent",
            "message": result["message"]
        })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"發送訊息失敗: {e}")
        raise HTTPException(status_code=500, detail=f"發送訊息失敗: {str(e)}")


@router.post("/api/messages/read")
async def mark_read_endpoint(
    request: MarkReadRequest,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    標記對話為已讀
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(mark_as_read, request.conversation_id, user_id))

        if not result["success"]:
            raise HTTPException(status_code=404, detail="對話不存在")

        # 取得對話資訊以通知對方（已讀回執）
        conv = await loop.run_in_executor(None, partial(get_conversation_by_id, request.conversation_id, user_id))
        if conv:
            # 確定對方用戶 ID
            other_user_id = conv["user2_id"] if conv["user1_id"] == user_id else conv["user1_id"]

            # 檢查對方是否為 Pro 會員（只有 Pro 會員能看到已讀回執）
            is_other_pro = _check_user_is_pro(other_user_id)
            if is_other_pro:
                await message_manager.send_to_user(other_user_id, {
                    "type": "read_receipt",
                    "conversation_id": request.conversation_id,
                    "read_by": user_id
                })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"標記已讀失敗: {e}")
        raise HTTPException(status_code=500, detail=f"標記已讀失敗: {str(e)}")


@router.post("/api/messages/greeting")
async def send_greeting_endpoint(
    request: SendMessageRequest,
    user_id: str = Query(..., description="發送者用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    發送打招呼訊息（Pro 會員專屬，可發給非好友）
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        # 驗證用戶存在
        loop = asyncio.get_running_loop()
        sender_exists = await loop.run_in_executor(None, get_user_by_id, user_id)
        if not sender_exists:
            raise HTTPException(status_code=401, detail="用戶不存在")
            
        receiver_exists = await loop.run_in_executor(None, get_user_by_id, request.to_user_id)
        if not receiver_exists:
            raise HTTPException(status_code=404, detail="接收者不存在")

        # 檢查是否為 Pro 會員
        is_pro = _check_user_is_pro(user_id)
        if not is_pro:
            raise HTTPException(status_code=403, detail="打招呼功能僅限 Pro 會員使用")

        # 檢查是否被封鎖
        blocked = await loop.run_in_executor(None, partial(is_blocked, user_id, request.to_user_id))
        if blocked:
            raise HTTPException(status_code=403, detail="無法發送訊息給此用戶")

        # 檢查打招呼限制
        limit_check = await loop.run_in_executor(None, partial(check_greeting_limit, user_id, is_pro))
        if not limit_check["can_send"]:
            raise HTTPException(
                status_code=429,
                detail=f"已達每月打招呼上限 ({limit_check['limit']} 條)"
            )

        # 發送打招呼
        result = await loop.run_in_executor(
            None, 
            partial(send_greeting, user_id, request.to_user_id, request.content)
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "發送失敗"))

        # 增加打招呼計數
        await loop.run_in_executor(None, increment_greeting_count, user_id)

        # 透過 WebSocket 推送
        await message_manager.send_to_user(request.to_user_id, {
            "type": "new_message",
            "message": result["message"]
        })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"發送打招呼失敗: {e}")
        raise HTTPException(status_code=500, detail=f"發送打招呼失敗: {str(e)}")


@router.get("/api/messages/search")
async def search_messages_endpoint(
    q: str = Query(..., min_length=1, max_length=100, description="搜尋關鍵字"),
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    搜尋訊息（Pro 會員專屬）
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        # 檢查是否為 Pro 會員
        is_pro = _check_user_is_pro(user_id)
        if not is_pro:
            raise HTTPException(status_code=403, detail="訊息搜尋功能僅限 Pro 會員使用")

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, partial(search_messages, user_id, q, limit=limit))

        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜尋訊息失敗: {e}")
        raise HTTPException(status_code=500, detail=f"搜尋訊息失敗: {str(e)}")


@router.get("/api/messages/unread-count")
async def get_unread_count_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得未讀訊息數量
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(None, get_unread_count, user_id)
        return {
            "success": True,
            "unread_count": count
        }
    except Exception as e:
        logger.error(f"取得未讀數量失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得未讀數量失敗: {str(e)}")


@router.get("/api/messages/limits")
async def get_message_limits_endpoint(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得用戶的訊息限制狀態
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        from core.database import get_config
        is_pro = _check_user_is_pro(user_id)
        
        loop = asyncio.get_running_loop()
        message_limit = await loop.run_in_executor(None, partial(check_message_limit, user_id, is_pro))
        greeting_limit = await loop.run_in_executor(None, partial(check_greeting_limit, user_id, is_pro))
        max_length = await loop.run_in_executor(None, partial(get_config, 'limit_message_max_length', 500))

        return {
            "success": True,
            "is_pro": is_pro,
            "message_limit": message_limit,
            "greeting_limit": greeting_limit,
            "max_length": max_length
        }
    except Exception as e:
        logger.error(f"取得限制狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得限制狀態失敗: {str(e)}")


# DEBUG: 臨時調試端點 - 查看訊息狀態
@router.get("/api/messages/debug/{conversation_id}")
async def debug_messages_endpoint(
    conversation_id: int,
    user_id: str = Query(..., description="用戶 ID"),
):
    """
    調試用 - 查看對話中訊息的 is_read 狀態
    """
    from core.database.connection import get_connection
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT id, from_user_id, to_user_id, is_read, 
                   substr(content, 1, 20) as preview
            FROM dm_messages 
            WHERE conversation_id = ?
            ORDER BY id DESC LIMIT 10
        ''', (conversation_id,))
        rows = c.fetchall()
        messages = [
            {
                "id": r[0],
                "from": r[1][:8] if r[1] else None,
                "to": r[2][:8] if r[2] else None,
                "is_read": bool(r[3]),
                "preview": r[4]
            }
            for r in rows
        ]
        return {
            "conversation_id": conversation_id,
            "viewer": user_id[:8] if user_id else None,
            "messages": messages
        }
    finally:
        conn.close()


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
        # 先接受連接，等待認證
        await websocket.accept()

        # 等待認證訊息
        try:
            auth_data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            auth_message = json.loads(auth_data)

            # Authenticate with Token
            token = auth_message.get("token") or auth_message.get("access_token")
            # If token is not provided but user_id is, it's INSECURE. We ENFORCE token.
            
            if not token:
                await websocket.send_json({"type": "error", "message": "Authentication required (Missing Token)"})
                await websocket.close()
                return

            # Verify Token
            try:
                payload = verify_token(token)
                user_id = payload.get("sub")
                if not user_id:
                    raise HTTPException(status_code=401, detail="Invalid token payload")
            except Exception as e:
                logger.warning(f"WebSocket auth failed: {e}")
                await websocket.send_json({"type": "error", "message": "Invalid Token"})
                await websocket.close()
                return

            # Optional: Check if the token user matches the claimed user_id if provided
            if auth_message.get("user_id") and auth_message["user_id"] != user_id:
                 logger.warning(f"WebSocket auth mismatch: Token user {user_id} != Claimed {auth_message['user_id']}")
                 await websocket.send_json({"type": "error", "message": "User ID mismatch"})
                 await websocket.close()
                 return   

            # 驗證用戶存在
            loop = asyncio.get_running_loop()
            user_exists = await loop.run_in_executor(None, get_user_by_id, user_id)
            if not user_exists:
                await websocket.send_json({"type": "error", "message": "用戶不存在"})
                await websocket.close()
                return

        except asyncio.TimeoutError:
            await websocket.send_json({"type": "error", "message": "認證超時"})
            await websocket.close()
            return

        # 重新註冊連接（因為已經 accept 過了，需要用不同方式）
        async with message_manager.lock:
            if user_id not in message_manager.active_connections:
                message_manager.active_connections[user_id] = set()
            message_manager.active_connections[user_id].add(websocket)

        logger.info(f"用戶 {user_id} WebSocket 認證成功")

        # 更新用戶最後活動時間
        await loop.run_in_executor(None, update_last_active, user_id)

        # 發送認證成功和未讀數量
        unread_count = await loop.run_in_executor(None, get_unread_count, user_id)
        await websocket.send_json({
            "type": "authenticated",
            "user_id": user_id,
            "unread_count": unread_count
        })

        # 主循環
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
