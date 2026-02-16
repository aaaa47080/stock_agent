"""
Agent Adapters - 将现有 Agents 适配到 V2 架构

这个模块提供适配器，将 core/agents.py 中的现有 Agents
包装成 core/agents_v2/base.py 的 ProfessionalAgent 接口。

这样可以在不修改现有代码的情况下，让旧 Agents 使用新的：
- HITL（人机协作）
- Feedback（反馈收集）
- Codebook（经验学习）
- Config（动态配置）
"""
from typing import List, Dict, Optional, Any, Tuple
from .base import ProfessionalAgent, AgentState
from .task import Task, TaskType
from .models import Viewpoint


class LegacyAgentAdapter(ProfessionalAgent):
    """
    旧版 Agent 适配器

    将现有 core/agents.py 中的 Agents 包装成 ProfessionalAgent 接口

    使用示例：
    ```python
    from core.agents import TechnicalAnalyst
    from core.agents_v2 import LegacyAgentAdapter

    # 包装旧版 Agent
    legacy_agent = TechnicalAnalyst(client)
    adapted = LegacyAgentAdapter(
        legacy_agent=legacy_agent,
        expertise="technical_analysis",
        system_prompt="技术分析师",
        personality="analytical"
    )

    # 现在可以用 v2 的方法
    should_join, reason = adapted.should_participate(task)
    tools = adapted.select_tools(task)
    ```
    """

    def __init__(
        self,
        legacy_agent: Any,
        expertise: str,
        system_prompt: str,
        personality: str = "balanced",
        task_keywords: List[str] = None
    ):
        """
        初始化适配器

        Args:
            legacy_agent: 旧版 Agent 实例（如 TechnicalAnalyst）
            expertise: 专业领域名称
            system_prompt: 系统提示
            personality: 分析风格
            task_keywords: 触发此 Agent 的关键词列表
        """
        super().__init__(expertise, system_prompt, personality)
        self.legacy_agent = legacy_agent
        self.task_keywords = task_keywords or []

    def select_tools(self, task: Task) -> List[Any]:
        """
        选择工具 - 适配旧版 Agent 的工具

        旧版 Agents 通常在 analyze() 方法中直接使用工具，
        这里返回一个空列表，因为工具在 legacy_agent 内部管理
        """
        # 旧版 Agents 工具在内部管理
        # 如果 legacy_agent 有 tools 属性，返回它
        if hasattr(self.legacy_agent, 'tools'):
            return self.legacy_agent.tools
        return []

    def should_participate(self, task: Task) -> Tuple[bool, str]:
        """
        判断是否应该参与此任务

        根据任务类型和关键词匹配
        """
        # 简单价格查询通常不需要深度分析
        if task.type == TaskType.SIMPLE_PRICE:
            return False, "简单价格查询不需要此 Agent"

        # 检查关键词匹配
        query_lower = task.query.lower()
        for keyword in self.task_keywords:
            if keyword in query_lower:
                return True, f"匹配关键词: {keyword}"

        # 默认参与（除非是简单查询）
        if task.type in [TaskType.ANALYSIS, TaskType.DEEP_ANALYSIS]:
            return True, f"任务类型匹配: {task.type.value}"

        return False, "任务类型不匹配"

    def analyze(self, market_data: Dict) -> Any:
        """
        执行分析 - 委托给旧版 Agent
        """
        self.state = AgentState.ANALYZING
        try:
            if hasattr(self.legacy_agent, 'analyze'):
                result = self.legacy_agent.analyze(market_data)
                self.state = AgentState.COMPLETED
                return result
            else:
                raise NotImplementedError("Legacy agent has no analyze() method")
        except Exception as e:
            self.state = AgentState.IDLE
            raise e


def create_technical_adapter(client: Any) -> LegacyAgentAdapter:
    """
    创建技术分析适配器

    Args:
        client: LLM client

    Returns:
        包装好的 TechnicalAnalyst
    """
    from core.agents import TechnicalAnalyst

    legacy = TechnicalAnalyst(client)
    return LegacyAgentAdapter(
        legacy_agent=legacy,
        expertise="technical_analysis",
        system_prompt="专业技术分析师，擅长多周期技术指标分析",
        personality="analytical",
        task_keywords=["技術", "RSI", "MACD", "MA", "指標", "圖表", "技術面"]
    )


