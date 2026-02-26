import os
import sys
import asyncio
from functools import partial
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from utils.llm_client import LLMClientFactory
from fastapi import Depends
from api.deps import get_current_user
from api.routers.admin import verify_admin_key

# LangChain Imports
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from core.config import (
    SUPPORTED_EXCHANGES, DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT
)
from core.database import get_prices, get_limits
import core.config as core_config
from utils.settings import Settings
from api.models import APIKeySettings, UserSettings, KeyValidationRequest
from api.utils import update_env_file, logger
from trading.okx_api_connector import OKXAPIConnector
import api.globals as globals

router = APIRouter()

# Get project root from sys.path or os.getcwd
project_root = os.getcwd()
FRONTEND_DEBUG_LOG = os.path.join(project_root, "frontend_debug.log")

# Pydantic model for debug log
from pydantic import BaseModel
from typing import Any, Optional

class DebugLogRequest(BaseModel):
    level: str = "info"
    message: str
    data: Optional[Any] = None

@router.post("/api/debug/log", dependencies=[Depends(verify_admin_key)])
async def write_debug_log(request: DebugLogRequest, x_admin_key: str = Header(None)):
    """接收前端日誌並寫入 frontend_debug.log"""
    from datetime import datetime
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{request.level.upper()}] {request.message}"
        if request.data:
            import json
            log_line += f" | {json.dumps(request.data, ensure_ascii=False, default=str)}"
        log_line += "\n"

        with open(FRONTEND_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(log_line)

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/debug/log", dependencies=[Depends(verify_admin_key)])
async def read_debug_log(lines: int = 50, x_admin_key: str = Header(None)):
    """讀取最後 N 行 frontend_debug.log"""
    try:
        if not os.path.exists(FRONTEND_DEBUG_LOG):
            return {"lines": [], "message": "Log file not found"}

        with open(FRONTEND_DEBUG_LOG, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {"lines": last_lines, "total": len(all_lines)}
    except Exception as e:
        return {"lines": [], "error": str(e)}

@router.delete("/api/debug/log", dependencies=[Depends(verify_admin_key)])
async def clear_debug_log():
    """清空 frontend_debug.log (Admin only)"""
    try:
        with open(FRONTEND_DEBUG_LOG, "w", encoding="utf-8") as f:
            f.write("")
        return {"success": True, "message": "Log cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "service": "Crypto Trading API"}

@router.post("/api/settings/validate-key")
async def validate_key(request: KeyValidationRequest, current_user: dict = Depends(get_current_user)):
    """測試 API Key 是否有效，並嘗試進行對話"""
    provider = request.provider
    key = request.api_key
    user_model = request.model  # 用戶選擇的模型

    if not key or len(key) < 5:
        return {"valid": False, "message": "Key 為空或過短"}

    test_prompt = "你好請問今天天氣好麻 (請簡短回答)"

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
                model_to_test = "gemini-2.0-flash-exp"
            elif provider == "openrouter":
                model_to_test = "gpt-4o-mini" # 或其他默認
            else:
                model_to_test = "gpt-4o-mini"

        # 嘗試初始化 LLM
        llm = init_chat_model(
            model=model_to_test,
            model_provider=lc_provider,
            temperature=0.5,
            api_key=key,
            base_url=base_url
        )
        
        # 使用 run_in_executor 避免阻塞，並加上 15 秒 timeout
        loop = asyncio.get_running_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: llm.invoke([HumanMessage(content=test_prompt)])),
            timeout=15.0
        )
        reply_text = response.content

        return {
            "valid": True,
            "message": f"驗證成功！連接正常。使用模型: {model_to_test}",
            "reply": reply_text,
            "provider": provider,
            "model": model_to_test
        }
        
    except asyncio.TimeoutError:
        logger.warning(f"Key validation timed out for {provider}")
        return {"valid": False, "message": "驗證失敗: 請求超時 (15秒)，請檢查網絡連接或稍後再試。"}
    except Exception as e:
        logger.warning(f"Key validation failed for {provider}: {e}")
        error_msg = str(e)
        if "401" in error_msg or "auth" in error_msg.lower() or "unauthorized" in error_msg.lower():
            error_msg = "認證失敗 (401)，請檢查 Key 是否正確。"
        elif "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower() or "exceeded your current quota" in error_msg.lower():
            error_msg = "額度不足或請求過多 (429)，請檢查您的計費詳情和用量限制。"
        elif "404" in error_msg or "not found" in error_msg.lower():
             error_msg = "連接成功但模型不可用 (404)。請檢查模型名稱是否正確。"
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
    current_provider = core_config.BULL_RESEARCHER_MODEL.get("provider", "openai")

    # Helper to check key existence using Factory logic
    def has_key(provider):
        return bool(LLMClientFactory._get_api_key(provider))

    response = {
        "supported_exchanges": SUPPORTED_EXCHANGES,
        "default_interval": DEFAULT_INTERVAL,
        "default_limit": DEFAULT_KLINES_LIMIT,
        "current_settings": {
            "enable_committee": core_config.ENABLE_COMMITTEE_MODE,
            "primary_model_provider": current_provider,
            "primary_model_name": core_config.BULL_RESEARCHER_MODEL.get("model"),
            "bull_committee_models": core_config.BULL_COMMITTEE_MODELS,
            "bear_committee_models": core_config.BEAR_COMMITTEE_MODELS,
            # Mask keys for security
            "has_openai_key": has_key("openai"),
            "has_google_key": has_key("google_gemini"),
            "has_openrouter_key": has_key("openrouter"),
            "has_current_provider_key": has_key(current_provider),
        },
        # 測試模式配置
        "test_mode": core_config.TEST_MODE,
    }

    # 如果是測試模式，添加測試用戶資料
    if core_config.TEST_MODE:
        response["test_user"] = core_config.TEST_USER

    return response

@router.get("/api/model-config")
async def get_model_config():
    """獲取模型配置資訊"""
    from core.model_config import MODEL_CONFIG
    return {"model_config": MODEL_CONFIG}

@router.get("/api/config/prices")
async def get_pi_prices():
    """
    獲取 Pi 支付價格配置（從數據庫讀取）
    前端使用此 API 獲取動態價格，確保價格與後端驗證一致

    商用化設計：配置存儲在數據庫中，可通過管理 API 即時修改
    """
    return {
        "prices": await asyncio.get_running_loop().run_in_executor(None, get_prices),
        "currency": "Pi"
    }

@router.get("/api/config/limits")
async def get_forum_limits():
    """
    獲取論壇限制配置（從數據庫讀取）
    前端使用此 API 獲取動態限制，確保限制與後端驗證一致

    商用化設計：配置存儲在數據庫中，可通過管理 API 即時修改
    """
    return {
        "limits": await asyncio.get_running_loop().run_in_executor(None, get_limits)
    }

@router.post("/api/settings/update")
async def update_user_settings(settings: UserSettings, current_user: dict = Depends(get_current_user)):
    """
    更新用戶設置 (LLM API Keys, 模型選擇, 委員會模式)

    ⚠️ 安全改進: OKX API Keys 不再通過此端點處理
    - OKX Keys 現在使用 BYOK (Bring Your Own Keys) 模式
    - 金鑰僅存儲在用戶瀏覽器的 localStorage 中
    - 每次請求時從前端傳遞，後端不存儲
    """
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

        # ⚠️ OKX Keys are NO LONGER stored in backend (BYOK Mode)
        # They are managed client-side via OKXKeyManager

        # 2. Update Committee Mode
        Settings.update(ENABLE_COMMITTEE_MODE=settings.enable_committee)
        core_config.ENABLE_COMMITTEE_MODE = settings.enable_committee
        
        # 3. Update Model Configuration
        new_model_config = {
            "provider": settings.primary_model_provider,
            "model": settings.primary_model_name
        }
        
        logger.info(f"Updating model config to: {new_model_config}, Committee Mode: {settings.enable_committee}")
        
        # 更新核心配置中的模型定義
        core_config.BULL_RESEARCHER_MODEL = new_model_config
        core_config.BEAR_RESEARCHER_MODEL = new_model_config
        core_config.TRADER_MODEL = new_model_config
        # 同步更新合成模型，確保委員會模式下的總結也能正常執行
        core_config.SYNTHESIS_MODEL = new_model_config
        
        # 4. Update Committee Lists (若有提供)
        if settings.bull_committee_models is not None:
            core_config.BULL_COMMITTEE_MODELS = settings.bull_committee_models
            
        if settings.bear_committee_models is not None:
            core_config.BEAR_COMMITTEE_MODELS = settings.bear_committee_models

        # 5. Save to .env file for persistence
        if env_updates:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, partial(update_env_file, env_updates, project_root))

        return {"success": True, "message": "系統設置已更新！(模式與模型已切換)"}
        
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/settings/keys")
async def update_api_keys(settings: APIKeySettings, current_user: dict = Depends(get_current_user)):
    """接收前端傳來的 API Keys，寫入 .env 並熱重載連接器"""
    
    try:
        # 1. Update .env file for persistence
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, 
            partial(
                update_env_file, 
                {
                    "OKX_API_KEY": settings.api_key,
                    "OKX_API_SECRET": settings.secret_key,
                    "OKX_PASSPHRASE": settings.passphrase
                }, 
                project_root
            )
        )
        
        # 2. Update environment variables for current process
        os.environ["OKX_API_KEY"] = settings.api_key
        os.environ["OKX_API_SECRET"] = settings.secret_key
        os.environ["OKX_PASSPHRASE"] = settings.passphrase
        
        # 3. Re-initialize the connector
        globals.okx_connector = OKXAPIConnector()
        
        # 4. Verify connection immediately
        if not globals.okx_connector.test_connection():
            return {"success": False, "message": "Keys saved, but connection failed. Please check your inputs."}
            
        logger.info("API Keys updated and connector re-initialized successfully.")
        return {"success": True, "message": "API Keys 設定成功且連線正常！"}
        
    except Exception as e:
        logger.error(f"Failed to update API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def read_index():
    """返回主頁面 index.html"""
    if os.path.exists("web/index.html"):
        return FileResponse(
            "web/index.html", 
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return {"message": "Welcome to Crypto API. Frontend not found."}