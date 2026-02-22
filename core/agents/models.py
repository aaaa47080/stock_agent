"""
Agent V4 — Data Models

All core data structures for the V4 agent framework.
No dependency on V3 models.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from enum import Enum


class TaskComplexity(Enum):
    SIMPLE    = "simple"
    COMPLEX   = "complex"
    AMBIGUOUS = "ambiguous"


@dataclass
class CollaborationRequest:
    requesting_agent: str
    needed_agent: str
    context: str
    priority: Literal["required", "optional"]


@dataclass
class AgentResult:
    success: bool
    message: str
    agent_name: str
    data: dict = field(default_factory=dict)
    quality: Literal["pass", "fail"] = "pass"
    quality_fail_reason: Optional[str] = None
    needs_collaboration: Optional[CollaborationRequest] = None


@dataclass
class SubTask:
    step: int
    description: str
    agent: str
    tool_hint: Optional[str] = None
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[AgentResult] = None
    context: dict = field(default_factory=dict)


@dataclass
class MemoryFact:
    """A single extracted fact persisted across turns."""
    key: str            # snake_case, e.g. preferred_coin
    value: str          # e.g. BTC
    source_turn: int    # turn index this was extracted from
    confidence: str = "high"  # high / medium / low


@dataclass
class ExecutionContext:
    session_id: str
    original_query: str
    complexity: TaskComplexity
    intent: str
    topics: List[str]
    plan: List[SubTask]
    user_clarifications: List[str] = field(default_factory=list)
    agent_results: List[AgentResult] = field(default_factory=list)
    retry_count: int = 0
    codebook_entry_id: Optional[str] = None
