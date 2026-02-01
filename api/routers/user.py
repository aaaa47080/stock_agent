import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from api.deps import create_access_token, get_current_user
from api.models import (
    WatchlistRequest
)
from api.utils import logger

# Pi Network API 配置
PI_API_KEY = os.getenv("PI_API_KEY", "")
PI_API_BASE = "https://api.minepi.com/v2"
from core.database import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    create_or_get_pi_user, get_user_by_pi_uid, is_username_available,
    link_pi_wallet, get_user_wallet_status
)
import asyncio
from functools import partial
from core.config import TEST_MODE, TEST_USER

router = APIRouter()

@router.get("/api/watchlist/{user_id}")
async def get_user_watchlist(user_id: str, current_user: dict = Depends(get_current_user)):
    """獲取用戶的自選清單"""
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this data")
    try:
        loop = asyncio.get_running_loop()
        symbols = await loop.run_in_executor(None, get_watchlist, user_id)
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
        loop = asyncio.get_running_loop()
        
        # [Optimization] Abuse Prevention: Enforce Watchlist Limit
        # Limit to 10 symbols to prevent users from spamming "On-Demand" analysis for thousands of coins
        current_list = await loop.run_in_executor(None, get_watchlist, request.user_id)
        if len(current_list) >= 10:
             raise HTTPException(status_code=400, detail="自選清單已滿 (上限 10 個)，請移除舊幣種後再試。")

        await loop.run_in_executor(None, partial(add_to_watchlist, request.user_id, request.symbol.upper()))
        return {"success": True, "message": f"{request.symbol} 已加入自選清單"}
    except Exception as e:
        logger.error(f"新增自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="新增失敗")

@router.post("/api/watchlist/remove")
async def remove_watchlist(request: WatchlistRequest, current_user: dict = Depends(get_current_user)):
    """從自選清單移除幣種"""
    if current_user["user_id"] != request.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this data")
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(remove_from_watchlist, request.user_id, request.symbol.upper()))
        return {"success": True, "message": f"{request.symbol} 已從自選清單移除"}
    except Exception as e:
        logger.error(f"移除自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="移除失敗")

@router.get("/api/user/check/{username}")
async def check_username_availability(username: str):
    """檢查用戶名是否可用（同時檢查 Pi 和 Email 用戶）"""
    try:
        loop = asyncio.get_running_loop()
        available = await loop.run_in_executor(None, is_username_available, username)
        if not available:
            return {"available": False, "message": "此用戶名已被註冊"}
        return {"available": True, "message": "用戶名可用"}
    except Exception as e:
        logger.error(f"檢查用戶名失敗: {e}")
        raise HTTPException(status_code=500, detail="檢查失敗")

# --- Dev/Test Login Endpoint ---
from pydantic import BaseModel
from typing import Optional

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

    # 如果有指定 user_id，使用它；否則使用默認值
    if request and request.user_id:
        test_user_id = request.user_id
        # 根據 user_id 生成不同的 username
        suffix = test_user_id.split('-')[-1] if '-' in test_user_id else test_user_id[-3:]
        test_username = f"TestUser_{suffix}"
    else:
        test_user_id = TEST_USER.get("uid", "test-user-001")
        test_username = TEST_USER.get("username", "TestUser")

    access_token = create_access_token(
        data={"sub": test_user_id, "username": test_username}
    )

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
    username: str
    access_token: str = None

@router.post("/api/user/pi-sync")
async def sync_pi_user(request: PiUserSyncRequest):
    """
    同步 Pi Network 用戶到資料庫
    - 首次登入時自動創建用戶
    - 之後登入時返回現有用戶資料
    - 驗證 Pi Access Token 確保身份真實性
    """
    # Server-side verification of Pi Access Token
    if request.access_token:
        try:
            # Import verification module
            from api.pi_verification import verify_pi_access_token
            
            # Verify token against Pi Network API
            pi_user_data = await verify_pi_access_token(
                request.access_token, 
                request.pi_uid
            )
            
            # Token is valid and UID matches
            logger.info(f"Pi token verified for user: {pi_user_data.get('username')}")
            
        except HTTPException as e:
            # Token verification failed - reject the request
            logger.warning(f"Pi token verification failed for uid {request.pi_uid}: {e.detail}")
            raise e
    else:
        # No token provided - this should not happen in production
        logger.error(f"Pi sync attempted without access token for uid: {request.pi_uid}")
        raise HTTPException(
            status_code=401, 
            detail="Pi Access Token is required for authentication"
        )
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(create_or_get_pi_user, pi_uid=request.pi_uid, username=request.username)
        )

        # Generate JWT for Pi User
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
                "auth_method": result["auth_method"]
            },
            "is_new_user": result.get("is_new", False)
        }
    except ValueError as e:
        # 用戶名衝突
        logger.warning(f"Pi 用戶同步失敗 - 用戶名衝突: {e}")
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Pi 用戶同步失敗: {e}")
        raise HTTPException(status_code=500, detail="同步失敗")

