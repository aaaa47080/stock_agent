"""Agent Orchestrator for coordinating multi-agent analysis"""
from typing import Dict, List, Optional
from .base import ProfessionalAgent
from .task import Task, TaskType


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

    CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX',
        'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'NEAR',
        'APT', 'ARB', 'OP', 'PI'
    }

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

    def parse_task(self, query: str) -> Task:
        """
        解析用戶查詢為 Task 對象

        Args:
            query: 用戶查詢字符串

        Returns:
            Task 對象，包含解析後的任務信息
        """
        symbols = self._extract_symbols(query)
        task_type = self._determine_task_type(query)

        analysis_depth = "normal"
        if "深度" in query or "詳細" in query:
            analysis_depth = "deep"
        elif "快速" in query or "簡單" in query:
            analysis_depth = "quick"

        needs_backtest = "回測" in query or "歷史" in query

        return Task(
            query=query,
            type=task_type,
            symbols=symbols,
            analysis_depth=analysis_depth,
            needs_backtest=needs_backtest
        )

    def _extract_symbols(self, query: str) -> List[str]:
        """
        從查詢中提取加密貨幣符號

        Args:
            query: 用戶查詢字符串

        Returns:
            找到的符號列表，如果沒有找到則返回 ['BTC']
        """
        query_upper = query.upper()
        found = [s for s in self.CRYPTO_SYMBOLS if s in query_upper]
        return found if found else ["BTC"]

    def _determine_task_type(self, query: str) -> TaskType:
        """
        判斷任務類型

        Args:
            query: 用戶查詢字符串

        Returns:
            TaskType 枚舉值
        """
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["現價", "多少錢", "價格", "多少"]):
            if len(query_lower) < 15:
                return TaskType.SIMPLE_PRICE

        if any(kw in query_lower for kw in ["深度", "辯論", "多空", "完整"]):
            return TaskType.DEEP_ANALYSIS

        return TaskType.ANALYSIS
