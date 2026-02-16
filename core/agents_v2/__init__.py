"""Professional Agent System V2

This package contains the new Agent-driven architecture that replaces
the flow-driven system with a more flexible, professional agent model.
"""

__version__ = "0.5.0"

from .base import AgentState, ProfessionalAgent
from .models import Viewpoint, DiscussionRound
from .task import Task, TaskType, ParsedIntent
from .technical import TechnicalAgent
from .orchestrator import Orchestrator
from .llm_parser import LLMTaskParser
from .memory import ConversationContext, ConversationMemory
from .tool_registry import ToolRegistry, ToolInfo
from .config import GraphConfig, AgentFeatureConfig, FeatureToggle, create_default_config
from .hitl import (
    HITLManager,
    HITLState,
    HITLCheckpoint,
    ReviewPoint,
    create_hitl_manager_with_defaults,
    create_trading_checkpoints,
)
from .feedback import (
    FeedbackCollector,
    Feedback,
    FeedbackType,
    FeedbackSource,
    AgentPerformance,
    create_quick_feedback,
)
from .codebook import (
    Codebook,
    Experience,
    ExperienceCategory,
    MarketCondition,
    ExperienceMatch,
)
from .adapters import (
    LegacyAgentAdapter,
    DebaterAdapter,
    create_technical_adapter,
    create_sentiment_adapter,
    create_fundamental_adapter,
    create_news_adapter,
    create_bull_researcher_adapter,
    create_bear_researcher_adapter,
    create_neutral_researcher_adapter,
    register_legacy_agents,
)

__all__ = [
    # Base
    "AgentState",
    "ProfessionalAgent",
    # Models
    "Viewpoint",
    "DiscussionRound",
    # Task
    "Task",
    "TaskType",
    "ParsedIntent",
    # LLM Parser
    "LLMTaskParser",
    # Agents
    "TechnicalAgent",
    "Orchestrator",
    # Memory
    "ConversationContext",
    "ConversationMemory",
    # Tools
    "ToolRegistry",
    "ToolInfo",
    # Config
    "GraphConfig",
    "AgentFeatureConfig",
    "FeatureToggle",
    "create_default_config",
    # HITL (Phase 6-7)
    "HITLManager",
    "HITLState",
    "HITLCheckpoint",
    "ReviewPoint",
    "create_hitl_manager_with_defaults",
    "create_trading_checkpoints",
    # Feedback (Phase 8)
    "FeedbackCollector",
    "Feedback",
    "FeedbackType",
    "FeedbackSource",
    "AgentPerformance",
    "create_quick_feedback",
    # Codebook (Phase 9)
    "Codebook",
    "Experience",
    "ExperienceCategory",
    "MarketCondition",
    "ExperienceMatch",
    # Adapters (Phase 10)
    "LegacyAgentAdapter",
    "DebaterAdapter",
    "create_technical_adapter",
    "create_sentiment_adapter",
    "create_fundamental_adapter",
    "create_news_adapter",
    "create_bull_researcher_adapter",
    "create_bear_researcher_adapter",
    "create_neutral_researcher_adapter",
    "register_legacy_agents",
]
