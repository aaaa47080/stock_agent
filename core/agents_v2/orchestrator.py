"""Agent Orchestrator for coordinating multi-agent analysis"""
from typing import Dict, List, Optional
from .base import ProfessionalAgent


class Orchestrator:
    """
    Agent 協調中心

    職責：
    - 任務解析
    - Agent 調度
    - 資源分配
    - 衝突解決
    - 結果整合

    注意：Orchestrator 協調但不硬性控制流程
    """

    def __init__(self):
        self.agents: Dict[str, ProfessionalAgent] = {}
        self.conversation_memory = None  # 將在 Phase 3 實現
        self.hitl_manager = None         # 將在 Phase 7 實現
        self.codebook = None             # 將在 Phase 9 實現
        self.feedback_collector = None   # 將在 Phase 8 實現

    def register_agent(self, agent: ProfessionalAgent) -> None:
        """
        註冊 Agent 到協調中心

        Args:
            agent: 要註冊的 Agent 實例
        """
        self.agents[agent.expertise] = agent

    def unregister_agent(self, expertise: str) -> bool:
        """
        移除已註冊的 Agent

        Args:
            expertise: Agent 的專業領域

        Returns:
            是否成功移除
        """
        if expertise in self.agents:
            del self.agents[expertise]
            return True
        return False

    def get_agent(self, expertise: str) -> Optional[ProfessionalAgent]:
        """
        根據專業領域獲取 Agent

        Args:
            expertise: 專業領域名稱

        Returns:
            Agent 實例或 None
        """
        return self.agents.get(expertise)
