"""
加密貨幣工具共用模組
Shared imports, constants, and cache functions
"""
import time
from typing import Dict, Optional

# API Base URLs
ETHERSCAN_BASE = "https://api.etherscan.io/api"
DEXSCREENER_BASE = "https://api.dexscreener.com/latest"

# In-Memory TTL Cache
_COINGECKO_CACHE: Dict = {}


def get_cached_data(key: str, ttl_seconds: int = 300) -> Optional[str]:
    """Get cached data if still valid"""
    if key in _COINGECKO_CACHE:
        timestamp, data = _COINGECKO_CACHE[key]
        if time.time() - timestamp < ttl_seconds:
            return data
    return None


def set_cached_data(key: str, data: str):
    """Store data in cache"""
    _COINGECKO_CACHE[key] = (time.time(), data)
