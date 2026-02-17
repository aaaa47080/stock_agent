"""
Agent V4 — Tool Definitions

All tools use LangChain @tool decorator.
Each agent gets only the tools it should use (set in bootstrap.py).
"""
from langchain_core.tools import tool


# ============================================
# 新聞工具
# ============================================

@tool
def google_news(symbol: str = "BTC", limit: int = 5) -> list:
    """從 Google News RSS 獲取加密貨幣相關新聞，無需 API Key"""
    from utils.utils import get_crypto_news_google
    return get_crypto_news_google(symbol=symbol, limit=limit)


@tool
def aggregate_news(symbol: str = "BTC", limit: int = 5) -> list:
    """從多個來源聚合加密貨幣新聞（Google, CryptoCompare）"""
    from utils.utils import get_crypto_news
    return get_crypto_news(symbol=symbol, limit=limit, enabled_sources=["google", "cryptocompare"])


# ============================================
# 技術分析工具
# ============================================

@tool
def technical_analysis(symbol: str = "BTC", interval: str = "1d") -> dict:
    """獲取加密貨幣的技術指標（RSI, MACD, 均線等）"""
    from core.tools.crypto_tools import technical_analysis_tool
    return technical_analysis_tool.invoke({"symbol": symbol, "interval": interval})


@tool
def price_data(symbol: str = "BTC") -> list:
    """獲取加密貨幣的即時價格和歷史K線數據"""
    from utils.utils import get_binance_klines
    return get_binance_klines(symbol=f"{symbol}USDT", interval="1d", limit=30)


@tool
def get_crypto_price(symbol: str = "BTC") -> dict:
    """獲取加密貨幣的即時價格（精確價格查詢）"""
    from core.tools.crypto_tools import get_crypto_price_tool
    result = get_crypto_price_tool.invoke({"symbol": symbol})
    return {"price_info": result}


# ============================================
# 所有工具列表（供 Manager prompt 用）
# ============================================

ALL_TOOLS = [
    google_news,
    aggregate_news,
    technical_analysis,
    price_data,
    get_crypto_price,
]
