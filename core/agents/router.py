"""
Agent V4 — Router

路由決策由 Manager 透過 LLM 做出，不使用關鍵詞硬編碼。
此類別僅提供 agent 獲取功能。
"""
from .agent_registry import AgentRegistry
from .models import CollaborationRequest


class AgentRouter:
    """路由器 - 僅負責獲取 agent 實例，路由決策由 Manager LLM 做出"""

    def __init__(self, registry: AgentRegistry):
        self._registry = registry

    def get_agent(self, agent_name: str):
        """根據 agent 名稱獲取 agent 實例

        Args:
            agent_name: agent 名稱（如 "crypto", "forex" 等）

        Returns:
            對應的 agent 實例，如果不存在則返回 chat agent
        """
        agent = self._registry.get(agent_name)
        if not agent:
            agent = self._registry.get("chat")
        return agent

    def route_collaboration(self, request: CollaborationRequest):
        """處理協作請求"""
        agent = self._registry.get(request.needed_agent)
        if agent is not None:
            return agent
        matches = self._registry.find_by_capability(request.needed_agent)
        if matches:
            best = max(matches, key=lambda m: m.priority)
            return self._registry.get(best.name)
        return None
