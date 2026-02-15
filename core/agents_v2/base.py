"""Professional Agent base classes and interfaces"""
from enum import Enum


class AgentState(Enum):
    """Agent 運行狀態"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DISCUSSING = "discussing"
    WAITING_FEEDBACK = "waiting_feedback"
    COMPLETED = "completed"
