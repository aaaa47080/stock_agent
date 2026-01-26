"""
回覆相關 API（推/噓/一般回覆）
"""
from fastapi import APIRouter, HTTPException, Query

from core.database import (
    get_post_by_id,
    add_comment,
    get_comments,
    get_daily_comment_count,
)
from .models import AddCommentRequest

router = APIRouter(prefix="/api/forum/posts", tags=["Forum - Comments"])


# 有效的回覆類型
VALID_COMMENT_TYPES = ["push", "boo", "comment"]


@router.get("/{post_id}/comments")
async def list_comments(post_id: int):
    """
    獲取文章的回覆列表
    """
    try:
        # 確認文章存在
        post = get_post_by_id(post_id, increment_view=False)
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        comments = get_comments(post_id)
        return {
            "success": True,
            "comments": comments,
            "count": len(comments)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取回覆列表失敗: {str(e)}")


@router.post("/{post_id}/comments")
async def add_new_comment(
    post_id: int,
    request: AddCommentRequest,
    user_id: str = Query(..., description="用戶 ID"),
):
    """
    新增回覆

    類型：
    - push: 推（支持）
    - boo: 噓（反對）
    - comment: 一般回覆

    限制：
    - 免費會員每日回覆上限從 /api/config/limits 獲取
    - PRO 會員無限制
    """
    try:
        # 驗證回覆類型
        if request.type not in VALID_COMMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"無效的回覆類型，可選: {', '.join(VALID_COMMENT_TYPES)}"
            )

        # 確認文章存在
        post = get_post_by_id(post_id, increment_view=False)
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        # 新增回覆
        result = add_comment(
            post_id=post_id,
            user_id=user_id,
            comment_type=request.type,
            content=request.content,
            parent_id=request.parent_id,
        )

        if not result["success"]:
            if result.get("error") == "daily_limit_reached":
                raise HTTPException(
                    status_code=429,
                    detail=f"已達每日回覆上限 ({result['limit']} 則)，升級 PRO 會員可無限回覆"
                )
            raise HTTPException(status_code=500, detail=result.get("error", "新增回覆失敗"))

        return {
            "success": True,
            "message": "回覆成功",
            "comment_id": result["comment_id"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增回覆失敗: {str(e)}")


@router.post("/{post_id}/push")
async def push_post(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    content: str = Query(None, max_length=100, description="推文內容（選填）"),
):
    """
    推文（快捷方式）
    """
    try:
        post = get_post_by_id(post_id, increment_view=False)
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        result = add_comment(
            post_id=post_id,
            user_id=user_id,
            comment_type="push",
            content=content,
        )

        if not result["success"]:
            if result.get("error") == "daily_limit_reached":
                raise HTTPException(status_code=429, detail="已達每日回覆上限")
            raise HTTPException(status_code=500, detail=result.get("error", "推文失敗"))

        return {"success": True, "message": "推文成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推文失敗: {str(e)}")


@router.post("/{post_id}/boo")
async def boo_post(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    content: str = Query(None, max_length=100, description="噓文內容（選填）"),
):
    """
    噓文（快捷方式）
    """
    try:
        post = get_post_by_id(post_id, increment_view=False)
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        result = add_comment(
            post_id=post_id,
            user_id=user_id,
            comment_type="boo",
            content=content,
        )

        if not result["success"]:
            if result.get("error") == "daily_limit_reached":
                raise HTTPException(status_code=429, detail="已達每日回覆上限")
            raise HTTPException(status_code=500, detail=result.get("error", "噓文失敗"))

        return {"success": True, "message": "噓文成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"噓文失敗: {str(e)}")


@router.get("/{post_id}/comment-status")
async def get_comment_status(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
):
    """
    獲取用戶在該文章的回覆狀態（今日剩餘回覆數等）
    """
    try:
        daily_count = get_daily_comment_count(user_id)
        return {
            "success": True,
            "today_count": daily_count["count"],
            "daily_limit": daily_count["limit"],
            "remaining": daily_count["remaining"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取回覆狀態失敗: {str(e)}")
