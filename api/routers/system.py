import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.config import (
    SUPPORTED_EXCHANGES, DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT
)
from api.models import APIKeySettings
from api.utils import update_env_file, logger
from trading.okx_api_connector import OKXAPIConnector
import api.globals as globals

router = APIRouter()

# Get project root from sys.path or os.getcwd
project_root = os.getcwd()

@router.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "service": "Crypto Trading API"}

@router.get("/api/config")
async def get_config():
    """回傳前端需要的配置資訊"""
    return {
        "supported_exchanges": SUPPORTED_EXCHANGES,
        "default_interval": DEFAULT_INTERVAL,
        "default_limit": DEFAULT_KLINES_LIMIT
    }

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
