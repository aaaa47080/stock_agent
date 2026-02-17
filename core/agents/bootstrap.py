"""
Agent V4 Bootstrap.

Assembles all components: tools → agents → manager.
Each agent gets only the @tool functions it should use.
"""
from .agent_registry import AgentRegistry, AgentMetadata
from .hitl import HITLManager
from .codebook import Codebook
from .prompt_registry import PromptRegistry
from .manager import ManagerAgent

# Import @tool functions
from .tools import (
    technical_analysis, price_data, get_crypto_price,
    google_news, aggregate_news,
    ALL_TOOLS,
)

# Import agent classes
from .agents import TechAgent, NewsAgent, ChatAgent
from .agents.full_analysis_agent import FullAnalysisAgent


def bootstrap(llm_client, web_mode: bool = False) -> ManagerAgent:
    PromptRegistry.load()
    agent_registry = AgentRegistry()
    hitl = HITLManager(max_questions_per_session=10)
    codebook = Codebook(storage_path="data/codebook_v4.json")

    # ── Create Agents with their specific tools ──

    tech = TechAgent(llm_client, [technical_analysis, price_data, get_crypto_price], hitl)
    agent_registry.register(tech, AgentMetadata(
        name="technical",
        display_name="Tech Agent",
        description="深度技術分析 Agent — 提供 RSI、MACD、均線等完整技術指標分析報告。適合「分析 ETH 技術面」「BTC 走勢分析」等需要詳細指標解讀的請求，不適合簡單的價格查詢",
        capabilities=["RSI", "MACD", "MA", "technical analysis", "trend", "support/resistance"],
        allowed_tools=["technical_analysis", "price_data", "get_crypto_price"],
        priority=10,
    ))

    news = NewsAgent(llm_client, [google_news, aggregate_news], hitl)
    agent_registry.register(news, AgentMetadata(
        name="news",
        display_name="News Agent",
        description="新聞搜集 Agent — 從多個來源獲取並總結加密貨幣新聞。適合「BTC 最新新聞」「PI 有什麼消息」等新聞相關請求",
        capabilities=["news", "sentiment", "events", "market dynamics"],
        allowed_tools=["google_news", "aggregate_news"],
        priority=10,
    ))

    chat = ChatAgent(llm_client, [get_crypto_price], hitl)
    agent_registry.register(chat, AgentMetadata(
        name="chat",
        display_name="Chat Agent",
        description="一般對話與簡單查詢 Agent — 處理問候、閒聊、一般知識問題、系統說明，以及簡單的即時價格查詢（如「PI 多少錢」「BTC 價格」）。所有其他 Agent 無法處理的請求都由此 Agent 處理",
        capabilities=["conversation", "greeting", "help", "general", "price lookup", "即時價格"],
        allowed_tools=["get_crypto_price"],
        priority=1,
    ))

    full = FullAnalysisAgent(llm_client, [], hitl)
    agent_registry.register(full, AgentMetadata(
        name="full_analysis",
        display_name="深度分析 Agent",
        description="完整市場分析 Agent — 整合技術、情緒、基本面、新聞四維分析，加上多空辯論與裁決，產出完整投資分析報告。適合「BTC 值得投資嗎」「幫我完整分析 ETH」「給我 SOL 深度分析」等複雜分析請求",
        capabilities=["full_analysis", "investment_analysis", "debate", "deep_analysis",
                       "深度分析", "完整分析", "值得投資", "多空分析"],
        allowed_tools=[],
        priority=20,  # highest priority for complex analysis
    ))

    return ManagerAgent(
        llm_client=llm_client,
        agent_registry=agent_registry,
        all_tools=ALL_TOOLS,
        hitl=hitl,
        codebook=codebook,
        web_mode=web_mode,
    )
