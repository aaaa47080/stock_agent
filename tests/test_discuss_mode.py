"""Tests for Discuss Mode — free-form Q&A after plan confirmation."""
from __future__ import annotations
import asyncio
from typing import get_type_hints
from unittest.mock import MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    return msg


def _make_mock_llm(response_content: str):
    """LLM that always returns the given JSON string."""
    llm = MagicMock()
    llm.invoke.return_value = _make_llm_response(response_content)
    return llm


def _make_mock_llm_fn(side_effect_fn):
    """LLM whose invoke() calls side_effect_fn(messages)."""
    llm = MagicMock()
    llm.invoke.side_effect = side_effect_fn
    return llm


def _make_manager_agent(mock_llm):
    """Create a minimal ManagerAgent with mocked dependencies."""
    from core.agents.manager import ManagerAgent

    agent_registry = MagicMock()
    agent_registry.agents_info_for_prompt.return_value = "us_stock: US stocks\nchat: General"
    agent_registry.list_all.return_value = [
        MagicMock(name="us_stock"), MagicMock(name="chat"), MagicMock(name="crypto")
    ]

    tool_registry = MagicMock()
    tool_registry.list_all_tools.return_value = []
    tool_registry.get.return_value = None

    codebook = MagicMock()
    codebook.find_similar_entries.return_value = []

    return ManagerAgent(
        llm_client=mock_llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        codebook=codebook,
        web_mode=True,
    )


# ── Task 1: ManagerState fields ──────────────────────────────────────────────

def test_manager_state_has_discuss_mode():
    from core.agents.manager import ManagerState
    hints = get_type_hints(ManagerState, include_extras=True)
    assert "discuss_mode" in hints


def test_manager_state_has_discuss_plan_snapshot():
    from core.agents.manager import ManagerState
    hints = get_type_hints(ManagerState, include_extras=True)
    assert "discuss_plan_snapshot" in hints


def test_manager_state_has_replan_request():
    from core.agents.manager import ManagerState
    hints = get_type_hints(ManagerState, include_extras=True)
    assert "replan_request" in hints


# ── Task 2: classify prompt + replan_request ─────────────────────────────────

def test_classify_prompt_has_replan_request_field():
    """classify prompt JSON schema must include replan_request."""
    from core.agents.prompt_registry import PromptRegistry
    rendered = PromptRegistry.render(
        "manager", "classify",
        query="依照前面討論的進行規劃",
        agents_info="us_stock: US stocks",
        tools_info="get_stock_price",
        history="先前討論了SMCI的股價",
    )
    assert "replan_request" in rendered


def test_classify_node_sets_replan_request_true():
    """_classify_node sets replan_request=True when LLM returns it."""
    mock_llm = _make_mock_llm(
        '{"complexity":"simple","intent":"us_stock","topics":["SMCI"],'
        '"symbols":{"us":"SMCI","tw":null,"crypto":null},"ambiguity_question":null,'
        '"replan_request":true}'
    )
    agent = _make_manager_agent(mock_llm)
    state = {"query": "依照前面討論的進行規劃", "history": "", "discuss_mode": True}
    result = asyncio.run(agent._classify_node(state))
    assert result.get("replan_request") is True
    assert result.get("discuss_mode") is False  # cleared when replan detected


def test_classify_node_clears_discuss_mode_on_replan():
    """When replan_request=True, _classify_node must clear discuss_mode."""
    mock_llm = _make_mock_llm(
        '{"complexity":"simple","intent":"us_stock","topics":["SMCI"],'
        '"symbols":{"us":"SMCI","tw":null,"crypto":null},"ambiguity_question":null,'
        '"replan_request":true}'
    )
    agent = _make_manager_agent(mock_llm)
    state = {"query": "開始分析", "history": "", "discuss_mode": True}
    result = asyncio.run(agent._classify_node(state))
    assert result.get("discuss_mode") is False


# ── Task 3: _confirm_plan_node intent detection ───────────────────────────────

def test_confirm_plan_routes_question_to_discuss():
    """When user types a question, _detect_confirm_intent returns 'question'."""
    mock_llm = _make_mock_llm("question")
    agent = _make_manager_agent(mock_llm)
    result = asyncio.run(agent._detect_confirm_intent(
        "目前價格多少？",
        "步驟1: [us_stock] 查詢SMCI"
    ))
    assert result == "question"


def test_confirm_plan_routes_modify_to_negotiate():
    """When user types a modification request, intent is 'modify'."""
    mock_llm = _make_mock_llm("modify")
    agent = _make_manager_agent(mock_llm)
    result = asyncio.run(agent._detect_confirm_intent(
        "移除第3步",
        "步驟1: [us_stock] 查詢SMCI"
    ))
    assert result == "modify"


# ── Task 4: discuss prompt + _discuss_node ────────────────────────────────────

def test_discuss_prompt_renders():
    """discuss prompt must render with all required placeholders."""
    from core.agents.prompt_registry import PromptRegistry
    result = PromptRegistry.render(
        "manager", "discuss",
        query="SMCI適合投資嗎",
        plan_text="步驟1: [us_stock] 查詢SMCI",
        history="",
        tools_info="get_stock_price, get_us_stock_news",
        tool_results="無",
        question="目前價格多少？",
    )
    assert "SMCI" in result
    assert "目前價格多少" in result


def test_discuss_node_keeps_discuss_mode_true():
    """_discuss_node must return discuss_mode=True."""
    agent = _make_manager_agent(_make_mock_llm('{"answer": "SMCI目前$45", "tool_call": null}'))
    state = {
        "query": "SMCI適合投資嗎",
        "discuss_mode": True,
        "discuss_plan_snapshot": [{"step": 1, "description": "查詢SMCI", "agent": "us_stock"}],
        "plan": [{"step": 1, "description": "查詢SMCI", "agent": "us_stock"}],
        "discussion_question": "目前價格多少？",
        "history": "",
    }
    result = asyncio.run(agent._discuss_node(state))
    assert result.get("discuss_mode") is True


