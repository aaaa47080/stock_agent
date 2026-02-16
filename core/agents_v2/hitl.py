"""
Human-in-the-Loop (HITL) Manager

使用 LangGraph 的 interrupt + checkpointer 机制实现人机协作
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime


class HITLState(Enum):
    """人机协作状态"""
    PENDING = "pending"              # 等待用户回应
    APPROVED = "approved"            # 用户已批准
    REJECTED = "rejected"            # 用户已拒绝
    NEEDS_DISCUSSION = "discussion"  # 需要进一步讨论
    MODIFIED = "modified"            # 用户修改后批准
    TIMEOUT = "timeout"              # 超时


@dataclass
class ReviewPoint:
    """
    审核点 - 需要用户确认的决策点

    用于在关键决策前暂停工作流，等待用户确认
    """
    id: str
    title: str                              # 审核标题
    content: str                            # 审核内容（Markdown）
    options: List[Dict[str, str]]           # 可选操作 [{"label": "同意", "value": "approve"}, ...]
    context: Dict[str, Any] = field(default_factory=dict)  # 相关上下文
    state: HITLState = HITLState.PENDING
    user_response: Optional[str] = None     # 用户选择
    user_feedback: Optional[str] = None     # 用户反馈
    created_at: datetime = field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "options": self.options,
            "context": self.context,
            "state": self.state.value,
            "user_response": self.user_response,
            "user_feedback": self.user_feedback,
            "created_at": self.created_at.isoformat(),
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }


@dataclass
class HITLCheckpoint:
    """
    HITL 检查点配置

    定义工作流中需要用户确认的检查点
    """
    name: str                               # 检查点名称
    description: str                        # 描述
    condition: Optional[Callable[[dict], bool]] = None  # 触发条件
    auto_approve_after_seconds: Optional[int] = None    # 自动批准超时（秒）
    require_reason: bool = False            # 拒绝时是否需要填写原因

    def should_interrupt(self, context: dict) -> bool:
        """判断是否需要中断"""
        if self.condition:
            return self.condition(context)
        return True


class HITLManager:
    """
    Human-in-the-Loop 管理器

    职责：
    - 管理审核点
    - 处理用户响应
    - 支持暂停/继续工作流
    - 记录用户决策历史

    使用方式（与 LangGraph 整合）：

    ```python
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph

    # 1. 创建 HITL Manager
    hitl = HITLManager()

    # 2. 设置检查点
    hitl.add_checkpoint(HITLCheckpoint(
        name="trade_approval",
        description="交易确认",
        condition=lambda ctx: ctx.get("decision") in ["buy", "sell"],
        require_reason=True
    ))

    # 3. 在 LangGraph 工作流中使用
    checkpointer = MemorySaver()
    workflow = StateGraph(State)
    # ... 添加节点 ...

    # 编译时指定 interrupt 点
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=hitl.get_interrupt_points()
    )

    # 4. 执行时检查是否需要用户确认
    result = app.invoke(inputs, config)
    if hitl.needs_review(result):
        review = hitl.create_review_point(result)
        # 返回给前端等待用户确认...

    # 5. 用户确认后继续
    hitl.process_response(review_id, "approve", feedback="同意执行")
    result = app.invoke(None, config)  # 继续执行
    ```
    """

    def __init__(self, auto_timeout: int = 300):
        """
        初始化 HITL Manager

        Args:
            auto_timeout: 自动超时时间（秒），默认 5 分钟
        """
        self.checkpoints: Dict[str, HITLCheckpoint] = {}
        self.pending_reviews: Dict[str, ReviewPoint] = {}
        self.review_history: List[ReviewPoint] = []
        self.auto_timeout = auto_timeout

    def add_checkpoint(self, checkpoint: HITLCheckpoint) -> None:
        """添加检查点"""
        self.checkpoints[checkpoint.name] = checkpoint

    def remove_checkpoint(self, name: str) -> bool:
        """移除检查点"""
        if name in self.checkpoints:
            del self.checkpoints[name]
            return True
        return False

    def get_interrupt_points(self) -> List[str]:
        """
        获取 LangGraph 的 interrupt_before 列表

        Returns:
            需要中断的节点名称列表
        """
        # 返回所有检查点名称，用于 LangGraph 的 interrupt_before
        return list(self.checkpoints.keys())

    def should_interrupt(self, checkpoint_name: str, context: dict) -> bool:
        """
        判断指定检查点是否需要中断

        Args:
            checkpoint_name: 检查点名称
            context: 当前上下文

        Returns:
            是否需要中断等待用户确认
        """
        checkpoint = self.checkpoints.get(checkpoint_name)
        if not checkpoint:
            return False
        return checkpoint.should_interrupt(context)

    def create_review_point(
        self,
        checkpoint_name: str,
        content: str,
        context: dict = None,
        custom_options: List[Dict] = None
    ) -> ReviewPoint:
        """
        创建审核点

        Args:
            checkpoint_name: 检查点名称
            content: 审核内容（Markdown）
            context: 相关上下文
            custom_options: 自定义选项（覆盖默认）

        Returns:
            ReviewPoint 实例
        """
        checkpoint = self.checkpoints.get(checkpoint_name)
        if not checkpoint:
            raise ValueError(f"Unknown checkpoint: {checkpoint_name}")

        # 默认选项
        default_options = [
            {"label": "✅ 同意", "value": "approve", "style": "primary"},
            {"label": "❌ 拒绝", "value": "reject", "style": "danger"},
            {"label": "💬 有疑问", "value": "discuss", "style": "secondary"},
        ]
        options = custom_options or default_options

        review = ReviewPoint(
            id=f"{checkpoint_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title=checkpoint.description,
            content=content,
            options=options,
            context=context or {},
        )

        self.pending_reviews[review.id] = review
        return review

    def get_review(self, review_id: str) -> Optional[ReviewPoint]:
        """获取审核点"""
        return self.pending_reviews.get(review_id)

    def process_response(
        self,
        review_id: str,
        response: str,
        feedback: str = None,
        modifications: dict = None
    ) -> HITLState:
        """
        处理用户响应

        Args:
            review_id: 审核点 ID
            response: 用户选择（approve/reject/discuss/modify）
            feedback: 用户反馈
            modifications: 用户修改的参数

        Returns:
            新状态
        """
        review = self.pending_reviews.get(review_id)
        if not review:
            raise ValueError(f"Unknown review: {review_id}")

        review.user_response = response
        review.user_feedback = feedback
        review.responded_at = datetime.now()

        # 更新状态
        response_to_state = {
            "approve": HITLState.APPROVED,
            "reject": HITLState.REJECTED,
            "discuss": HITLState.NEEDS_DISCUSSION,
            "modify": HITLState.MODIFIED,
        }
        review.state = response_to_state.get(response, HITLState.PENDING)

        # 记录到历史
        self.review_history.append(review)
        del self.pending_reviews[review_id]

        return review.state

    def get_pending_reviews(self) -> List[ReviewPoint]:
        """获取所有待处理的审核点"""
        return list(self.pending_reviews.values())

    def get_review_history(self, limit: int = 50) -> List[ReviewPoint]:
        """获取审核历史"""
        return self.review_history[-limit:]

    def check_timeout(self) -> List[ReviewPoint]:
        """
        检查超时的审核点

        Returns:
            超时的审核点列表
        """
        import time
        now = time.time()
        timed_out = []

        for review in self.pending_reviews.values():
            elapsed = now - review.created_at.timestamp()
            if elapsed > self.auto_timeout:
                review.state = HITLState.TIMEOUT
                timed_out.append(review)
                self.review_history.append(review)

        for review in timed_out:
            del self.pending_reviews[review.id]

        return timed_out

    def clear_pending(self) -> int:
        """清除所有待处理的审核点"""
        count = len(self.pending_reviews)
        self.pending_reviews.clear()
        return count


# 预设的交易审核检查点
def create_trading_checkpoints() -> List[HITLCheckpoint]:
    """
    创建交易系统常用的检查点

    Returns:
        预设的检查点列表
    """
    return [
        HITLCheckpoint(
            name="trade_decision",
            description="交易决策确认",
            condition=lambda ctx: ctx.get("decision") in ["buy", "sell", "long", "short"],
            require_reason=True
        ),
        HITLCheckpoint(
            name="high_risk_trade",
            description="高风险交易确认",
            condition=lambda ctx: ctx.get("risk_level") in ["high", "extreme"],
            require_reason=True
        ),
        HITLCheckpoint(
            name="large_position",
            description="大仓位确认",
            condition=lambda ctx: ctx.get("position_pct", 0) > 0.3,  # 超过 30% 仓位
            require_reason=True
        ),
        HITLCheckpoint(
            name="analysis_review",
            description="分析结果确认",
            condition=lambda ctx: ctx.get("analysis_depth") == "deep",
            require_reason=False
        ),
    ]


# 便捷函数
def create_hitl_manager_with_defaults() -> HITLManager:
    """
    创建带默认检查点的 HITL Manager

    Returns:
        配置好的 HITLManager 实例
    """
    manager = HITLManager()
    for checkpoint in create_trading_checkpoints():
        manager.add_checkpoint(checkpoint)
    return manager
