"""Professional Agent System V2

This package contains the new Agent-driven architecture that replaces
the flow-driven system with a more flexible, professional agent model.
"""

__version__ = "0.1.0"

from .base import AgentState, ProfessionalAgent
from .models import Viewpoint, DiscussionRound
from .task import Task, TaskType
from .technical import TechnicalAgent

__all__ = [
    "AgentState",
    "ProfessionalAgent",
    "Viewpoint",
    "DiscussionRound",
    "Task",
    "TaskType",
    "TechnicalAgent",
]
