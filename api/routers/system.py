import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import openai
import google.generativeai as genai

from core.config import (
    SUPPORTED_EXCHANGES, DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT
)
import core.config as core_config
from utils.settings import Settings
from api.models import APIKeySettings, UserSettings, KeyValidationRequest
from api.utils import update_env_file, logger
from trading.okx_api_connector import OKXAPIConnector
from interfaces.chat_interface import CryptoAnalysisBot
import api.globals as globals

router = APIRouter()

# Get project root from sys.path or os.getcwd
project_root = os.getcwd()

@router.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "service": "Crypto Trading API"}

@router.post("/api/settings/validate-key")
async def validate_key(request: KeyValidationRequest):
    """測試 API Key 是否有效"""
    provider = request.provider
    key = request.api_key
    
    if not key or len(key) < 5:
        return {"valid": False, "message": "Key 為空或過短"}

    try:
        if provider == "openai":
            client = openai.OpenAI(api_key=key)
            # 嘗試列出模型，這是最輕量的驗證方式
            client.models.list()
            return {"valid": True, "message": "OpenAI Key 驗證成功"}
            
        elif provider == "google_gemini":
            genai.configure(api_key=key)
            # 嘗試列出模型
            # genai.list_models() 返回的是 generator，需轉 list 觸發請求
            models = list(genai.list_models()) 
            return {"valid": True, "message": "Google Gemini Key 驗證成功"}
            
        elif provider == "openrouter":
            client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
            )
            client.models.list()
            return {"valid": True, "message": "OpenRouter Key 驗證成功"}
            
        return {"valid": False, "message": "未知的提供商"}
        
    except Exception as e:
        logger.warning(f"Key validation failed for {provider}: {e}")
        error_msg = str(e)
        if "401" in error_msg:
            error_msg = "認證失敗 (401)，請檢查 Key 是否正確。"
        elif "429" in error_msg:
            error_msg = "額度不足或請求過多 (429)。"
        return {"valid": False, "message": f"驗證失敗: {error_msg}"}

@router.get("/api/config")
async def get_config():
    """回傳前端需要的配置資訊"""
    current_provider = core_config.BULL_RESEARCHER_MODEL.get("provider", "openai")

    # 檢查當前使用的 provider 是否有 API key
    has_current_key = False
    if current_provider == "openai":
        has_current_key = bool(os.getenv("OPENAI_API_KEY"))
    elif current_provider == "google_gemini":
        has_current_key = bool(os.getenv("GOOGLE_API_KEY"))
    elif current_provider == "openrouter":
        has_current_key = bool(os.getenv("OPENROUTER_API_KEY"))

    return {
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
            "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
            "has_google_key": bool(os.getenv("GOOGLE_API_KEY")),
            "has_openrouter_key": bool(os.getenv("OPENROUTER_API_KEY")),
            "has_current_provider_key": has_current_key,  # 當前使用的 provider 是否有 key
        }
    }

@router.post("/api/settings/update")
async def update_user_settings(settings: UserSettings):
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
            update_env_file(env_updates, project_root)

        # 6. Re-initialize CryptoAnalysisBot if it wasn't initialized or needs refresh
        try:
            # Re-initialize only if keys were updated or bot is missing
            if env_updates or globals.bot is None:
                logger.info("Re-initializing CryptoAnalysisBot with new settings...")
                globals.bot = CryptoAnalysisBot()
                logger.info("CryptoAnalysisBot re-initialized successfully")
        except Exception as e:
            logger.error(f"Failed to re-initialize CryptoAnalysisBot: {e}")
            # Don't fail the request, just log it. The user might need to fix the key.
            
        return {"success": True, "message": "系統設置已更新！(模式與模型已切換)"}
        
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/settings/keys")
async def update_api_keys(settings: APIKeySettings):
    """接收前端傳來的 API Keys，寫入 .env 並熱重載連接器"""
    
    try:
        # 1. Update .env file for persistence
        update_env_file({
            "OKX_API_KEY": settings.api_key,
            "OKX_API_SECRET": settings.secret_key,
            "OKX_PASSPHRASE": settings.passphrase
        }, project_root)
        
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
        return FileResponse("web/index.html")
    return {"message": "Welcome to Crypto API. Frontend not found."}
