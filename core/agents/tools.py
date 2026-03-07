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
    """獲取加密貨幣最新新聞。

    ⚠️ 觸發條件：當用戶問題包含以下關鍵字時，必須使用此工具：
    - 「新聞」「消息」「動態」「資訊」「事件」
    - 「最新」「最近」「近期」+ 任何市場相關詞
    - 「發生了什麼」「有什麼消息」「市場情緒」

    ⚠️ 輸出格式：返回的新聞列表包含 title 和 url 欄位。
    你必須將結果格式化為 Markdown 連結格式：
    - **正確格式**：[標題](url)
    - **錯誤格式**：只顯示標題而省略 URL

    Args:
        symbol: 幣種代碼，如 BTC、ETH、SOL
        limit: 返回新聞數量，預設 5

    Returns:
        包含 title, url, description, source 的新聞列表
    """
    from utils.utils import get_crypto_news_google
    return get_crypto_news_google(symbol=symbol, limit=limit)


@tool
def aggregate_news(symbol: str = "BTC", limit: int = 5) -> list:
    """從多個來源聚合加密貨幣新聞（Google + CryptoCompare）。

    ⚠️ 觸發條件：當用戶問題包含以下關鍵字時，必須使用此工具：
    - 「新聞」「消息」「動態」「資訊」「事件」
    - 「最新」「最近」「近期」+ 任何市場相關詞
    - 「發生了什麼」「有什麼消息」「市場情緒」
    - 需要更全面的新聞來源時（比 google_news 更完整）

    ⚠️ 輸出格式：返回的新聞列表包含 title 和 url 欄位。
    你必須將結果格式化為 Markdown 連結格式：
    - **正確格式**：[標題](url)
    - **錯誤格式**：只顯示標題而省略 URL

    Args:
        symbol: 幣種代碼，如 BTC、ETH、SOL
        limit: 返回新聞數量，預設 5

    Returns:
        包含 title, url, description, source 的新聞列表
    """
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
    """通用網絡搜索 (DuckDuckGo)，用於獲取即時資訊。

    ⚠️ 觸發條件：
    1. 需要最新/即時資訊，且其他專用工具無法滿足時
    2. 用戶問「宏觀市場」「整體經濟」「全球事件」等超出單一幣種範圍的問題
    3. 專用新聞工具（google_news/aggregate_news）返回空結果時的備選方案

    注意：對於加密貨幣新聞，應優先使用 google_news 或 aggregate_news

    Args:
        query: 搜索關鍵字，如 "Bitcoin ETF approval news 2024"
        purpose: 搜索目的說明
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
# DexScreener DEX 數據工具
# ============================================

@tool
def get_dex_pair_info_tool(token_address: str) -> dict:
    """獲取 DEX 代幣對的詳細資訊（價格、流動性、交易量）"""
    from core.tools.crypto_tools import get_dex_pair_info
    return get_dex_pair_info.invoke({"token_address": token_address})


@tool
def get_trending_dex_pairs_tool(query: str) -> list:
    """搜索熱門 DEX 交易對（如 PEPE、WIF、DOGE）"""
    from core.tools.crypto_tools import get_trending_dex_pairs
    return get_trending_dex_pairs.invoke({"query": query})


# ============================================
# Etherscan 鏈上數據工具
# ============================================

@tool
def get_eth_balance_tool(address: str) -> dict:
    """查詢以太坊地址的 ETH 餘額"""
    from core.tools.crypto_tools import get_eth_balance
    return get_eth_balance.invoke({"address": address})


@tool
def get_erc20_token_balance_tool(address: str, contract_address: str) -> dict:
    """查詢以太坊地址的 ERC20 代幣餘額"""
    from core.tools.crypto_tools import get_erc20_token_balance
    return get_erc20_token_balance.invoke({"address": address, "contract_address": contract_address})


@tool
def get_address_transactions_tool(address: str, limit: int = 10) -> dict:
    """查詢以太坊地址的最近交易記錄"""
    from core.tools.crypto_tools import get_address_transactions
    return get_address_transactions.invoke({"address": address, "limit": limit})


@tool
def get_contract_info_tool(contract_address: str) -> dict:
    """查詢以太坊智能合約的基本資訊"""
    from core.tools.crypto_tools import get_contract_info
    return get_contract_info.invoke({"contract_address": contract_address})


@tool
def get_eth_price_etherscan_tool() -> dict:
    """從 Etherscan 獲取 ETH 即時價格"""
    from core.tools.crypto_tools import get_eth_price_from_etherscan
    return get_eth_price_from_etherscan.invoke({})


# ============================================
# 大宗商品工具 (Commodity Tools)
# ============================================

@tool
def get_commodity_price_tool(commodity: str) -> dict:
    """查詢大宗商品即時價格（黃金、白銀、石油、天然氣、銅等）"""
    from core.tools.commodity_tools import get_commodity_price
    return get_commodity_price.invoke({"commodity": commodity})


@tool
def get_commodity_futures_tool(futures_type: str) -> dict:
    """查詢商品期貨價格（原油、黃金、白銀、天然氣期貨）"""
    from core.tools.commodity_tools import get_commodity_futures_price
    return get_commodity_futures_price.invoke({"futures_type": futures_type})


@tool
def get_all_commodities_prices_tool() -> dict:
    """獲取所有主要大宗商品價格一覽表"""
    from core.tools.commodity_tools import get_all_commodities_prices
    return get_all_commodities_prices.invoke({})


@tool
def get_gold_silver_ratio_tool() -> dict:
    """獲取金銀比（重要的市場情緒指標）"""
    from core.tools.commodity_tools import get_gold_silver_ratio
    return get_gold_silver_ratio.invoke({})


@tool
def get_oil_analysis_tool() -> dict:
    """獲取原油價格綜合分析（WTI vs 布蘭特）"""
    from core.tools.commodity_tools import get_oil_price_analysis
    return get_oil_price_analysis.invoke({})


# ============================================
# 外匯工具 (Forex Tools)
# ============================================

@tool
def get_forex_rate_tool(pair: str) -> dict:
    """查詢外匯即時匯率（USD/TWD、USD/JPY、EUR/USD等）"""
    from core.tools.forex_tools import get_forex_rate
    return get_forex_rate.invoke({"pair": pair})


@tool
def get_all_forex_rates_tool() -> dict:
    """獲取所有主要貨幣對的即時匯率一覽表"""
    from core.tools.forex_tools import get_all_forex_rates
    return get_all_forex_rates.invoke({})


@tool
def get_usd_twd_rate_tool() -> dict:
    """查詢美元/台幣即時匯率"""
    from core.tools.forex_tools import get_usd_twd_rate
    return get_usd_twd_rate.invoke({})


@tool
def get_central_bank_rates_tool() -> dict:
    """獲取主要央行利率（Fed、ECB、BOJ、台灣央行）"""
    from core.tools.forex_tools import get_central_bank_rates
    return get_central_bank_rates.invoke({})


# ============================================
# 經濟數據工具 (Economic Tools)
# ============================================

@tool
def get_market_indices_tool() -> dict:
    """獲取美股主要市場指數（S&P 500、道瓊、那斯達克、VIX）"""
    from core.tools.economic_tools import get_market_indices
    return get_market_indices.invoke({})


@tool
def get_vix_index_tool() -> dict:
    """獲取 VIX 恐慌指數詳細資訊和市場情緒判讀"""
    from core.tools.economic_tools import get_vix_index
    return get_vix_index.invoke({})


@tool
def get_sp500_performance_tool() -> dict:
    """獲取 S&P 500 指數詳細表現和各期間報酬"""
    from core.tools.economic_tools import get_sp500_performance
    return get_sp500_performance.invoke({})


@tool
def get_sector_performance_tool() -> dict:
    """獲取美股 11 大板塊表現（科技、金融、能源等）"""
    from core.tools.economic_tools import get_us_sector_performance
    return get_us_sector_performance.invoke({})


@tool
def get_economic_calendar_tool() -> dict:
    """獲取近期重要經濟事件行事曆"""
    from core.tools.economic_tools import get_economic_calendar
    return get_economic_calendar.invoke({})


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
    # DexScreener tools
    get_dex_pair_info_tool,
    get_trending_dex_pairs_tool,
    # Etherscan tools
    get_eth_balance_tool,
    get_erc20_token_balance_tool,
    get_address_transactions_tool,
    get_contract_info_tool,
    get_eth_price_etherscan_tool,
    # Commodity tools
    get_commodity_price_tool,
    get_commodity_futures_tool,
    get_all_commodities_prices_tool,
    get_gold_silver_ratio_tool,
    get_oil_analysis_tool,
    # Forex tools
    get_forex_rate_tool,
    get_all_forex_rates_tool,
    get_usd_twd_rate_tool,
    get_central_bank_rates_tool,
    # Economic tools
    get_market_indices_tool,
    get_vix_index_tool,
    get_sp500_performance_tool,
    get_sector_performance_tool,
    get_economic_calendar_tool,
]
