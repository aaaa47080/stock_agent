import asyncio
import logging
from core.config import (
    MARKET_PULSE_TARGETS, MARKET_PULSE_UPDATE_INTERVAL,
    FUNDING_RATE_UPDATE_INTERVAL
)

# 設定日誌
logger = logging.getLogger("API")

# --- 全域快取 (Screener) ---
# 用於儲存市場掃描結果，避免每次請求都重新運算
cached_screener_result = {
    "timestamp": None,
    "data": None
}

# --- 全域快取 (Market Pulse) ---
# 用於儲存市場脈動 AI 分析結果
MARKET_PULSE_CACHE = {}

# --- 全域快取 (Funding Rate) ---
FUNDING_RATE_CACHE = {
    "timestamp": None,
    "data": {}
}

# Locks for concurrency control
screener_lock = asyncio.Lock()
funding_rate_lock = asyncio.Lock()
symbol_locks = {} # {symbol: asyncio.Lock()}

def get_symbol_lock(symbol: str) -> asyncio.Lock:
    if symbol not in symbol_locks:
        symbol_locks[symbol] = asyncio.Lock()
    return symbol_locks[symbol]

# Global Instances
bot = None
okx_connector = None
