from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from api.deps import (
    clear_token_cookies,
    create_access_token,
    create_refresh_token,
    get_current_user,
    set_token_cookies,
)
from api.middleware.rate_limit import limiter
from api.models import WatchlistRequest
from api.pi_verification import PI_API_BASE, PI_API_KEY, verify_pi_access_token
from api.utils import logger, run_sync
from core.audit import audit_log
from core.config import TEST_MODE, TEST_USER
from core.database import (
    add_to_watchlist,
    create_or_get_pi_user,
    get_prices,
    get_user_wallet_status,
    get_watchlist,
    remove_from_watchlist,
)
from core.database.user import get_user_by_id, upgrade_to_pro

router = APIRouter()


@router.get("/api/watchlist")
async def get_user_watchlist(current_user: dict = Depends(get_current_user)):
    """獲取用戶的自選清單"""
    try:
        user_id = current_user["user_id"]
        symbols = await run_sync(get_watchlist, user_id)
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"獲取自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="無法獲取自選清單")


@router.post("/api/watchlist/add")
@limiter.limit("20/minute")
async def add_watchlist(
    request: Request,
    req: WatchlistRequest,
    current_user: dict = Depends(get_current_user),
):
    """新增幣種到自選清單"""
    try:
        user_id = current_user["user_id"]
        current_list = await run_sync(get_watchlist, user_id)
        if len(current_list) >= 10:
            raise HTTPException(
                status_code=400,
                detail="自選清單已滿 (上限 10 個)，請移除舊幣種後再試。",
            )

        await run_sync(add_to_watchlist, user_id, req.symbol.upper())
        return {"success": True, "message": f"{req.symbol} 已加入自選清單"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"新增自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="新增失敗")


@router.post("/api/watchlist/remove")
@limiter.limit("20/minute")
async def remove_watchlist(
    request: Request,
    req: WatchlistRequest,
    current_user: dict = Depends(get_current_user),
):
    """從自選清單移除幣種"""
    try:
        user_id = current_user["user_id"]
        await run_sync(remove_from_watchlist, user_id, req.symbol.upper())
        return {"success": True, "message": f"{req.symbol} 已從自選清單移除"}
    except Exception as e:
        logger.error(f"移除自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="移除失敗")


# --- Dev/Test Login Endpoint ---


class DevLoginRequest(BaseModel):
    user_id: Optional[str] = None
    confirmation: str = Field(
        "I_UNDERSTAND_THE_RISKS", description='Must be "I_UNDERSTAND_THE_RISKS"'
    )

    def model_post_init(self, __context):
        if self.confirmation != "I_UNDERSTAND_THE_RISKS":
            raise ValueError('confirmation must be "I_UNDERSTAND_THE_RISKS"')


@router.post("/api/user/dev-login")
@limiter.limit("5/minute")
async def dev_login(request: Request, response: Response, body: DevLoginRequest = None):
    """
    僅在 TEST_MODE=True 時可用的開發測試登入
    返回測試用戶的 JWT Token
    可選：傳入 user_id 以切換到特定測試用戶
    """
    if not TEST_MODE:
        raise HTTPException(status_code=403, detail="Test mode is disabled")

    if body and body.user_id:
        test_user_id = body.user_id
        suffix = (
            test_user_id.split("-")[-1] if "-" in test_user_id else test_user_id[-3:]
        )
        test_username = f"TestUser_{suffix}"
    else:
        test_user_id = TEST_USER.get("uid", "test-user-001")
        test_username = TEST_USER.get("username", "TestUser")

    access_token = create_access_token(
        data={"sub": test_user_id, "username": test_username}
    )
    refresh_token = create_refresh_token(
        data={"sub": test_user_id, "username": test_username}
    )

    try:
        existing_user = await run_sync(get_user_by_id, test_user_id)
        if not existing_user:
            await run_sync(create_or_get_pi_user, test_user_id, test_username)
            logger.info(
                f"[DEV LOGIN] Created missing mock user {test_username} ({test_user_id}) in DB."
            )

        if test_user_id == "test-user-004":
            await run_sync(upgrade_to_pro, test_user_id, 12, None)

    except Exception as e:
        logger.error(f"[DEV LOGIN] Error ensuring test user exists: {e}")

    set_token_cookies(response, access_token, refresh_token)

    return {
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours in seconds
        "user": {
            "uid": test_user_id,
            "username": test_username,
            "authMethod": "dev_test",
        },
    }


# --- Pi Network User Endpoints ---


class PiUserSyncRequest(BaseModel):
    pi_uid: str
    username: Optional[str] = None
    access_token: Optional[str] = None
    wallet_address: Optional[str] = None


@router.post("/api/user/pi-sync")
@limiter.limit("5/minute")
async def sync_pi_user(request: Request, response: Response, body: PiUserSyncRequest):
    """
    同步 Pi Network 用戶到資料庫
    - 首次登入時自動創建用戶
    - 之後登入時返回現有用戶資料
    - 驗證 Pi Access Token 確保身份真實性
    """
    if not body.access_token:
        logger.error(f"Pi sync attempted without access token for uid: {body.pi_uid}")
        raise HTTPException(
            status_code=401, detail="Pi Access Token is required for authentication"
        )

    try:
        pi_user_data = await verify_pi_access_token(body.access_token, body.pi_uid)
        verified_wallet = (
            pi_user_data.get("wallet_address")
            or pi_user_data.get("walletAddress")
            or (pi_user_data.get("credentials") or {}).get("wallet_address")
            or body.wallet_address
        )
    except HTTPException as e:
        logger.warning(
            f"Pi token verification failed for uid {body.pi_uid}: {e.detail}"
        )
        raise e

    try:
        result = await run_sync(
            lambda: create_or_get_pi_user(
                pi_uid=body.pi_uid,
                username=body.username,
                wallet_address=verified_wallet,
            )
        )

        access_token = create_access_token(
            data={"sub": result["user_id"], "username": result["username"]}
        )
        refresh_token = create_refresh_token(
            data={"sub": result["user_id"], "username": result["username"]}
        )

        set_token_cookies(response, access_token, refresh_token)

        return {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 86400,  # 24 hours in seconds
            "user": {
                "user_id": result["user_id"],
                "username": result["username"],
                "auth_method": result["auth_method"],
                "role": result.get("role", "user"),
                "membership_tier": result.get("membership_tier", "free"),
                "has_wallet": True,
            },
            "is_new_user": result.get("is_new", False),
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
    has_wallet = bool(current_user.get("pi_uid")) or bool(current_user.get("has_wallet"))
    if not has_wallet and current_user.get("auth_method") == "pi_network":
        has_wallet = True

    return {
        "success": True,
        "user": {
            "user_id": current_user.get("user_id"),
            "username": current_user.get("username"),
            "role": current_user.get("role", "user"),
            "auth_method": current_user.get("auth_method"),
            "membership_tier": current_user.get("membership_tier", "free"),
            "pi_uid": current_user.get("pi_uid"),
            "pi_username": current_user.get("pi_username"),
            "has_wallet": has_wallet,
        },
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/api/user/refresh")
@limiter.limit("10/minute")
async def refresh_access_token(
    request: Request, response: Response, body: RefreshTokenRequest = None
):
    """
    使用 refresh token 獲取新的 access token。
    Reads refresh_token from cookie first, falls back to request body.
    """
    from api.deps import REFRESH_TOKEN_COOKIE, verify_token

    refresh_token_value = body.refresh_token if body and body.refresh_token else None
    if not refresh_token_value:
        refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE)

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
        )

    # Check if the refresh token has been revoked (e.g., from logout)
    from api.deps import is_token_revoked

    if is_token_revoked(refresh_token_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    try:
        payload = verify_token(refresh_token_value)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user_id = payload.get("sub")
        username = payload.get("username")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        new_access_token = create_access_token(
            data={"sub": user_id, "username": username}
        )
        new_refresh_token = create_refresh_token(
            data={"sub": user_id, "username": username}
        )

        set_token_cookies(response, new_access_token, new_refresh_token)

        return {
            "success": True,
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 86400,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
        )


@router.post("/api/user/logout")
@limiter.limit("30/minute")
async def logout(request: Request, response: Response):
    """Clear JWT cookies on logout and revoke refresh token."""
    from api.deps import REFRESH_TOKEN_COOKIE, revoke_token

    # Revoke the refresh token to prevent token reuse after logout
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_token_value:
        revoke_token(refresh_token_value)

    clear_token_cookies(response)
    return {"success": True}


# --- Pi Payment Handling Endpoints ---


class ClientLogRequest(BaseModel):
    source: str = Field(..., description="Log source (e.g., 'premium', 'forum')")
    level: str = Field(default="info", description="Log level")
    message: str = Field(..., description="Log message")
    data: Optional[dict] = Field(default=None, description="Additional data")


@router.post("/api/client/log")
async def client_log(body: ClientLogRequest, current_user: dict = Depends(get_current_user)):
    """接收前端 client-side logs 並寫入 server logs"""
    user_id = current_user.get("user_id", "unknown")
    log_msg = f"[CLIENT:{body.source}] [{body.level.upper()}] {body.message}"

    if body.data:
        log_msg += f" | data: {body.data}"

    log_msg += f" | user: {user_id}"

    if body.level == "error":
        logger.error(log_msg)
    elif body.level == "warning":
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    return {"status": "ok"}


class ApprovePaymentRequest(BaseModel):
    paymentId: str


class CompletePaymentRequest(BaseModel):
    paymentId: str
    txid: str


@router.post("/api/user/payment/approve")
@limiter.limit("10/minute")
async def approve_payment(
    request: Request,
    body: ApprovePaymentRequest,
    current_user: dict = Depends(get_current_user),
):
    """接收前端通知，驗證金額後呼叫 Pi Server API 核准支付"""
    logger.info(f"[PAYMENT] === APPROVE START ===")
    logger.info(f"[PAYMENT] paymentId: {body.paymentId}")
    logger.info(f"[PAYMENT] userId: {current_user['user_id']}")
    logger.info(f"[PAYMENT] PI_API_KEY configured: {bool(PI_API_KEY and PI_API_KEY != 'your_pi_api_key_here')}")
    logger.info(f"[PAYMENT] TEST_MODE: {TEST_MODE}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        if TEST_MODE and current_user.get("user_id") == TEST_USER.get("uid"):
            logger.info("TEST_MODE: Mocking payment approval")
            return {
                "status": "ok",
                "message": "Payment approved (Test Mode)",
                "data": {"status": "approved"},
            }
        msg = "Server configuration error: PI_API_KEY not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    try:
        async with httpx.AsyncClient() as client:
            get_response = await client.get(
                f"{PI_API_BASE}/payments/{body.paymentId}",
                headers={"Authorization": f"Key {PI_API_KEY}"},
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
                    logger.error(
                        f"Payment amount mismatch! Expected: {expected_amount}, Actual: {actual_amount}, Type: {payment_type}"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"金額不正確: 預期 {expected_amount} Pi, 實際 {actual_amount} Pi",
                    )
                logger.info(
                    f"Payment amount verified: {actual_amount} Pi for {payment_type}"
                )
            else:
                logger.warning(
                    f"Unknown payment type: {payment_type}, amount: {actual_amount}"
                )

            approve_response = await client.post(
                f"{PI_API_BASE}/payments/{body.paymentId}/approve",
                headers={"Authorization": f"Key {PI_API_KEY}"},
            )
            approve_response.raise_for_status()
            result = approve_response.json()
            logger.info(f"Pi API Approve Response: {result}")
            return {"status": "ok", "message": "Payment approved", "data": result}

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Pi API Approve Error: {e.response.status_code} - {e.response.text}"
        )
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Pi API Error: {e.response.text}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pi Payment Approval Failed: {e}")
        raise HTTPException(
            status_code=500, detail="Payment approval failed, please try again later"
        )


@router.post("/api/user/payment/complete")
@limiter.limit("10/minute")
async def complete_payment(
    request: Request,
    body: CompletePaymentRequest,
    current_user: dict = Depends(get_current_user),
):
    """接收前端通知，呼叫 Pi Server API 完成支付"""
    logger.info(f"[PAYMENT] === COMPLETE START ===")
    logger.info(f"[PAYMENT] paymentId: {body.paymentId}")
    logger.info(f"[PAYMENT] txid: {body.txid}")
    logger.info(f"[PAYMENT] userId: {current_user['user_id']}")
    logger.info(f"[PAYMENT] PI_API_KEY configured: {bool(PI_API_KEY and PI_API_KEY != 'your_pi_api_key_here')}")
    logger.info(f"[PAYMENT] TEST_MODE: {TEST_MODE}")

    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        if TEST_MODE and current_user.get("user_id") == TEST_USER.get("uid"):
            logger.info("TEST_MODE: Mocking payment completion")
            return {
                "status": "ok",
                "message": "Payment completed (Test Mode)",
                "data": {"status": "completed"},
                "txid": body.txid,
            }
        msg = "Server configuration error: PI_API_KEY not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PI_API_BASE}/payments/{body.paymentId}/complete",
                headers={"Authorization": f"Key {PI_API_KEY}"},
                json={"txid": body.txid},
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Pi API Complete Response: {result}")
            return {
                "status": "ok",
                "message": "Payment completed",
                "data": result,
                "txid": body.txid,
            }
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Pi API Complete Error: {e.response.status_code} - {e.response.text}"
        )
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Pi API Error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Pi Payment Completion Failed: {e}")
        raise HTTPException(
            status_code=500, detail="Payment completion failed, please try again later"
        )


@router.get("/api/user/wallet-status")
async def get_wallet_status(current_user: dict = Depends(get_current_user)):
    """獲取用戶錢包綁定狀態"""
    try:
        user_id = current_user["user_id"]
        if TEST_MODE and (
            user_id == TEST_USER.get("uid") or user_id.startswith("test-user-")
        ):
            return {
                "success": True,
                "has_wallet": True,
                "auth_method": "pi_network",
                "pi_uid": user_id,
                "pi_username": TEST_USER.get("username", "TestUser"),
            }

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
@limiter.limit("10/minute")
async def save_user_api_key_endpoint(
    request: Request,
    req: SaveAPIKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """儲存用戶的 API Key（加密後存入資料庫）"""
    from core.database.user_api_keys import save_user_api_key

    user_id = current_user["user_id"]
    try:
        result = await run_sync(
            save_user_api_key, user_id, req.provider, req.api_key, req.model
        )
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to save API key")
            )

        logger.info(f"API key saved for user {user_id}, provider: {req.provider}")
        audit_log(
            action="api_key_saved",
            user_id=user_id,
            metadata={"provider": req.provider},
        )
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
async def get_user_api_key_endpoint(
    provider: str, current_user: dict = Depends(get_current_user)
):
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
@limiter.limit("10/minute")
async def delete_user_api_key_endpoint(
    request: Request, provider: str, current_user: dict = Depends(get_current_user)
):
    """刪除用戶的 API Key"""
    import re

    if not re.match(r"^[a-zA-Z0-9_-]+$", provider):
        raise HTTPException(status_code=400, detail="Invalid provider name")
    from core.database.user_api_keys import delete_user_api_key

    user_id = current_user["user_id"]
    try:
        result = await run_sync(delete_user_api_key, user_id, provider)
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to delete")
            )

        logger.info(f"API key deleted for user {user_id}, provider: {provider}")
        audit_log(
            action="api_key_deleted", user_id=user_id, metadata={"provider": provider}
        )
        return {"success": True, "message": "API Key 已刪除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete API key error: {e}")
        raise HTTPException(status_code=500, detail="刪除失敗")


@router.get("/api/user/auth-status-page")
async def auth_status_page():
    """Mobile-friendly debug page — open this URL in Pi Browser after login."""
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auth Status</title>
<style>
body{background:#111;color:#eee;font-family:monospace;padding:16px;font-size:14px}
h2{color:#f5c842}
.ok{color:#4ade80;font-weight:bold}
.fail{color:#f87171;font-weight:bold}
.warn{color:#fbbf24;font-weight:bold}
table{width:100%;border-collapse:collapse;margin-bottom:16px}
td{padding:8px;border-bottom:1px solid #333}
pre{background:#222;padding:8px;overflow:auto;font-size:12px;white-space:pre-wrap}
button{background:#f5c842;color:#111;border:none;padding:10px 20px;border-radius:8px;font-size:16px;margin:8px 0}
</style></head><body>
<h2>Auth Status Debug</h2>
<table id="ls-table"><tr><td colspan="2">Loading localStorage...</td></tr></table>
<h3>API /api/user/me result:</h3>
<pre id="api-result">Loading...</pre>
<h3>API /api/user/auth-debug result:</h3>
<pre id="debug-result">Loading...</pre>
<button onclick="runTest()">Re-run Test</button>
<script>
function show(id, html){ document.getElementById(id).innerHTML = html; }

function lsTable(){
  var data = localStorage.getItem('pi_user');
  if(!data) return '<tr><td colspan="2" class="fail">No pi_user in localStorage — not logged in</td></tr>';
  try{
    var u = JSON.parse(data);
    var rows = '';
    for(var k in u){ rows += '<tr><td>'+k+'</td><td class="ok">'+(u[k]||'(empty)')+'</td></tr>'; }
    return rows;
  }catch(e){ return '<tr><td colspan="2" class="fail">Parse error: '+e+'</td></tr>'; }
}

async function runTest(){
  document.getElementById('ls-table').innerHTML = lsTable();

  // Test /api/user/me with credentials
  try{
    var r = await fetch('/api/user/me', {credentials:'include'});
    var status = r.status;
    var body = await r.text();
    var color = status===200?'ok':'fail';
    show('api-result','<span class="'+color+'">HTTP '+status+'</span>\\n'+body);
  }catch(e){
    show('api-result','<span class="fail">Error: '+e+'</span>');
  }

  // Test auth-debug
  try{
    var r2 = await fetch('/api/user/auth-debug', {credentials:'include'});
    var body2 = await r2.text();
    show('debug-result', body2);
  }catch(e){
    show('debug-result','<span class="fail">Error: '+e+'</span>');
  }
}

runTest();
</script></body></html>"""
    return HTMLResponse(content=html)


@router.get("/api/user/auth-debug")
async def auth_debug(request: Request):
    """Temporary diagnostic endpoint — no auth required. Returns HTML for mobile debugging."""
    from fastapi.responses import HTMLResponse
    import os
    import jwt as pyjwt
    from api.deps import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE

    pi_api_key = os.getenv("PI_API_KEY", "")
    pi_sandbox_key = os.getenv("PI_SANDBOX_API_KEY", "")
    pi_sandbox = os.getenv("PI_SANDBOX", "false")

    rows = [
        ("JWT_SECRET_KEY set", "YES ✓" if SECRET_KEY else "NO ✗", bool(SECRET_KEY)),
        ("JWT_SECRET_KEY length", str(len(SECRET_KEY)) if SECRET_KEY else "0", bool(SECRET_KEY and len(SECRET_KEY) >= 32)),
        ("PI_API_KEY set", "YES ✓" if pi_api_key else "NO ✗", bool(pi_api_key)),
        ("PI_SANDBOX_API_KEY set", "YES ✓" if pi_sandbox_key else "NO ✗", bool(pi_sandbox_key)),
        ("PI_SANDBOX mode", pi_sandbox, pi_sandbox == "false"),
        ("access_token cookie", "present ✓" if ACCESS_TOKEN_COOKIE in request.cookies else "missing ✗", ACCESS_TOKEN_COOKIE in request.cookies),
        ("refresh_token cookie", "present ✓" if REFRESH_TOKEN_COOKIE in request.cookies else "missing ✗", REFRESH_TOKEN_COOKIE in request.cookies),
        ("Authorization header", "present ✓" if request.headers.get("Authorization") else "missing", False),
    ]

    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    jwt_status = "no token"
    jwt_ok = False
    if token and SECRET_KEY:
        try:
            pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            jwt_status = "decode OK ✓"
            jwt_ok = True
        except pyjwt.ExpiredSignatureError:
            jwt_status = "EXPIRED ✗"
        except pyjwt.InvalidTokenError as e:
            jwt_status = f"INVALID: {e} ✗"
    elif token and not SECRET_KEY:
        jwt_status = "no secret key"

    rows.append(("JWT decode result", jwt_status, jwt_ok))

    def row_html(label, value, ok):
        color = "#4ade80" if ok else "#f87171"
        return f'<tr><td style="padding:8px;border-bottom:1px solid #333">{label}</td><td style="padding:8px;border-bottom:1px solid #333;color:{color};font-weight:bold">{value}</td></tr>'

    table = "".join(row_html(l, v, ok) for l, v, ok in rows)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auth Debug</title>
<style>body{{background:#111;color:#eee;font-family:monospace;padding:16px}}
table{{width:100%;border-collapse:collapse}}h2{{color:#f5c842}}</style>
</head><body>
<h2>Auth Debug</h2>
<table>{table}</table>
<p style="color:#888;font-size:12px;margin-top:16px">
PI_API_KEY is required for Pi login to work.<br>
If missing, add it in Zeabur environment variables.
</p>
</body></html>"""
    return HTMLResponse(content=html)


@router.post("/api/user/api-keys/model")
@limiter.limit("10/minute")
async def save_user_model_endpoint(
    request: Request,
    req: SaveModelRequest,
    current_user: dict = Depends(get_current_user),
):
    """儲存用戶選擇的模型（不更改 API Key）"""
    from core.database.user_api_keys import save_user_model_selection

    user_id = current_user["user_id"]
    try:
        result = await run_sync(
            save_user_model_selection, user_id, req.provider, req.model
        )
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to save model")
            )
        return {"success": True, "message": "模型選擇已儲存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save model error: {e}")
        raise HTTPException(status_code=500, detail="儲存失敗")

