"""
個人後台相關 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_current_user
from api.utils import run_sync
from core.database import (
    get_daily_comment_count,
    get_daily_post_count,
    get_tips_received,
    get_tips_sent,
    get_tips_total_received,
    get_user_forum_stats,
    get_user_membership,
    get_user_payment_history,
    get_user_posts,
)

router = APIRouter(prefix="/api/forum/me", tags=["Forum - Me"])


@router.get("/limits")
async def get_my_limits(current_user: dict = Depends(get_current_user)):
    """
    獲取我的每日限制狀態 (發文與回覆)
    """
    try:
        user_id = current_user["user_id"]

        post_limits = await run_sync(get_daily_post_count, user_id)
        comment_limits = await run_sync(get_daily_comment_count, user_id)
        membership = await run_sync(get_user_membership, user_id)

        return {
            "success": True,
            "limits": {"post": post_limits, "comment": comment_limits},
            "membership": membership,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取限制狀態失敗，請稍後再試")


@router.get("/stats")
async def get_my_stats(current_user: dict = Depends(get_current_user)):
    """
    獲取我的論壇統計資料

    包含：
    - 文章數
    - 回覆數
    - 獲得的推數
    - 收到的打賞總額
    - 會員狀態
    - 今日回覆狀況
    """
    try:
        user_id = current_user["user_id"]

        stats = await run_sync(get_user_forum_stats, user_id)
        membership = await run_sync(get_user_membership, user_id)
        daily_comments = await run_sync(get_daily_comment_count, user_id)

        return {
            "success": True,
            "stats": {
                **stats,
                "membership": membership,
                "daily_comments": daily_comments,
            },
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取統計資料失敗，請稍後再試")


@router.get("/posts")
async def get_my_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取我的文章列表
    """
    try:
        user_id = current_user["user_id"]

        posts = await run_sync(
            lambda: get_user_posts(user_id, limit=limit, offset=offset)
        )
        return {
            "success": True,
            "posts": posts,
            "count": len(posts),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取文章列表失敗，請稍後再試")


@router.get("/tips/sent")
async def get_my_sent_tips(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取我送出的打賞記錄
    """
    try:
        user_id = current_user["user_id"]

        tips = await run_sync(
            lambda: get_tips_sent(user_id, limit=limit, offset=offset)
        )
        return {
            "success": True,
            "tips": tips,
            "count": len(tips),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取打賞記錄失敗，請稍後再試")


@router.get("/tips/received")
async def get_my_received_tips(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取我收到的打賞記錄
    """
    try:
        user_id = current_user["user_id"]

        tips = await run_sync(
            lambda: get_tips_received(user_id, limit=limit, offset=offset)
        )
        total = await run_sync(get_tips_total_received, user_id)
        return {
            "success": True,
            "tips": tips,
            "count": len(tips),
            "total_received": total,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取打賞記錄失敗，請稍後再試")


@router.get("/payments")
async def get_my_payments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取我的發文付款記錄
    """
    try:
        user_id = current_user["user_id"]

        payments = await run_sync(
            lambda: get_user_payment_history(user_id, limit=limit, offset=offset)
        )
        return {
            "success": True,
            "payments": payments,
            "count": len(payments),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取付款記錄失敗，請稍後再試")


@router.get("/membership")
async def get_my_membership(current_user: dict = Depends(get_current_user)):
    """
    獲取我的會員狀態
    """
    try:
        user_id = current_user["user_id"]

        membership = await run_sync(get_user_membership, user_id)
        return {
            "success": True,
            "membership": membership,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取會員狀態失敗，請稍後再試")
