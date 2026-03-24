import asyncio
import logging
from collections import OrderedDict
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger("API")
logger.setLevel(logging.INFO)

MARKET_PULSE_CACHE: TTLCache = TTLCache(maxsize=500, ttl=300)
FUNDING_RATE_CACHE: TTLCache = TTLCache(maxsize=100, ttl=60)

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
symbol_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
_MAX_SYMBOL_LOCKS = 1000


def get_symbol_lock(symbol: str) -> asyncio.Lock:
    if symbol not in symbol_locks:
        if len(symbol_locks) >= _MAX_SYMBOL_LOCKS:
            symbol_locks.popitem(last=False)
        symbol_locks[symbol] = asyncio.Lock()
    else:
        symbol_locks.move_to_end(symbol)
    return symbol_locks[symbol]


# Global Instances
okx_connector: Optional[Any] = None
v4_manager: Optional[Any] = None  # ManagerAgent (V4) — 替代 CryptoAnalysisBot
