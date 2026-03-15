"""
Premium 會員相關 API
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.database import get_user_membership, upgrade_to_pro
from api.deps import get_current_user
from api.utils import logger, run_sync

router = APIRouter(prefix="/api/premium", tags=["Premium"])
PLAN_MONTHS = {
    "premium_monthly": 1,
    "premium_yearly": 12,
}


class UpgradeRequest(BaseModel):
    user_id: str
    plan: str = "premium_monthly"  # premium_monthly, premium_yearly
    tx_hash: Optional[str] = None  # Pi 支付交易哈希
    months: int = 1  # 訂閱月數


@router.get("/pricing")
async def get_pricing_plans():
    """獲取會員定價方案"""
    from core.config import PI_PAYMENT_PRICES
    return {
        "success": True,
        "pricing": {
            "premium": {
                "monthly": PI_PAYMENT_PRICES.get("premium_monthly", 5.0),
                "yearly": PI_PAYMENT_PRICES.get("premium_yearly", 40.0),
            }
        },
        "pi_price_usd": 0.17,  # 參考價格
        "savings": {
            "premium_yearly_save": 20.0,  # Premium 年費省 20 Pi
        }
    }


@router.post("/upgrade")
async def upgrade_to_premium(request: UpgradeRequest, current_user: dict = Depends(get_current_user)):
    """
    升級到 Premium 會員

    Args:
        user_id: 用戶ID
        plan: 訂閱方案 (premium_monthly, premium_yearly)
        tx_hash: Pi 支付交易哈希 (正式環境需要)
        months: 訂閱月數
    """
    if current_user["user_id"] != request.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    plan = (request.plan or "premium_monthly").strip().lower()
    if plan not in PLAN_MONTHS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    # 會員期間以方案定義為準，避免前後端語意不一致
    months = PLAN_MONTHS[plan]

    try:
        current_membership = await run_sync(get_user_membership, request.user_id)

        if not current_membership:
            raise HTTPException(status_code=404, detail="用戶不存在")

        # 在正式環境中，需要驗證 tx_hash
        # 這裡簡化處理，實際部署時需要驗證 Pi 支付
        success = await run_sync(
            lambda: upgrade_to_pro(
                user_id=request.user_id,
                months=months,
                tx_hash=request.tx_hash
            )
        )

        if not success:
            raise HTTPException(status_code=500, detail="升級失敗")

        new_membership = await run_sync(get_user_membership, request.user_id)

        logger.info(f"用戶 {request.user_id} 成功升級到 Premium 會員，plan={plan}, months={months}")

        return {
            "success": True,
            "message": f"成功升級到 Premium 會員 {months} 個月！",
            "plan": plan,
            "months": months,
            "membership": new_membership
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"升級 Premium 會員失敗: {e}")
        raise HTTPException(status_code=500, detail="升級失敗，請稍後再試")


@router.get("/status/{user_id}")
async def get_premium_status(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    獲取用戶 Premium 會員狀態
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this membership status")

    try:
        membership = await run_sync(get_user_membership, user_id)

        if not membership:
            raise HTTPException(status_code=404, detail="用戶不存在")

        return {
            "success": True,
            "membership": membership
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 Premium 會員狀態失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取狀態失敗，請稍後再試")
