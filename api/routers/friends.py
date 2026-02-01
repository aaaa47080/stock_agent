"""
好友功能 API 端點
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field

from core.database import (
    search_users,
    get_public_user_profile,
    send_friend_request,
    accept_friend_request,
    reject_friend_request,
    cancel_friend_request,
    remove_friend,
    block_user,
    unblock_user,
    get_blocked_users,
    get_friends_list,
    get_pending_requests_received,
    get_pending_requests_sent,
    get_friendship_status,
    get_friends_count,
    get_pending_count,
    get_user_by_id,
)
from api.utils import logger
import asyncio
from functools import partial

from api.deps import get_current_user
from fastapi import Depends

router = APIRouter()


# ============================================================================
# 請求模型
# ============================================================================

class FriendActionRequest(BaseModel):
    """好友操作請求"""
    target_user_id: str = Field(..., description="目標用戶 ID")


# ============================================================================
# 用戶搜尋 / 發現
# ============================================================================

@router.get("/api/friends/search")
async def search_users_endpoint(
    q: str = Query(..., min_length=1, max_length=50, description="搜尋關鍵字"),
    user_id: str = Query(..., description="當前用戶 ID"),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    以用戶名搜尋用戶
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")

        loop = asyncio.get_running_loop()
        users = await loop.run_in_executor(None, partial(search_users, query=q, limit=limit, exclude_user_id=user_id))

        # 為每個用戶添加好友狀態
        for user in users:
            status = await loop.run_in_executor(None, get_friendship_status, user_id, user["user_id"])
            user["friend_status"] = status.get("status") if status else None
            user["is_friend"] = status.get("status") == "accepted" if status else False
            # 重要：返回 is_requester 讓前端知道是誰發起的請求
            user["is_requester"] = status.get("is_requester") if status else False

        return {"success": True, "users": users, "count": len(users)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜尋用戶失敗: {e}")
        raise HTTPException(status_code=500, detail=f"搜尋失敗: {str(e)}")


@router.get("/api/friends/profile/{target_user_id}")
async def get_user_profile(
    target_user_id: str,
    user_id: Optional[str] = Query(None, description="查看者的用戶 ID"),
):
    """
    取得用戶的公開資料
    """
    try:
        loop = asyncio.get_running_loop()
        profile = await loop.run_in_executor(None, partial(get_public_user_profile, target_user_id, viewer_user_id=user_id))
        if not profile:
            raise HTTPException(status_code=404, detail="用戶不存在")
        return {"success": True, "profile": profile}
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得用戶資料失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得資料失敗: {str(e)}")


# ============================================================================
# 好友請求
# ============================================================================

@router.post("/api/friends/request")
async def send_request(
    request: FriendActionRequest,
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    發送好友請求
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")

        loop = asyncio.get_running_loop()
        # 驗證用戶存在
        user_exists = await loop.run_in_executor(None, get_user_by_id, user_id)
        if not user_exists:
            raise HTTPException(status_code=401, detail="用戶不存在")
        target_exists = await loop.run_in_executor(None, get_user_by_id, request.target_user_id)
        if not target_exists:
            raise HTTPException(status_code=404, detail="目標用戶不存在")

        result = await loop.run_in_executor(None, send_friend_request, user_id, request.target_user_id)

        if not result["success"]:
            error_messages = {
                "cannot_add_self": "無法加自己為好友",
                "already_friends": "你們已經是好友了",
                "request_pending": "已有待處理的好友請求",
                "user_blocked_you": "無法發送請求給此用戶",
                "you_blocked_user": "你已封鎖此用戶，請先解除封鎖",
            }
            raise HTTPException(
                status_code=400,
                detail=error_messages.get(result["error"], result["error"])
            )

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"發送好友請求失敗: {e}")
        raise HTTPException(status_code=500, detail=f"發送請求失敗: {str(e)}")


@router.post("/api/friends/accept")
async def accept_request(
    request: FriendActionRequest,
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    接受好友請求
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, accept_friend_request, user_id, request.target_user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail="找不到此好友請求")

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"接受好友請求失敗: {e}")
        raise HTTPException(status_code=500, detail=f"接受請求失敗: {str(e)}")


@router.post("/api/friends/reject")
async def reject_request(
    request: FriendActionRequest,
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    拒絕好友請求
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, reject_friend_request, user_id, request.target_user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail="找不到此好友請求")

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"拒絕好友請求失敗: {e}")
        raise HTTPException(status_code=500, detail=f"拒絕請求失敗: {str(e)}")


@router.post("/api/friends/cancel")
async def cancel_request(
    request: FriendActionRequest,
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取消已發送的好友請求
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, cancel_friend_request, user_id, request.target_user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail="找不到此好友請求")

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消好友請求失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取消請求失敗: {str(e)}")


@router.delete("/api/friends/remove")
async def remove_friend_endpoint(
    target_user_id: str = Query(..., description="好友的用戶 ID"),
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    移除好友
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, remove_friend, user_id, target_user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail="你們不是好友")

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除好友失敗: {e}")
        raise HTTPException(status_code=500, detail=f"移除好友失敗: {str(e)}")


# ============================================================================
# 封鎖功能
# ============================================================================

@router.post("/api/friends/block")
async def block_user_endpoint(
    request: FriendActionRequest,
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    封鎖用戶
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, block_user, user_id, request.target_user_id)

        if not result["success"]:
            error_messages = {
                "cannot_block_self": "無法封鎖自己",
            }
            raise HTTPException(
                status_code=400,
                detail=error_messages.get(result["error"], result["error"])
            )

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"封鎖用戶失敗: {e}")
        raise HTTPException(status_code=500, detail=f"封鎖失敗: {str(e)}")


@router.post("/api/friends/unblock")
async def unblock_user_endpoint(
    request: FriendActionRequest,
    user_id: str = Query(..., description="當前用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    解除封鎖
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, unblock_user, user_id, request.target_user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail="此用戶未被封鎖")

        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解除封鎖失敗: {e}")
        raise HTTPException(status_code=500, detail=f"解除封鎖失敗: {str(e)}")


@router.get("/api/friends/blocked")
async def get_blocked_list(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得封鎖名單
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        blocked = await loop.run_in_executor(None, get_blocked_users, user_id)
        return {
            "success": True,
            "blocked_users": blocked,
            "count": len(blocked)
        }
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's an HTTPException that wasn't caught (e.g. import mismatch)
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            raise e
        logger.error(f"取得封鎖名單失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得封鎖名單失敗: {str(e)}")


# ============================================================================
# 好友列表
# ============================================================================

@router.get("/api/friends/list")
async def get_friends(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    取得好友列表
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        friends = await loop.run_in_executor(None, partial(get_friends_list, user_id, limit=limit, offset=offset))
        count = await loop.run_in_executor(None, get_friends_count, user_id)

        return {
            "success": True,
            "friends": friends,
            "count": len(friends),
            "total": count
        }
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's an HTTPException that wasn't caught (e.g. import mismatch)
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            raise e
        logger.error(f"取得好友列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得好友列表失敗: {str(e)}")


@router.get("/api/friends/requests/received")
async def get_received_requests(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得收到的好友請求
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        requests = await loop.run_in_executor(None, get_pending_requests_received, user_id)
        return {
            "success": True,
            "requests": requests,
            "count": len(requests)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得好友請求失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得好友請求失敗: {str(e)}")


@router.get("/api/friends/requests/sent")
async def get_sent_requests(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得已發送的好友請求
    """
    try:
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
        loop = asyncio.get_running_loop()
        requests = await loop.run_in_executor(None, get_pending_requests_sent, user_id)
        return {
            "success": True,
            "requests": requests,
            "count": len(requests)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得已發送請求失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得已發送請求失敗: {str(e)}")


@router.get("/api/friends/status/{target_user_id}")
async def get_status(
    target_user_id: str,
    user_id: str = Query(..., description="當前用戶 ID"),
):
    """
    取得與特定用戶的好友狀態
    """
    try:
        loop = asyncio.get_running_loop()
        status = await loop.run_in_executor(None, get_friendship_status, user_id, target_user_id)
        return {
            "success": True,
            "status": status.get("status") if status else None,
            "is_friend": status.get("status") == "accepted" if status else False,
            "is_requester": status.get("is_requester") if status else False,
            "details": status
        }
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得好友狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得狀態失敗: {str(e)}")


@router.get("/api/friends/counts")
async def get_counts(
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    取得好友相關數量（好友數、待處理請求數）
    """
    try:
        print(f"[DEBUG_FRIENDS] Auth check: current={current_user.get('user_id')} target={user_id}")
        if current_user["user_id"] != user_id:
             print(f"[DEBUG_FRIENDS] 403 Mismatch! Current: '{current_user.get('user_id')}' vs Target: '{user_id}'")
             raise HTTPException(status_code=403, detail=f"Not authorized. user_id={user_id}, current={current_user.get('user_id')}")
        loop = asyncio.get_running_loop()
        friends_count = await loop.run_in_executor(None, get_friends_count, user_id)
        pending_received = await loop.run_in_executor(None, get_pending_count, user_id)
        return {
            "success": True,
            "friends_count": friends_count,
            "pending_received": pending_received,
        }
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得好友數量失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得數量失敗: {str(e)}")
