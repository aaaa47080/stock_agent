from typing import Optional, List
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
    signal_type: str = "RSI" # RSI, MACD, MA_CROSS
    interval: str = "1h"

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
