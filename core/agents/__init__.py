__version__ = "5.0.0"

from .bootstrap import bootstrap
from .models import (
    TaskComplexity, CollaborationRequest, AgentResult, SubTask,
    ManagerStateV2, TaskNode, TaskGraph, AgentContext,
)
from .prompt_registry import PromptRegistry
from .description_loader import AgentDescriptionLoader, get_agent_descriptions
from .agent_registry import AgentRegistry
from .tool_registry import ToolRegistry
from .router import AgentRouter
from .manager import ManagerAgent

__all__ = [
    "bootstrap", "ManagerAgent",
    "TaskComplexity", "CollaborationRequest", "AgentResult", "SubTask",
    "PromptRegistry", "AgentDescriptionLoader", "get_agent_descriptions",
    "AgentRegistry", "ToolRegistry", "AgentRouter",
    "ManagerStateV2", "TaskNode", "TaskGraph", "AgentContext",
]
