"""
可疑錢包追蹤系統 - 舉報管理 API
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
import asyncio
from functools import partial
import logging

from api.deps import get_current_user
from core.database.scam_tracker import (
    create_scam_report,
    get_scam_reports,
    get_scam_report_by_id,
    search_wallet,
)
from core.database.system_config import get_config
from core.database.user import get_user_by_id
from .models import ScamReportCreate, ScamReportResponse, ScamReportDetailResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Scam Tracker - Reports"])


@router.get("", response_model=dict)
async def list_scam_reports(
    scam_type: Optional[str] = Query(None, description="詐騙類型篩選"),
    status: Optional[str] = Query(None, description="驗證狀態篩選 (pending/verified/disputed)"),
    sort_by: str = Query("latest", description="排序方式 (latest/most_voted/most_viewed)"),
    limit: int = Query(20, ge=1, le=100, description="每頁數量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """
    獲取舉報列表

    公開端點，所有用戶可查看。
    """
    try:
        loop = asyncio.get_running_loop()
        reports = await loop.run_in_executor(
            None,
            partial(get_scam_reports, scam_type=scam_type, status=status,
                   sort_by=sort_by, limit=limit, offset=offset)
        )

        return {
            "success": True,
            "reports": reports,
            "count": len(reports)
        }
    except Exception as e:
        logger.error(f"List scam reports failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"獲取舉報列表失敗: {str(e)}")


@router.get("/search", response_model=dict)
async def search_scam_wallet(
    wallet_address: str = Query(..., description="錢包地址"),
):
    """
    搜尋錢包是否被舉報

    公開端點，返回該錢包的舉報詳情（如果存在）。
    """
    try:
        loop = asyncio.get_running_loop()
        report = await loop.run_in_executor(
            None,
            search_wallet,
            wallet_address
        )

        if report:
            return {
                "success": True,
                "found": True,
                "report": report
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": "該錢包未被舉報"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search scam wallet failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜尋失敗: {str(e)}")


@router.get("/config", response_model=dict)
async def get_scam_tracker_config():
    """
    獲取詐騙追蹤系統配置

    返回詐騙類型列表和相關配置。
    """
    try:
        scam_types = get_config('scam_types', [])

        return {
            "success": True,
            "scam_types": scam_types,
            "verification_threshold": get_config('scam_verification_vote_threshold', 10),
            "verification_approve_rate": get_config('scam_verification_approve_rate', 0.7),
        }
    except Exception as e:
        logger.error(f"Get scam tracker config failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"獲取配置失敗: {str(e)}")


@router.get("/{report_id}", response_model=dict)
async def get_scam_report_detail(
    report_id: int,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    獲取舉報詳情

    公開端點，如果提供 token 則包含用戶投票狀態。
    """
    try:
        user_id = current_user.get("user_id") if current_user else None

        loop = asyncio.get_running_loop()
        report = await loop.run_in_executor(
            None,
            partial(get_scam_report_by_id, report_id, increment_view=True, viewer_user_id=user_id)
        )

        if not report:
            raise HTTPException(status_code=404, detail="舉報不存在")

        return {
            "success": True,
            "report": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get scam report detail failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"獲取舉報詳情失敗: {str(e)}")


@router.post("", response_model=dict)
async def create_new_scam_report(
    request: ScamReportCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    提交新舉報

    僅 PRO 會員可使用。
    """
    try:
        user_id = current_user.get("user_id")

        # 驗證用戶是否存在
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_user_by_id, user_id)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="用戶不存在或憑證失效，請重新登入"
            )

        result = await loop.run_in_executor(
            None,
            partial(
                create_scam_report,
                scam_wallet_address=request.scam_wallet_address,
                reporter_user_id=user_id,
                reporter_wallet_address=request.reporter_wallet_address,
                scam_type=request.scam_type,
                description=request.description,
                transaction_hash=request.transaction_hash
            )
        )

        if result.get("success"):
            return {
                "success": True,
                "report_id": result["report_id"],
                "message": "舉報提交成功"
            }
        else:
            error = result.get("error")
            detail = result.get("detail", "")

            # 處理各種錯誤情況
            if error == "pro_membership_required":
                raise HTTPException(status_code=403, detail="需要 PRO 會員權限")
            elif error == "daily_limit_reached":
                limit = result.get("limit", 5)
                used = result.get("used", 0)
                raise HTTPException(
                    status_code=429,
                    detail=f"已達每日舉報上限 ({used}/{limit})"
                )
            elif error == "already_reported":
                existing_id = result.get("existing_report_id")
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "該錢包已被舉報",
                        "existing_report_id": existing_id
                    }
                )
            elif error == "invalid_scam_wallet":
                raise HTTPException(status_code=400, detail=f"可疑錢包地址無效: {detail}")
            elif error == "invalid_reporter_wallet":
                raise HTTPException(status_code=400, detail=f"舉報者錢包地址無效: {detail}")
            elif error == "invalid_tx_hash":
                raise HTTPException(status_code=400, detail=f"交易哈希無效: {detail}")
            elif error == "content_validation_failed":
                warnings = result.get("warnings", [])
                raise HTTPException(
                    status_code=400,
                    detail={"error": "內容審核未通過", "warnings": warnings}
                )
            else:
                raise HTTPException(status_code=500, detail=f"提交失敗: {error}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create scam report failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交舉報失敗: {str(e)}")
