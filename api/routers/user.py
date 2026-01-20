import os
import httpx
from fastapi import APIRouter, HTTPException
from api.models import (
    WatchlistRequest, UserRegisterRequest, UserLoginRequest,
    ForgotPasswordRequest, ResetPasswordRequest
)
from api.utils import logger

# Pi Network API 配置
PI_API_KEY = os.getenv("PI_API_KEY", "")
PI_API_BASE = "https://api.minepi.com/v2"
from core.database import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    create_user, get_user_by_username, verify_password,
    get_user_by_email, create_reset_token, get_reset_token,
    delete_reset_token, update_password,
    record_login_attempt, is_account_locked, get_failed_attempts,
    MAX_LOGIN_ATTEMPTS,
    # Pi Network 用戶相關
    create_or_get_pi_user, get_user_by_pi_uid, is_username_available,
    link_pi_wallet, get_user_wallet_status
)
from core.email_service import send_reset_email, is_email_configured

router = APIRouter()

@router.get("/api/watchlist/{user_id}")
async def get_user_watchlist(user_id: str):
    """獲取用戶的自選清單"""
    try:
        symbols = get_watchlist(user_id)
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"獲取自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="無法獲取自選清單")

@router.post("/api/watchlist/add")
async def add_watchlist(request: WatchlistRequest):
    """新增幣種到自選清單"""
    try:
        add_to_watchlist(request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已加入自選清單"}
    except Exception as e:
        logger.error(f"新增自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="新增失敗")

@router.post("/api/watchlist/remove")
async def remove_watchlist(request: WatchlistRequest):
    """從自選清單移除幣種"""
    try:
        remove_from_watchlist(request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已從自選清單移除"}
    except Exception as e:
        logger.error(f"移除自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="移除失敗")

@router.post("/api/user/register")
async def register_user(request: UserRegisterRequest):
    """註冊新用戶"""
    try:
        user = create_user(request.username, request.password, request.email)
        return {"success": True, "user_id": user["user_id"], "username": user["username"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"註冊失敗: {e}")
        raise HTTPException(status_code=500, detail="註冊失敗")

@router.post("/api/user/login")
async def login_user(request: UserLoginRequest):
    """用戶登入（含暴力破解防護）"""
    try:
        # 1. 檢查帳號是否被鎖定
        is_locked, remaining_minutes = is_account_locked(request.username)
        if is_locked:
            hours = remaining_minutes // 60
            mins = remaining_minutes % 60
            time_str = f"{hours}小時{mins}分鐘" if hours > 0 else f"{mins}分鐘"
            raise HTTPException(
                status_code=403,
                detail=f"帳號已被鎖定，請在 {time_str} 後再試"
            )

        # 2. 驗證用戶
        user = get_user_by_username(request.username)
        if not user or not verify_password(user["password_hash"], request.password):
            # 記錄失敗的登入嘗試
            record_login_attempt(request.username, success=False)

            # 檢查剩餘嘗試次數
            failed_count = get_failed_attempts(request.username)
            remaining = MAX_LOGIN_ATTEMPTS - failed_count

            if remaining <= 0:
                raise HTTPException(
                    status_code=403,
                    detail="登入失敗次數過多，帳號已被鎖定 24 小時"
                )
            elif remaining <= 3:
                raise HTTPException(
                    status_code=401,
                    detail=f"無效的用戶名或密碼（剩餘 {remaining} 次嘗試機會）"
                )
            else:
                raise HTTPException(status_code=401, detail="無效的用戶名或密碼")

        # 3. 登入成功，記錄並清除失敗記錄
        record_login_attempt(request.username, success=True)

        return {
            "success": True,
            "user": {
                "uid": user["user_id"],
                "username": user["username"],
                "authMethod": "password"
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"登入失敗: {e}")
        raise HTTPException(status_code=500, detail="登入失敗")

@router.get("/api/user/check/{username}")
async def check_username_availability(username: str):
    """檢查用戶名是否可用（同時檢查 Pi 和 Email 用戶）"""
    try:
        available = is_username_available(username)
        if not available:
            return {"available": False, "message": "此用戶名已被註冊"}
        return {"available": True, "message": "用戶名可用"}
    except Exception as e:
        logger.error(f"檢查用戶名失敗: {e}")
        raise HTTPException(status_code=500, detail="檢查失敗")


@router.get("/api/user/check-email/{email}")
async def check_email_availability(email: str):
    """檢查 Email 是否可用"""
    try:
        user = get_user_by_email(email)
        if user:
            return {"available": False, "message": "此 Email 已被註冊"}
        return {"available": True, "message": "Email 可用"}
    except Exception as e:
        logger.error(f"檢查 Email 失敗: {e}")
        raise HTTPException(status_code=500, detail="檢查失敗")


# --- Pi Network User Endpoints ---

from pydantic import BaseModel

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
    """
    try:
        result = create_or_get_pi_user(
            pi_uid=request.pi_uid,
            username=request.username
        )

        return {
            "success": True,
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
async def get_pi_user(pi_uid: str):
    """根據 Pi UID 獲取用戶資料"""
    try:
        user = get_user_by_pi_uid(pi_uid)
        if not user:
            raise HTTPException(status_code=404, detail="用戶不存在")
        return {"success": True, "user": user}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 Pi 用戶失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取失敗")


# --- Password Reset Endpoints ---

@router.post("/api/user/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """請求密碼重置（發送重置郵件）"""
    try:
        # 檢查 Email 服務是否配置
        if not is_email_configured():
            raise HTTPException(
                status_code=503,
                detail="Email service not configured. Please contact administrator."
            )

        # 查找用戶
        user = get_user_by_email(request.email)
        if not user:
            # 安全性考量：不透露 email 是否存在
            return {
                "success": True,
                "message": "If the email exists, a reset link has been sent."
            }

        # 創建重置 Token
        token = create_reset_token(user["user_id"])
        if not token:
            raise HTTPException(status_code=500, detail="Failed to create reset token")

        # 發送郵件
        email_sent = send_reset_email(
            to_email=request.email,
            reset_token=token,
            username=user["username"]
        )

        if not email_sent:
            raise HTTPException(status_code=500, detail="Failed to send reset email")

        return {
            "success": True,
            "message": "If the email exists, a reset link has been sent."
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/api/user/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """驗證重置 Token 是否有效"""
    try:
        token_data = get_reset_token(token)
        if not token_data:
            return {"valid": False, "message": "Invalid or expired token"}

        return {"valid": True, "message": "Token is valid"}

    except Exception as e:
        logger.error(f"Verify token error: {e}")
        raise HTTPException(status_code=500, detail="Verification failed")


@router.post("/api/user/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """使用 Token 重置密碼"""
    try:
        # 驗證 Token
        token_data = get_reset_token(request.token)
        if not token_data:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        # 密碼驗證
        if len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        # 更新密碼
        success = update_password(token_data["user_id"], request.new_password)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update password")

        # 刪除已使用的 Token
        delete_reset_token(request.token)

        return {"success": True, "message": "Password has been reset successfully"}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred")


# --- Pi Payment Handling Endpoints ---

class ApprovePaymentRequest(BaseModel):
    paymentId: str

class CompletePaymentRequest(BaseModel):
    paymentId: str
    txid: str

@router.post("/api/user/payment/approve")
async def approve_payment(request: ApprovePaymentRequest):
    """
    接收前端通知，呼叫 Pi Server API 核准支付
    官方文檔: https://pi-apps.github.io/community-developer-guide/docs/gettingStarted/piAppPlatform/piAppPlatformAPIs/
    """
    logger.info(f"Pi Payment Approval Requested: {request.paymentId}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        logger.warning("PI_API_KEY not configured, skipping actual API call")
        return {"status": "ok", "message": "Payment approval received (API key not configured)"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PI_API_BASE}/payments/{request.paymentId}/approve",
                headers={"Authorization": f"Key {PI_API_KEY}"}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Pi API Approve Response: {result}")
            return {"status": "ok", "message": "Payment approved", "data": result}
    except httpx.HTTPStatusError as e:
        logger.error(f"Pi API Approve Error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Pi API Error: {e.response.text}")
    except Exception as e:
        logger.error(f"Pi Payment Approval Failed: {e}")
        raise HTTPException(status_code=500, detail=f"Payment approval failed: {str(e)}")


@router.post("/api/user/payment/complete")
async def complete_payment(request: CompletePaymentRequest):
    """
    接收前端通知，呼叫 Pi Server API 完成支付
    官方文檔: https://pi-apps.github.io/community-developer-guide/docs/gettingStarted/piAppPlatform/piAppPlatformAPIs/
    """
    logger.info(f"Pi Payment Completion Requested: {request.paymentId}, txid: {request.txid}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        logger.warning("PI_API_KEY not configured, skipping actual API call")
        return {"status": "ok", "message": "Payment completion received (API key not configured)", "txid": request.txid}

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
async def link_wallet(request: LinkWalletRequest):
    """
    綁定 Pi 錢包到現有帳密用戶
    """
    try:
        result = link_pi_wallet(
            user_id=request.user_id,
            pi_uid=request.pi_uid,
            pi_username=request.pi_username
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Link wallet error: {e}")
        raise HTTPException(status_code=500, detail="綁定失敗")


@router.get("/api/user/wallet-status/{user_id}")
async def get_wallet_status(user_id: str):
    """
    獲取用戶錢包綁定狀態
    """
    try:
        status = get_user_wallet_status(user_id)
        return {"success": True, **status}
    except Exception as e:
        logger.error(f"Get wallet status error: {e}")
        raise HTTPException(status_code=500, detail="獲取狀態失敗")
