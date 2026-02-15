"""Professional Agent System V2

This package contains the new Agent-driven architecture that replaces
the flow-driven system with a more flexible, professional agent model.
"""

__version__ = "0.2.0"

from .base import AgentState, ProfessionalAgent
from .models import Viewpoint, DiscussionRound
from .task import Task, TaskType
from .technical import TechnicalAgent
from .orchestrator import Orchestrator
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
]
