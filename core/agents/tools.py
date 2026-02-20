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

@tool
def web_search(query: str, purpose: str = "general") -> str:
    """
    Perform a general web search to find information not available in the internal database.
    Use this for:
    1. Looking up current events, news, or market sentiment.
    2. Finding specific facts (e.g., "Pi Network current price", "competitors of Solana").
    3. Verifying information.
    """
    from core.tools.web_search import web_search_tool
    return web_search_tool.invoke({"query": query, "purpose": purpose})

# ============================================
# 所有工具列表（供 Manager prompt 用）
# ============================================

# ============================================
# 台股工具 (TW Stock Tools)
# ============================================

@tool
def tw_price(ticker: str) -> dict:
    """獲取台股即時價格（yfinance）"""
    from core.tools.tw_stock_tools import tw_stock_price
    return tw_stock_price.invoke({"ticker": ticker})


@tool
def tw_technical(ticker: str) -> dict:
    """計算台股技術指標 RSI/MACD/KD/MA"""
    from core.tools.tw_stock_tools import tw_technical_analysis
    return tw_technical_analysis.invoke({"ticker": ticker})


@tool
def tw_fundamentals_tool(ticker: str) -> dict:
    """獲取台股基本面資料"""
    from core.tools.tw_stock_tools import tw_fundamentals
    return tw_fundamentals.invoke({"ticker": ticker})


@tool
def tw_institutional_tool(ticker: str) -> dict:
    """獲取台股三大法人籌碼資料"""
    from core.tools.tw_stock_tools import tw_institutional
    return tw_institutional.invoke({"ticker": ticker})


@tool
def tw_news_tool(ticker: str, company_name: str = "") -> list:
    """獲取台股新聞"""
    from core.tools.tw_stock_tools import tw_news
    return tw_news.invoke({"ticker": ticker, "company_name": company_name})


# ============================================
# 所有工具列表（供 Manager prompt 用）
# ============================================

ALL_TOOLS = [
    google_news,
    aggregate_news,
    technical_analysis,
    price_data,
    get_crypto_price,
    web_search,
    tw_price,
    tw_technical,
    tw_fundamentals_tool,
    tw_institutional_tool,
    tw_news_tool,
]
