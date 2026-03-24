"""
Manager Agent - Multi-Agent Coordination Center (Facade)

This package contains the ManagerAgent class and its supporting modules,
refactored from the original monolithic manager.py for maintainability.

All external imports should continue to use:
    from core.agents.manager import ManagerAgent
    from core.agents.manager import MANAGER_GRAPH_RECURSION_LIMIT
    from core.agents.manager import MAX_GRAPH_TASKS
    from core.agents.manager import _get_history_for_prompt
"""

from core.agents.context_budget import (  # noqa: F401
    CONTEXT_CHAR_BUDGET,
    format_compact_state,
    history_exceeds_budget,
)
from core.agents.manager._main import (
    AGENT_EXECUTION_TIMEOUT,
    MANAGER_GRAPH_RECURSION_LIMIT,
    MAX_GRAPH_TASKS,
    MEMORY_CONSOLIDATION_THRESHOLD,
    MEMORY_IDLE_TIMEOUT,
    ManagerAgent,
    _background_tasks,
    _experience_store,
    _extract_model_name_for_manager,
    _get_checkpointer,
    _get_history_for_prompt,
    _per_user_checkpointer,
    _read_compact_for_manager,
    _run_background,
    _TracedGraph,
)
from core.agents.models import CLEAR_SENTINEL  # noqa: F401

__all__ = [
    "CLEAR_SENTINEL",
    "ManagerAgent",
    "MANAGER_GRAPH_RECURSION_LIMIT",
    "MAX_GRAPH_TASKS",
    "MEMORY_CONSOLIDATION_THRESHOLD",
    "MEMORY_IDLE_TIMEOUT",
    "AGENT_EXECUTION_TIMEOUT",
    "_TracedGraph",
    "_extract_model_name_for_manager",
    "_get_checkpointer",
    "_get_history_for_prompt",
    "_per_user_checkpointer",
    "_read_compact_for_manager",
    "_run_background",
    "_background_tasks",
    "_experience_store",
]
