import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

# LangChain Imports
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

import core.config as core_config
from api.deps import get_current_user
from api.middleware.rate_limit import limiter
from api.models import KeyValidationRequest, UserSettings
from api.routers.admin import verify_admin_key
from api.utils import logger, run_sync, update_env_file
from core.config import DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT, SUPPORTED_EXCHANGES
from core.model_config import GEMINI_DEFAULT_MODEL, MODEL_CONFIG, OPENAI_DEFAULT_MODEL
from core.orm.config_repo import config_repo
from utils.llm_client import LLMClientFactory
from utils.settings import Settings

router = APIRouter()

# Get project root from sys.path or os.getcwd
project_root = os.getcwd()

# Reuse the same RotatingFileHandler logger from api_server.py
_frontend_debug_logger = logging.getLogger("frontend_debug")

# NOTE: POST and GET /api/debug/log are removed — api_server.py already
# provides safer versions at /api/debug-log (RotatingFileHandler, max length).


@router.delete("/api/debug/log", dependencies=[Depends(verify_admin_key)])
async def clear_debug_log():
    """清空 frontend_debug.log (Admin only) — resets the rotating handler."""
    try:
        # Remove all handlers from the logger and close them
        for handler in list(_frontend_debug_logger.handlers):
            handler.close()
            _frontend_debug_logger.removeHandler(handler)

        # Truncate the log file
        log_path = os.path.join(project_root, "frontend_debug.log")
        if os.path.exists(log_path):
            os.truncate(log_path, 0)

        # Re-create the RotatingFileHandler
        rotating_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        rotating_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        _frontend_debug_logger.addHandler(rotating_handler)

        return {"success": True, "message": "Log cleared"}
    except Exception as e:
        logger.error(f"Failed to clear debug log: {e}")
        return {"success": False, "error": "清空日誌失敗"}


@router.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "service": "Crypto Trading API"}


