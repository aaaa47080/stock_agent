"""
Price Alerts API Router

Endpoints for managing user price alerts.
"""
import asyncio
from functools import partial
from fastapi import APIRouter, HTTPException, Depends
from api.deps import get_current_user
from api.models import CreateAlertRequest
from core.database import (
    create_alert, get_user_alerts, delete_alert,
    count_user_alerts, create_price_alerts_table,
)
from api.utils import logger

router = APIRouter()

# Initialize table on import
try:
    create_price_alerts_table()
    logger.info("Price alerts table initialized")
except Exception as e:
    logger.warning(f"Could not initialize price_alerts table: {e}")

MAX_ALERTS_PER_USER = 20


@router.post("/api/alerts")
async def create_alert_endpoint(
    request: CreateAlertRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new price alert."""
    user_id = current_user["user_id"]
    loop = asyncio.get_running_loop()

    count = await loop.run_in_executor(None, count_user_alerts, user_id)
    if count >= MAX_ALERTS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"已達警報上限（最多 {MAX_ALERTS_PER_USER} 個），請刪除舊警報後再試。"
        )

    try:
        alert = await loop.run_in_executor(
            None,
            partial(
                create_alert,
                user_id=user_id,
                symbol=request.symbol,
                market=request.market,
                condition=request.condition,
                target=request.target,
                repeat=request.repeat,
            ),
        )
        return {"success": True, "alert": alert}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"建立警報失敗: {e}")
        raise HTTPException(status_code=500, detail="建立警報失敗")


@router.get("/api/alerts")
async def get_alerts_endpoint(current_user: dict = Depends(get_current_user)):
    """Get all alerts for the current user."""
    user_id = current_user["user_id"]
    loop = asyncio.get_running_loop()
    try:
        alerts = await loop.run_in_executor(None, get_user_alerts, user_id)
        return {"success": True, "alerts": alerts}
    except Exception as e:
        logger.error(f"獲取警報失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取警報失敗")


@router.delete("/api/alerts/{alert_id}")
async def delete_alert_endpoint(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a specific alert (ownership enforced)."""
    user_id = current_user["user_id"]
    loop = asyncio.get_running_loop()
    try:
        deleted = await loop.run_in_executor(None, partial(delete_alert, alert_id, user_id))
        if not deleted:
            raise HTTPException(status_code=404, detail="警報不存在或無權限刪除")
        return {"success": True, "message": "警報已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除警報失敗: {e}")
        raise HTTPException(status_code=500, detail="刪除警報失敗")
