__version__ = "4.0.0"
from .bootstrap import bootstrap
from .manager import ManagerAgent
from .models import TaskComplexity, CollaborationRequest, AgentResult, SubTask, ExecutionContext
from .prompt_registry import PromptRegistry
__all__ = ["bootstrap", "ManagerAgent", "TaskComplexity", "AgentResult", "SubTask", "ExecutionContext", "PromptRegistry"]
