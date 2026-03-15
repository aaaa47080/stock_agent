import os
import asyncio
import httpx
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.deps import create_access_token, get_current_user
from api.models import WatchlistRequest
from api.utils import logger, run_sync
from core.config import TEST_MODE, TEST_USER
from core.database import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    create_or_get_pi_user, get_user_wallet_status,
    get_prices
)
from core.database.user import get_user_by_id, upgrade_to_pro
from api.pi_verification import verify_pi_access_token
from core.audit import audit_log

# Pi Network API 配置
PI_API_KEY = os.getenv("PI_API_KEY", "")
PI_API_BASE = "https://api.minepi.com/v2"

router = APIRouter()



@router.get("/api/watchlist/{user_id}")
async def get_user_watchlist(user_id: str, current_user: dict = Depends(get_current_user)):
    """獲取用戶的自選清單"""
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this data")
    try:
        symbols = await run_sync(get_watchlist, user_id)
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"獲取自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="無法獲取自選清單")

@router.post("/api/watchlist/add")
async def add_watchlist(request: WatchlistRequest, current_user: dict = Depends(get_current_user)):
    """新增幣種到自選清單"""
    if current_user["user_id"] != request.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this data")
    try:
        # Limit to 10 symbols to prevent spamming "On-Demand" analysis
        current_list = await run_sync(get_watchlist, request.user_id)
        if len(current_list) >= 10:
            raise HTTPException(status_code=400, detail="自選清單已滿 (上限 10 個)，請移除舊幣種後再試。")

        await run_sync(add_to_watchlist, request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已加入自選清單"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"新增自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="新增失敗")

@router.post("/api/watchlist/remove")
async def remove_watchlist(request: WatchlistRequest, current_user: dict = Depends(get_current_user)):
    """從自選清單移除幣種"""
    if current_user["user_id"] != request.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this data")
    try:
        await run_sync(remove_from_watchlist, request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已從自選清單移除"}
    except Exception as e:
        logger.error(f"移除自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="移除失敗")

# --- Dev/Test Login Endpoint ---

class DevLoginRequest(BaseModel):
    user_id: Optional[str] = None

@router.post("/api/user/dev-login")
async def dev_login(request: DevLoginRequest = None):
    """
    僅在 TEST_MODE=True 時可用的開發測試登入
    返回測試用戶的 JWT Token
    可選：傳入 user_id 以切換到特定測試用戶
    """
    if not TEST_MODE:
        raise HTTPException(status_code=403, detail="Test mode is disabled")

    if request and request.user_id:
        test_user_id = request.user_id
        suffix = test_user_id.split('-')[-1] if '-' in test_user_id else test_user_id[-3:]
        test_username = f"TestUser_{suffix}"
    else:
        test_user_id = TEST_USER.get("uid", "test-user-001")
        test_username = TEST_USER.get("username", "TestUser")

    access_token = create_access_token(
        data={"sub": test_user_id, "username": test_username}
    )

    # Ensure test user exists in DB to prevent foreign key issues
    try:
        existing_user = await run_sync(get_user_by_id, test_user_id)
        if not existing_user:
            await run_sync(create_or_get_pi_user, test_user_id, test_username)
            print(f"[DEV LOGIN] Created missing mock user {test_username} ({test_user_id}) in DB.")

        if test_user_id == "test-user-004":
            await run_sync(upgrade_to_pro, test_user_id, 12, None)

    except Exception as e:
        print(f"[DEV LOGIN] Error ensuring test user exists: {e}")

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "uid": test_user_id,
            "username": test_username,
            "authMethod": "dev_test"
        }
    }

# --- Pi Network User Endpoints ---

class PiUserSyncRequest(BaseModel):
    pi_uid: str
    username: Optional[str] = None
    access_token: Optional[str] = None
    wallet_address: Optional[str] = None

@router.post("/api/user/pi-sync")
async def sync_pi_user(request: PiUserSyncRequest):
    """
    同步 Pi Network 用戶到資料庫
    - 首次登入時自動創建用戶
    - 之後登入時返回現有用戶資料
    - 驗證 Pi Access Token 確保身份真實性
    """
    if not request.access_token:
        logger.error(f"Pi sync attempted without access token for uid: {request.pi_uid}")
        raise HTTPException(status_code=401, detail="Pi Access Token is required for authentication")

    try:
        pi_user_data = await verify_pi_access_token(request.access_token, request.pi_uid)
        # Extract wallet_address — try known field names from Pi API
        verified_wallet = (
            pi_user_data.get('wallet_address')
            or pi_user_data.get('walletAddress')
            or (pi_user_data.get('credentials') or {}).get('wallet_address')
            or request.wallet_address
        )
    except HTTPException as e:
        logger.warning(f"Pi token verification failed for uid {request.pi_uid}: {e.detail}")
        raise e

    try:
        result = await run_sync(
            lambda: create_or_get_pi_user(
                pi_uid=request.pi_uid,
                username=request.username,
                wallet_address=verified_wallet,
            )
        )

        access_token = create_access_token(
            data={"sub": result["user_id"], "username": result["username"]}
        )

        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "user_id": result["user_id"],
                "username": result["username"],
                "auth_method": result["auth_method"],
                "role": result.get("role", "user"),
                "membership_tier": result.get("membership_tier", "free"),
                "has_wallet": True,  # Pi login = wallet connected (pi_uid exists)
            },
            "is_new_user": result.get("is_new", False)
        }
    except ValueError as e:
        logger.warning(f"Pi 用戶同步失敗 - 用戶名衝突: {e}")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Pi 用戶同步失敗: {e}")
        raise HTTPException(status_code=500, detail="同步失敗")

