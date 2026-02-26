"""
Agent V4 Bootstrap.

Assembles all components: tools → agents → manager.
Instantiates ToolRegistry and registers tools with permission checks.
"""
from langchain_core.messages import SystemMessage

from .agent_registry import AgentRegistry, AgentMetadata
from .tool_registry import ToolRegistry, ToolMetadata
from .hierarchical_memory import CodebookFactory, BaseHierarchicalCodebook
from .prompt_registry import PromptRegistry
from .manager import ManagerAgent

# Import @tool functions — crypto
from .tools import (
    technical_analysis, price_data, get_crypto_price,
    google_news, aggregate_news, web_search,
    get_fear_and_greed_index, get_trending_tokens, get_futures_data,
    get_current_time_taipei, get_defillama_tvl, get_crypto_categories_and_gainers,
    get_token_unlocks, get_token_supply,
    tw_price, tw_technical, tw_fundamentals_tool, tw_institutional_tool, tw_news_tool,
)

# Import @tool functions — US stock
from core.tools.us_stock_tools import (
    us_stock_price, us_technical_analysis, us_fundamentals,
    us_earnings, us_news, us_institutional_holders, us_insider_transactions,
)

# Import agent classes
from .agents import TechAgent, NewsAgent, ChatAgent, TWStockAgent, USStockAgent, CryptoAgent


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
        """Delegate bind_tools but preserve language injection in the returned wrapper."""
        bound = self._llm.bind_tools(tools, **kwargs)
        wrapper = LanguageAwareLLM.__new__(LanguageAwareLLM)
        wrapper._llm = bound
        wrapper._lang_msg = self._lang_msg
        return wrapper

    def __getattr__(self, name):
        return getattr(self._llm, name)


