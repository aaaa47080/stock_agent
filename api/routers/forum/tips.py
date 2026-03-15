"""
打賞相關 API
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from api.utils import run_sync

from api.deps import get_current_user
from core.database import (
    get_post_by_id,
    create_tip,
    get_tips_sent,
    get_tips_received,
    get_tips_total_received,
)
from .models import CreateTipRequest

router = APIRouter(prefix="/api/forum", tags=["Forum - Tips"])


@router.post("/posts/{post_id}/tip")
async def tip_post(
    post_id: int,
    request: CreateTipRequest,
    user_id: str = Query(..., description="打賞者的用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    打賞文章

    - 打賞金額從 /api/config/prices 獲取
    - Pi 從打賞者錢包直接轉到作者錢包（P2P）
    - 需提供交易哈希作為憑證
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to tip as this user")

    try:
        post = await run_sync(lambda: get_post_by_id(post_id, increment_view=False))
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章不存在")

        if post["user_id"] == user_id:
            raise HTTPException(status_code=400, detail="不能打賞自己的文章")

        tip_id = await run_sync(
            lambda: create_tip(
                post_id=post_id,
                from_user_id=user_id,
                to_user_id=post["user_id"],
                amount=request.amount,
                tx_hash=request.tx_hash,
            )
        )

        return {
            "success": True,
            "message": "打賞成功",
            "tip_id": tip_id,
            "amount": request.amount,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="打賞失敗，請稍後再試")


@router.get("/tips/sent")
async def get_sent_tips(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    獲取用戶送出的打賞記錄
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        tips = await run_sync(lambda: get_tips_sent(user_id, limit=limit))
        return {
            "success": True,
            "tips": tips,
            "count": len(tips),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取打賞記錄失敗，請稍後再試")


@router.get("/tips/received")
async def get_received_tips(
    user_id: str = Query(..., description="用戶 ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    獲取用戶收到的打賞記錄
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        tips = await run_sync(lambda: get_tips_received(user_id, limit=limit))
        total = await run_sync(get_tips_total_received, user_id)
        return {
            "success": True,
            "tips": tips,
            "count": len(tips),
            "total_received": total,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取打賞記錄失敗，請稍後再試")
