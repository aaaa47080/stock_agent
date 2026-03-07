"""
Agent V2 Bootstrap.

新版 ManagerAgent V2 的啟動器。
"""
from langchain_core.messages import SystemMessage
from typing import Optional

from .agent_registry import AgentRegistry, AgentMetadata
from .tool_registry import ToolRegistry, ToolMetadata
from .manager_v2 import ManagerAgentV2

# 導入工具
from .tools import (
    technical_analysis, price_data, get_crypto_price,
    google_news, aggregate_news, web_search,
    get_fear_and_greed_index, get_trending_tokens, get_futures_data,
    get_current_time_taipei, get_defillama_tvl, get_crypto_categories_and_gainers,
    get_token_unlocks, get_token_supply,
    tw_price, tw_technical, tw_fundamentals_tool, tw_institutional_tool, tw_news_tool,
    tw_major_news_tool, tw_pe_ratio_tool, tw_monthly_revenue_tool,
    tw_dividend_tool, tw_foreign_top20_tool,
    get_dex_pair_info_tool, get_trending_dex_pairs_tool,
    get_eth_balance_tool, get_erc20_token_balance_tool,
    get_address_transactions_tool, get_contract_info_tool, get_eth_price_etherscan_tool,
    get_commodity_price_tool, get_commodity_futures_tool,
    get_all_commodities_prices_tool, get_gold_silver_ratio_tool, get_oil_analysis_tool,
    get_forex_rate_tool, get_all_forex_rates_tool, get_usd_twd_rate_tool, get_central_bank_rates_tool,
    get_market_indices_tool, get_vix_index_tool, get_sp500_performance_tool,
    get_sector_performance_tool, get_economic_calendar_tool,
)

from core.tools.crypto_tools import (
    get_gas_fees, get_whale_transactions, get_exchange_flow,
)

from core.tools.pi_tools import (
    get_pi_price, get_pi_network_info, get_pi_ecosystem, get_pi_tools_guide,
)

from core.tools.us_stock_tools import (
    us_stock_price, us_technical_analysis, us_fundamentals,
    us_earnings, us_news, us_institutional_holders, us_insider_transactions,
)

from .agents import ChatAgent, TWStockAgent, USStockAgent, CryptoAgent, CommodityAgent, ForexAgent, EconomicAgent


class LanguageAwareLLM:
    """Wraps any LangChain LLM client to automatically prepend a language instruction."""

    _INSTRUCTIONS = {
        "zh-TW": "請以繁體中文回覆所有回應。",
        "en": "Please respond in English for all your responses.",
    }

    def __init__(self, llm, language: str = "zh-TW"):
        self._llm = llm
        self._lang_msg = self._INSTRUCTIONS.get(language, self._INSTRUCTIONS["zh-TW"])

    def invoke(self, messages, **kwargs):
        messages = list(messages)
        if messages and isinstance(messages[0], SystemMessage):
            messages[0] = SystemMessage(content=messages[0].content + f"\n\n{self._lang_msg}")
        else:
            messages.insert(0, SystemMessage(content=self._lang_msg))
        return self._llm.invoke(messages, **kwargs)

    def bind_tools(self, tools, **kwargs):
        bound = self._llm.bind_tools(tools, **kwargs)
        wrapper = LanguageAwareLLM.__new__(LanguageAwareLLM)
        wrapper._llm = bound
        wrapper._lang_msg = self._lang_msg
        return wrapper

    def __getattr__(self, name):
        return getattr(self._llm, name)