@router.post("/api/settings/validate-key")
@limiter.limit("10/minute")  # 🔒 Security: 防止滥用 LLM 验证
async def validate_key(
    body: KeyValidationRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """測試 API Key 是否有效，並嘗試進行對話"""
    provider = body.provider
    key = body.api_key
    user_model = body.model  # 用戶選擇的模型

    # Audit log for sensitive operation
    try:
        from core.audit import audit_log

        audit_log(
            action="api_key_validation",
            user_id=current_user.get("user_id"),
            metadata={"provider": provider},
        )
    except ImportError:
        pass

    if not key or len(key) < 5:
        return {"valid": False, "message": "Key 為空或過短"}

    test_prompt = "Hello, please respond briefly to confirm this is working."

    try:
        reply_text = ""

        # 統一使用 LangChain init_chat_model 進行驗證

        # 映射 provider
        lc_provider = "openai"
        base_url = None

        if provider == "google_gemini":
            lc_provider = "google_genai"
        elif provider == "openrouter":
            lc_provider = "openai"
            base_url = "https://openrouter.ai/api/v1"
        elif provider == "openai":
            lc_provider = "openai"
        else:
            return {"valid": False, "message": "未知的提供商"}

        # 決定模型名稱
        if user_model:
            model_to_test = user_model
        else:
            if provider == "google_gemini":
                model_to_test = GEMINI_DEFAULT_MODEL
            elif provider == "openrouter":
                model_to_test = OPENAI_DEFAULT_MODEL
            else:
                model_to_test = OPENAI_DEFAULT_MODEL

        # 嘗試初始化 LLM
        llm = init_chat_model(
            model=model_to_test,
            model_provider=lc_provider,
            temperature=0.5,
            api_key=key,
            base_url=base_url,
        )

        # 使用 run_in_executor 避免阻塞，並加上 15 秒 timeout
        response = await asyncio.wait_for(
            run_sync(lambda: llm.invoke([HumanMessage(content=test_prompt)])),
            timeout=15.0,
        )
        reply_text = response.content

        return {
            "valid": True,
            "message": f"驗證成功！連接正常。使用模型: {model_to_test}",
            "reply": reply_text,
            "provider": provider,
            "model": model_to_test,
        }

    except asyncio.TimeoutError:
        logger.warning(f"Key validation timed out for {provider}")
        return {
            "valid": False,
            "message": "驗證失敗: 請求超時 (15秒)，請檢查網絡連接或稍後再試。",
        }
    except Exception as e:
        logger.warning(f"Key validation failed for {provider}: {e}")
        error_msg = str(e)
        if (
            "401" in error_msg
            or "auth" in error_msg.lower()
            or "unauthorized" in error_msg.lower()
        ):
            error_msg = "認證失敗 (401)，請檢查 Key 是否正確。"
        elif (
            "429" in error_msg
            or "quota" in error_msg.lower()
            or "rate" in error_msg.lower()
            or "exceeded your current quota" in error_msg.lower()
        ):
            error_msg = "額度不足或請求過多 (429)，請檢查您的計費詳情和用量限制。"
        elif "404" in error_msg or "not found" in error_msg.lower():
            error_msg = "模型目前不可用 (404)。可能原因：① 模型名稱錯誤 ② Free tier 暫時無負載（稍後重試）③ 模型已下架。"
        elif "400" in error_msg:
            if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
                error_msg = "API Key 無效，請檢查 Key 是否正確。"
            elif "access not configured" in error_msg.lower():
                error_msg = "API 服務未啟用，請確保已在 Google Cloud Console 中啟用 Generative Language API。"
            else:
                error_msg = "請求參數錯誤 (400)。請檢查模型名稱是否正確。"
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            error_msg = "連接超時或網絡問題。請檢查網絡連接。"

        return {"valid": False, "message": f"驗證失敗: {error_msg}"}


@router.get("/api/config")
async def get_config():
    """回傳前端需要的配置資訊"""
    current_provider = core_config.PRIMARY_MODEL.get("provider", "openai")

    # Helper to check key existence using Factory logic
    def has_key(provider):
        return bool(LLMClientFactory._get_api_key(provider))

    response = {
        "supported_exchanges": SUPPORTED_EXCHANGES,
        "default_interval": DEFAULT_INTERVAL,
        "default_limit": DEFAULT_KLINES_LIMIT,
        "current_settings": {
            "primary_model_provider": current_provider,
            "primary_model_name": core_config.PRIMARY_MODEL.get("model"),
            # Mask keys for security
            "has_openai_key": has_key("openai"),
            "has_google_key": has_key("google_gemini"),
            "has_openrouter_key": has_key("openrouter"),
            "has_current_provider_key": has_key(current_provider),
        },
    }

    return response


@router.get("/api/model-config")
async def get_model_config():
    """獲取模型配置資訊"""
    return {"model_config": MODEL_CONFIG}


@router.get("/api/config/prices")
async def get_pi_prices():
    """
    獲取 Pi 支付價格配置（從數據庫讀取）
    前端使用此 API 獲取動態價格，確保價格與後端驗證一致

    商用化設計：配置存儲在數據庫中，可通過管理 API 即時修改
    """
    return {"prices": await config_repo.get_prices(), "currency": "Pi"}


@router.get("/api/config/limits")
async def get_forum_limits():
    """
    獲取論壇限制配置（從數據庫讀取）
    前端使用此 API 獲取動態限制，確保限制與後端驗證一致

    商用化設計：配置存儲在數據庫中，可通過管理 API 即時修改
    """
    return {"limits": await config_repo.get_limits()}


@router.post("/api/settings/update")
@limiter.limit("10/minute")  # 🔒 Security: 防止设置滥用
async def update_user_settings(
    settings: UserSettings,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    更新用戶設置 (LLM API Keys, 模型選擇, 委員會模式)

    ⚠️ 安全改進: OKX API Keys 不再通過此端點處理
    - OKX Keys 現在使用 BYOK (Bring Your Own Keys) 模式
    - 金鑰僅存儲在用戶瀏覽器的 localStorage 中
    - 每次請求時從前端傳遞，後端不存儲
    """
    # Audit log for sensitive operation
    try:
        from core.audit import audit_log

        audit_log(
            action="settings_update",
            user_id=current_user.get("user_id"),
            metadata={"provider": settings.primary_model_provider},
        )
    except ImportError:
        pass

    try:
        env_updates = {}

        # 1. Update LLM API Keys (Only LLM keys are stored in backend)
        if settings.openai_api_key:
            env_updates["OPENAI_API_KEY"] = settings.openai_api_key
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
            Settings.update(OPENAI_API_KEY=settings.openai_api_key)

        if settings.google_api_key:
            env_updates["GOOGLE_API_KEY"] = settings.google_api_key
            os.environ["GOOGLE_API_KEY"] = settings.google_api_key
            Settings.update(GOOGLE_API_KEY=settings.google_api_key)

        if settings.openrouter_api_key:
            env_updates["OPENROUTER_API_KEY"] = settings.openrouter_api_key
            os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
            Settings.update(OPENROUTER_API_KEY=settings.openrouter_api_key)

        # 2. Update Model Configuration
        new_model_config = {
            "provider": settings.primary_model_provider,
            "model": settings.primary_model_name,
        }

        logger.info(f"Updating model config to: {new_model_config}")

        # 更新核心配置中的模型定義（統一配置，向後兼容）
        core_config.PRIMARY_MODEL = new_model_config
        # 向後兼容：同步更新舊的別名（deprecated）
        core_config.BULL_RESEARCHER_MODEL = new_model_config
        core_config.BEAR_RESEARCHER_MODEL = new_model_config
        core_config.TRADER_MODEL = new_model_config
        core_config.SYNTHESIS_MODEL = new_model_config

        # 4. Save to .env file for persistence
        if env_updates:
            await run_sync(lambda: update_env_file(env_updates, project_root))

        return {"success": True, "message": "系統設置已更新！(模式與模型已切換)"}

    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail="更新設置失敗，請稍後再試")


@router.get("/")
async def read_index():
    """返回主頁面 index.html"""
    if os.path.exists("web/index.html"):
        return FileResponse(
            "web/index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "Welcome to Crypto API. Frontend not found."}


# ============================================================================
# Test Mode Endpoints (僅在 TEST_MODE 啟用時可用)
# ============================================================================


class TestTierRequest(BaseModel):
    tier: str  # "free", "premium"


@router.post("/api/test-mode/switch-tier")
async def switch_test_tier(
    request: TestTierRequest, current_user: dict = Depends(get_current_user)
):
    """
    切換測試帳號的會員等級（僅測試模式）

    用於測試不同會員等級的功能：
    - free: 免費會員功能
    - premium: Premium 會員功能
    """
    from core.config import TEST_MODE

    if not TEST_MODE:
        raise HTTPException(status_code=403, detail="此功能僅在測試模式下可用")

    valid_tiers = ["free", "premium"]
    if request.tier not in valid_tiers:
        raise HTTPException(
            status_code=400, detail=f"無效的等級，必須是: {', '.join(valid_tiers)}"
        )

    # 更新環境變量（當前進程有效）
    os.environ["TEST_USER_TIER"] = request.tier

    logger.info(f"[TEST_MODE] Tier switched to: {request.tier}")

    return {
        "success": True,
        "tier": request.tier,
        "message": f"測試帳號已切換為 {request.tier.upper()} 等級",
    }


@router.get("/api/test-mode/current-tier")
async def get_current_test_tier(current_user: dict = Depends(get_current_user)):
    """
    獲取當前測試帳號的會員等級（僅測試模式）
    """
    from core.config import TEST_MODE

    if not TEST_MODE:
        raise HTTPException(status_code=403, detail="此功能僅在測試模式下可用")

    from core.orm.tools_repo import _normalize_tier as normalize_membership_tier

    current_tier = normalize_membership_tier(
        current_user.get("membership_tier", os.environ.get("TEST_USER_TIER", "premium"))
    )

    return {
        "tier": current_tier,
        "is_test_mode": True,
        "user_id": current_user.get("user_id"),
    }