def bootstrap(llm_client, web_mode: bool = False, language: str = "zh-TW") -> ManagerAgent:
    PromptRegistry.load()
    agent_registry = AgentRegistry()
    tool_registry  = ToolRegistry()
    codebook       = CodebookFactory()

    # ── Register Crypto Tools ──
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
        name="google_news",
        description="從 Google News RSS 獲取加密貨幣新聞",
        input_schema={"symbol": "str", "limit": "int"},
        handler=google_news,
        allowed_agents=["news", "crypto", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="aggregate_news",
        description="多來源加密貨幣新聞聚合",
        input_schema={"symbol": "str", "limit": "int"},
        handler=aggregate_news,
        allowed_agents=["news", "crypto", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_crypto_price",
        description="獲取加密貨幣即時價格",
        input_schema={"symbol": "str"},
        handler=get_crypto_price,
        allowed_agents=["technical", "crypto", "chat", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_fear_and_greed_index",
        description="獲取全球加密貨幣市場恐慌與貪婪指數 (Fear & Greed Index)",
        input_schema={},
        handler=get_fear_and_greed_index,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_trending_tokens",
        description="獲取目前全網最熱門搜尋的加密貨幣 (Trending Tokens)",
        input_schema={},
        handler=get_trending_tokens,
        allowed_agents=["crypto", "chat", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_futures_data",
        description="獲取加密貨幣永續合約的資金費率與多空情緒 (Funding Rates)",
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
        description="從 DefiLlama 獲取特定協議或公鏈的 TVL (總鎖倉價值)",
        input_schema={"protocol_name": "str"},
        handler=get_defillama_tvl,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_crypto_categories_and_gainers",
        description="獲取 CoinGecko 上表現最佳的加密貨幣板塊與熱點 (Sectors)",
        input_schema={},
        handler=get_crypto_categories_and_gainers,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_token_unlocks",
        description="獲取代幣未來的解鎖日程與數量 (Token Unlocks)。當需要評估代幣拋壓時使用。",
        input_schema={"symbol": "str"},
        handler=get_token_unlocks,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_token_supply",
        description="獲取代幣的總發行量、最大供應量與目前市場流通量 (Tokenomics)。",
        input_schema={"symbol": "str"},
        handler=get_token_supply,
        allowed_agents=["crypto", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="web_search",
        description="通用網絡搜索 (DuckDuckGo)",
        input_schema={"query": "str", "purpose": "str"},
        handler=web_search,
        allowed_agents=["chat", "news", "crypto", "manager"],
    ))

    # ── Register TW Stock Tools ──
    tool_registry.register(ToolMetadata(
        name="tw_stock_price",
        description="獲取台股即時價格和近期 OHLCV",
        input_schema={"ticker": "str"},
        handler=tw_price,
        allowed_agents=["tw_stock", "chat"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_technical_analysis",
        description="計算台股技術指標 RSI/MACD/KD/MA",
        input_schema={"ticker": "str"},
        handler=tw_technical,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_fundamentals",
        description="獲取台股基本面資料（P/E, EPS, ROE）",
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
        description="獲取台股相關新聞（Google News RSS）",
        input_schema={"ticker": "str", "company_name": "str"},
        handler=tw_news_tool,
        allowed_agents=["tw_stock"],
    ))

    # ── Register US Stock Tools ──
    tool_registry.register(ToolMetadata(
        name="us_stock_price",
        description="獲取美股即時價格數據（15分鐘延遲，Yahoo Finance）",
        input_schema={"symbol": "str"},
        handler=us_stock_price,
        allowed_agents=["us_stock", "chat"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_technical_analysis",
        description="計算美股技術指標：RSI、MACD、布林帶、均線",
        input_schema={"symbol": "str"},
        handler=us_technical_analysis,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_fundamentals",
        description="獲取美股基本面：P/E、EPS、ROE、市值、股息率",
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
        input_schema={"symbol": "str", "limit": "int (optional, default 5)"},
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

    # ── Wrap LLM with language awareness ──
    lang_llm = LanguageAwareLLM(llm_client, language)

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
    crypto = CryptoAgent(lang_llm, tool_registry)
    agent_registry.register(crypto, AgentMetadata(
        name="crypto",
        display_name="Crypto Agent",
        description="加密貨幣專業分析師 — 提供即時價格、時間、技術指標、合約資金費率、解鎖日程(Unlocks)、代幣發行流通量(Supply)、恐慌貪婪指數、全網熱門幣種、TVL鎖倉量、最強板塊與最新新聞。不直接提供交易決策。",
        capabilities=["RSI", "MACD", "MA", "technical analysis", "crypto news", "加密貨幣", "技術指標", "資金費率", "恐慌貪婪指數", "熱門幣種", "多空情緒", "TVL", "板塊", "時間", "解鎖", "unlock", "流通量", "發行量", "supply"],
        allowed_tools=[
            "get_current_time_taipei", "technical_analysis", "price_data", "get_crypto_price", 
            "google_news", "aggregate_news", "web_search",
            "get_fear_and_greed_index", "get_trending_tokens", "get_futures_data",
            "get_defillama_tvl", "get_crypto_categories_and_gainers", "get_token_unlocks", "get_token_supply"
        ],
        priority=10,
    ))

    tw = TWStockAgent(lang_llm, tool_registry)
    agent_registry.register(tw, AgentMetadata(
        name="tw_stock",
        display_name="TW Stock Agent",
        description="台灣股市全方位分析 — 即時價格、時間、技術指標（RSI/MACD/KD/均線）、基本面（P/E/EPS）、三大法人籌碼、台股新聞。適合台積電、鴻海、聯發科等台股查詢，接受股票代號（2330）或公司名稱（台積電）。",
        capabilities=["台股", "台灣股市", "上市", "上櫃", "股票代號", "RSI", "MACD", "KD", "均線", "本益比", "EPS", "外資", "投信", "法人", "籌碼", "股價", "台股股價", "即時股價", "時間"],
        allowed_tools=["get_current_time_taipei", "tw_stock_price", "tw_technical_analysis", "tw_fundamentals", "tw_institutional", "tw_news", "web_search"],
        priority=10,
    ))

    # us = USStockAgent(lang_llm, tool_registry)
    # agent_registry.register(us, AgentMetadata(
    #     name="us_stock",
    #     display_name="US Stock Agent",
    #     description="美股分析（開發中）— 識別 NYSE/NASDAQ 股票代號，提供基本信息。適合 AAPL/TSLA/TSM 等美股查詢。",
    #     capabilities=["美股", "US stock", "NYSE", "NASDAQ", "AAPL", "TSLA", "TSM", "NVDA"],
    #     allowed_tools=[],
    #     priority=5,
    # ))

    chat = ChatAgent(lang_llm, tool_registry)
    agent_registry.register(chat, AgentMetadata(
        name="chat",
        display_name="Chat Agent",
        description="一般對話助手 — 處理閒聊、問候、自我介紹、平台使用說明、系統時間查詢、即時價格查詢、一般知識問答，以及主觀意見問題。不負責主動搜尋新聞或執行技術分析。",
        capabilities=["conversation", "greeting", "help", "general knowledge", "price lookup", "即時價格", "平台說明", "閒聊", "時間", "現在幾點"],
        allowed_tools=["get_current_time_taipei", "get_crypto_price", "web_search"],
        priority=1,
    ))

    return ManagerAgent(
        llm_client=lang_llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        codebook=codebook,
        web_mode=web_mode,
    )
