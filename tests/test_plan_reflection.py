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
