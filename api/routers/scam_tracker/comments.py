"""
可疑錢包追蹤系統 - 評論 API
"""
from fastapi import APIRouter, HTTPException, Query, Depends
import asyncio
import logging

from api.deps import get_current_user
from core.database.scam_tracker import (
    add_scam_comment,
    get_scam_comments,
)
from core.database.user import get_user_by_id
from .models import CommentCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["Scam Tracker - Comments"])


async def run_sync(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


@router.get("/{report_id}", response_model=dict)
async def list_scam_comments(
    report_id: int,
    limit: int = Query(50, ge=1, le=100, description="每頁數量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """
    獲取評論列表

    公開端點，所有用戶可查看。
    """
    try:
        comments = await run_sync(
            lambda: get_scam_comments(report_id=report_id, limit=limit, offset=offset)
        )

        return {
            "success": True,
            "comments": comments,
            "count": len(comments)
        }
    except Exception as e:
        logger.error(f"List scam comments failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="獲取評論列表失敗，請稍後再試")


@router.post("/{report_id}", response_model=dict)
async def add_comment_to_report(
    report_id: int,
    request: CommentCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    添加評論

    僅 Premium 會員可使用，用於分享受騙經歷或補充證據。
    """
    try:
        user_id = current_user.get("user_id")

        # 驗證用戶是否存在
        user = await run_sync(get_user_by_id, user_id)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="用戶不存在或憑證失效，請重新登入"
            )

        result = await run_sync(
            lambda: add_scam_comment(
                report_id=report_id,
                user_id=user_id,
                content=request.content,
                transaction_hash=request.transaction_hash
            )
        )

        if result.get("success"):
            return {
                "success": True,
                "comment_id": result["comment_id"],
                "message": "評論添加成功"
            }
        else:
            error = result.get("error")
            detail = result.get("detail", "")

            if error == "premium_membership_required":
                raise HTTPException(status_code=403, detail="需要 Premium 會員權限")
            elif error == "report_not_found":
                raise HTTPException(status_code=404, detail="舉報不存在")
            elif error == "invalid_tx_hash":
                raise HTTPException(status_code=400, detail=f"交易哈希無效: {detail}")
            elif error == "content_validation_failed":
                warnings = result.get("warnings", [])
                raise HTTPException(
                    status_code=400,
                    detail={"error": "內容審核未通過", "warnings": warnings}
                )
            else:
                raise HTTPException(status_code=500, detail=f"添加評論失敗: {error}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add scam comment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="添加評論失敗，請稍後再試")
