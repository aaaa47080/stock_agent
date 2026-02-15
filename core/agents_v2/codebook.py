"""
Codebook - 经验学习系统

存储和检索 Agent 的成功经验，让 Agent 可以从过去的成功案例中学习。

工作原理：
1. 记录成功的分析案例（用户反馈好的）
2. 根据市场条件分类存储
3. 在类似市场条件下，Agent 可以参考过去的成功经验
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import json
import hashlib


class MarketCondition(Enum):
    """市场条件分类"""
    TRENDING_UP = "trending_up"       # 明显上涨趋势
    TRENDING_DOWN = "trending_down"   # 明显下跌趋势
    RANGING = "ranging"               # 震荡区间
    HIGH_VOLATILITY = "high_volatility"  # 高波动
    LOW_VOLATILITY = "low_volatility"    # 低波动
    BREAKOUT = "breakout"             # 突破
    REVERSAL = "reversal"             # 反转
    UNKNOWN = "unknown"               # 未知


class ExperienceCategory(Enum):
    """经验类别"""
    SUCCESSFUL_TRADE = "successful_trade"     # 成功交易
    AVOIDED_LOSS = "avoided_loss"             # 避免亏损
    ACCURATE_PREDICTION = "accurate_prediction"  # 准确预测
    GOOD_TIMING = "good_timing"               # 好的时机
    RISK_MANAGEMENT = "risk_management"       # 风险管理


@dataclass
class Experience:
    """
    单条经验记录

    存储一个成功案例的完整信息
    """
    id: str
    category: ExperienceCategory
    agent_name: str                          # 哪个 Agent 的经验

    # 市场条件
    market_condition: MarketCondition
    symbol: str
    timeframe: str

    # 经验内容
    situation: str                           # 市场情况描述
    action: str                              # Agent 采取的行动
    reasoning: str                           # Agent 的推理过程
    outcome: str                             # 结果

    # 验证信息
    user_rating: int                         # 用户评分 1-5
    verified: bool = False                   # 是否验证过

    # 元数据
    tags: List[str] = field(default_factory=list)
    indicators: Dict[str, Any] = field(default_factory=dict)  # 相关指标值
    created_at: datetime = field(default_factory=datetime.now)
    use_count: int = 0                       # 被参考次数

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "agent_name": self.agent_name,
            "market_condition": self.market_condition.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "situation": self.situation,
            "action": self.action,
            "reasoning": self.reasoning,
            "outcome": self.outcome,
            "user_rating": self.user_rating,
            "verified": self.verified,
            "tags": self.tags,
            "indicators": self.indicators,
            "created_at": self.created_at.isoformat(),
            "use_count": self.use_count,
        }

    def create_embedding_key(self) -> str:
        """创建用于相似度匹配的嵌入键"""
        # 简化版：用市场条件 + 关键指标创建特征键
        key_parts = [
            self.market_condition.value,
            self.timeframe,
        ]
        # 添加关键指标范围
        for k, v in self.indicators.items():
            if isinstance(v, (int, float)):
                # 离散化为范围
                if v < 30:
                    key_parts.append(f"{k}_low")
                elif v < 70:
                    key_parts.append(f"{k}_mid")
                else:
                    key_parts.append(f"{k}_high")
        return "|".join(key_parts)


@dataclass
class ExperienceMatch:
    """
    经验匹配结果
    """
    experience: Experience
    similarity_score: float                  # 相似度 0-1
    relevance_reason: str                    # 为什么相关


class Codebook:
    """
    经验手册 - Agent 的成功案例库

    职责：
    - 存储成功经验
    - 根据市场条件检索相似经验
    - 提供经验参考给 Agent
    - 学习用户反馈好的案例

    使用示例：
    ```python
    codebook = Codebook()

    # 记录成功经验
    exp = codebook.record_experience(
        category=ExperienceCategory.SUCCESSFUL_TRADE,
        agent_name="technical_analysis",
        market_condition=MarketCondition.TRENDING_UP,
        symbol="BTC",
        timeframe="4h",
        situation="BTC 突破前高，RSI 65，成交量放大",
        action="建议买入，目标 +10%",
        reasoning="技术面突破确认，动能强劲",
        outcome="价格上涨 12%",
        user_rating=5,
        indicators={"rsi": 65, "volume_change": 150}
    )

    # 查找相似经验
    current_market = {
        "market_condition": MarketCondition.TRENDING_UP,
        "symbol": "ETH",
        "timeframe": "4h",
        "indicators": {"rsi": 62, "volume_change": 140}
    }
    matches = codebook.find_similar_experiences(current_market)
    for match in matches:
        print(f"相似度: {match.similarity_score:.0%}")
        print(f"参考: {match.experience.action}")
    ```
    """

    MIN_RATING_TO_STORE = 4  # 最低评分才存储

    def __init__(self):
        self.experiences: Dict[str, Experience] = {}
        self._exp_counter = 0
        # 索引：按市场条件分类
        self._condition_index: Dict[str, List[str]] = {}
        # 索引：按 Agent 分类
        self._agent_index: Dict[str, List[str]] = {}

    def record_experience(
        self,
        category: ExperienceCategory,
        agent_name: str,
        market_condition: MarketCondition,
        symbol: str,
        timeframe: str,
        situation: str,
        action: str,
        reasoning: str,
        outcome: str,
        user_rating: int,
        indicators: Dict[str, Any] = None,
        tags: List[str] = None
    ) -> Optional[Experience]:
        """
        记录一条经验

        只有用户评分 >= MIN_RATING_TO_STORE 的才会被存储

        Args:
            category: 经验类别
            agent_name: Agent 名称
            market_condition: 市场条件
            symbol: 交易对
            timeframe: 时间周期
            situation: 市场情况描述
            action: 采取的行动
            reasoning: 推理过程
            outcome: 结果
            user_rating: 用户评分
            indicators: 相关指标
            tags: 标签

        Returns:
            Experience 实例或 None（评分太低）
        """
        if user_rating < self.MIN_RATING_TO_STORE:
            return None

        self._exp_counter += 1
        exp_id = f"exp_{self._exp_counter:06d}"

        experience = Experience(
            id=exp_id,
            category=category,
            agent_name=agent_name,
            market_condition=market_condition,
            symbol=symbol,
            timeframe=timeframe,
            situation=situation,
            action=action,
            reasoning=reasoning,
            outcome=outcome,
            user_rating=user_rating,
            tags=tags or [],
            indicators=indicators or {},
        )

        self.experiences[exp_id] = experience
        self._update_indices(experience)

        return experience

    def _update_indices(self, experience: Experience) -> None:
        """更新索引"""
        # 按市场条件索引
        condition_key = experience.market_condition.value
        if condition_key not in self._condition_index:
            self._condition_index[condition_key] = []
        self._condition_index[condition_key].append(experience.id)

        # 按 Agent 索引
        if experience.agent_name not in self._agent_index:
            self._agent_index[experience.agent_name] = []
        self._agent_index[experience.agent_name].append(experience.id)

    def find_similar_experiences(
        self,
        current_market: Dict[str, Any],
        agent_name: str = None,
        limit: int = 5,
        min_similarity: float = 0.3
    ) -> List[ExperienceMatch]:
        """
        查找相似的历史经验

        Args:
            current_market: 当前市场条件
            agent_name: 可选，只查找特定 Agent 的经验
            limit: 返回数量限制
            min_similarity: 最低相似度

        Returns:
            相似经验列表，按相似度排序
        """
        matches: List[ExperienceMatch] = []

        # 确定搜索范围
        search_ids = set()
        if agent_name and agent_name in self._agent_index:
            search_ids.update(self._agent_index[agent_name])
        else:
            search_ids.update(self.experiences.keys())

        # 如果有市场条件，优先搜索同条件的
        market_cond = current_market.get("market_condition")
        if market_cond and market_cond.value in self._condition_index:
            condition_ids = set(self._condition_index[market_cond.value])
            # 优先搜索同条件的
            search_ids = search_ids & condition_ids if search_ids else condition_ids

        # 计算相似度
        current_indicators = current_market.get("indicators", {})
        current_timeframe = current_market.get("timeframe", "")

        for exp_id in search_ids:
            exp = self.experiences.get(exp_id)
            if not exp:
                continue

            similarity, reason = self._calculate_similarity(
                exp,
                market_cond,
                current_timeframe,
                current_indicators
            )

            if similarity >= min_similarity:
                matches.append(ExperienceMatch(
                    experience=exp,
                    similarity_score=similarity,
                    relevance_reason=reason
                ))

        # 按相似度排序
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:limit]

    def _calculate_similarity(
        self,
        experience: Experience,
        market_condition: MarketCondition,
        timeframe: str,
        indicators: Dict[str, Any]
    ) -> Tuple[float, str]:
        """
        计算相似度

        Returns:
            (相似度, 原因说明)
        """
        score = 0.0
        reasons = []

        # 市场条件匹配 (权重 0.4)
        if market_condition and experience.market_condition == market_condition:
            score += 0.4
            reasons.append("相同市场条件")

        # 时间周期匹配 (权重 0.2)
        if timeframe and experience.timeframe == timeframe:
            score += 0.2
            reasons.append("相同时间周期")

        # 指标相似度 (权重 0.4)
        if indicators and experience.indicators:
            indicator_score = self._compare_indicators(indicators, experience.indicators)
            score += indicator_score * 0.4
            if indicator_score > 0.5:
                reasons.append("指标相似")

        reason = "、".join(reasons) if reasons else "基础相似度"
        return score, reason

    def _compare_indicators(
        self,
        current: Dict[str, Any],
        stored: Dict[str, Any]
    ) -> float:
        """比较指标相似度"""
        common_keys = set(current.keys()) & set(stored.keys())
        if not common_keys:
            return 0.0

        total_diff = 0.0
        for key in common_keys:
            c_val = current[key]
            s_val = stored[key]
            if isinstance(c_val, (int, float)) and isinstance(s_val, (int, float)):
                # 归一化差异
                max_val = max(abs(c_val), abs(s_val), 1)
                diff = abs(c_val - s_val) / max_val
                total_diff += min(diff, 1.0)

        avg_diff = total_diff / len(common_keys)
        return 1.0 - avg_diff  # 差异越小，相似度越高

    def get_experience(self, exp_id: str) -> Optional[Experience]:
        """获取单条经验"""
        return self.experiences.get(exp_id)

    def mark_as_used(self, exp_id: str) -> None:
        """标记经验被参考"""
        exp = self.experiences.get(exp_id)
        if exp:
            exp.use_count += 1

    def get_agent_experiences(self, agent_name: str, limit: int = 20) -> List[Experience]:
        """获取特定 Agent 的所有经验"""
        ids = self._agent_index.get(agent_name, [])
        experiences = [self.experiences[i] for i in ids if i in self.experiences]
        # 按使用次数和评分排序
        experiences.sort(key=lambda e: (e.use_count, e.user_rating), reverse=True)
        return experiences[:limit]

    def get_top_experiences(self, limit: int = 10) -> List[Experience]:
        """获取最成功的经验"""
        all_exp = list(self.experiences.values())
        all_exp.sort(key=lambda e: (e.user_rating, e.use_count), reverse=True)
        return all_exp[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.experiences:
            return {
                "total_experiences": 0,
                "by_category": {},
                "by_agent": {},
                "avg_rating": 0,
            }

        by_category = {}
        by_agent = {}
        total_rating = 0

        for exp in self.experiences.values():
            # 按类别统计
            cat = exp.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            # 按 Agent 统计
            agent = exp.agent_name
            by_agent[agent] = by_agent.get(agent, 0) + 1

            total_rating += exp.user_rating

        return {
            "total_experiences": len(self.experiences),
            "by_category": by_category,
            "by_agent": by_agent,
            "avg_rating": round(total_rating / len(self.experiences), 2),
            "top_agents": sorted(by_agent.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def learn_from_feedback(
        self,
        feedback: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> Optional[Experience]:
        """
        从反馈中学习

        将高质量反馈转化为经验存储

        Args:
            feedback: FeedbackCollector 的反馈数据
            market_context: 市场上下文

        Returns:
            新创建的 Experience 或 None
        """
        rating = feedback.get("rating", 0)
        if rating < self.MIN_RATING_TO_STORE:
            return None

        return self.record_experience(
            category=ExperienceCategory.ACCURATE_PREDICTION,
            agent_name=feedback.get("agent_name", "unknown"),
            market_condition=market_context.get("market_condition", MarketCondition.UNKNOWN),
            symbol=market_context.get("symbol", "BTC"),
            timeframe=market_context.get("timeframe", "1h"),
            situation=market_context.get("situation", ""),
            action=market_context.get("action", ""),
            reasoning=market_context.get("reasoning", ""),
            outcome=feedback.get("comment", "用户反馈良好"),
            user_rating=rating,
            indicators=market_context.get("indicators", {}),
            tags=feedback.get("tags", []),
        )

    def export_experiences(self) -> List[Dict]:
        """导出所有经验"""
        return [exp.to_dict() for exp in self.experiences.values()]

    def import_experiences(self, experiences: List[Dict]) -> int:
        """导入经验"""
        count = 0
        for exp_data in experiences:
            try:
                exp = Experience(
                    id=exp_data["id"],
                    category=ExperienceCategory(exp_data["category"]),
                    agent_name=exp_data["agent_name"],
                    market_condition=MarketCondition(exp_data["market_condition"]),
                    symbol=exp_data["symbol"],
                    timeframe=exp_data["timeframe"],
                    situation=exp_data["situation"],
                    action=exp_data["action"],
                    reasoning=exp_data["reasoning"],
                    outcome=exp_data["outcome"],
                    user_rating=exp_data["user_rating"],
                    verified=exp_data.get("verified", False),
                    tags=exp_data.get("tags", []),
                    indicators=exp_data.get("indicators", {}),
                    created_at=datetime.fromisoformat(exp_data["created_at"]) if exp_data.get("created_at") else datetime.now(),
                    use_count=exp_data.get("use_count", 0),
                )
                self.experiences[exp.id] = exp
                self._update_indices(exp)
                count += 1
            except Exception as e:
                print(f"导入经验失败: {e}")
        return count
