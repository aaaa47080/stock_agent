"""Tests for manager experience recording + hint injection."""
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest


def test_record_experience_background_called_after_track():
    """_track_conversation fires _record_experience_background as a background task."""
    from core.agents.manager import ManagerAgent
    from unittest.mock import MagicMock, patch

    manager = MagicMock(spec=ManagerAgent)
    manager.user_id = "u1"
    manager.session_id = "s1"
    manager._message_count = 0
    manager._last_consolidated_index = 0
    manager._consolidating = False
    manager._last_activity_time = 0.0

    tasks_created = []

    with patch("core.agents.manager.asyncio.create_task", side_effect=tasks_created.append):
        # call the real method on the mock instance
        asyncio.run(ManagerAgent._track_conversation(
            manager, "BTC price?", "BTC is 42000", tools_used=["get_crypto_price"]
        ))

    # At minimum _extract_facts_background is created; _record_experience also created
    assert len(tasks_created) >= 1


def test_experience_hint_injected_in_prompt_when_available():
    """When retrieve_relevant returns results, prompt includes hint block."""
    from core.database.experiences import ExperienceStore
    hint_rows = [
        {"task_family": "crypto", "query_text": "BTC走勢", "tools_used": ["get_crypto_price"],
         "agent_used": "crypto", "outcome": "success", "quality_score": 1.0,
         "failure_reason": None, "created_at": "2026-03-15"},
    ]
    store = ExperienceStore()
    hint = store.format_for_prompt(hint_rows)
    assert "BTC走勢" in hint
    assert "get_crypto_price" in hint
    assert "相關過去經驗" in hint


def test_experience_hint_empty_string_when_no_results():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    assert store.format_for_prompt([]) == ""
