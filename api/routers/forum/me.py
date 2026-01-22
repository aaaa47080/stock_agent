"""
個人後台相關 API
"""
from fastapi import APIRouter, HTTPException, Query

from core.database import (
    get_user_posts,
    get_user_forum_stats,
    get_user_payment_history,
    get_tips_sent,
    get_tips_received,
    get_tips_total_received,
    get_user_membership,
    get_daily_comment_count,
    get_daily_post_count,
)

router = APIRouter(prefix="/api/forum/me", tags=["Forum - Me"])


@router.get("/limits")
async def get_my_limits(user_id: str = Query(..., description="用戶 ID")):
    """
    獲取我的每日限制狀態 (發文與回覆)
    """
    try:
        post_limits = get_daily_post_count(user_id)
        comment_limits = get_daily_comment_count(user_id)
        membership = get_user_membership(user_id)
        
        return {
            "success": True,
            "limits": {
                "post": post_limits,
                "comment": comment_limits
            },
            "membership": membership
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取限制狀態失敗: {str(e)}")


@router.get("/stats")
async def get_my_stats(user_id: str = Query(..., description="用戶 ID")):
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
        stats = get_user_forum_stats(user_id)
        membership = get_user_membership(user_id)
        daily_comments = get_daily_comment_count(user_id)

        return {
            "success": True,
            "stats": {
                **stats,
                "membership": membership,
                "daily_comments": daily_comments,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取統計資料失敗: {str(e)}")


@router.get("/posts")
async def get_my_posts(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    獲取我的文章列表
    """
    try:
        posts = get_user_posts(user_id, limit=limit, offset=offset)
        return {
            "success": True,
            "posts": posts,
            "count": len(posts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取文章列表失敗: {str(e)}")


@router.get("/tips/sent")
async def get_my_sent_tips(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    獲取我送出的打賞記錄
    """
    try:
        tips = get_tips_sent(user_id, limit=limit)
        return {
            "success": True,
            "tips": tips,
            "count": len(tips),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取打賞記錄失敗: {str(e)}")


@router.get("/tips/received")
async def get_my_received_tips(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    獲取我收到的打賞記錄
    """
    try:
        tips = get_tips_received(user_id, limit=limit)
        total = get_tips_total_received(user_id)
        return {
            "success": True,
            "tips": tips,
            "count": len(tips),
            "total_received": total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取打賞記錄失敗: {str(e)}")


@router.get("/payments")
async def get_my_payments(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    獲取我的發文付款記錄
    """
    try:
        payments = get_user_payment_history(user_id, limit=limit)
        return {
            "success": True,
            "payments": payments,
            "count": len(payments),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取付款記錄失敗: {str(e)}")


@router.get("/membership")
async def get_my_membership(user_id: str = Query(..., description="用戶 ID")):
    """
    獲取我的會員狀態
    """
    try:
        membership = get_user_membership(user_id)
        return {
            "success": True,
            "membership": membership,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取會員狀態失敗: {str(e)}")
