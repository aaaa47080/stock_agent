"""Professional Agent base classes and interfaces"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Viewpoint, DiscussionRound


class AgentState(Enum):
    """Agent 運行狀態"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DISCUSSING = "discussing"
    WAITING_FEEDBACK = "waiting_feedback"
    COMPLETED = "completed"


class ProfessionalAgent(ABC):
    """
    專業 Agent 抽象基類

    所有專業 Agent 都必須繼承此類，並實現以下自主能力：
    1. 工具選擇 - select_tools()
    2. 流程參與 - should_participate()
    """

    def __init__(
        self,
        expertise: str,
        system_prompt: str,
        personality: str = "balanced"
    ):
        """
        Initialize a Professional Agent.

        Args:
            expertise: 專業領域名稱 (e.g., "technical_analysis")
            system_prompt: 系統提示詞，定義 Agent 的行為
            personality: 分析風格 ("analytical", "aggressive", "conservative", "balanced")
        """
        self.expertise = expertise
        self.system_prompt = system_prompt
        self.personality = personality
        self.state = AgentState.IDLE
        self.available_tools: List[Any] = []
        self.current_viewpoint: Optional["Viewpoint"] = None
        self.discussion_history: List["DiscussionRound"] = []

    # === 自主能力 1: 工具選擇 ===
    @abstractmethod
    def select_tools(self, task: "Task") -> List[Any]:
        """
        自主決定需要哪些工具

        Args:
            task: 當前任務

        Returns:
            選中的工具列表
        """
        pass

    # === 自主能力 2: 流程參與 ===
    @abstractmethod
    def should_participate(self, task: "Task") -> tuple:
        """
        這個任務需要我參與嗎？

        Args:
            task: 當前任務

        Returns:
            (是否參與, 原因說明)
        """
        pass

    def _get_tool(self, tool_name: str) -> Optional[Any]:
        """根據名稱獲取工具"""
        for tool in self.available_tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                return tool
            if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                return tool
        return None
