"""
高級會員相關 API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from core.database import get_user_membership, upgrade_to_pro
from api.utils import logger

router = APIRouter(prefix="/api/premium", tags=["Premium"])

class UpgradeRequest(BaseModel):
    user_id: str
    months: int = 1
    tx_hash: Optional[str] = None  # Pi 支付交易哈希


@router.post("/upgrade")
async def upgrade_to_premium(request: UpgradeRequest):
    """
    升級到高級會員
    
    Args:
        user_id: 用戶ID
        months: 訂閱月份 (默認為1個月)
        tx_hash: Pi 支付交易哈希 (正式環境需要)
    """
    try:
        # 檢查當前會員狀態
        current_membership = get_user_membership(request.user_id)
        
        if not current_membership:
            raise HTTPException(status_code=404, detail="用戶不存在")
        
        # 如果已是高級會員，檢查是否過期
        if current_membership["is_pro"]:
            # TODO: 可以選擇續訂或擴展時間
            pass
        
        # 在正式環境中，需要驗證 tx_hash
        # 這裡簡化處理，實際部署時需要驗證 Pi 支付
        success = upgrade_to_pro(
            user_id=request.user_id,
            months=request.months,
            tx_hash=request.tx_hash
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="升級失敗")
        
        # 返回新的會員狀態
        new_membership = get_user_membership(request.user_id)
        
        logger.info(f"用戶 {request.user_id} 成功升級到高級會員，{request.months} 個月")
        
        return {
            "success": True,
            "message": f"成功升級到高級會員 {request.months} 個月！",
            "membership": new_membership
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"升級高級會員失敗: {e}")
        raise HTTPException(status_code=500, detail=f"升級失敗: {str(e)}")


@router.get("/status/{user_id}")
async def get_premium_status(user_id: str):
    """
    獲取用戶高級會員狀態
    """
    try:
        membership = get_user_membership(user_id)
        
        if not membership:
            raise HTTPException(status_code=404, detail="用戶不存在")
        
        return {
            "success": True,
            "membership": membership
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取高級會員狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取狀態失敗: {str(e)}")


# 添加到現有的路由器列表
def register_router(app):
    app.include_router(router)