def create_sentiment_adapter(client: Any) -> LegacyAgentAdapter:
    """
    创建情绪分析适配器
    """
    from core.agents import SentimentAnalyst

    legacy = SentimentAnalyst(client)
    return LegacyAgentAdapter(
        legacy_agent=legacy,
        expertise="sentiment_analysis",
        system_prompt="市场情绪分析师，分析社交媒体和恐惧贪婪指数",
        personality="balanced",
        task_keywords=["情緒", "恐懼", "貪婪", "社群", "輿論", "市場情緒"]
    )


def create_fundamental_adapter(client: Any) -> LegacyAgentAdapter:
    """
    创建基本面分析适配器
    """
    from core.agents import FundamentalAnalyst

    legacy = FundamentalAnalyst(client)
    return LegacyAgentAdapter(
        legacy_agent=legacy,
        expertise="fundamental_analysis",
        system_prompt="基本面分析师，分析链上数据和项目基本面",
        personality="conservative",
        task_keywords=["基本面", "鏈上", "估值", "項目", "價值"]
    )


def create_news_adapter(client: Any) -> LegacyAgentAdapter:
    """
    创建新闻分析适配器
    """
    from core.agents import NewsAnalyst

    legacy = NewsAnalyst(client)
    return LegacyAgentAdapter(
        legacy_agent=legacy,
        expertise="news_analysis",
        system_prompt="新闻分析师，分析加密货币相关新闻",
        personality="balanced",
        task_keywords=["新聞", "消息", "利好", "利空", "事件"]
    )


def register_legacy_agents(orchestrator: Any, client: Any) -> Dict[str, LegacyAgentAdapter]:
    """
    将所有旧版 Agents 注册到 Orchestrator

    Args:
        orchestrator: Orchestrator 实例
        client: LLM client

    Returns:
        注册的 Agent 字典
    """
    adapters = {
        "technical_analysis": create_technical_adapter(client),
        "sentiment_analysis": create_sentiment_adapter(client),
        "fundamental_analysis": create_fundamental_adapter(client),
        "news_analysis": create_news_adapter(client),
    }

    for adapter in adapters.values():
        orchestrator.register_agent(adapter)

    return adapters


# 为高级 Agents 创建适配器（可选）

class DebaterAdapter(ProfessionalAgent):
    """
    辩论者适配器 - 用于 Bull/Bear/Neutral Researcher
    """

    def __init__(
        self,
        legacy_agent: Any,
        stance: str,  # "bull", "bear", "neutral"
        expertise: str,
        system_prompt: str,
        personality: str = "balanced"
    ):
        super().__init__(expertise, system_prompt, personality)
        self.legacy_agent = legacy_agent
        self.stance = stance

    def select_tools(self, task: Task) -> List[Any]:
        return []

    def should_participate(self, task: Task) -> Tuple[bool, str]:
        # 辩论者只在深度分析时参与
        if task.type == TaskType.DEEP_ANALYSIS:
            return True, f"{self.stance} stance debater"
        return False, "只在深度分析时参与"

    def debate(
        self,
        analyst_reports: List,
        opponent_arguments: List = None,
        round_num: int = 1,
        topic: str = None
    ) -> Any:
        """执行辩论"""
        self.state = AgentState.DISCUSSING
        try:
            if hasattr(self.legacy_agent, 'debate'):
                result = self.legacy_agent.debate(
                    analyst_reports,
                    opponent_arguments,
                    round_num,
                    topic
                )
                self.state = AgentState.COMPLETED
                return result
            else:
                raise NotImplementedError("Legacy agent has no debate() method")
        except Exception as e:
            self.state = AgentState.IDLE
            raise e


def create_bull_researcher_adapter(client: Any) -> DebaterAdapter:
    """创建多头研究员适配器"""
    from core.agents import BullResearcher

    legacy = BullResearcher(client)
    return DebaterAdapter(
        legacy_agent=legacy,
        stance="bull",
        expertise="bull_researcher",
        system_prompt="多头研究员，寻找看涨理由",
        personality="aggressive"
    )


def create_bear_researcher_adapter(client: Any) -> DebaterAdapter:
    """创建空头研究员适配器"""
    from core.agents import BearResearcher

    legacy = BearResearcher(client)
    return DebaterAdapter(
        legacy_agent=legacy,
        stance="bear",
        expertise="bear_researcher",
        system_prompt="空头研究员，寻找看跌理由",
        personality="conservative"
    )


def create_neutral_researcher_adapter(client: Any) -> DebaterAdapter:
    """创建中立研究员适配器"""
    from core.agents import NeutralResearcher

    legacy = NeutralResearcher(client)
    return DebaterAdapter(
        legacy_agent=legacy,
        stance="neutral",
        expertise="neutral_researcher",
        system_prompt="中立研究员，客观评估多空双方观点",
        personality="balanced"
    )
