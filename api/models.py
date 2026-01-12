from typing import Optional, List, Dict
from pydantic import BaseModel
from core.config import (
    SUPPORTED_EXCHANGES, DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT
)

# 定義請求模型
class QueryRequest(BaseModel):
    message: str
    interval: str = DEFAULT_INTERVAL
    limit: int = DEFAULT_KLINES_LIMIT
    manual_selection: Optional[List[str]] = None
    auto_execute: bool = False
    market_type: str = "spot"
    # 用戶提供的 API key（必填）
    user_api_key: str
    user_provider: str  # "openai", "google_gemini", "openrouter"
    user_model: Optional[str] = None  # 用戶選擇的模型名稱
    session_id: str = "default"  # 會話 ID

class ScreenerRequest(BaseModel):
    exchange: str = SUPPORTED_EXCHANGES[0]
    symbols: Optional[List[str]] = None

class WatchlistRequest(BaseModel):
    user_id: str
    symbol: str

class KlineRequest(BaseModel):
    symbol: str
    exchange: str = SUPPORTED_EXCHANGES[0]
    interval: str = "1d"
    limit: int = 100

class BacktestRequest(BaseModel):
    symbol: str
    signal_type: str = "RSI_OVERSOLD" # RSI_OVERSOLD, MACD_CROSS
    interval: str = "1h"

class UserSettings(BaseModel):
    """用戶動態設置"""
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    
    # 模型選擇
    primary_model_provider: str = "google_gemini" # openai, google_gemini, openrouter
    # 從模型配置文件獲取默認模型
    try:
        from core.model_config import get_default_model
        primary_model_name: str = get_default_model("google_gemini")  # 默認為 Google Gemini
    except ImportError:
        primary_model_name: str = "gemini-3-flash-preview"  # 備用默認值
    
    # 委員會模式
    enable_committee: bool = False
    bull_committee_models: Optional[List[Dict[str, str]]] = None # List of {"provider": "...", "model": "..."}
    bear_committee_models: Optional[List[Dict[str, str]]] = None # List of {"provider": "...", "model": "..."}
    
    # OKX Keys (可選，若要在這裡統一管理)
    okx_api_key: Optional[str] = None
    okx_secret_key: Optional[str] = None
    okx_passphrase: Optional[str] = None

class APIKeySettings(BaseModel):
    api_key: str
    secret_key: str
    passphrase: str

class TradeExecutionRequest(BaseModel):
    symbol: str
    market_type: str # "spot" or "futures"
    side: str # "buy", "sell", "long", "short"
    amount: float # Investment/Margin amount in USDT
    leverage: int = 1
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class RefreshPulseRequest(BaseModel):
    symbols: Optional[List[str]] = None

class KeyValidationRequest(BaseModel):
    provider: str # openai, google_gemini, openrouter
    api_key: str
    model: Optional[str] = None  # 用戶選擇的模型名稱
