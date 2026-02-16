"""
Agent V3 Sub-Agents

各專業 Agent 的實現
"""
from typing import Dict, Tuple

from ..base import SubAgent
from ..models import Task
from ..tool_registry import ToolRegistry
from ..hitl import EnhancedHITLManager


def create_all_agents(
    llm_client,
    tool_registry: ToolRegistry,
    hitl: EnhancedHITLManager
) -> Dict[str, SubAgent]:
    """
    創建所有 Sub-Agents

    Args:
        llm_client: LLM 客戶端
        tool_registry: 工具註冊表
        hitl: HITL Manager

    Returns:
        Agent 名稱到 Agent 實例的映射
    """
    from .news_agent import NewsAgent
    from .tech_agent import TechAgent
    from .chat_agent import ChatAgent

    agents = {
        "news": NewsAgent(llm_client, tool_registry, hitl),
        "technical": TechAgent(llm_client, tool_registry, hitl),
        "chat": ChatAgent(llm_client, tool_registry, hitl),
    }

    return agents


__all__ = [
    "create_all_agents",
]
