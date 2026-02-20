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
    tw_price, tw_technical, tw_fundamentals_tool, tw_institutional_tool, tw_news_tool,
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
        allowed_agents=["tw_stock"],
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

    # ── Wrap LLM with language awareness ──
    lang_llm = LanguageAwareLLM(llm_client, language)

    # ── Create Agents ──

    # Legacy agents (kept for backward compatibility; not routed by default)
    tech = TechAgent(lang_llm, tool_registry)
    agent_registry.register(tech, AgentMetadata(
        name="technical",
        display_name="Tech Agent (Legacy)",
        description="[Legacy] 加密貨幣技術分析。新查詢請使用 crypto agent。",
        capabilities=["RSI", "MACD", "MA", "technical analysis"],
        allowed_tools=["technical_analysis", "price_data", "get_crypto_price"],
        priority=1,
    ))

    news = NewsAgent(lang_llm, tool_registry)
    agent_registry.register(news, AgentMetadata(
        name="news",
        display_name="News Agent (Legacy)",
        description="[Legacy] 加密貨幣新聞。新查詢請使用 crypto agent。",
        capabilities=["news", "新聞"],
        allowed_tools=["google_news", "aggregate_news", "web_search"],
        priority=1,
    ))

    # New unified agents
    crypto = CryptoAgent(lang_llm, tool_registry)
    agent_registry.register(crypto, AgentMetadata(
        name="crypto",
        display_name="Crypto Agent",
        description="加密貨幣全方位分析 — 技術指標（RSI/MACD/均線）+ 即時新聞。適合 BTC/ETH/SOL 等加密貨幣的技術分析、新聞查詢、整體分析。",
        capabilities=["RSI", "MACD", "MA", "technical analysis", "crypto news", "加密貨幣", "技術指標", "K線", "加密貨幣新聞"],
        allowed_tools=["technical_analysis", "price_data", "get_crypto_price", "google_news", "aggregate_news", "web_search"],
        priority=10,
    ))

    tw = TWStockAgent(lang_llm, tool_registry)
    agent_registry.register(tw, AgentMetadata(
        name="tw_stock",
        display_name="TW Stock Agent",
        description="台灣股市全方位分析 — 即時價格、技術指標（RSI/MACD/KD/均線）、基本面（P/E/EPS）、三大法人籌碼、台股新聞。適合台積電、鴻海、聯發科等台股查詢，接受股票代號（2330）或公司名稱（台積電）。",
        capabilities=["台股", "台灣股市", "上市", "上櫃", "股票代號", "RSI", "MACD", "KD", "均線", "本益比", "EPS", "外資", "投信", "法人", "籌碼"],
        allowed_tools=["tw_stock_price", "tw_technical_analysis", "tw_fundamentals", "tw_institutional", "tw_news"],
        priority=10,
    ))

    us = USStockAgent(lang_llm, tool_registry)
    agent_registry.register(us, AgentMetadata(
        name="us_stock",
        display_name="US Stock Agent",
        description="美股分析（開發中）— 識別 NYSE/NASDAQ 股票代號，提供基本信息。適合 AAPL/TSLA/TSM 等美股查詢。",
        capabilities=["美股", "US stock", "NYSE", "NASDAQ", "AAPL", "TSLA", "TSM", "NVDA"],
        allowed_tools=[],
        priority=5,
    ))

    chat = ChatAgent(lang_llm, tool_registry)
    agent_registry.register(chat, AgentMetadata(
        name="chat",
        display_name="Chat Agent",
        description="一般對話助手 — 處理閒聊、問候、自我介紹、平台使用說明、即時價格查詢、一般知識問答，以及主觀意見問題。不負責主動搜尋新聞或執行技術分析。",
        capabilities=["conversation", "greeting", "help", "general knowledge", "price lookup", "即時價格", "平台說明", "閒聊"],
        allowed_tools=["get_crypto_price", "web_search"],
        priority=1,
    ))

    return ManagerAgent(
        llm_client=lang_llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        codebook=codebook,
        web_mode=web_mode,
    )
