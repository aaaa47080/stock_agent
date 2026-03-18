"""Tests for context_budget module."""
from dataclasses import dataclass
from typing import Optional


# ── fixtures ─────────────────────────────────────────────────────────────────

def _make_compact(goal="查詢BTC", progress="取得價格", open_q="", next_s=""):
    from core.agents.context_budget import CompactPrompt
    return CompactPrompt(goal=goal, progress=progress,
                         open_questions=open_q, next_steps=next_s)


# ── budget check ─────────────────────────────────────────────────────────────

def test_short_history_under_budget():
    from core.agents.context_budget import history_exceeds_budget
    assert history_exceeds_budget("用戶: hi\n助手: hello") is False


def test_long_history_over_budget():
    from core.agents.context_budget import history_exceeds_budget, CONTEXT_CHAR_BUDGET
    long_history = "x" * (CONTEXT_CHAR_BUDGET + 1)
    assert history_exceeds_budget(long_history) is True


def test_empty_history_under_budget():
    from core.agents.context_budget import history_exceeds_budget
    assert history_exceeds_budget("") is False


# ── compact state formatting ──────────────────────────────────────────────────

def test_format_compact_state_includes_all_sections():
    from core.agents.context_budget import format_compact_state
    cp = _make_compact(goal="查詢BTC", progress="已取得價格", open_q="技術指標待確認", next_s="查詢RSI")
    result = format_compact_state(cp)
    assert "查詢BTC" in result
    assert "已取得價格" in result
    assert "技術指標待確認" in result
    assert "查詢RSI" in result


def test_format_compact_state_omits_empty_sections():
    from core.agents.context_budget import format_compact_state
    cp = _make_compact(goal="查詢BTC", progress="完成", open_q="", next_s="")
    result = format_compact_state(cp)
    assert "Open Questions" not in result
    assert "Next Steps" not in result


# ── manager integration ───────────────────────────────────────────────────────

def test_manager_uses_compact_state_when_over_budget():
    """When history > budget and compact state exists, manager returns formatted compact."""
    from unittest.mock import MagicMock, patch
    from core.agents.context_budget import CONTEXT_CHAR_BUDGET, CompactPrompt, format_compact_state

    long_history = "用戶: " + "x" * CONTEXT_CHAR_BUDGET

    mock_compact = CompactPrompt(
        goal="查詢BTC", progress="已完成", open_questions="", next_steps=""
    )

    with patch("core.agents.manager.history_exceeds_budget", return_value=True):
        with patch("core.agents.manager._read_compact_for_manager", return_value=mock_compact):
            from core.agents.manager import _get_history_for_prompt
            result = _get_history_for_prompt(long_history, user_id="u1", session_id="s1")

    assert "查詢BTC" in result
    assert "x" * 10 not in result  # raw history NOT passed through


def test_manager_uses_raw_history_when_under_budget():
    from unittest.mock import patch
    from core.agents.context_budget import CONTEXT_CHAR_BUDGET

    short_history = "用戶: hi\n助手: hello"

    with patch("core.agents.manager.history_exceeds_budget", return_value=False):
        from core.agents.manager import _get_history_for_prompt
        result = _get_history_for_prompt(short_history, user_id="u1", session_id="s1")

    assert result == short_history


def test_manager_falls_back_to_truncated_when_no_compact_state():
    from unittest.mock import patch
    from core.agents.context_budget import CONTEXT_CHAR_BUDGET

    long_history = "用戶: " + "x" * CONTEXT_CHAR_BUDGET

    with patch("core.agents.manager.history_exceeds_budget", return_value=True):
        with patch("core.agents.manager._read_compact_for_manager", return_value=None):
            from core.agents.manager import _get_history_for_prompt
            result = _get_history_for_prompt(long_history, user_id="u1", session_id="s1")

    # fallback: returns truncated to budget
    assert len(result) <= CONTEXT_CHAR_BUDGET