@router.get("/api/user/pi/{pi_uid}")
async def get_pi_user(pi_uid: str, current_user: dict = Depends(get_current_user)):
    """根據 Pi UID 獲取用戶資料"""
    # 僅允許查詢自己的 Pi 資料，或管理員
    # 這裡假設 current_user["user_id"] 可能不直接等於 pi_uid，需查表。
    # 簡單起見，先確保已登入。若需嚴格權限，需查詢 pi_uid 對應的 user_id
    # 安全起見，還是檢查一下是否為本人或有權限
    pass  # We will implement logic inside 
    try:
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_user_by_pi_uid, pi_uid)
        
        if not user:
            raise HTTPException(status_code=404, detail="用戶不存在")
            
        # Verify ownership
        if user["user_id"] != current_user["user_id"]:
             raise HTTPException(status_code=403, detail="Not authorized to view this Pi profile")

        return {"success": True, "user": user}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 Pi 用戶失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取失敗")





# --- Pi Payment Handling Endpoints ---

# 從數據庫獲取動態價格配置
from core.database import get_prices

class ApprovePaymentRequest(BaseModel):
    paymentId: str

class CompletePaymentRequest(BaseModel):
    paymentId: str
    txid: str

@router.post("/api/user/payment/approve")
async def approve_payment(request: ApprovePaymentRequest, current_user: dict = Depends(get_current_user)):
    """
    接收前端通知，驗證金額後呼叫 Pi Server API 核准支付
    """
    logger.info(f"Pi Payment Approval Requested: {request.paymentId} by User {current_user['user_id']}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        # Security Fix: Fail strictly if key is not configured
        msg = "Server configuration error: PI_API_KEY not set"
        
        # TEST_MODE: Allow bypass if key is missing but we represent a test user
        if TEST_MODE and current_user.get("user_id") == TEST_USER.get("uid"):
             logger.info("TEST_MODE: Mocking payment approval")
             return {"status": "ok", "message": "Payment approved (Test Mode)", "data": {"status": "approved"}}

        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    try:
        async with httpx.AsyncClient() as client:
            # ============================================
            # 步驟 1: 從 Pi API 獲取支付詳情
            # ============================================
            get_response = await client.get(
                f"{PI_API_BASE}/payments/{request.paymentId}",
                headers={"Authorization": f"Key {PI_API_KEY}"}
            )
            get_response.raise_for_status()
            payment_info = get_response.json()

            logger.info(f"Pi Payment Info: {payment_info}")

            # ============================================
            # 步驟 2: 驗證金額
            # ============================================
            actual_amount = payment_info.get("amount", 0)
            metadata = payment_info.get("metadata", {})
            payment_type = metadata.get("type", "unknown")

            # 查找預期價格（從數據庫動態獲取）
            loop = asyncio.get_running_loop()
            prices = await loop.run_in_executor(None, get_prices)
            expected_amount = prices.get(payment_type)

            if expected_amount is not None:
                # 有定義價格的類型，進行驗證
                if abs(actual_amount - expected_amount) > 0.001:  # 允許微小浮點誤差
                    logger.error(f"Payment amount mismatch! Expected: {expected_amount}, Actual: {actual_amount}, Type: {payment_type}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"金額不正確: 預期 {expected_amount} Pi, 實際 {actual_amount} Pi"
                    )
                logger.info(f"Payment amount verified: {actual_amount} Pi for {payment_type}")
            else:
                # 未定義的支付類型，記錄警告但允許通過（可根據需求改為拒絕）
                logger.warning(f"Unknown payment type: {payment_type}, amount: {actual_amount}")

            # ============================================
            # 步驟 3: 驗證通過，批准支付
            # ============================================
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
        raise  # 重新拋出我們自己的 HTTPException
    except Exception as e:
        logger.error(f"Pi Payment Approval Failed: {e}")
        raise HTTPException(status_code=500, detail=f"Payment approval failed: {str(e)}")


@router.post("/api/user/payment/complete")
async def complete_payment(request: CompletePaymentRequest, current_user: dict = Depends(get_current_user)):
    """
    接收前端通知，呼叫 Pi Server API 完成支付
    """
    logger.info(f"Pi Payment Completion Requested: {request.paymentId} by User {current_user['user_id']}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        # TEST_MODE: Allow bypass
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
        raise HTTPException(status_code=500, detail=f"Payment completion failed: {str(e)}")

# --- Pi Wallet Linking Endpoints ---

class LinkWalletRequest(BaseModel):
    user_id: str
    pi_uid: str
    pi_username: str
    access_token: str = None


@router.post("/api/user/link-wallet")
async def link_wallet(request: LinkWalletRequest, current_user: dict = Depends(get_current_user)):
    if current_user["user_id"] != request.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    """
    綁定 Pi 錢包到現有帳密用戶
    """
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(link_pi_wallet, user_id=request.user_id, pi_uid=request.pi_uid, pi_username=request.pi_username)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Link wallet error: {e}")
        raise HTTPException(status_code=500, detail="綁定失敗")


@router.get("/api/user/wallet-status/{user_id}")
async def get_wallet_status(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    獲取用戶錢包綁定狀態
    """
    try:
        # TEST_MODE: Mock wallet status for test user
        if TEST_MODE and (user_id == TEST_USER.get("uid") or user_id.startswith("test-user-")):
            return {
                "success": True,
                "is_linked": True,
                "wallet_address": f"GDTESTWALLET{user_id.replace('-', '').upper()}123",
                "linked_at": "2024-01-01T00:00:00Z"
            }

        loop = asyncio.get_running_loop()
        # Security Check
        if current_user["user_id"] != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")
             
        status = await loop.run_in_executor(None, get_user_wallet_status, user_id)
        return {"success": True, **status}
    except Exception as e:
        logger.error(f"Get wallet status error: {e}")
        raise HTTPException(status_code=500, detail="獲取狀態失敗")
