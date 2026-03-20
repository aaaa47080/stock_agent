"""
Agent V4 Bootstrap.

Assembles all components: tools → agents → manager.
Instantiates ToolRegistry and registers tools with permission checks.
"""

import asyncio
from typing import Dict, Optional

from langchain_core.messages import SystemMessage

from core.database.tools import normalize_membership_tier

# Import new free market data tools
from core.tools.crypto_tools import (
    get_exchange_flow,
    get_gas_fees,
    get_staking_yield,
    get_whale_transactions,
)

# Import Pi Network tools
from core.tools.pi_tools import (
    get_pi_ecosystem,
    get_pi_network_info,
    get_pi_price,
    get_pi_tools_guide,
)

# Import @tool functions — US stock
from core.tools.us_stock_tools import (
    us_earnings,
    us_fundamentals,
    us_insider_transactions,
    us_institutional_holders,
    us_news,
    us_stock_price,
    us_technical_analysis,
)

from .agent_registry import AgentMetadata, AgentRegistry

# Import agent classes
from .agents import (
    ChatAgent,
    CommodityAgent,
    CryptoAgent,
    EconomicAgent,
    ForexAgent,
    TWStockAgent,
    USStockAgent,
)
from .manager import ManagerAgent
from .prompt_registry import PromptRegistry
from .tool_registry import ToolMetadata, ToolRegistry

# Import @tool functions — crypto
from .tools import (
    aggregate_news,
    get_address_transactions_tool,
    get_all_commodities_prices_tool,
    get_all_forex_rates_tool,
    get_central_bank_rates_tool,
    get_commodity_futures_tool,
    # Commodity tools
    get_commodity_price_tool,
    get_contract_info_tool,
    get_crypto_categories_and_gainers,
    get_crypto_price,
    get_current_time_taipei,
    get_defillama_tvl,
    # DexScreener tools
    get_dex_pair_info_tool,
    get_economic_calendar_tool,
    get_erc20_token_balance_tool,
    # Etherscan tools
    get_eth_balance_tool,
    get_eth_price_etherscan_tool,
    get_fear_and_greed_index,
    # Forex tools
    get_forex_rate_tool,
    get_futures_data,
    get_gold_silver_ratio_tool,
    # Economic tools
    get_market_indices_tool,
    get_oil_analysis_tool,
    get_sector_performance_tool,
    get_sp500_performance_tool,
    get_token_supply,
    get_token_unlocks,
    get_trending_dex_pairs_tool,
    get_trending_tokens,
    get_usd_twd_rate_tool,
    get_vix_index_tool,
    google_news,
    technical_analysis,
    tw_dividend_tool,
    tw_foreign_top20_tool,
    tw_fundamentals_tool,
    tw_institutional_tool,
    tw_major_news_tool,
    tw_monthly_revenue_tool,
    tw_news_tool,
    tw_pe_ratio_tool,
    tw_price,
    tw_technical,
    web_search,
)


class LanguageAwareLLM:
    """Wraps any LangChain LLM client to automatically prepend a language instruction."""

    _INSTRUCTIONS = {
        "zh-TW": "請以繁體中文回覆所有回應。",
        "en": "Please respond in English for all your responses.",
    }

    def __init__(self, llm, language: str = "zh-TW"):
        self._llm = llm
        self._lang_msg = self._INSTRUCTIONS.get(language, self._INSTRUCTIONS["zh-TW"])

    def _inject_language(self, messages):
        messages = list(messages)
        if messages and isinstance(messages[0], SystemMessage):
            messages[0] = SystemMessage(
                content=messages[0].content + f"\n\n{self._lang_msg}"
            )
        else:
            messages.insert(0, SystemMessage(content=self._lang_msg))
        return messages

    def invoke(self, messages, **kwargs):
        return self._llm.invoke(self._inject_language(messages), **kwargs)

    async def ainvoke(self, messages, **kwargs):
        if hasattr(self._llm, "ainvoke"):
            return await self._llm.ainvoke(self._inject_language(messages), **kwargs)
        return await asyncio.to_thread(
            self._llm.invoke, self._inject_language(messages), **kwargs
        )

    def bind_tools(self, tools, **kwargs):
        """Delegate bind_tools but preserve language injection in the returned wrapper."""
        bound = self._llm.bind_tools(tools, **kwargs)
        wrapper = LanguageAwareLLM.__new__(LanguageAwareLLM)
        wrapper._llm = bound
        wrapper._lang_msg = self._lang_msg
        return wrapper

    def __getattr__(self, name):
        return getattr(self._llm, name)


