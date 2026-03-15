"""
回覆相關 API（推/噓/一般回覆）
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from api.utils import run_sync
import logging

from api.deps import get_current_user
from core.database import (
    get_post_by_id,
    add_comment,
    get_comments,
    get_daily_comment_count,
)
from core.database.notifications import notify_post_interaction
from api.routers.notifications import push_notification_to_user
from .models import AddCommentRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forum/posts", tags=["Forum - Comments"])


# 有效的回覆類型
VALID_COMMENT_TYPES = ["push", "boo", "comment"]


@router.get("/{post_id}/comments")
async def list_comments(post_id: int):
    """
    獲取文章的回覆列表
    """
    try:
        post = await run_sync(lambda: get_post_by_id(post_id, increment_view=False))
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        comments = await run_sync(get_comments, post_id)
        return {
            "success": True,
            "comments": comments,
            "count": len(comments)
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="獲取回覆列表失敗，請稍後再試")


@router.post("/{post_id}/comments")
async def add_new_comment(
    post_id: int,
    request: AddCommentRequest,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    新增回覆

    類型：
    - push: 推（支持）
    - boo: 噓（反對）
    - comment: 一般回覆

    限制：
    - 免費會員每日回覆上限從 /api/config/limits 獲取
    - Premium 會員無限制
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to comment as this user")

    try:
        if request.type not in VALID_COMMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"無效的回覆類型，可選: {', '.join(VALID_COMMENT_TYPES)}"
            )

        post = await run_sync(lambda: get_post_by_id(post_id, increment_view=False))
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        result = await run_sync(
            lambda: add_comment(
                post_id=post_id,
                user_id=user_id,
                comment_type=request.type,
                content=request.content,
                parent_id=request.parent_id,
            )
        )

        if not result["success"]:
            if result.get("error") == "daily_limit_reached":
                raise HTTPException(
                    status_code=429,
                    detail=f"已達每日回覆上限 ({result['limit']} 則)，升級 Premium 會員可無限回覆"
                )
            raise HTTPException(status_code=500, detail=result.get("error", "新增回覆失敗"))

        # 通知文章作者（不通知自己）
        if post["user_id"] != user_id:
            try:
                from_username = current_user.get("username", user_id)
                notification = await run_sync(
                    notify_post_interaction,
                    post["user_id"],
                    from_username,
                    request.type,
                    post_id,
                    post["title"]
                )
                if notification:
                    await push_notification_to_user(post["user_id"], notification)
            except Exception as notify_error:
                logger.warning(f"Failed to send comment notification: {notify_error}")

        return {
            "success": True,
            "message": "回覆成功",
            "comment_id": result["comment_id"]
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="新增回覆失敗，請稍後再試")


async def _react_post(
    post_id: int, reaction: str, user_id: str, content: Optional[str], current_user: dict
):
    """推/噓文共用邏輯"""
    post = await run_sync(lambda: get_post_by_id(post_id, increment_view=False))
    if not post or post["is_hidden"]:
        raise HTTPException(status_code=404, detail="文章不存在")

    result = await run_sync(
        lambda: add_comment(post_id=post_id, user_id=user_id, comment_type=reaction, content=content)
    )

    if not result["success"]:
        if result.get("error") == "daily_limit_reached":
            raise HTTPException(status_code=429, detail="已達每日回覆上限")
        raise HTTPException(status_code=500, detail=result.get("error", f"{reaction}失敗"))

    if post["user_id"] != user_id:
        try:
            notification = await run_sync(
                notify_post_interaction,
                post["user_id"], current_user.get("username", user_id), reaction, post_id, post["title"]
            )
            if notification:
                await push_notification_to_user(post["user_id"], notification)
        except Exception as e:
            logger.warning(f"Failed to send {reaction} notification: {e}")

    labels = {"push": "推文", "boo": "噓文"}
    return {"success": True, "message": f"{labels.get(reaction, reaction)}成功"}


@router.post("/{post_id}/push")
async def push_post(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    content: str = Query(None, max_length=100, description="推文內容（選填）"),
    current_user: dict = Depends(get_current_user)
):
    """推文（快捷方式）"""
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        return await _react_post(post_id, "push", user_id, content, current_user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="推文失敗，請稍後再試")


@router.post("/{post_id}/boo")
async def boo_post(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    content: str = Query(None, max_length=100, description="噓文內容（選填）"),
    current_user: dict = Depends(get_current_user)
):
    """噓文（快捷方式）"""
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        return await _react_post(post_id, "boo", user_id, content, current_user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="噓文失敗，請稍後再試")


@router.get("/{post_id}/comment-status")
async def get_comment_status(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    獲取用戶在該文章的回覆狀態（今日剩餘回覆數等）
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        daily_count = await run_sync(get_daily_comment_count, user_id)
        return {
            "success": True,
            "today_count": daily_count["count"],
            "daily_limit": daily_count["limit"],
            "remaining": daily_count["remaining"],
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取回覆狀態失敗，請稍後再試")