# 工具清單 fallback
_TOOL_FALLBACK = {
    "crypto": [
        "get_current_time_taipei", "technical_analysis", "price_data", "get_crypto_price",
        "google_news", "aggregate_news", "web_search", "get_fear_and_greed_index",
        "get_trending_tokens", "get_futures_data", "get_defillama_tvl",
        "get_crypto_categories_and_gainers", "get_token_unlocks", "get_token_supply",
        "get_gas_fees", "get_whale_transactions", "get_exchange_flow",
        "get_dex_pair_info", "get_trending_dex_pairs",
        "get_eth_balance", "get_erc20_token_balance", "get_address_transactions",
        "get_contract_info", "get_eth_price_etherscan",
    ],
    "tw_stock": [
        "get_current_time_taipei", "tw_stock_price", "tw_technical_analysis",
        "tw_fundamentals", "tw_institutional", "tw_news", "tw_major_news",
        "tw_pe_ratio", "tw_monthly_revenue", "tw_dividend", "tw_foreign_top20", "web_search",
    ],
    "us_stock": [
        "us_stock_price", "us_technical_analysis", "us_fundamentals", "us_earnings",
        "us_news", "us_institutional_holders", "us_insider_transactions", "get_current_time_taipei",
    ],
    "chat": [
        "get_current_time_taipei", "get_crypto_price", "web_search",
        "get_pi_price", "get_pi_network_info", "get_pi_ecosystem",
    ],
    "commodity": [
        "get_commodity_price", "get_commodity_futures_price", "get_all_commodities_prices",
        "get_gold_silver_ratio", "get_oil_price_analysis", "get_current_time_taipei", "web_search",
    ],
    "forex": [
        "get_forex_rate", "get_all_forex_rates", "get_usd_twd_rate", "get_central_bank_rates",
        "get_current_time_taipei", "web_search",
    ],
    "economic": [
        "get_market_indices", "get_vix_index", "get_sp500_performance", "get_sector_performance",
        "get_economic_calendar", "get_current_time_taipei", "web_search",
    ],
}


def _get_tools_fn(user_tier: str, user_id: Optional[str]) -> callable:
    """獲取工具函數"""
    try:
        from core.database.tools import seed_tools_catalog, get_allowed_tools as _get_tools
        seed_tools_catalog()

        def tools_fn(agent_id: str) -> list:
            return _get_tools(agent_id, user_tier=user_tier, user_id=user_id)
        return tools_fn
    except Exception as e:
        import logging
        logging.warning(f"[bootstrap_v2] Tool DB unavailable, using fallback: {e}")

        def tools_fn(agent_id: str) -> list:
            return _TOOL_FALLBACK.get(agent_id, [])
        return tools_fn


def bootstrap_v2(llm_client, web_mode: bool = False, language: str = "zh-TW",
                 user_tier: str = "free", user_id: Optional[str] = None) -> ManagerAgentV2:
    """
    初始化 ManagerAgent V2
    """
    agent_registry = AgentRegistry()
    tool_registry = ToolRegistry()

    # 獲取工具函數
    tools_fn = _get_tools_fn(user_tier, user_id)

    # 註冊工具
    _register_tools(tool_registry)

    # 包裝 LLM
    lang_llm = LanguageAwareLLM(llm_client, language)

    # 註冊 Agents
    _register_agents(agent_registry, lang_llm, tool_registry, tools_fn)

    return ManagerAgentV2(
        llm_client=lang_llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        web_mode=web_mode,
    )


