"""Agent Orchestrator for coordinating multi-agent analysis"""
from typing import Dict, List, Optional, Any
from langchain_core.language_models import BaseChatModel

from .base import ProfessionalAgent
from .task import Task, TaskType
from .hitl import HITLManager, HITLState, ReviewPoint, create_hitl_manager_with_defaults
from .config import GraphConfig, create_default_config, FeatureToggle
from .llm_parser import LLMTaskParser
from .memory import ConversationMemory
from utils.llm_client import LLMClientFactory


class Orchestrator:
    """
    Agent 協調中心

    職責：
    - 任務解析（使用 LLM，不再是硬編碼規則）
    - Agent 調度
    - 資源分配
    - 衝突解決
    - 結果整合
    - 人機協作 (HITL)

    整合 LangGraph 的 interrupt 機制實現人機協作
    """

    def __init__(
        self,
        llm_client: BaseChatModel = None,
        config: GraphConfig = None,
        enable_hitl: bool = True
    ):
        """
        初始化 Orchestrator

        Args:
            llm_client: LangChain LLM client（必需，用於任務解析）
            config: GraphConfig 配置实例
            enable_hitl: 是否启用人机协作
        """
        # LLM Client - 用於任務解析
        self.llm_client = llm_client or LLMClientFactory.create_client("openai", "gpt-4o-mini")
        self.parser = LLMTaskParser(self.llm_client)

        self.config = config or create_default_config()
        self.agents: Dict[str, ProfessionalAgent] = {}

        # 对话记忆系统 - 已启用
        self.conversation_memory = ConversationMemory()
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

        使用 LLM 進行語義理解，不再是硬編碼規則匹配。

        Args:
            query: 用戶查詢字符串

        Returns:
            Task 對象，包含解析後的任務信息
        """
        # 使用 LLM Parser 解析
        return self.parser.to_task(query)

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

    # ========================================
    # 对话记忆方法
    # ========================================

    def analyze_with_memory(self, query: str, session_id: str) -> Task:
        """
        带记忆的分析

        利用对话记忆处理上下文引用，如「它呢」「刚才那个」等。

        Args:
            query: 用户查询
            session_id: 会话 ID

        Returns:
            Task 对象，可能包含从历史中推断的符号
        """
        ctx = self.conversation_memory.get_or_create(session_id)

        # 更新上下文
        self.conversation_memory.update_with_query(ctx, query)

        # 解析任务
        task = self.parse_task(query)

        # 如果没有符号但有历史符号，使用最近的
        if not task.symbols or task.symbols == ['BTC']:  # BTC 是默认值
            if ctx.symbols_mentioned:
                # 使用最近提到的符号
                task.symbols = [ctx.symbols_mentioned[-1]]

        # 记录分析到上下文
        ctx.add_analysis({
            "query": query,
            "symbols": task.symbols,
            "type": task.type.value,
            "time": ctx.last_activity.isoformat() if hasattr(ctx.last_activity, 'isoformat') else str(ctx.last_activity)
        })

        return task

    def get_context_symbols(self, session_id: str) -> List[str]:
        """
        获取会话中提到的所有符号

        Args:
            session_id: 会话 ID

        Returns:
            符号列表
        """
        ctx = self.conversation_memory.get_or_create(session_id)
        return ctx.symbols_mentioned

    def get_recent_analyses(self, session_id: str, limit: int = 5) -> List[Dict]:
        """
        获取最近的分析历史

        Args:
            session_id: 会话 ID
            limit: 返回数量限制

        Returns:
            分析历史列表
        """
        ctx = self.conversation_memory.get_or_create(session_id)
        return ctx.analysis_history[-limit:]
