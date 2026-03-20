"""
工具輔助函數
提供符號標準化、交易所查找等通用功能
"""

import re
from typing import List, Optional, Tuple

from core.config import SUPPORTED_EXCHANGES
from data.data_fetcher import get_data_fetcher


def normalize_symbol(symbol: str, exchange: str = "okx") -> str:
    """
    標準化交易對符號

    Args:
        symbol: 原始符號，如 'BTC', 'BTC-USDT', 'BTCUSDT'
        exchange: 交易所名稱

    Returns:
        標準化後的符號，如 'BTC-USDT' (OKX) 或 'BTCUSDT' (Binance)
    """
    if not symbol:
        return ""
    symbol = symbol.upper().strip()

    # 1. 先提取基礎幣種 (Base Currency)
    base_symbol = symbol.replace("-", "").replace("_", "")

    if base_symbol.endswith("USDT"):
        base_symbol = base_symbol[:-4]
    elif base_symbol.endswith("BUSD"):
        base_symbol = base_symbol[:-4]
    elif base_symbol.endswith("USD"):
        base_symbol = base_symbol[:-3]

    # 2. 根據交易所格式化
    if exchange.lower() == "binance":
        return f"{base_symbol}USDT"
    else:  # okx (default)
        return f"{base_symbol}-USDT"


def find_available_exchange(symbol: str) -> Tuple[Optional[str], Optional[str]]:
    """
    查找交易對可用的交易所

    Args:
        symbol: 加密貨幣符號

    Returns:
        (exchange, normalized_symbol) 或 (None, None)
    """
    for exchange in SUPPORTED_EXCHANGES:
        try:
            normalized = normalize_symbol(symbol, exchange)
            fetcher = get_data_fetcher(exchange)
            test_data = fetcher.get_historical_klines(normalized, "1d", limit=1)
            if test_data is not None and not test_data.empty:
                return (exchange, normalized)
        except Exception:
            continue
    return (None, None)


# 常用加密貨幣符號列表
CRYPTO_SYMBOLS = [
    # Major coins
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "ADA",
    "DOGE",
    "DOT",
    "AVAX",
    "LTC",
    "LINK",
    "UNI",
    "BCH",
    "SHIB",
    "ETC",
    "TRX",
    "MATIC",
    "XLM",
    "ATOM",
    "NEAR",
    "APT",
    "AR",
    "PI",
    "TON",
    "BNB",
    "SUI",
    "STX",
    "FLOW",
    "HBAR",
    "VET",
    "ALGO",
    "XTZ",
    "EOS",
    "XMR",
    "ZEC",
    "ZIL",
    "ONT",
    "THETA",
    "AAVE",
    "SAND",
    "MANA",
    "PEPE",
    "FLOKI",
    "MEME",
    "WIF",
    "BONK",
    "RENDER",
    "TAO",
    "SEI",
    "JUP",
    "PYTH",
    "STRK",
    "WLD",
    "ORDI",
    "INJ",
    "TIA",
    "DYM",
    "FIL",
    "ICP",
    "FTM",
    "CRV",
    "MKR",
    "COMP",
    "YFI",
    "SNX",
    "DYDX",
    "GMX",
    "SUSHI",
    "NEO",
    "DASH",
    "ZEN",
    "BAT",
    "IOTA",
    "QTUM",
]

# 常見非幣種詞（避免誤識別）
COMMON_WORDS = {
    "USDT",
    "BUSD",
    "USD",
    "THE",
    "AND",
    "FOR",
    "ARE",
    "CAN",
    "SEE",
    "DID",
    "HAS",
    "WAS",
    "NOT",
    "BUT",
    "ALL",
    "ANY",
    "NEW",
    "NOW",
    "ONE",
    "TWO",
    "BUY",
    "SELL",
    "PAY",
    "GET",
    "RUN",
    "SET",
    "TOP",
    "LOW",
    "KEY",
    "USE",
    "TRY",
    "BIG",
    "OLD",
    "BAD",
    "HOT",
    "RED",
    "BIT",
    "EAT",
    "FLY",
    "MAN",
    "BOY",
    "ART",
    "CAR",
    "DAY",
    "WAY",
    "HEY",
    "WHY",
    "HOW",
    "WHO",
}


def extract_crypto_symbols(text: str) -> List[str]:
    """
    從文本中提取加密貨幣符號

    Args:
        text: 用戶輸入文本

    Returns:
        識別到的加密貨幣符號列表
    """
    # 使用負向前瞻和負向後顧來匹配幣種符號前後不是字母數字
    escaped_symbols = [re.escape(symbol) for symbol in CRYPTO_SYMBOLS]
    pattern = r"(?<![a-zA-Z0-9])(" + "|".join(escaped_symbols) + r")(?![a-zA-Z0-9])"
    matches = re.findall(pattern, text.upper(), re.IGNORECASE)

    # 去重並過濾常見非幣種詞
    return list(set(m for m in matches if m not in COMMON_WORDS))


def format_price(price: float) -> str:
    """
    智能價格格式化函數

    根據價格大小自動選擇適當的小數位數，
    確保低價代幣（如 SHIB、PEPE）能正確顯示。

    Args:
        price: 價格數值

    Returns:
        格式化後的價格字符串
    """
    if price is None or price == 0:
        return "N/A"

    abs_price = abs(price)

    # 根據價格範圍選擇小數位數
    if abs_price >= 1000:
        # 高價幣（如 BTC）：整數 + 2 位小數
        return f"${price:,.2f}"
    elif abs_price >= 1:
        # 中價幣（如 ETH, SOL）：2 位小數
        return f"${price:.2f}"
    elif abs_price >= 0.01:
        # 低價幣（如 DOGE）：4 位小數
        return f"${price:.4f}"
    elif abs_price >= 0.0001:
        # 超低價幣（如 SHIB）：6 位小數
        return f"${price:.6f}"
    else:
        # 極低價幣（如 PEPE）：8 位小數
        return f"${price:.8f}"