def bootstrap(
    llm_client,
    web_mode: bool = False,
    language: str = "zh-TW",
    user_tier: str = "free",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> ManagerAgent:
    user_tier = normalize_membership_tier(user_tier)
    PromptRegistry.load()
    lang_llm = LanguageAwareLLM(llm_client, language)

    cache_key = _manager_cache_key(user_id, session_id)
    existing = _manager_cache.get(cache_key)

    if existing is not None:
        existing.llm = lang_llm
        existing.user_tier = user_tier
        existing.user_id = user_id or "anonymous"
        if hasattr(existing, "tool_access_resolver"):
            existing.tool_access_resolver.update_scope(user_tier, existing.user_id)
        if session_id:
            existing.session_id = session_id
            existing._memory_store = None
        for agent in existing.agent_registry._agents.values():
            if hasattr(agent, "llm"):
                agent.llm = lang_llm
            if hasattr(agent, "user_tier"):
                agent.user_tier = user_tier
            if hasattr(agent, "user_id"):
                agent.user_id = user_id
        return existing

    agent_registry = AgentRegistry()
    tool_registry = ToolRegistry()

    # ── Register Crypto Tools ──
    tool_registry.register(
        ToolMetadata(
            name="technical_analysis",
            description="獲取加密貨幣技術指標（RSI, MACD, 均線）",
            input_schema={"symbol": "str", "interval": "str"},
            handler=technical_analysis,
            allowed_agents=["technical", "crypto", "full_analysis"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="google_news",
            description="從 Google News RSS 獲取加密貨幣新聞",
            input_schema={"symbol": "str", "limit": "int"},
            handler=google_news,
            allowed_agents=["news", "crypto", "full_analysis", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="aggregate_news",
            description="多來源加密貨幣新聞聚合",
            input_schema={"symbol": "str", "limit": "int"},
            handler=aggregate_news,
            allowed_agents=["news", "crypto", "full_analysis", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_crypto_price",
            description="獲取加密貨幣即時價格",
            input_schema={"symbol": "str"},
            handler=get_crypto_price,
            allowed_agents=["technical", "crypto", "chat", "full_analysis", "manager"],
            role="market_lookup",
            priority=100,
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_fear_and_greed_index",
            description="獲取全球加密貨幣市場恐慌與貪婪指數 (Fear & Greed Index)",
            input_schema={},
            handler=get_fear_and_greed_index,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_trending_tokens",
            description="獲取目前全網最熱門搜尋的加密貨幣 (Trending Tokens)",
            input_schema={},
            handler=get_trending_tokens,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_futures_data",
            description="獲取加密貨幣永續合約的資金費率與多空情緒 (Funding Rates)",
            input_schema={"symbol": "str"},
            handler=get_futures_data,
            allowed_agents=["crypto"],
            required_tier="premium",
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_current_time_taipei",
            description="獲取目前台灣/UTC+8的精準時間與日期",
            input_schema={},
            handler=get_current_time_taipei,
            allowed_agents=["crypto", "chat", "tw_stock", "us_stock", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_defillama_tvl",
            description="從 DefiLlama 獲取特定協議或公鏈的 TVL (總鎖倉價值)",
            input_schema={"protocol_name": "str"},
            handler=get_defillama_tvl,
            allowed_agents=["crypto", "manager"],
            required_tier="premium",
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_crypto_categories_and_gainers",
            description="獲取 CoinGecko 上表現最佳的加密貨幣板塊與熱點 (Sectors)",
            input_schema={},
            handler=get_crypto_categories_and_gainers,
            allowed_agents=["crypto", "manager"],
            required_tier="premium",
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_token_unlocks",
            description="獲取代幣未來的解鎖日程與數量 (Token Unlocks)。當需要評估代幣拋壓時使用。",
            input_schema={"symbol": "str"},
            handler=get_token_unlocks,
            allowed_agents=["crypto", "manager"],
            required_tier="premium",
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_token_supply",
            description="獲取代幣的總發行量、最大供應量與目前市場流通量 (Tokenomics)。",
            input_schema={"symbol": "str"},
            handler=get_token_supply,
            allowed_agents=["crypto", "manager"],
            required_tier="premium",
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="web_search",
            description="通用網絡搜索 (DuckDuckGo)",
            input_schema={"query": "str", "purpose": "str"},
            handler=web_search,
            allowed_agents=["chat", "news", "crypto", "manager"],
            role="discovery_lookup",
            priority=80,
        )
    )

    # ── Register New Free Market Data Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_gas_fees",
            description="獲取 Ethereum 網路的即時 Gas 費用",
            input_schema={},
            handler=get_gas_fees,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_whale_transactions",
            description="獲取加密貨幣的大額鏈上轉帳（鯨魚交易）",
            input_schema={"symbol": "str", "min_value_usd": "int"},
            handler=get_whale_transactions,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_exchange_flow",
            description="獲取加密貨幣交易所的資金流向數據",
            input_schema={"symbol": "str"},
            handler=get_exchange_flow,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_staking_yield",
            description="獲取加密貨幣的質押年化收益率(APY)。支援 SOL、ETH、ADA、ATOM 等主流 PoS 代幣。",
            input_schema={"symbol": "str"},
            handler=get_staking_yield,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )

    # ── Register DexScreener Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_dex_pair_info",
            description="獲取 DEX 代幣對的詳細資訊（價格、流動性、交易量）。輸入代幣合約地址。",
            input_schema={"token_address": "str"},
            handler=get_dex_pair_info_tool,
            allowed_agents=["crypto", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_trending_dex_pairs",
            description="搜索熱門 DEX 交易對（如 PEPE、WIF、DOGE）。輸入代幣名稱或符號。",
            input_schema={"query": "str"},
            handler=get_trending_dex_pairs_tool,
            allowed_agents=["crypto", "manager"],
        )
    )

    # ── Register Etherscan On-chain Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_eth_balance",
            description="查詢以太坊地址的 ETH 餘額。輸入 0x 開頭的 42 字符地址。",
            input_schema={"address": "str"},
            handler=get_eth_balance_tool,
            allowed_agents=["crypto", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_erc20_token_balance",
            description="查詢以太坊地址的 ERC20 代幣餘額。需要錢包地址和代幣合約地址。",
            input_schema={"address": "str", "contract_address": "str"},
            handler=get_erc20_token_balance_tool,
            allowed_agents=["crypto", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_address_transactions",
            description="查詢以太坊地址的最近交易記錄。可追蹤資金流向。",
            input_schema={"address": "str", "limit": "int (optional)"},
            handler=get_address_transactions_tool,
            allowed_agents=["crypto", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_contract_info",
            description="查詢以太坊智能合約的基本資訊（創建者、代幣資訊等）。",
            input_schema={"contract_address": "str"},
            handler=get_contract_info_tool,
            allowed_agents=["crypto", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_eth_price_etherscan",
            description="從 Etherscan 獲取 ETH 即時價格。",
            input_schema={},
            handler=get_eth_price_etherscan_tool,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )

    # ── Register Commodity Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_commodity_price",
            description="查詢大宗商品即時價格（黃金、白銀、石油、天然氣、銅等）。",
            input_schema={"commodity": "str (gold, silver, oil, natural_gas, copper)"},
            handler=get_commodity_price_tool,
            allowed_agents=["commodity", "crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_commodity_futures_price",
            description="查詢商品期貨價格（WTI原油、布蘭特原油、黃金期貨、白銀期貨等）。",
            input_schema={
                "futures_type": "str (crude_oil, brent_oil, gold, silver, natural_gas)"
            },
            handler=get_commodity_futures_tool,
            allowed_agents=["commodity", "crypto", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_all_commodities_prices",
            description="獲取所有主要大宗商品價格一覽表。",
            input_schema={},
            handler=get_all_commodities_prices_tool,
            allowed_agents=["commodity", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_gold_silver_ratio",
            description="獲取金銀比（Gold-Silver Ratio），重要的市場情緒指標。",
            input_schema={},
            handler=get_gold_silver_ratio_tool,
            allowed_agents=["commodity", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_oil_price_analysis",
            description="獲取原油價格綜合分析（WTI vs 布蘭特原油比較）。",
            input_schema={},
            handler=get_oil_analysis_tool,
            allowed_agents=["commodity", "manager"],
        )
    )

    # ── Register Forex Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_forex_rate",
            description="查詢外匯即時匯率（USD/TWD、USD/JPY、EUR/USD等主要貨幣對）。",
            input_schema={"pair": "str (如 USD/TWD、EUR/USD)"},
            handler=get_forex_rate_tool,
            allowed_agents=["forex", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_all_forex_rates",
            description="獲取所有主要貨幣對的即時匯率一覽表。",
            input_schema={},
            handler=get_all_forex_rates_tool,
            allowed_agents=["forex", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_usd_twd_rate",
            description="查詢美元/台幣即時匯率（專用快捷工具）。",
            input_schema={},
            handler=get_usd_twd_rate_tool,
            allowed_agents=["forex", "chat", "tw_stock", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_central_bank_rates",
            description="獲取主要央行利率（Fed、ECB、BOJ、台灣央行）。",
            input_schema={},
            handler=get_central_bank_rates_tool,
            allowed_agents=["forex", "manager"],
        )
    )

    # ── Register Economic Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_market_indices",
            description="獲取美股主要市場指數（S&P 500、道瓊、那斯達克、VIX恐慌指數）。",
            input_schema={},
            handler=get_market_indices_tool,
            allowed_agents=["economic", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_vix_index",
            description="獲取 VIX 恐慌指數詳細資訊和市場情緒判讀。",
            input_schema={},
            handler=get_vix_index_tool,
            allowed_agents=["economic", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_sp500_performance",
            description="獲取 S&P 500 指數詳細表現和各期間報酬。",
            input_schema={},
            handler=get_sp500_performance_tool,
            allowed_agents=["economic", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_sector_performance",
            description="獲取美股 11 大板塊表現（科技、金融、能源等）。",
            input_schema={},
            handler=get_sector_performance_tool,
            allowed_agents=["economic", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_economic_calendar",
            description="獲取近期重要經濟事件行事曆（利率決議、CPI、非農等）。",
            input_schema={},
            handler=get_economic_calendar_tool,
            allowed_agents=["economic", "manager"],
        )
    )

    # ── Register Pi Network Tools ──
    tool_registry.register(
        ToolMetadata(
            name="get_pi_price",
            description="獲取 Pi Network (PI) 幣的即時價格",
            input_schema={},
            handler=get_pi_price,
            allowed_agents=["crypto", "chat", "manager"],
            role="market_lookup",
            priority=120,
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_pi_network_info",
            description="獲取 Pi Network 的專案資訊和市場數據",
            input_schema={},
            handler=get_pi_network_info,
            allowed_agents=["crypto", "chat", "manager"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_pi_ecosystem",
            description="獲取 Pi Network 生態系統資訊",
            input_schema={},
            handler=get_pi_ecosystem,
            allowed_agents=["crypto", "chat"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="get_pi_tools_guide",
            description="顯示 Pi Network 工具使用指南",
            input_schema={},
            handler=get_pi_tools_guide,
            allowed_agents=["chat"],
        )
    )

    # ── Register TW Stock Tools ──
    tool_registry.register(
        ToolMetadata(
            name="tw_stock_price",
            description="獲取台股即時價格和近期 OHLCV",
            input_schema={"ticker": "str"},
            handler=tw_price,
            allowed_agents=["tw_stock", "chat"],
            role="market_lookup",
            priority=100,
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_technical_analysis",
            description="計算台股技術指標 RSI/MACD/KD/MA",
            input_schema={"ticker": "str"},
            handler=tw_technical,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_fundamentals",
            description="獲取台股基本面資料（P/E, EPS, ROE）",
            input_schema={"ticker": "str"},
            handler=tw_fundamentals_tool,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_institutional",
            description="獲取台股三大法人籌碼資料",
            input_schema={"ticker": "str"},
            handler=tw_institutional_tool,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_news",
            description="獲取台股相關新聞（Google News RSS）",
            input_schema={"ticker": "str", "company_name": "str"},
            handler=tw_news_tool,
            allowed_agents=["tw_stock"],
        )
    )
    # ── Register TWSE OpenAPI Tools ──
    tool_registry.register(
        ToolMetadata(
            name="tw_major_news",
            description="獲取台股上市公司今日重大訊息（TWSE 官方數據）",
            input_schema={"limit": "int (optional, default 10)"},
            handler=tw_major_news_tool,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_pe_ratio",
            description="獲取台股個股本益比(P/E)、殖利率(Dividend Yield)、股價淨值比(P/B)",
            input_schema={"code": "str (股票代號)"},
            handler=tw_pe_ratio_tool,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_monthly_revenue",
            description="獲取台股月營收資料，含月增率與年增率",
            input_schema={"code": "str (股票代號，空白為全市場)"},
            handler=tw_monthly_revenue_tool,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_dividend",
            description="獲取台股股利分派資訊（現金股利、配股、除息日）",
            input_schema={"code": "str (股票代號，空白為全市場)"},
            handler=tw_dividend_tool,
            allowed_agents=["tw_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="tw_foreign_top20",
            description="獲取外資及陸資持股台股前20名，含持股比率與可投資上限",
            input_schema={},
            handler=tw_foreign_top20_tool,
            allowed_agents=["tw_stock"],
        )
    )

    # ── Register US Stock Tools ──
    tool_registry.register(
        ToolMetadata(
            name="us_stock_price",
            description="獲取美股即時價格數據（15分鐘延遲，Yahoo Finance）",
            input_schema={"symbol": "str"},
            handler=us_stock_price,
            allowed_agents=["us_stock", "chat"],
            role="market_lookup",
            priority=100,
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="us_technical_analysis",
            description="計算美股技術指標：RSI、MACD、布林帶、均線",
            input_schema={"symbol": "str"},
            handler=us_technical_analysis,
            allowed_agents=["us_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="us_fundamentals",
            description="獲取美股基本面：P/E、EPS、ROE、市值、股息率",
            input_schema={"symbol": "str"},
            handler=us_fundamentals,
            allowed_agents=["us_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="us_earnings",
            description="獲取美股財報數據和財報日曆",
            input_schema={"symbol": "str"},
            handler=us_earnings,
            allowed_agents=["us_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="us_news",
            description="獲取美股相關最新新聞",
            input_schema={"symbol": "str", "limit": "int (optional, default 5)"},
            handler=us_news,
            allowed_agents=["us_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="us_institutional_holders",
            description="獲取美股機構持倉數據",
            input_schema={"symbol": "str"},
            handler=us_institutional_holders,
            allowed_agents=["us_stock"],
        )
    )
    tool_registry.register(
        ToolMetadata(
            name="us_insider_transactions",
            description="獲取美股內部人交易記錄",
            input_schema={"symbol": "str"},
            handler=us_insider_transactions,
            allowed_agents=["us_stock"],
        )
    )

    # ── Register ToolResultCompactor retrieval tool ──
    from langchain_core.tools import tool as lc_tool

    from core.agents.tool_compactor import retrieve_tool_result as _retrieve_fn

    _owner_id = user_id  # capture per-user scope in closure

    @lc_tool
    def tool_result_retrieve(uuid: str) -> str:
        """Retrieve the full content of a previously compacted tool result by its UUID key."""
        return _retrieve_fn(uuid, requester_id=_owner_id)

    tool_registry.register(
        ToolMetadata(
            name="tool_result_retrieve",
            description="Retrieve the full content of a previously compacted tool result by its UUID key.",
            input_schema={"uuid": "str"},
            handler=tool_result_retrieve,
            allowed_agents=[],  # [] = available to all agents
            required_tier="free",
        )
    )

    # ── Create Agents ──

    # Legacy agents (hidden from LLM classify; kept for backward compatibility via direct name lookup)
    # tech = TechAgent(lang_llm, tool_registry)
    # agent_registry.register(tech, AgentMetadata(
    #     name="technical",
    #     display_name="Tech Agent (Legacy)",
    #     description="[Legacy] 加密貨幣技術分析。新查詢請使用 crypto agent。",
    #     capabilities=["RSI", "MACD", "MA", "technical analysis"],
    #     allowed_tools=["technical_analysis", "price_data", "get_crypto_price"],
    #     priority=1,
    #     hidden=True,
    # ))

    # news = NewsAgent(lang_llm, tool_registry)
    # agent_registry.register(news, AgentMetadata(
    #     name="news",
    #     display_name="News Agent (Legacy)",
    #     description="[Legacy] 加密貨幣新聞。新查詢請使用 crypto agent。",
    #     capabilities=["news", "新聞"],
    #     allowed_tools=["google_news", "aggregate_news", "web_search"],
    #     priority=1,
    #     hidden=True,
    # ))

    # New unified agents
    crypto = CryptoAgent(lang_llm, tool_registry, user_tier=user_tier, user_id=user_id)
    agent_registry.register(
        crypto,
        AgentMetadata(
            name="crypto",
            display_name="Crypto Agent",
            description="加密貨幣專業分析師 — 提供即時價格、時間、技術指標、合約資金費率、質押收益率(APY)、解鎖日程(Unlocks)、代幣發行流通量(Supply)、恐慌貪婪指數、全網熱門幣種、TVL鎖倉量、最強板塊、鯨魚交易與最新新聞。不直接提供交易決策。",
            capabilities=[
                "RSI",
                "MACD",
                "MA",
                "technical analysis",
                "crypto news",
                "加密貨幣",
                "技術指標",
                "資金費率",
                "恐慌貪婪指數",
                "熱門幣種",
                "多空情緒",
                "TVL",
                "板塊",
                "時間",
                "解鎖",
                "unlock",
                "流通量",
                "發行量",
                "supply",
                "質押",
                "staking",
                "收益率",
                "APY",
                "鯨魚",
                "whale",
            ],
            priority=10,
        ),
    )

    tw = TWStockAgent(lang_llm, tool_registry, user_tier=user_tier, user_id=user_id)
    agent_registry.register(
        tw,
        AgentMetadata(
            name="tw_stock",
            display_name="TW Stock Agent",
            description="台灣股市全方位分析 — 即時價格、時間、技術指標（RSI/MACD/KD/均線）、基本面（P/E/EPS）、三大法人籌碼、台股新聞。適用於台股查詢，接受股票代號或公司名稱。",
            capabilities=[
                "台股",
                "台灣股市",
                "上市",
                "上櫃",
                "股票代號",
                "RSI",
                "MACD",
                "KD",
                "均線",
                "本益比",
                "EPS",
                "外資",
                "投信",
                "法人",
                "籌碼",
                "股價",
                "台股股價",
                "即時股價",
                "時間",
            ],
            priority=10,
        ),
    )

    us = USStockAgent(lang_llm, tool_registry, user_tier=user_tier, user_id=user_id)
    agent_registry.register(
        us,
        AgentMetadata(
            name="us_stock",
            display_name="US Stock Agent",
            description="美股全方位分析 — 即時價格（15分鐘延遲）、技術指標（RSI/MACD/MA/布林帶）、"
            "基本面（P/E、EPS、ROE、市值）、財報數據與日曆、機構持倉、"
            "內部人交易、最新新聞。適用於 NYSE/NASDAQ 股票查詢，接受股票代號或公司名稱。",
            capabilities=[
                "美股",
                "US stock",
                "NYSE",
                "NASDAQ",
                "大型股",
                "成長股",
                "價值股",
                "科技股",
                "金融股",
                "醫療股",
                "標普500",
                "道瓊",
                "那斯達克",
                "S&P500",
            ],
            priority=8,
        ),
    )

    # ── Commodity Agent ──
    commodity = CommodityAgent(
        lang_llm, tool_registry, user_tier=user_tier, user_id=user_id
    )
    agent_registry.register(
        commodity,
        AgentMetadata(
            name="commodity",
            display_name="Commodity Agent",
            description="大宗商品專業分析師 — 提供黃金、白銀、原油、天然氣、銅等商品的即時價格、期貨價格、金銀比分析。適合投資者了解商品市場動態、避險情緒。",
            capabilities=[
                "黃金",
                "白銀",
                "原油",
                "石油",
                "天然氣",
                "銅",
                "commodity",
                "gold",
                "silver",
                "oil",
                "natural_gas",
                "copper",
                "金銀比",
                "期貨",
                "ETF",
                "WTI",
                "布蘭特",
            ],
            priority=9,
        ),
    )

    # ── Forex Agent ──
    forex = ForexAgent(lang_llm, tool_registry, user_tier=user_tier, user_id=user_id)
    agent_registry.register(
        forex,
        AgentMetadata(
            name="forex",
            display_name="Forex Agent",
            description="外匯專業分析師 — 提供主要貨幣對匯率（USD/TWD、EUR/USD、USD/JPY等）、央行利率資訊。適合投資者了解匯率走勢和外匯市場動態。",
            capabilities=[
                "外匯",
                "匯率",
                "forex",
                "貨幣",
                "USD/TWD",
                "EUR/USD",
                "USD/JPY",
                "美元",
                "台幣",
                "日圓",
                "歐元",
                "央行利率",
                "Fed",
                "ECB",
            ],
            priority=8,
        ),
    )

    # ── Economic Agent ──
    economic = EconomicAgent(
        lang_llm, tool_registry, user_tier=user_tier, user_id=user_id
    )
    agent_registry.register(
        economic,
        AgentMetadata(
            name="economic",
            display_name="Economic Agent",
            description="經濟數據專業分析師 — 提供市場指數（S&P 500、道瓊、那斯達克）、VIX恐慌指數、板塊表現、經濟事件行事曆。適合投資者了解宏觀經濟和市場情緒。",
            capabilities=[
                "經濟",
                "指數",
                "VIX",
                "恐慌指數",
                "S&P 500",
                "道瓊",
                "那斯達克",
                "板塊",
                "市場情緒",
                "經濟數據",
                "GDP",
                "CPI",
                "非農",
            ],
            priority=7,
        ),
    )

    chat = ChatAgent(lang_llm, tool_registry, user_tier=user_tier, user_id=user_id)
    agent_registry.register(
        chat,
        AgentMetadata(
            name="chat",
            display_name="Chat Agent",
            description="一般對話助手 — 處理閒聊、問候、自我介紹、平台使用說明、系統時間查詢、即時價格查詢、一般知識問答，以及主觀意見問題。不負責主動搜尋新聞或執行技術分析。",
            capabilities=[
                "conversation",
                "greeting",
                "help",
                "general knowledge",
                "price lookup",
                "即時價格",
                "平台說明",
                "閒聊",
                "時間",
                "現在幾點",
            ],
            priority=1,
        ),
    )

    manager = ManagerAgent(
        llm_client=lang_llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        web_mode=web_mode,
        user_tier=user_tier,
        user_id=user_id,
        session_id=session_id or "default",
    )
    _manager_cache[cache_key] = manager
    return manager


# ── Manager Instance Cache ─────────────────────────────────────────────────────
_manager_cache: Dict[str, ManagerAgent] = {}


def _manager_cache_key(user_id: str, session_id: str = "default") -> str:
    return f"{user_id}:{session_id or 'default'}"


def get_manager_instances(user_id: str) -> list[ManagerAgent]:
    """獲取指定用戶的所有 ManagerAgent 實例。"""
    prefix = f"{user_id}:"
    return [
        manager for key, manager in _manager_cache.items() if key.startswith(prefix)
    ]


def get_manager_instance(user_id: str, session_id: str = None) -> ManagerAgent:
    """獲取已緩存的 ManagerAgent 實例。未指定 session 時回傳最近建立的那個。"""
    if session_id is not None:
        return _manager_cache.get(_manager_cache_key(user_id, session_id))

    prefix = f"{user_id}:"
    for key in reversed(list(_manager_cache.keys())):
        if key.startswith(prefix):
            return _manager_cache[key]
    return None


def invalidate_manager_cache(user_id: str, session_id: str = None) -> None:
    """清除指定用戶的 Manager 緩存；可選擇只清單一 session。"""
    if session_id is not None:
        _manager_cache.pop(_manager_cache_key(user_id, session_id), None)
        return

    prefix = f"{user_id}:"
    for key in [key for key in _manager_cache.keys() if key.startswith(prefix)]:
        _manager_cache.pop(key, None)