def test_discuss_node_preserves_plan():
    """_discuss_node must NOT set plan_confirmed=False or clear the plan."""
    agent = _make_manager_agent(_make_mock_llm('{"answer": "BTC $68000", "tool_call": null}'))
    state = {
        "query": "BTC適合投資嗎",
        "discuss_mode": True,
        "discuss_plan_snapshot": [{"step": 1, "description": "查詢BTC", "agent": "crypto"}],
        "plan": [{"step": 1, "description": "查詢BTC", "agent": "crypto"}],
        "discussion_question": "現在多少錢？",
        "history": "",
    }
    result = asyncio.run(agent._discuss_node(state))
    assert "plan_confirmed" not in result  # must not touch plan_confirmed


def test_discuss_node_calls_tool_when_needed():
    """When LLM returns tool_call, _discuss_node executes the tool and re-calls itself."""
    call_count = [0]

    def llm_side_effect(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_llm_response('{"answer": "", "tool_call": {"name": "get_stock_price", "args": {"ticker": "SMCI"}}}')
        return _make_llm_response('{"answer": "SMCI目前$45.23", "tool_call": null}')

    agent = _make_manager_agent(_make_mock_llm_fn(llm_side_effect))
    mock_tool = MagicMock()
    mock_tool.handler.invoke.return_value = {"price": 45.23, "ticker": "SMCI"}
    agent.tool_registry.get = MagicMock(return_value=mock_tool)

    state = {
        "query": "SMCI適合投資嗎", "discuss_mode": True,
        "discuss_plan_snapshot": [], "plan": [],
        "discussion_question": "目前價格多少？", "history": "",
    }
    result = asyncio.run(agent._discuss_node(state))
    assert "SMCI" in result.get("final_response", "")
    assert call_count[0] == 2  # LLM called twice


def test_discuss_node_uses_plan_context():
    """_discuss_node must include plan_snapshot in the context sent to LLM."""
    captured_prompt = []

    def llm_side_effect(messages):
        captured_prompt.append(messages[0].content)
        return _make_llm_response('{"answer": "計畫包含4個步驟", "tool_call": null}')

    agent = _make_manager_agent(_make_mock_llm_fn(llm_side_effect))
    state = {
        "query": "SMCI值得買嗎", "discuss_mode": True,
        "discuss_plan_snapshot": [
            {"step": 1, "description": "查詢SMCI股價", "agent": "us_stock"},
            {"step": 2, "description": "分析技術指標", "agent": "us_stock"},
        ],
        "plan": [],
        "discussion_question": "你這樣排有什麼優點？",
        "history": "",
    }
    asyncio.run(agent._discuss_node(state))
    assert "查詢SMCI股價" in captured_prompt[0]


# ── Task 5: _after_classify routing ──────────────────────────────────────────

def test_after_classify_routes_discuss_mode_to_discuss():
    """When discuss_mode=True and no replan_request, route to discuss."""
    agent = _make_manager_agent(MagicMock())
    state = {
        "discuss_mode": True,
        "replan_request": False,
        "complexity": "simple",
        "intent": "us_stock",
        "plan_confirmed": False,
    }
    result = agent._after_classify(state)
    assert result == "discuss"


def test_after_classify_routes_replan_to_normal():
    """When discuss_mode=False (cleared by replan), route normally."""
    agent = _make_manager_agent(MagicMock())
    state = {
        "discuss_mode": False,
        "replan_request": True,
        "complexity": "complex",
        "intent": "us_stock",
        "plan_confirmed": False,
    }
    result = agent._after_classify(state)
    assert result == "plan"  # normal complex routing


def test_graph_has_classify_to_discuss_edge():
    """Graph must support classify → discuss routing."""
    agent = _make_manager_agent(MagicMock())
    graph = agent.graph
    assert "discuss" in graph.get_graph().nodes


# ── Task 6: plan prompt discussion context ────────────────────────────────────

def test_plan_prompt_references_discussion():
    """plan prompt must mention discussion context when discuss_mode was active."""
    from core.agents.prompt_registry import PromptRegistry
    rendered = PromptRegistry.render(
        "manager", "plan",
        query="SMCI適合投資嗎",
        agent="us_stock",
        topics="SMCI",
        clarifications="無",
        past_experience="無",
        agents_info="us_stock: US stocks",
        tools_info="get_stock_price",
        research_summary="無",
        research_clarifications="無",
        reflection_suggestion="無",
        discussion_summary="用戶已了解SMCI目前股價為$45，並問過計畫設計的優點",
    )
    assert "討論" in rendered or "discussion" in rendered.lower()


# ── Task 7: classify guard ────────────────────────────────────────────────────

def test_classify_node_does_not_clear_discuss_mode_without_replan():
    """_classify_node must not return discuss_mode=False unless replan_request=True."""
    mock_llm = _make_mock_llm(
        '{"complexity":"simple","intent":"us_stock","topics":["SMCI"],'
        '"symbols":{"us":"SMCI","tw":null,"crypto":null},"ambiguity_question":null,'
        '"replan_request":false}'
    )
    agent = _make_manager_agent(mock_llm)
    state = {"query": "目前RSI多少？", "history": "", "discuss_mode": True}
    result = asyncio.run(agent._classify_node(state))
    # Must NOT set discuss_mode=False
    assert result.get("discuss_mode") is not False
