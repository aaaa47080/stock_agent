__version__ = "4.0.0"
from .bootstrap import bootstrap
from .manager import ManagerAgent
from .models import TaskComplexity, CollaborationRequest, AgentResult, SubTask, ExecutionContext
from .prompt_registry import PromptRegistry

# Legacy Agents (for backward compatibility with core/graph.py)
from .legacy import (
    TechnicalAnalyst, SentimentAnalyst, FundamentalAnalyst, NewsAnalyst,
    BullResearcher, BearResearcher, NeutralResearcher,
    Trader, RiskManager, FundManager,
    CommitteeSynthesizer, DataFactChecker, DebateJudge,
    CryptoAgent
)

__all__ = [
    "bootstrap", "ManagerAgent", "TaskComplexity", "AgentResult", "SubTask", "ExecutionContext", "PromptRegistry",
    "TechnicalAnalyst", "SentimentAnalyst", "FundamentalAnalyst", "NewsAnalyst",
    "BullResearcher", "BearResearcher", "NeutralResearcher",
    "Trader", "RiskManager", "FundManager",
    "CommitteeSynthesizer", "DataFactChecker", "DebateJudge",
    "CryptoAgent"
]
