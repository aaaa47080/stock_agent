"""LangGraph 風格的動態配置管理"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


class FeatureToggle(Enum):
    """功能開關"""
    ON = "on"
    OFF = "off"
    AUTO = "auto"


@dataclass
class AgentFeatureConfig:
    """單一 Agent 的配置"""
    name: str
    enabled: bool = True
    tools: List[str] = field(default_factory=list)
    priority: int = 0
    condition: Optional[Callable[[dict], bool]] = None

    def should_run(self, context: dict) -> bool:
        """根據上下文決定是否執行"""
        if not self.enabled:
            return False
        if self.condition:
            return self.condition(context)
        return True


@dataclass
class GraphConfig:
    """LangGraph 風格的運行時配置"""

    agents: Dict[str, AgentFeatureConfig] = field(default_factory=dict)
    tools: Dict[str, bool] = field(default_factory=dict)
    features: Dict[str, FeatureToggle] = field(default_factory=lambda: {
        "multi_timeframe": FeatureToggle.ON,
        "debate": FeatureToggle.AUTO,
        "risk_assessment": FeatureToggle.ON,
        "hitl": FeatureToggle.OFF,
        "codebook": FeatureToggle.OFF,
    })
    model_settings: Dict[str, Any] = field(default_factory=lambda: {
        "fast_model": "gpt-4o-mini",
        "deep_model": "gpt-4o",
    })

    def get_active_agents(self, context: dict = None) -> List[str]:
        context = context or {}
        return [name for name, cfg in self.agents.items() if cfg.should_run(context)]

    def get_active_tools(self, agent_name: str = None) -> List[str]:
        if agent_name and agent_name in self.agents:
            return [t for t in self.agents[agent_name].tools if self.tools.get(t, True)]
        return [t for t, enabled in self.tools.items() if enabled]

    def is_feature_enabled(self, feature: str) -> bool:
        return self.features.get(feature, FeatureToggle.OFF) == FeatureToggle.ON

    def disable_agent(self, name: str):
        if name in self.agents:
            self.agents[name].enabled = False

    def enable_agent(self, name: str):
        if name in self.agents:
            self.agents[name].enabled = True

    def disable_tool(self, name: str):
        self.tools[name] = False

    def enable_tool(self, name: str):
        self.tools[name] = True

    def set_feature(self, feature: str, toggle: FeatureToggle):
        self.features[feature] = toggle


def create_default_config() -> GraphConfig:
    """創建預設配置"""
    config = GraphConfig()

    config.agents = {
        "technical_analysis": AgentFeatureConfig(
            name="technical_analysis",
            enabled=True,
            tools=["rsi", "macd", "bollinger_bands", "support_resistance"],
            priority=1,
            condition=lambda ctx: ctx.get("task_type") != "simple_price"
        ),
        "sentiment_analysis": AgentFeatureConfig(
            name="sentiment_analysis",
            enabled=True,
            tools=["social_sentiment"],
            priority=2,
            condition=lambda ctx: ctx.get("task_type") != "simple_price"
        ),
        "news_analysis": AgentFeatureConfig(
            name="news_analysis",
            enabled=True,
            tools=["crypto_news"],
            priority=2,
            condition=lambda ctx: ctx.get("analysis_depth") == "deep"
        ),
        "debater": AgentFeatureConfig(
            name="debater",
            enabled=True,
            tools=[],
            priority=3,
            condition=lambda ctx: ctx.get("has_conflict", False)
        ),
        "risk_manager": AgentFeatureConfig(
            name="risk_manager",
            enabled=True,
            tools=[],
            priority=99,
        ),
    }

    config.tools = {
        "rsi": True,
        "macd": True,
        "bollinger_bands": True,
        "support_resistance": True,
        "social_sentiment": True,
        "crypto_news": True,
    }

    return config
