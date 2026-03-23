"""
回覆相關 API（推/噓/一般回覆）
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_current_user
from api.middleware.rate_limit import limiter
from api.routers.notifications import push_notification_to_user
from api.utils import run_sync
from core.database import get_daily_comment_count
from core.orm.forum_repo import forum_repo
from core.orm.notifications_repo import notifications_repo

from .models import AddCommentRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forum/posts", tags=["Forum - Comments"])


# 有效的回覆類型
VALID_COMMENT_TYPES = ["push", "boo", "comment"]


@router.get("/{post_id}/comments")
async def list_comments(
    post_id: int,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    獲取文章的回覆列表
    """
    try:
        post = await forum_repo.get_post_by_id(post_id, increment_view=False)
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        comments = await forum_repo.get_comments(post_id, limit=limit, offset=offset)
        return {"success": True, "comments": comments, "count": len(comments)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="獲取回覆列表失敗，請稍後再試")


@router.post("/{post_id}/comments")
@limiter.limit("30/minute")
async def add_new_comment(
    request: Request,
    post_id: int,
    body: AddCommentRequest,
    current_user: dict = Depends(get_current_user),
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
    try:
        user_id = current_user["user_id"]

        if body.type not in VALID_COMMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"無效的回覆類型，可選: {', '.join(VALID_COMMENT_TYPES)}",
            )

        post = await forum_repo.get_post_by_id(post_id, increment_view=False)
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        result = await forum_repo.add_comment(
            post_id=post_id,
            user_id=user_id,
            comment_type=body.type,
            content=body.content,
            parent_id=body.parent_id,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=result.get("error", "新增回覆失敗")
            )

        if post["user_id"] != user_id:
            try:
                from_username = current_user.get("username", user_id)
                notification = await notifications_repo.notify_post_interaction(
                    post["user_id"],
                    from_username,
                    body.type,
                    post_id,
                    post["title"],
                )
                if notification:
                    await push_notification_to_user(post["user_id"], notification)
            except Exception as notify_error:
                logger.warning(f"Failed to send comment notification: {notify_error}")

        return {
            "success": True,
            "message": "回覆成功",
            "comment_id": result["comment_id"],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="新增回覆失敗，請稍後再試")


async def _react_post(
    post_id: int,
    reaction: str,
    user_id: str,
    content: Optional[str],
    current_user: dict,
):
    """推/噓文共用邏輯"""
    post = await forum_repo.get_post_by_id(post_id, increment_view=False)
    if not post or post["is_hidden"]:
        raise HTTPException(status_code=404, detail="文章不存在")

    result = await forum_repo.add_comment(
        post_id=post_id, user_id=user_id, comment_type=reaction, content=content
    )

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", f"{reaction}失敗")
        )

    if post["user_id"] != user_id:
        try:
            notification = await notifications_repo.notify_post_interaction(
                post["user_id"],
                current_user.get("username", user_id),
                reaction,
                post_id,
                post["title"],
            )
            if notification:
                await push_notification_to_user(post["user_id"], notification)
        except Exception as e:
            logger.warning(f"Failed to send {reaction} notification: {e}")

    labels = {"push": "推文", "boo": "噓文"}
    return {"success": True, "message": f"{labels.get(reaction, reaction)}成功"}


@router.post("/{post_id}/push")
@limiter.limit("30/minute")
async def push_post(
    request: Request,
    post_id: int,
    content: str = Query(None, max_length=100, description="推文內容（選填）"),
    current_user: dict = Depends(get_current_user),
):
    """推文（快捷方式）"""
    try:
        user_id = current_user["user_id"]
        return await _react_post(post_id, "push", user_id, content, current_user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="推文失敗，請稍後再試")


@router.post("/{post_id}/boo")
@limiter.limit("30/minute")
async def boo_post(
    request: Request,
    post_id: int,
    content: str = Query(None, max_length=100, description="噓文內容（選填）"),
    current_user: dict = Depends(get_current_user),
):
    """噓文（快捷方式）"""
    try:
        user_id = current_user["user_id"]
        return await _react_post(post_id, "boo", user_id, content, current_user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="噓文失敗，請稍後再試")


@router.get("/{post_id}/comment-status")
async def get_comment_status(
    post_id: int, current_user: dict = Depends(get_current_user)
):
    """
    獲取用戶在該文章的回覆狀態（今日剩餘回覆數等）
    """
    try:
        user_id = current_user["user_id"]

        daily_count = await run_sync(get_daily_comment_count, user_id)
        return {
            "success": True,
            "today_count": daily_count["count"],
            "daily_limit": daily_count["limit"],
            "remaining": daily_count["remaining"],
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取回覆狀態失敗，請稍後再試")
