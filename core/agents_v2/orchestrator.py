"""Agent Orchestrator for coordinating multi-agent analysis"""
from typing import Dict, List, Optional, Any
from .base import ProfessionalAgent
from .task import Task, TaskType
from .hitl import HITLManager, HITLState, ReviewPoint, create_hitl_manager_with_defaults
from .config import GraphConfig, create_default_config, FeatureToggle


class Orchestrator:
    """
    Agent 協調中心

    職責：
    - 任務解析
    - Agent 調度
    - 資源分配
    - 衝突解決
    - 結果整合
    - 人機協作 (HITL)

    整合 LangGraph 的 interrupt 機制實現人機協作
    """

    CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX',
        'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'NEAR',
        'APT', 'ARB', 'OP', 'PI'
    }

    def __init__(self, config: GraphConfig = None, enable_hitl: bool = True):
        """
        初始化 Orchestrator

        Args:
            config: GraphConfig 配置实例
            enable_hitl: 是否启用人机协作
        """
        self.config = config or create_default_config()
        self.agents: Dict[str, ProfessionalAgent] = {}
        self.conversation_memory = None  # Phase 3
        self.codebook = None             # Phase 9
        self.feedback_collector = None   # Phase 8

        # Phase 6-7: HITL Manager
        self.hitl_manager: Optional[HITLManager] = None
        self._hitl_enabled = enable_hitl
        if enable_hitl:
            self._init_hitl()

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

    def gather_participants(self, task: Task) -> List[ProfessionalAgent]:
        """
        讓 Agents 自主決定是否參與

        Args:
            task: 當前任務

        Returns:
            願意參與的 Agent 列表
        """
        participants = []
        for agent in self.agents.values():
            should_join, reason = agent.should_participate(task)
            if should_join:
                participants.append(agent)
        return participants

    # ========================================
    # Phase 6-7: Human-in-the-Loop 方法
    # ========================================

    def _init_hitl(self) -> None:
        """初始化 HITL Manager"""
        self.hitl_manager = create_hitl_manager_with_defaults()

    def is_hitl_enabled(self) -> bool:
        """检查 HITL 是否启用"""
        return self._hitl_enabled and self.hitl_manager is not None

    def enable_hitl(self) -> None:
        """启用 HITL"""
        if not self.hitl_manager:
            self._init_hitl()
        self._hitl_enabled = True
        self.config.set_feature("hitl", FeatureToggle.ON)

    def disable_hitl(self) -> None:
        """禁用 HITL（自动批准所有决策）"""
        self._hitl_enabled = False
        self.config.set_feature("hitl", FeatureToggle.OFF)

    def create_review_point(
        self,
        checkpoint_name: str,
        content: str,
        context: dict = None,
        custom_options: List[Dict] = None
    ) -> Optional[ReviewPoint]:
        """
        创建审核点，等待用户确认

        Args:
            checkpoint_name: 检查点名称（如 "trade_decision", "high_risk_trade"）
            content: 审核内容（Markdown 格式）
            context: 相关上下文数据
            custom_options: 自定义选项

        Returns:
            ReviewPoint 或 None（如果 HITL 未启用）
        """
        if not self.is_hitl_enabled():
            return None
        return self.hitl_manager.create_review_point(
            checkpoint_name, content, context, custom_options
        )

    def get_pending_reviews(self) -> List[ReviewPoint]:
        """获取所有待处理的审核点"""
        if not self.is_hitl_enabled():
            return []
        return self.hitl_manager.get_pending_reviews()

    def process_user_response(
        self,
        review_id: str,
        response: str,
        feedback: str = None,
        modifications: dict = None
    ) -> Optional[HITLState]:
        """
        处理用户响应

        Args:
            review_id: 审核点 ID
            response: 用户选择（approve/reject/discuss/modify）
            feedback: 用户反馈
            modifications: 用户修改的参数

        Returns:
            新状态或 None
        """
        if not self.is_hitl_enabled():
            return None
        return self.hitl_manager.process_response(
            review_id, response, feedback, modifications
        )

    def should_interrupt(self, checkpoint_name: str, context: dict) -> bool:
        """
        判断是否应该中断工作流等待用户确认

        这是与 LangGraph 整合的关键方法：
        - 在 workflow 编译时使用 interrupt_before
        - 在运行时调用此方法判断是否真的需要中断

        Args:
            checkpoint_name: 检查点名称
            context: 当前上下文

        Returns:
            是否需要中断
        """
        if not self.is_hitl_enabled():
            return False
        return self.hitl_manager.should_interrupt(checkpoint_name, context)

    def get_langgraph_interrupt_points(self) -> List[str]:
        """
        获取 LangGraph 的 interrupt_before 列表

        用于编译 LangGraph workflow：
        ```python
        app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=orchestrator.get_langgraph_interrupt_points()
        )
        ```

        Returns:
            需要中断的节点名称列表
        """
        if not self.is_hitl_enabled():
            return []
        return self.hitl_manager.get_interrupt_points()

    def get_review_history(self, limit: int = 50) -> List[ReviewPoint]:
        """获取审核历史"""
        if not self.is_hitl_enabled():
            return []
        return self.hitl_manager.get_review_history(limit)
