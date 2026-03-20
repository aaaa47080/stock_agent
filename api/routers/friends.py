"""
好友功能 API 端點
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from core.orm.friends_repo import friends_repo
from core.orm.notifications_repo import notifications_repo
from core.orm.repositories import user_repo
from core.orm.session import get_async_session
from api.utils import logger
from api.deps import get_current_user
from fastapi import Depends
from api.routers.notifications import push_notification_to_user

router = APIRouter()


class FriendActionRequest(BaseModel):
    target_user_id: str = Field(..., description="目標用戶 ID")


# ============================================================================
# 用戶搜尋 / 發現
# ============================================================================

@router.get("/api/friends/search")
async def search_users_endpoint(
    q: str = Query(..., min_length=1, max_length=50, description="搜尋關鍵字"),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        users = await friends_repo.search_users(
            query=q, limit=limit, exclude_user_id=user_id, session=session,
        )

        if users:
            other_ids = [u["user_id"] for u in users]
            bulk_status = await friends_repo.get_bulk_friendship_status(
                user_id, other_ids, session=session,
            )
            for u in users:
                status = bulk_status.get(u["user_id"])
                u["friend_status"] = status.get("status") if status else None
                u["is_friend"] = status.get("status") == "accepted" if status else False
                u["is_requester"] = status.get("is_requester") if status else False

        return {"success": True, "users": users, "count": len(users)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search users failed: %s", e)
        raise HTTPException(status_code=500, detail="搜尋失敗，請稍後再試")


@router.get("/api/friends/profile/{target_user_id}")
async def get_user_profile(
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        profile = await friends_repo.get_public_user_profile(
            target_user_id, viewer_user_id=user_id, session=session,
        )
        if not profile:
            raise HTTPException(status_code=404, detail="用戶不存在")
        return {"success": True, "profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get user profile failed: %s", e)
        raise HTTPException(status_code=500, detail="取得資料失敗，請稍後再試")


# ============================================================================
# 好友請求
# ============================================================================

@router.post("/api/friends/request")
async def send_request(
    request: FriendActionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        user_exists = await user_repo.get_by_id(user_id, session=session)
        if not user_exists:
            raise HTTPException(status_code=401, detail="用戶不存在")
        target_exists = await user_repo.get_by_id(request.target_user_id, session=session)
        if not target_exists:
            raise HTTPException(status_code=404, detail="目標用戶不存在")

        result = await friends_repo.send_friend_request(
            user_id, request.target_user_id, session=session,
        )

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
                detail=error_messages.get(result["error"], result["error"]),
            )

        try:
            current_username = current_user.get("username", user_id)
            notification = await notifications_repo.create_notification(
                user_id=request.target_user_id,
                notification_type="friend_request",
                title="好友請求",
                body=f"{current_username} 想加你為好友",
                data={
                    "from_user_id": user_id,
                    "from_username": current_username,
                },
                session=session,
            )
            if notification:
                await push_notification_to_user(request.target_user_id, notification)
            logger.info("Friend request notification sent to %s", request.target_user_id)
        except Exception as notify_error:
            logger.warning("Failed to send friend request notification: %s", notify_error)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Send friend request failed: %s", e)
        raise HTTPException(status_code=500, detail="發送請求失敗，請稍後再試")


@router.post("/api/friends/accept")
async def accept_request(
    request: FriendActionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        result = await friends_repo.accept_friend_request(
            user_id, request.target_user_id, session=session,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail="找不到此好友請求")

        try:
            current_username = current_user.get("username", user_id)
            notification = await notifications_repo.create_notification(
                user_id=request.target_user_id,
                notification_type="friend_request",
                title="好友已接受",
                body=f"{current_username} 已接受你的好友請求",
                data={
                    "from_user_id": user_id,
                    "from_username": current_username,
                    "action": "accepted",
                },
                session=session,
            )
            if notification:
                await push_notification_to_user(request.target_user_id, notification)
            logger.info("Friend accepted notification sent to %s", request.target_user_id)
        except Exception as notify_error:
            logger.warning("Failed to send friend accepted notification: %s", notify_error)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Accept friend request failed: %s", e)
        raise HTTPException(status_code=500, detail="接受請求失敗，請稍後再試")


@router.post("/api/friends/reject")
async def reject_request(
    request: FriendActionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        result = await friends_repo.reject_friend_request(
            user_id, request.target_user_id, session=session,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail="找不到此好友請求")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Reject friend request failed: %s", e)
        raise HTTPException(status_code=500, detail="拒絕請求失敗，請稍後再試")


@router.post("/api/friends/cancel")
async def cancel_request(
    request: FriendActionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        result = await friends_repo.cancel_friend_request(
            user_id, request.target_user_id, session=session,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail="找不到此好友請求")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cancel friend request failed: %s", e)
        raise HTTPException(status_code=500, detail="取消請求失敗，請稍後再試")


@router.delete("/api/friends/remove")
async def remove_friend_endpoint(
    target_user_id: str = Query(..., description="好友的用戶 ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        result = await friends_repo.remove_friend(
            user_id, target_user_id, session=session,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail="你們不是好友")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Remove friend failed: %s", e)
        raise HTTPException(status_code=500, detail="移除好友失敗，請稍後再試")


# ============================================================================
# 封鎖功能
# ============================================================================

@router.post("/api/friends/block")
async def block_user_endpoint(
    request: FriendActionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        result = await friends_repo.block_user(
            user_id, request.target_user_id, session=session,
        )

        if not result["success"]:
            error_messages = {
                "cannot_block_self": "無法封鎖自己",
            }
            raise HTTPException(
                status_code=400,
                detail=error_messages.get(result["error"], result["error"]),
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Block user failed: %s", e)
        raise HTTPException(status_code=500, detail="封鎖失敗，請稍後再試")


@router.post("/api/friends/unblock")
async def unblock_user_endpoint(
    request: FriendActionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        result = await friends_repo.unblock_user(
            user_id, request.target_user_id, session=session,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail="此用戶未被封鎖")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unblock user failed: %s", e)
        raise HTTPException(status_code=500, detail="解除封鎖失敗，請稍後再試")


@router.get("/api/friends/blocked")
async def get_blocked_list(
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        blocked = await friends_repo.get_blocked_users(user_id, limit=limit, session=session)
        return {
            "success": True,
            "blocked_users": blocked,
            "count": len(blocked),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get blocked list failed: %s", e)
        raise HTTPException(status_code=500, detail="取得封鎖名單失敗，請稍後再試")


# ============================================================================
# 好友列表
# ============================================================================

@router.get("/api/friends/list")
async def get_friends(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        friends = await friends_repo.get_friends_list(
            user_id, limit=limit, offset=offset, session=session,
        )
        count = await friends_repo.get_friends_count(user_id, session=session)

        return {
            "success": True,
            "friends": friends,
            "count": len(friends),
            "total": count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get friends list failed: %s", e)
        raise HTTPException(status_code=500, detail="取得好友列表失敗，請稍後再試")


@router.get("/api/friends/requests/received")
async def get_received_requests(
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        requests = await friends_repo.get_pending_requests_received(
            user_id, limit=limit, session=session,
        )
        return {
            "success": True,
            "requests": requests,
            "count": len(requests),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get received requests failed: %s", e)
        raise HTTPException(status_code=500, detail="取得好友請求失敗，請稍後再試")


@router.get("/api/friends/requests/sent")
async def get_sent_requests(
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        requests = await friends_repo.get_pending_requests_sent(
            user_id, limit=limit, session=session,
        )
        return {
            "success": True,
            "requests": requests,
            "count": len(requests),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get sent requests failed: %s", e)
        raise HTTPException(status_code=500, detail="取得已發送請求失敗，請稍後再試")


@router.get("/api/friends/status/{target_user_id}")
async def get_status(
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        status = await friends_repo.get_friendship_status(
            user_id, target_user_id, session=session,
        )
        return {
            "success": True,
            "status": status.get("status") if status else None,
            "is_friend": status.get("status") == "accepted" if status else False,
            "is_requester": status.get("is_requester") if status else False,
            "details": status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get friend status failed: %s", e)
        raise HTTPException(status_code=500, detail="取得狀態失敗，請稍後再試")


@router.get("/api/friends/counts")
async def get_counts(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user_id = current_user["user_id"]
        friends_count = await friends_repo.get_friends_count(user_id, session=session)
        pending_received = await friends_repo.get_pending_count(user_id, session=session)
        return {
            "success": True,
            "friends_count": friends_count,
            "pending_received": pending_received,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get friend counts failed: %s", e)
        raise HTTPException(status_code=500, detail="取得數量失敗，請稍後再試")
