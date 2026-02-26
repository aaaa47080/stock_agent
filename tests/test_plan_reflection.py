"""Tests for Plan Reflection feature."""
from core.config import PLAN_REFLECTION_MAX_RETRIES


def test_plan_reflection_max_retries_exists():
    assert isinstance(PLAN_REFLECTION_MAX_RETRIES, int)
    assert PLAN_REFLECTION_MAX_RETRIES >= 1


from core.agents.manager import ManagerState


def test_manager_state_has_reflection_fields():
    hints = ManagerState.__annotations__
    assert "plan_reflection_count" in hints
    assert "plan_reflection_suggestion" in hints


from core.agents.prompt_registry import PromptRegistry


def test_reflect_plan_prompt_renders():
    result = PromptRegistry.render(
        "manager", "reflect_plan",
        query="INTC值得買嗎",
        history="（無）",
        topics="INTC",
        clarifications="無",
        plan_text="1. us_stock agent 查詢 INTC 股價",
        agents_info="us_stock: 美股分析",
        previous_suggestion="無",
    )
    assert "INTC" in result
    assert "approved" in result


import asyncio
from unittest.mock import MagicMock


def _make_manager():
    """Create a minimal ManagerAgent for unit testing."""
    from core.agents.manager import ManagerAgent
    llm = MagicMock()
    agent_registry = MagicMock()
    agent_registry.agents_info_for_prompt.return_value = "us_stock: 美股"
    agent_registry.list_all.return_value = []
    tool_registry = MagicMock()
    tool_registry.list_all_tools.return_value = []
    codebook = MagicMock()
    return ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        codebook=codebook,
    )


def _run(coro):
    return asyncio.run(coro)


def test_reflect_plan_approved_returns_approved_true():
    manager = _make_manager()
    manager.llm.invoke.return_value = MagicMock(
        content='{"approved": true, "reason": "計畫正確", "suggestion": null}'
    )
    state = {
        "session_id": "s1", "query": "INTC值得買嗎", "complexity": "complex",
        "intent": "us_stock", "topics": ["INTC"], "history": "無",
        "plan": [{"step": 1, "description": "查INTC", "agent": "us_stock",
                  "tool_hint": None, "status": "pending", "result": None, "context": None}],
        "plan_reflection_count": 0,
    }
    result = _run(manager._reflect_plan_node(state))
    assert result["plan_reflection_approved"] is True
    assert result.get("plan_reflection_suggestion") is None


def test_reflect_plan_rejected_increments_count_and_sets_suggestion():
    manager = _make_manager()
    manager.llm.invoke.return_value = MagicMock(
        content='{"approved": false, "reason": "標的錯誤", "suggestion": "應該查INTC而非AMD"}'
    )
    state = {
        "session_id": "s1", "query": "INTC值得買嗎", "complexity": "complex",
        "intent": "us_stock", "topics": ["INTC"], "history": "無",
        "plan": [{"step": 1, "description": "查AMD", "agent": "us_stock",
                  "tool_hint": None, "status": "pending", "result": None, "context": None}],
        "plan_reflection_count": 0,
    }
    result = _run(manager._reflect_plan_node(state))
    assert result["plan_reflection_approved"] is False
    assert result["plan_reflection_count"] == 1
    assert "INTC" in result["plan_reflection_suggestion"]


def test_reflect_plan_simple_query_skips_reflection():
    manager = _make_manager()
    state = {
        "session_id": "s1", "query": "BTC價格", "complexity": "simple",
        "intent": "crypto", "topics": ["BTC"], "history": "無",
        "plan": [{"step": 1, "description": "BTC價格", "agent": "crypto",
                  "tool_hint": None, "status": "pending", "result": None, "context": None}],
    }
    result = _run(manager._reflect_plan_node(state))
    assert result["plan_reflection_approved"] is True
    manager.llm.invoke.assert_not_called()


def test_reflect_plan_llm_error_auto_approves():
    manager = _make_manager()
    manager.llm.invoke.side_effect = Exception("LLM unavailable")
    state = {
        "session_id": "s1", "query": "INTC值得買嗎", "complexity": "complex",
        "intent": "us_stock", "topics": ["INTC"], "history": "無",
        "plan": [{"step": 1, "description": "查INTC", "agent": "us_stock",
                  "tool_hint": None, "status": "pending", "result": None, "context": None}],
        "plan_reflection_count": 0,
    }
    result = _run(manager._reflect_plan_node(state))
    assert result["plan_reflection_approved"] is True


def test_after_reflect_plan_approved_goes_to_confirm():
    manager = _make_manager()
    state = {"complexity": "complex", "plan_reflection_approved": True,
             "plan_reflection_count": 0, "plan_confirmed": False}
    assert manager._after_reflect_plan(state) == "confirm"


def test_after_reflect_plan_rejected_goes_to_re_plan():
    manager = _make_manager()
    state = {"complexity": "complex", "plan_reflection_approved": False,
             "plan_reflection_count": 1, "plan_confirmed": False}
    assert manager._after_reflect_plan(state) == "re_plan"


def test_after_reflect_plan_max_retries_fallback_to_confirm():
    from core.config import PLAN_REFLECTION_MAX_RETRIES
    manager = _make_manager()
    state = {"complexity": "complex", "plan_reflection_approved": False,
             "plan_reflection_count": PLAN_REFLECTION_MAX_RETRIES,
             "plan_confirmed": False}
    assert manager._after_reflect_plan(state) == "confirm"


def test_graph_has_reflect_plan_node():
    manager = _make_manager()
    nodes = list(manager.graph.get_graph().nodes.keys())
    assert "reflect_plan" in nodes


def test_graph_reflect_plan_connects_to_plan_on_re_plan():
    manager = _make_manager()
    graph = manager.graph.get_graph()
    edges = [(e.source, e.target) for e in graph.edges]
    # reflect_plan should be able to route back to plan
    targets_from_reflect = [t for (s, t) in edges if s == "reflect_plan"]
    assert "plan" in targets_from_reflect


def test_plan_node_passes_reflection_suggestion_to_prompt():
    """Verify _plan_node includes reflection_suggestion in its render call."""
    import inspect
    from core.agents.manager import ManagerAgent
    src = inspect.getsource(ManagerAgent._plan_node)
    assert "reflection_suggestion" in src
