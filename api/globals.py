import asyncio
import logging
from typing import Any, Optional

# 設定日誌
logger = logging.getLogger("API")
logger.setLevel(logging.INFO)  # Ensure this logger also logs at INFO level

# Global caches
MARKET_PULSE_CACHE = {}
FUNDING_RATE_CACHE = {}

# Analysis Status Tracker
ANALYSIS_STATUS = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current_batch": [],
    "start_time": None,
}

# Screener cache structure
cached_screener_result = {"timestamp": None, "data": None}

# Locks for concurrency control
screener_lock = asyncio.Lock()
funding_rate_lock = asyncio.Lock()
symbol_locks = {}  # {symbol: asyncio.Lock()}


def get_symbol_lock(symbol: str) -> asyncio.Lock:
    if symbol not in symbol_locks:
        symbol_locks[symbol] = asyncio.Lock()
    return symbol_locks[symbol]


# Global Instances
okx_connector: Optional[Any] = None
v4_manager: Optional[Any] = None  # ManagerAgent (V4) — 替代 CryptoAnalysisBot
