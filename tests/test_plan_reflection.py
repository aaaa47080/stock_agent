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
