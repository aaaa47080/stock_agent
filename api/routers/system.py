import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import openai
import google.generativeai as genai
from dotenv import load_dotenv
from utils.llm_client import LLMClientFactory

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
    """測試 API Key 是否有效，並嘗試進行對話"""
    provider = request.provider
    key = request.api_key
    user_model = request.model  # 用戶選擇的模型

    if not key or len(key) < 5:
        return {"valid": False, "message": "Key 為空或過短"}

    test_prompt = "你好請問今天天氣好麻 (請簡短回答)"

    try:
        reply_text = ""

        if provider == "openai":
            client = openai.OpenAI(api_key=key)
            # 如果用戶指定了模型，優先使用用戶的模型，否則使用默認模型
            model_to_test = user_model if user_model and user_model.startswith('gpt') else "gpt-4o-mini"
            completion = client.chat.completions.create(
                model=model_to_test,
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=50
            )
            reply_text = completion.choices[0].message.content

        elif provider == "google_gemini":
            # 使用與實際應用相同的 GeminiWrapper 來確保一致性
            from utils.llm_client import GeminiWrapper
            import google.generativeai as genai
            genai.configure(api_key=key)

            # 如果用戶指定了模型，優先使用用戶的模型
            if user_model and user_model.startswith('gemini'):
                # 僅測試用戶指定的模型
                models_to_try = [user_model]
            else:
                # 從配置文件獲取可用模型
                try:
                    from core.model_config import get_available_models
                    available_models = get_available_models("google_gemini")
                    models_to_try = [model['value'] for model in available_models]
                except ImportError:
                    # 如果配置文件不可用，使用默認值
                    models_to_try = ["gemini-3-flash-preview"]
            last_error = None

            for model_name in models_to_try:
                try:
                    # 使用 GeminiWrapper 進行測試，確保與實際應用行為一致
                    wrapper = GeminiWrapper(genai)
                    response = wrapper.create(
                        model=model_name,
                        messages=[{"role": "user", "content": test_prompt}],
                        temperature=0.5,
                        max_tokens=50
                    )
                    reply_text = response.choices[0].message.content
                    # 如果成功，就跳出循環
                    break
                except Exception as e:
                    # 檢查是否是因為內容審核問題
                    error_str = str(e)
                    if "blocked due to content policy" in error_str:
                        # 這表示 API 連接正常，但內容被審核系統拒絕
                        # 我們可以嘗試另一個模型
                        logger.warning(f"Gemini model {model_name} content was blocked by policy: {e}")
                        continue
                    elif "response.text" in error_str and "finish_reason" in error_str:
                        # 這可能是因為內容被審核系統拒絕，但仍表示 API 連接正常
                        logger.warning(f"Gemini model {model_name} returned blocked content: {e}")
                        continue
                    else:
                        last_error = e
                        continue

            # 如果所有模型都失敗，拋出最後一個錯誤
            if not reply_text and last_error:
                raise last_error

        elif provider == "openrouter":
            client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
            )
            # 如果用戶指定了模型，優先使用用戶的模型
            if user_model:
                test_model = user_model
            else:
                # 否則獲取模型列表，使用默認模型
                models = client.models.list()
                if not models.data:
                    raise ValueError("無法獲取模型列表")
                # 使用列表中的第一個模型 (通常是免費或熱門模型)
                test_model = models.data[0].id

            completion = client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=50
            )
            reply_text = completion.choices[0].message.content

        else:
            return {"valid": False, "message": "未知的提供商"}

        return {
            "valid": True,
            "message": f"驗證成功！連接正常。使用模型: {user_model or 'default'}",
            "reply": reply_text,
            "provider": provider,
            "model": user_model or "default"
        }
        
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
    # Reload .env to pick up manual changes
    load_dotenv(override=True)

    current_provider = core_config.BULL_RESEARCHER_MODEL.get("provider", "openai")

    # Helper to check key existence using Factory logic
    def has_key(provider):
        return bool(LLMClientFactory._get_api_key(provider))

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
            "has_openai_key": has_key("openai"),
            "has_google_key": has_key("google_gemini"),
            "has_openrouter_key": has_key("openrouter"),
            "has_current_provider_key": has_key(current_provider),
        }
    }

@router.get("/api/model-config")
async def get_model_config():
    """獲取模型配置資訊"""
    from core.model_config import MODEL_CONFIG
    return {"model_config": MODEL_CONFIG}

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