@router.get("/api/user/me")
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """獲取當前登入用戶的資料"""
    return {
        "success": True,
        "user": {
            "user_id": current_user.get("user_id"),
            "username": current_user.get("username"),
            "role": current_user.get("role", "user"),
            "auth_method": current_user.get("auth_method"),
        }
    }


# --- Pi Payment Handling Endpoints ---

class ApprovePaymentRequest(BaseModel):
    paymentId: str

class CompletePaymentRequest(BaseModel):
    paymentId: str
    txid: str

@router.post("/api/user/payment/approve")
async def approve_payment(request: ApprovePaymentRequest, current_user: dict = Depends(get_current_user)):
    """接收前端通知，驗證金額後呼叫 Pi Server API 核准支付"""
    logger.info(f"Pi Payment Approval Requested: {request.paymentId} by User {current_user['user_id']}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        if TEST_MODE and current_user.get("user_id") == TEST_USER.get("uid"):
            logger.info("TEST_MODE: Mocking payment approval")
            return {"status": "ok", "message": "Payment approved (Test Mode)", "data": {"status": "approved"}}
        msg = "Server configuration error: PI_API_KEY not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    try:
        async with httpx.AsyncClient() as client:
            get_response = await client.get(
                f"{PI_API_BASE}/payments/{request.paymentId}",
                headers={"Authorization": f"Key {PI_API_KEY}"}
            )
            get_response.raise_for_status()
            payment_info = get_response.json()
            logger.info(f"Pi Payment Info: {payment_info}")

            actual_amount = payment_info.get("amount", 0)
            payment_type = payment_info.get("metadata", {}).get("type", "unknown")

            prices = await run_sync(get_prices)
            expected_amount = prices.get(payment_type)

            if expected_amount is not None:
                if abs(actual_amount - expected_amount) > 0.001:
                    logger.error(f"Payment amount mismatch! Expected: {expected_amount}, Actual: {actual_amount}, Type: {payment_type}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"金額不正確: 預期 {expected_amount} Pi, 實際 {actual_amount} Pi"
                    )
                logger.info(f"Payment amount verified: {actual_amount} Pi for {payment_type}")
            else:
                logger.warning(f"Unknown payment type: {payment_type}, amount: {actual_amount}")

            approve_response = await client.post(
                f"{PI_API_BASE}/payments/{request.paymentId}/approve",
                headers={"Authorization": f"Key {PI_API_KEY}"}
            )
            approve_response.raise_for_status()
            result = approve_response.json()
            logger.info(f"Pi API Approve Response: {result}")
            return {"status": "ok", "message": "Payment approved", "data": result}

    except httpx.HTTPStatusError as e:
        logger.error(f"Pi API Approve Error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Pi API Error: {e.response.text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pi Payment Approval Failed: {e}")
        raise HTTPException(status_code=500, detail="Payment approval failed, please try again later")


@router.post("/api/user/payment/complete")
async def complete_payment(request: CompletePaymentRequest, current_user: dict = Depends(get_current_user)):
    """接收前端通知，呼叫 Pi Server API 完成支付"""
    logger.info(f"Pi Payment Completion Requested: {request.paymentId} by User {current_user['user_id']}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        if TEST_MODE and current_user.get("user_id") == TEST_USER.get("uid"):
            logger.info("TEST_MODE: Mocking payment completion")
            return {"status": "ok", "message": "Payment completed (Test Mode)", "data": {"status": "completed"}, "txid": request.txid}
        msg = "Server configuration error: PI_API_KEY not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PI_API_BASE}/payments/{request.paymentId}/complete",
                headers={"Authorization": f"Key {PI_API_KEY}"},
                json={"txid": request.txid}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Pi API Complete Response: {result}")
            return {"status": "ok", "message": "Payment completed", "data": result, "txid": request.txid}
    except httpx.HTTPStatusError as e:
        logger.error(f"Pi API Complete Error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Pi API Error: {e.response.text}")
    except Exception as e:
        logger.error(f"Pi Payment Completion Failed: {e}")
        raise HTTPException(status_code=500, detail="Payment completion failed, please try again later")

@router.get("/api/user/wallet-status/{user_id}")
async def get_wallet_status(user_id: str, current_user: dict = Depends(get_current_user)):
    """獲取用戶錢包綁定狀態"""
    try:
        if TEST_MODE and (user_id == TEST_USER.get("uid") or user_id.startswith("test-user-")):
            return {
                "success": True,
                "has_wallet": True,
                "auth_method": "pi_network",
                "pi_uid": user_id,
                "pi_username": TEST_USER.get("username", "TestUser")
            }

        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        status = await run_sync(get_user_wallet_status, user_id)
        return {"success": True, **status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get wallet status error: {e}")
        raise HTTPException(status_code=500, detail="獲取狀態失敗")


# --- User API Key Management Endpoints ---

class SaveAPIKeyRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None

class SaveModelRequest(BaseModel):
    provider: str
    model: str


@router.post("/api/user/api-keys")
async def save_user_api_key_endpoint(
    request: SaveAPIKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """儲存用戶的 API Key（加密後存入資料庫）"""
    from core.database.user_api_keys import save_user_api_key

    user_id = current_user["user_id"]
    try:
        result = await run_sync(save_user_api_key, user_id, request.provider, request.api_key, request.model)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to save API key"))

        logger.info(f"API key saved for user {user_id}, provider: {request.provider}")
        audit_log(action="api_key_saved", user_id=user_id, metadata={"provider": request.provider})
        return {"success": True, "message": "API Key 已安全儲存"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save API key error: {e}")
        raise HTTPException(status_code=500, detail="儲存失敗")


@router.get("/api/user/api-keys")
async def get_user_api_keys_endpoint(current_user: dict = Depends(get_current_user)):
    """獲取用戶所有 API Key 的狀態（遮蔽版本，用於前端顯示）"""
    from core.database.user_api_keys import get_all_user_api_keys

    user_id = current_user["user_id"]
    try:
        keys = await run_sync(get_all_user_api_keys, user_id)
        return {"success": True, "keys": keys}
    except Exception as e:
        logger.error(f"Get API keys error: {e}")
        raise HTTPException(status_code=500, detail="獲取失敗")


@router.get("/api/user/api-keys/{provider}")
async def get_user_api_key_endpoint(provider: str, current_user: dict = Depends(get_current_user)):
    """獲取特定 provider 的 API Key 狀態（遮蔽版本）"""
    from core.database.user_api_keys import get_user_api_key_masked

    user_id = current_user["user_id"]
    try:
        key_info = await run_sync(get_user_api_key_masked, user_id, provider)
        return {"success": True, **key_info}
    except Exception as e:
        logger.error(f"Get API key error: {e}")
        raise HTTPException(status_code=500, detail="獲取失敗")


@router.delete("/api/user/api-keys/{provider}")
async def delete_user_api_key_endpoint(provider: str, current_user: dict = Depends(get_current_user)):
    """刪除用戶的 API Key"""
    from core.database.user_api_keys import delete_user_api_key

    user_id = current_user["user_id"]
    try:
        result = await run_sync(delete_user_api_key, user_id, provider)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete"))

        logger.info(f"API key deleted for user {user_id}, provider: {provider}")
        audit_log(action="api_key_deleted", user_id=user_id, metadata={"provider": provider})
        return {"success": True, "message": "API Key 已刪除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete API key error: {e}")
        raise HTTPException(status_code=500, detail="刪除失敗")


@router.post("/api/user/api-keys/model")
async def save_user_model_endpoint(request: SaveModelRequest, current_user: dict = Depends(get_current_user)):
    """儲存用戶選擇的模型（不更改 API Key）"""
    from core.database.user_api_keys import save_user_model_selection

    user_id = current_user["user_id"]
    try:
        result = await run_sync(save_user_model_selection, user_id, request.provider, request.model)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to save model"))
        return {"success": True, "message": "模型選擇已儲存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save model error: {e}")
        raise HTTPException(status_code=500, detail="儲存失敗")


@router.get("/api/user/api-keys/{provider}/full")
async def get_user_api_key_full_endpoint(provider: str, current_user: dict = Depends(get_current_user)):
    """獲取完整的 API Key（僅用於實際 API 調用）"""
    from core.database.user_api_keys import get_user_api_key

    user_id = current_user["user_id"]
    try:
        key = await run_sync(get_user_api_key, user_id, provider)
        if key is None:
            return {"success": False, "key": None}

        audit_log(action="api_key_full_access", user_id=user_id, metadata={"provider": provider})
        return {"success": True, "key": key}

    except Exception as e:
        logger.error(f"Get full API key error: {e}")
        raise HTTPException(status_code=500, detail="獲取失敗")


# --- Token Refresh Endpoint ---

@router.post("/api/user/refresh-token")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """
    刷新 JWT Token（備用方案，不需要 Pi SDK）
    當無法使用 Pi SDK 靜默刷新時使用。需要有效的 JWT token。
    """
    try:
        new_access_token = create_access_token(
            data={"sub": current_user["user_id"], "username": current_user.get("username", "user")}
        )
        logger.info(f"Token refreshed for user: {current_user['user_id']}")
        audit_log(action="token_refresh", user_id=current_user["user_id"], metadata={"method": "backend_refresh"})
        return {"success": True, "access_token": new_access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=500, detail="Token 刷新失敗")
