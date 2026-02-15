"""
Feedback Collector - 用户反馈收集系统

收集用户对 Agent 分析结果的反馈，用于：
1. 评估 Agent 表现
2. 改进分析质量
3. 训练 Codebook（经验学习）
4. 生成统计报告
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import json


class FeedbackType(Enum):
    """反馈类型"""
    HELPFUL = "helpful"           # 有帮助
    NOT_HELPFUL = "not_helpful"   # 没帮助
    ACCURATE = "accurate"         # 准确
    INACCURATE = "inaccurate"     # 不准确
    TOO_CONSERVATIVE = "too_conservative"  # 太保守
    TOO_AGGRESSIVE = "too_aggressive"      # 太激进
    MISSING_INFO = "missing_info"           # 缺少信息
    SUGGESTION = "suggestion"               # 建议


class FeedbackSource(Enum):
    """反馈来源"""
    EXPLICIT = "explicit"         # 用户主动提供
    IMPLICIT = "implicit"         # 隐式（如点击、停留时间）
    POST_TRADE = "post_trade"     # 交易后反馈
    COMPARISON = "comparison"     # 对比其他分析


@dataclass
class Feedback:
    """
    单条反馈记录
    """
    id: str
    session_id: str                       # 会话 ID
    agent_name: str                       # Agent 名称
    feedback_type: FeedbackType           # 反馈类型
    source: FeedbackSource = FeedbackSource.EXPLICIT

    # 反馈内容
    rating: Optional[int] = None          # 1-5 星评分
    comment: Optional[str] = None         # 文字评论
    tags: List[str] = field(default_factory=list)  # 标签

    # 上下文
    context: Dict[str, Any] = field(default_factory=dict)  # 反馈时的上下文
    decision: Optional[str] = None        # 当时的决策
    outcome: Optional[str] = None         # 实际结果（如果有）

    # 时间
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "feedback_type": self.feedback_type.value,
            "source": self.source.value,
            "rating": self.rating,
            "comment": self.comment,
            "tags": self.tags,
            "context": self.context,
            "decision": self.decision,
            "outcome": self.outcome,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AgentPerformance:
    """
    Agent 表现统计
    """
    agent_name: str
    total_feedbacks: int = 0
    helpful_count: int = 0
    accurate_count: int = 0
    total_rating: float = 0.0

    # 按类型统计
    feedback_by_type: Dict[str, int] = field(default_factory=dict)

    # 时间窗口统计
    recent_ratings: List[int] = field(default_factory=list)  # 最近 N 次评分
    recent_accuracy: List[bool] = field(default_factory=list)  # 最近 N 次准确性

    @property
    def average_rating(self) -> float:
        if not self.recent_ratings:
            return 0.0
        return sum(self.recent_ratings) / len(self.recent_ratings)

    @property
    def accuracy_rate(self) -> float:
        if not self.recent_accuracy:
            return 0.0
        return sum(self.recent_accuracy) / len(self.recent_accuracy)

    @property
    def helpful_rate(self) -> float:
        if self.total_feedbacks == 0:
            return 0.0
        return self.helpful_count / self.total_feedbacks

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "total_feedbacks": self.total_feedbacks,
            "helpful_count": self.helpful_count,
            "accurate_count": self.accurate_count,
            "average_rating": round(self.average_rating, 2),
            "accuracy_rate": round(self.accuracy_rate, 2),
            "helpful_rate": round(self.helpful_rate, 2),
            "feedback_by_type": self.feedback_by_type,
        }


class FeedbackCollector:
    """
    反馈收集器

    职责：
    - 收集用户反馈
    - 计算 Agent 表现统计
    - 生成反馈报告
    - 为 Codebook 提供数据

    使用示例：
    ```python
    collector = FeedbackCollector()

    # 收集反馈
    feedback = collector.collect(
        session_id="session_123",
        agent_name="technical_analysis",
        feedback_type=FeedbackType.HELPFUL,
        rating=4,
        comment="分析很准确，RSI 指标很有参考价值"
    )

    # 获取 Agent 表现
    performance = collector.get_agent_performance("technical_analysis")
    print(f"平均评分: {performance.average_rating}")
    print(f"准确率: {performance.accuracy_rate:.0%}")
    ```
    """

    MAX_RECENT_ITEMS = 50  # 保留最近 50 条记录用于计算

    def __init__(self):
        self.feedbacks: List[Feedback] = []
        self.performances: Dict[str, AgentPerformance] = {}
        self._feedback_counter = 0

    def collect(
        self,
        session_id: str,
        agent_name: str,
        feedback_type: FeedbackType,
        rating: int = None,
        comment: str = None,
        tags: List[str] = None,
        context: dict = None,
        source: FeedbackSource = FeedbackSource.EXPLICIT
    ) -> Feedback:
        """
        收集反馈

        Args:
            session_id: 会话 ID
            agent_name: Agent 名称
            feedback_type: 反馈类型
            rating: 1-5 星评分（可选）
            comment: 文字评论（可选）
            tags: 标签列表（可选）
            context: 上下文（可选）
            source: 反馈来源

        Returns:
            Feedback 实例
        """
        self._feedback_counter += 1
        feedback_id = f"fb_{self._feedback_counter:06d}"

        feedback = Feedback(
            id=feedback_id,
            session_id=session_id,
            agent_name=agent_name,
            feedback_type=feedback_type,
            source=source,
            rating=max(1, min(5, rating)) if rating else None,
            comment=comment,
            tags=tags or [],
            context=context or {},
        )

        self.feedbacks.append(feedback)
        self._update_performance(feedback)

        return feedback

    def _update_performance(self, feedback: Feedback) -> None:
        """更新 Agent 表现统计"""
        agent_name = feedback.agent_name

        if agent_name not in self.performances:
            self.performances[agent_name] = AgentPerformance(agent_name=agent_name)

        perf = self.performances[agent_name]
        perf.total_feedbacks += 1

        # 更新类型统计
        fb_type = feedback.feedback_type.value
        perf.feedback_by_type[fb_type] = perf.feedback_by_type.get(fb_type, 0) + 1

        # 更新 helpful 计数
        if feedback.feedback_type == FeedbackType.HELPFUL:
            perf.helpful_count += 1

        # 更新 accurate 计数
        if feedback.feedback_type == FeedbackType.ACCURATE:
            perf.accurate_count += 1

        # 更新最近评分
        if feedback.rating:
            perf.recent_ratings.append(feedback.rating)
            if len(perf.recent_ratings) > self.MAX_RECENT_ITEMS:
                perf.recent_ratings.pop(0)

        # 更新最近准确性
        is_accurate = feedback.feedback_type in [FeedbackType.ACCURATE, FeedbackType.HELPFUL]
        perf.recent_accuracy.append(is_accurate)
        if len(perf.recent_accuracy) > self.MAX_RECENT_ITEMS:
            perf.recent_accuracy.pop(0)

    def get_agent_performance(self, agent_name: str) -> Optional[AgentPerformance]:
        """获取指定 Agent 的表现统计"""
        return self.performances.get(agent_name)

    def get_all_performances(self) -> Dict[str, AgentPerformance]:
        """获取所有 Agent 的表现统计"""
        return self.performances

    def get_feedbacks_by_session(self, session_id: str) -> List[Feedback]:
        """获取指定会话的所有反馈"""
        return [fb for fb in self.feedbacks if fb.session_id == session_id]

    def get_feedbacks_by_agent(self, agent_name: str, limit: int = 50) -> List[Feedback]:
        """获取指定 Agent 的反馈"""
        agent_feedbacks = [fb for fb in self.feedbacks if fb.agent_name == agent_name]
        return agent_feedbacks[-limit:]

    def get_recent_feedbacks(self, limit: int = 20) -> List[Feedback]:
        """获取最近的反馈"""
        return self.feedbacks[-limit:]

    def generate_report(self) -> Dict[str, Any]:
        """
        生成反馈报告

        Returns:
            包含统计信息的字典
        """
        total_feedbacks = len(self.feedbacks)

        # 计算整体统计
        total_helpful = sum(1 for fb in self.feedbacks if fb.feedback_type == FeedbackType.HELPFUL)
        total_accurate = sum(1 for fb in self.feedbacks if fb.feedback_type == FeedbackType.ACCURATE)

        # 计算平均评分
        ratings = [fb.rating for fb in self.feedbacks if fb.rating]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        # 各 Agent 表现
        agent_stats = {
            name: perf.to_dict()
            for name, perf in self.performances.items()
        }

        return {
            "summary": {
                "total_feedbacks": total_feedbacks,
                "helpful_rate": total_helpful / total_feedbacks if total_feedbacks > 0 else 0,
                "accurate_rate": total_accurate / total_feedbacks if total_feedbacks > 0 else 0,
                "average_rating": round(avg_rating, 2),
            },
            "agents": agent_stats,
            "feedback_by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> Dict[str, int]:
        """按类型统计反馈数量"""
        counts = {}
        for fb in self.feedbacks:
            fb_type = fb.feedback_type.value
            counts[fb_type] = counts.get(fb_type, 0) + 1
        return counts

    def export_for_codebook(self, min_rating: int = 4) -> List[Dict]:
        """
        导出高质量反馈供 Codebook 学习

        Args:
            min_rating: 最低评分阈值

        Returns:
            高质量反馈列表
        """
        high_quality = [
            fb.to_dict()
            for fb in self.feedbacks
            if fb.rating and fb.rating >= min_rating
            and fb.feedback_type in [FeedbackType.HELPFUL, FeedbackType.ACCURATE]
        ]
        return high_quality

    def clear_old_feedbacks(self, keep_recent: int = 1000) -> int:
        """
        清除旧反馈，只保留最近的

        Args:
            keep_recent: 保留的反馈数量

        Returns:
            清除的反馈数量
        """
        if len(self.feedbacks) <= keep_recent:
            return 0

        removed = len(self.feedbacks) - keep_recent
        self.feedbacks = self.feedbacks[-keep_recent:]
        return removed


# 便捷函数
def create_quick_feedback(
    session_id: str,
    agent_name: str,
    is_helpful: bool,
    rating: int = None,
    comment: str = None
) -> Dict[str, Any]:
    """
    创建快速反馈的辅助函数

    用于前端快速收集用户反馈
    """
    return {
        "session_id": session_id,
        "agent_name": agent_name,
        "feedback_type": FeedbackType.HELPFUL.value if is_helpful else FeedbackType.NOT_HELPFUL.value,
        "rating": rating,
        "comment": comment,
    }
