"""
可疑錢包追蹤系統 - 投票 API
"""
from fastapi import APIRouter, HTTPException, Depends
import asyncio
from functools import partial
import logging

from api.deps import get_current_user
from core.database.scam_tracker import vote_scam_report
from .models import VoteRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/votes", tags=["Scam Tracker - Votes"])


@router.post("/{report_id}", response_model=dict)
async def vote_on_report(
    report_id: int,
    request: VoteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    對舉報投票

    支持 Toggle 切換：
    - 點擊相同類型 = 取消投票
    - 點擊不同類型 = 切換投票

    需要登入，舉報者本人不能對自己的舉報投票。
    """
    try:
        user_id = current_user.get("user_id")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                vote_scam_report,
                report_id=report_id,
                user_id=user_id,
                vote_type=request.vote_type
            )
        )

        if result.get("success"):
            action = result.get("action")
            action_messages = {
                "voted": f"{'贊同' if request.vote_type == 'approve' else '反對'}成功",
                "cancelled": f"已取消{'贊同' if request.vote_type == 'approve' else '反對'}",
                "switched": f"已切換為{'贊同' if request.vote_type == 'approve' else '反對'}"
            }

            return {
                "success": True,
                "action": action,
                "message": action_messages.get(action, "投票成功")
            }
        else:
            error = result.get("error")

            if error == "report_not_found":
                raise HTTPException(status_code=404, detail="舉報不存在")
            elif error == "cannot_vote_own_report":
                raise HTTPException(status_code=403, detail="不能對自己的舉報投票")
            elif error == "vote_too_fast":
                raise HTTPException(status_code=429, detail="投票過於頻繁，請稍後再試")
            else:
                raise HTTPException(status_code=500, detail=f"投票失敗: {error}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vote on scam report failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"投票失敗: {str(e)}")