def _register_tools(tool_registry: ToolRegistry):
    """註冊所有工具"""

    # === Crypto Tools ===
    tool_registry.register(ToolMetadata(
        name="technical_analysis",
        description="獲取加密貨幣技術指標（RSI, MACD, 均線）",
        input_schema={"symbol": "str", "interval": "str"},
        handler=technical_analysis,
        allowed_agents=["technical", "crypto", "full_analysis"],
    ))
    tool_registry.register(ToolMetadata(
        name="price_data",
        description="獲取加密貨幣即時和歷史價格數據",
        input_schema={"symbol": "str"},
        handler=price_data,
        allowed_agents=["technical", "crypto", "full_analysis"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_crypto_price",
        description="獲取加密貨幣即時價格",
        input_schema={"symbol": "str"},
        handler=get_crypto_price,
        allowed_agents=["technical", "crypto", "chat", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="google_news",
        description="獲取加密貨幣最新新聞（觸發詞：新聞、消息、動態、最新、發生了什麼、市場情緒）",
        input_schema={"symbol": "str", "limit": "int"},
        handler=google_news,
        allowed_agents=["news", "crypto", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="aggregate_news",
        description="多來源新聞聚合，比 google_news 更完整（觸發詞：新聞、消息、動態、最新、發生了什麼、市場情緒）",
        input_schema={"symbol": "str", "limit": "int"},
        handler=aggregate_news,
        allowed_agents=["news", "crypto", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="web_search",
        description="通用網絡搜索（觸發詞：宏觀市場、整體經濟、全球事件；或當專用工具無結果時的備選）",
        input_schema={"query": "str", "purpose": "str"},
        handler=web_search,
        allowed_agents=["chat", "news", "crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_fear_and_greed_index",
        description="獲取全球加密貨幣市場恐慌與貪婪指數",
        input_schema={},
        handler=get_fear_and_greed_index,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_trending_tokens",
        description="獲取目前全網最熱門搜尋的加密貨幣",
        input_schema={},
        handler=get_trending_tokens,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_futures_data",
        description="獲取加密貨幣永續合約的資金費率與多空情緒",
        input_schema={"symbol": "str"},
        handler=get_futures_data,
        allowed_agents=["crypto"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_current_time_taipei",
        description="獲取目前台灣/UTC+8的精準時間與日期",
        input_schema={},
        handler=get_current_time_taipei,
        allowed_agents=["crypto", "chat", "tw_stock", "us_stock", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_defillama_tvl",
        description="從 DefiLlama 獲取特定協議或公鏈的 TVL",
        input_schema={"protocol_name": "str"},
        handler=get_defillama_tvl,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_crypto_categories_and_gainers",
        description="獲取 CoinGecko 上表現最佳的加密貨幣板塊與熱點",
        input_schema={},
        handler=get_crypto_categories_and_gainers,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_token_unlocks",
        description="獲取代幣未來的解鎖日程與數量",
        input_schema={"symbol": "str"},
        handler=get_token_unlocks,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_token_supply",
        description="獲取代幣的總發行量、最大供應量與目前市場流通量",
        input_schema={"symbol": "str"},
        handler=get_token_supply,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_gas_fees",
        description="獲取 Ethereum 網路的即時 Gas 費用",
        input_schema={},
        handler=get_gas_fees,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_whale_transactions",
        description="獲取加密貨幣的大額鏈上轉帳（鯨魚交易）",
        input_schema={"symbol": "str", "min_value_usd": "int"},
        handler=get_whale_transactions,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_exchange_flow",
        description="獲取加密貨幣交易所的資金流向數據",
        input_schema={"symbol": "str"},
        handler=get_exchange_flow,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_dex_pair_info",
        description="獲取 DEX 代幣對的詳細資訊",
        input_schema={"token_address": "str"},
        handler=get_dex_pair_info_tool,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_trending_dex_pairs",
        description="搜索熱門 DEX 交易對",
        input_schema={"query": "str"},
        handler=get_trending_dex_pairs_tool,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_eth_balance",
        description="查詢以太坊地址的 ETH 餘額",
        input_schema={"address": "str"},
        handler=get_eth_balance_tool,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_erc20_token_balance",
        description="查詢以太坊地址的 ERC20 代幣餘額",
        input_schema={"address": "str", "contract_address": "str"},
        handler=get_erc20_token_balance_tool,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_address_transactions",
        description="查詢以太坊地址的最近交易記錄",
        input_schema={"address": "str", "limit": "int"},
        handler=get_address_transactions_tool,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_contract_info",
        description="查詢以太坊智能合約的基本資訊",
        input_schema={"contract_address": "str"},
        handler=get_contract_info_tool,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_eth_price_etherscan",
        description="從 Etherscan 獲取 ETH 即時價格",
        input_schema={},
        handler=get_eth_price_etherscan_tool,
        allowed_agents=["crypto", "chat", "manager"],
    ))

    # === Commodity Tools ===
    tool_registry.register(ToolMetadata(
        name="get_commodity_price",
        description="查詢大宗商品即時價格",
        input_schema={"commodity": "str"},
        handler=get_commodity_price_tool,
        allowed_agents=["commodity", "crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_commodity_futures_price",
        description="查詢商品期貨價格",
        input_schema={"futures_type": "str"},
        handler=get_commodity_futures_tool,
        allowed_agents=["commodity", "crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_all_commodities_prices",
        description="獲取所有主要大宗商品價格一覽表",
        input_schema={},
        handler=get_all_commodities_prices_tool,
        allowed_agents=["commodity", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_gold_silver_ratio",
        description="獲取金銀比",
        input_schema={},
        handler=get_gold_silver_ratio_tool,
        allowed_agents=["commodity", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_oil_price_analysis",
        description="獲取原油價格綜合分析",
        input_schema={},
        handler=get_oil_analysis_tool,
        allowed_agents=["commodity", "manager"],
    ))

    # === Forex Tools ===
    tool_registry.register(ToolMetadata(
        name="get_forex_rate",
        description="查詢外匯即時匯率",
        input_schema={"pair": "str"},
        handler=get_forex_rate_tool,
        allowed_agents=["forex", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_all_forex_rates",
        description="獲取所有主要貨幣對的即時匯率一覽表",
        input_schema={},
        handler=get_all_forex_rates_tool,
        allowed_agents=["forex", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_usd_twd_rate",
        description="查詢美元/台幣即時匯率",
        input_schema={},
        handler=get_usd_twd_rate_tool,
        allowed_agents=["forex", "chat", "tw_stock", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_central_bank_rates",
        description="獲取主要央行利率",
        input_schema={},
        handler=get_central_bank_rates_tool,
        allowed_agents=["forex", "manager"],
    ))

    # === Economic Tools ===
    tool_registry.register(ToolMetadata(
        name="get_market_indices",
        description="獲取美股主要市場指數",
        input_schema={},
        handler=get_market_indices_tool,
        allowed_agents=["economic", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_vix_index",
        description="獲取 VIX 恐慌指數詳細資訊",
        input_schema={},
        handler=get_vix_index_tool,
        allowed_agents=["economic", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_sp500_performance",
        description="獲取 S&P 500 指數詳細表現",
        input_schema={},
        handler=get_sp500_performance_tool,
        allowed_agents=["economic", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_sector_performance",
        description="獲取美股 11 大板塊表現",
        input_schema={},
        handler=get_sector_performance_tool,
        allowed_agents=["economic", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_economic_calendar",
        description="獲取近期重要經濟事件行事曆",
        input_schema={},
        handler=get_economic_calendar_tool,
        allowed_agents=["economic", "manager"],
    ))

    # === Pi Network Tools ===
    tool_registry.register(ToolMetadata(
        name="get_pi_price",
        description="獲取 Pi Network (PI) 幣的即時價格",
        input_schema={},
        handler=get_pi_price,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_pi_network_info",
        description="獲取 Pi Network 的專案資訊",
        input_schema={},
        handler=get_pi_network_info,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_pi_ecosystem",
        description="獲取 Pi Network 生態系統資訊",
        input_schema={},
        handler=get_pi_ecosystem,
        allowed_agents=["crypto", "chat"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_pi_tools_guide",
        description="顯示 Pi Network 工具使用指南",
        input_schema={},
        handler=get_pi_tools_guide,
        allowed_agents=["chat"],
    ))

    # === TW Stock Tools ===
    tool_registry.register(ToolMetadata(
        name="tw_stock_price",
        description="獲取台股即時價格",
        input_schema={"ticker": "str"},
        handler=tw_price,
        allowed_agents=["tw_stock", "chat"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_technical_analysis",
        description="計算台股技術指標",
        input_schema={"ticker": "str"},
        handler=tw_technical,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_fundamentals",
        description="獲取台股基本面資料",
        input_schema={"ticker": "str"},
        handler=tw_fundamentals_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_institutional",
        description="獲取台股三大法人籌碼資料",
        input_schema={"ticker": "str"},
        handler=tw_institutional_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_news",
        description="獲取台股相關新聞",
        input_schema={"ticker": "str", "company_name": "str"},
        handler=tw_news_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_major_news",
        description="獲取台股上市公司今日重大訊息",
        input_schema={"limit": "int"},
        handler=tw_major_news_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_pe_ratio",
        description="獲取台股個股本益比",
        input_schema={"code": "str"},
        handler=tw_pe_ratio_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_monthly_revenue",
        description="獲取台股月營收資料",
        input_schema={"code": "str"},
        handler=tw_monthly_revenue_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_dividend",
        description="獲取台股股利分派資訊",
        input_schema={"code": "str"},
        handler=tw_dividend_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_foreign_top20",
        description="獲取外資及陸資持股台股前20名",
        input_schema={},
        handler=tw_foreign_top20_tool,
        allowed_agents=["tw_stock"],
    ))

    # === US Stock Tools ===
    tool_registry.register(ToolMetadata(
        name="us_stock_price",
        description="獲取美股即時價格數據",
        input_schema={"symbol": "str"},
        handler=us_stock_price,
        allowed_agents=["us_stock", "chat"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_technical_analysis",
        description="計算美股技術指標",
        input_schema={"symbol": "str"},
        handler=us_technical_analysis,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_fundamentals",
        description="獲取美股基本面",
        input_schema={"symbol": "str"},
        handler=us_fundamentals,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_earnings",
        description="獲取美股財報數據和財報日曆",
        input_schema={"symbol": "str"},
        handler=us_earnings,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_news",
        description="獲取美股相關最新新聞",
        input_schema={"symbol": "str", "limit": "int"},
        handler=us_news,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_institutional_holders",
        description="獲取美股機構持倉數據",
        input_schema={"symbol": "str"},
        handler=us_institutional_holders,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_insider_transactions",
        description="獲取美股內部人交易記錄",
        input_schema={"symbol": "str"},
        handler=us_insider_transactions,
        allowed_agents=["us_stock"],
    ))


def _register_agents(agent_registry: AgentRegistry, lang_llm, tool_registry: ToolRegistry, tools_fn):
    """註冊所有 agents"""

    crypto = CryptoAgent(lang_llm, tool_registry)
    agent_registry.register(crypto, AgentMetadata(
        name="crypto",
        display_name="Crypto Agent",
        description="加密貨幣專業分析師 — 提供即時價格、時間、技術指標、合約資金費率、解鎖日程、代幣發行流通量、恐慌貪婪指數、全網熱門幣種、TVL鎖倉量、最強板塊與最新新聞。",
        capabilities=["RSI", "MACD", "MA", "technical analysis", "crypto news", "加密貨幣", "技術指標"],
        allowed_tools=tools_fn("crypto"),
        priority=10,
    ))

    tw = TWStockAgent(lang_llm, tool_registry)
    agent_registry.register(tw, AgentMetadata(
        name="tw_stock",
        display_name="TW Stock Agent",
        description="台灣股市全方位分析 — 即時價格、時間、技術指標、基本面、三大法人籌碼、台股新聞。",
        capabilities=["台股", "台灣股市", "上市", "上櫃", "股票代號"],
        allowed_tools=tools_fn("tw_stock"),
        priority=10,
    ))

    us = USStockAgent(lang_llm, tool_registry)
    agent_registry.register(us, AgentMetadata(
        name="us_stock",
        display_name="US Stock Agent",
        description="美股全方位分析 — 即時價格、技術指標、基本面、財報數據與日曆、機構持倉、最新新聞。",
        capabilities=["美股", "US stock", "NYSE", "NASDAQ"],
        allowed_tools=tools_fn("us_stock"),
        priority=8,
    ))

    commodity = CommodityAgent(lang_llm, tool_registry)
    agent_registry.register(commodity, AgentMetadata(
        name="commodity",
        display_name="Commodity Agent",
        description="大宗商品專業分析師 — 提供黃金、白銀、原油、天然氣、銅等商品的即時價格、期貨價格、金銀比分析。",
        capabilities=["黃金", "白銀", "原油", "石油", "天然氣", "commodity"],
        allowed_tools=tools_fn("commodity"),
        priority=9,
    ))

    forex = ForexAgent(lang_llm, tool_registry)
    agent_registry.register(forex, AgentMetadata(
        name="forex",
        display_name="Forex Agent",
        description="外匯專業分析師 — 提供主要貨幣對匯率、央行利率資訊。",
        capabilities=["外匯", "匯率", "forex", "貨幣"],
        allowed_tools=tools_fn("forex"),
        priority=8,
    ))

    economic = EconomicAgent(lang_llm, tool_registry)
    agent_registry.register(economic, AgentMetadata(
        name="economic",
        display_name="Economic Agent",
        description="經濟數據專業分析師 — 提供市場指數、VIX恐慌指數、板塊表現、經濟事件行事曆。",
        capabilities=["經濟", "指數", "VIX", "恐慌指數", "S&P 500"],
        allowed_tools=tools_fn("economic"),
        priority=7,
    ))

    chat = ChatAgent(lang_llm, tool_registry)
    agent_registry.register(chat, AgentMetadata(
        name="chat",
        display_name="Chat Agent",
        description="一般對話助手 — 處理閒聊、問候、自我介紹、平台使用說明、系統時間查詢、即時價格查詢、一般知識問答。",
        capabilities=["conversation", "greeting", "help", "general knowledge"],
        allowed_tools=tools_fn("chat"),
        priority=1,
    ))
