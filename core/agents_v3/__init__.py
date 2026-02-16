"""
Agent V3 - 真正的多 Agent 協作系統

這個套件實現了一個基於 ReAct 模式的多 Agent 系統，
由 Manager Agent 統籌調度各專業 Sub-Agent 協作完成任務。

核心特性：
- 真正的 Agent 協作，而非 if-else 硬編碼
- ReAct 循環（Reasoning + Acting）
- 智能化 HITL（由 LLM 決定何時詢問使用者）
- 工具註冊制
- 完整的對話記憶

使用方式：
    from core.agents_v3 import create_agent_system

    manager = create_agent_system(llm_client)
    result = manager.process("分析 BTC 最新新聞")
"""

__version__ = "3.0.0"

# 資料模型
from .models import (
    TaskType,
    AgentState,
    HITLTriggerType,
    Task,
    SubTask,
    AgentResult,
    Action,
    ConversationContext,
    ToolInfo,
)

# 工具系統
from .tools import (
    BaseTool,
    ToolResult,
    FunctionTool,
    GoogleNewsTool,
    CryptoPanicTool,
    MultiSourceNewsTool,
    TechnicalAnalysisTool,
    PriceDataTool,
    WebSearchTool,
    LLMTool,
    create_default_tools,
)

from .tool_registry import (
    ToolRegistry,
    create_default_registry,
)

# HITL 系統
from .hitl import (
    HITLQuestion,
    HITLResponse,
    EnhancedHITLManager,
)

# 記憶系統
from .memory import (
    ConversationContext as MemoryContext,
    ConversationMemory,
)

# Agent 基類
from .base import (
    AgentThought,
    SubAgent,
)

# Manager Agent
from .manager import ManagerAgent

# Sub-Agents (延遲導入，避免循環依賴)
from .agents.news_agent import NewsAgent
from .agents.tech_agent import TechAgent
from .agents.chat_agent import ChatAgent


def create_agent_system(
    llm_client,
    enable_hitl: bool = True,
    max_questions: int = 5
) -> ManagerAgent:
    """
    創建完整的 Agent 系統

    Args:
        llm_client: LangChain LLM 客戶端
        enable_hitl: 是否啟用 HITL
        max_questions: 每會話最大詢問次數

    Returns:
        配置好的 ManagerAgent 實例
    """
    # 創建工具註冊表
    registry = create_default_registry(llm_client)

    # 創建 HITL Manager
    hitl = EnhancedHITLManager(
        llm_client=llm_client,
        max_questions_per_session=max_questions
    ) if enable_hitl else None

    # 創建 Sub-Agents（延遲導入避免循環依賴）
    from .agents import create_all_agents
    agents = create_all_agents(llm_client, registry, hitl)

    # 創建 Manager
    manager = ManagerAgent(
        llm_client=llm_client,
        agents=agents,
        tool_registry=registry,
        hitl=hitl
    )

    return manager


__all__ = [
    # 版本
    "__version__",

    # 工廠函數
    "create_agent_system",

    # 資料模型
    "TaskType",
    "AgentState",
    "HITLTriggerType",
    "Task",
    "SubTask",
    "AgentResult",
    "Action",
    "ConversationContext",
    "ToolInfo",

    # 工具
    "BaseTool",
    "ToolResult",
    "FunctionTool",
    "GoogleNewsTool",
    "CryptoPanicTool",
    "MultiSourceNewsTool",
    "TechnicalAnalysisTool",
    "PriceDataTool",
    "WebSearchTool",
    "LLMTool",
    "create_default_tools",
    "ToolRegistry",
    "create_default_registry",

    # HITL
    "HITLQuestion",
    "HITLResponse",
    "EnhancedHITLManager",

    # 記憶
    "ConversationMemory",

    # Agents
    "AgentThought",
    "SubAgent",
    "ManagerAgent",
]
