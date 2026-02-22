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
# 專業加密貨幣市場數據 API
# ============================================

@tool
def get_fear_and_greed_index() -> str:
    """獲取加密貨幣市場全域的恐慌與貪婪指數"""
    from core.tools.crypto_tools import get_fear_and_greed_index
    return get_fear_and_greed_index.invoke({})

@tool
def get_trending_tokens() -> str:
    """獲取目前全網最熱門搜尋的加密貨幣"""
    from core.tools.crypto_tools import get_trending_tokens
    return get_trending_tokens.invoke({})

@tool
def get_futures_data(symbol: str = "BTC") -> str:
    """獲取加密貨幣永續合約的資金費率與多空情緒"""
    from core.tools.crypto_tools import get_futures_data
    return get_futures_data.invoke({"symbol": symbol})

@tool
def get_current_time_taipei() -> str:
    """獲取目前台灣/UTC+8的精準時間與日期"""
    from core.tools.crypto_tools import get_current_time_taipei
    return get_current_time_taipei.invoke({})

@tool
def get_defillama_tvl(protocol_name: str) -> str:
    """從 DefiLlama 獲取特定協議或公鏈的 TVL (總鎖倉價值)"""
    from core.tools.crypto_tools import get_defillama_tvl
    return get_defillama_tvl.invoke({"protocol_name": protocol_name})

@tool
def get_crypto_categories_and_gainers() -> str:
    """獲取 CoinGecko 上表現最佳的加密貨幣板塊"""
    from core.tools.crypto_tools import get_crypto_categories_and_gainers
    return get_crypto_categories_and_gainers.invoke({})

@tool
def get_token_unlocks(symbol: str) -> str:
    """獲取代幣未來的解鎖日程與數量 (Token Unlocks)"""
    from core.tools.crypto_tools import get_token_unlocks
    return get_token_unlocks.invoke({"symbol": symbol})

@tool
def get_token_supply(symbol: str) -> str:
    """獲取代幣的發行量、目前市場流通量與最大供應量上限"""
    from core.tools.crypto_tools import get_token_supply
    return get_token_supply.invoke({"symbol": symbol})


# ============================================
# 通用網絡搜尋工具
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


@tool
def tw_major_news_tool(limit: int = 10) -> list:
    """獲取台股上市公司今日重大訊息（TW Stock major announcements）"""
    from core.tools.tw_stock_tools import tw_major_news
    return tw_major_news.invoke({"limit": limit})


@tool
def tw_pe_ratio_tool(code: str) -> dict:
    """獲取台股個股本益比(P/E)、殖利率(Dividend Yield)、股價淨值比(P/B)。
    code: 股票代號，如 '2330'、'2317'"""
    from core.tools.tw_stock_tools import tw_pe_ratio
    return tw_pe_ratio.invoke({"code": code})


@tool
def tw_monthly_revenue_tool(code: str = "") -> list:
    """獲取台股月營收資料，含月增率與年增率。code 為股票代號，空白為全市場前30筆"""
    from core.tools.tw_stock_tools import tw_monthly_revenue
    return tw_monthly_revenue.invoke({"code": code})


@tool
def tw_dividend_tool(code: str = "") -> list:
    """獲取台股股利分派（現金股利、配股、除息日）。code 為股票代號，空白為近期全市場"""
    from core.tools.tw_stock_tools import tw_dividend_info
    return tw_dividend_info.invoke({"code": code})


@tool
def tw_foreign_top20_tool() -> list:
    """獲取外資及陸資持股台股前20名，含持股比率與可投資上限"""
    from core.tools.tw_stock_tools import tw_foreign_holding_top20
    return tw_foreign_holding_top20.invoke({})


# ============================================
# 所有工具列表（供 Manager prompt 用）
# ============================================

ALL_TOOLS = [
    google_news,
    aggregate_news,
    technical_analysis,
    price_data,
    get_crypto_price,
    get_fear_and_greed_index,
    get_trending_tokens,
    get_futures_data,
    get_current_time_taipei,
    get_defillama_tvl,
    get_crypto_categories_and_gainers,
    get_token_unlocks,
    web_search,
    tw_price,
    tw_technical,
    tw_fundamentals_tool,
    tw_institutional_tool,
    tw_news_tool,
    # TWSE OpenAPI tools
    tw_major_news_tool,
    tw_pe_ratio_tool,
    tw_monthly_revenue_tool,
    tw_dividend_tool,
    tw_foreign_top20_tool,
]
