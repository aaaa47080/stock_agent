"""Tests for ExperienceStore — task_experiences + tool_execution_stats."""
from unittest.mock import patch, MagicMock


# ── record_experience ─────────────────────────────────────────────────────────

def test_record_experience_calls_db_execute():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    with patch("core.database.experiences.DatabaseBase.execute") as mock_exec:
        store.record_experience(
            user_id="u1", session_id="s1", task_family="crypto",
            query="BTC價格", tools_used=["get_crypto_price"],
            agent_used="crypto", outcome="success",
            quality_score=1.0, failure_reason=None, response_chars=500,
        )
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert "task_experiences" in call_args[0]


def test_record_experience_maps_quality_string_to_float():
    from core.database.experiences import _quality_to_float
    assert _quality_to_float("pass") == 1.0
    assert _quality_to_float("fail") == 0.0
    assert _quality_to_float(None) is None
    assert _quality_to_float(0.75) == 0.75


# ── record_tool_stat ──────────────────────────────────────────────────────────

def test_record_tool_stat_calls_db_execute():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    with patch("core.database.experiences.DatabaseBase.execute") as mock_exec:
        store.record_tool_stat(
            user_id="u1", tool_name="get_crypto_price",
            success=True, latency_ms=120, output_chars=300, error_type=None,
        )
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert "tool_execution_stats" in call_args[0]


# ── retrieve_relevant ─────────────────────────────────────────────────────────

def test_retrieve_relevant_returns_list():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    rows = [
        {"id": 1, "task_family": "crypto", "query_text": "BTC走勢",
         "tools_used": ["get_crypto_price"], "agent_used": "crypto",
         "outcome": "success", "quality_score": 1.0,
         "failure_reason": None, "created_at": "2026-03-18"},
    ]
    with patch("core.database.experiences.DatabaseBase.query_all", return_value=rows):
        results = store.retrieve_relevant(
            user_id="u1", task_family="crypto",
            query="BTC今天怎麼樣", llm=None,
        )
    assert isinstance(results, list)
    assert len(results) == 1


def test_retrieve_relevant_returns_empty_on_db_error():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    with patch("core.database.experiences.DatabaseBase.query_all", side_effect=Exception("DB down")):
        results = store.retrieve_relevant(
            user_id="u1", task_family="crypto", query="BTC", llm=None
        )
    assert results == []


# ── user isolation ────────────────────────────────────────────────────────────

def test_retrieve_relevant_filters_by_user_id():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    captured_params = {}
    def fake_query_all(sql, params):
        captured_params["params"] = params
        return []
    with patch("core.database.experiences.DatabaseBase.query_all", side_effect=fake_query_all):
        store.retrieve_relevant(user_id="u-specific", task_family="crypto", query="BTC", llm=None)
    assert "u-specific" in captured_params["params"]


def test_retrieve_relevant_rejects_null_user_id():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    results = store.retrieve_relevant(
        user_id=None, task_family="crypto", query="BTC", llm=None
    )
    assert results == []


# ── layer 3 LLM rerank skipped when < 2 candidates ───────────────────────────

def test_layer3_skipped_when_fewer_than_2_candidates():
    from core.database.experiences import ExperienceStore
    store = ExperienceStore()
    mock_llm = MagicMock()
    rows = [{"id": 1, "task_family": "crypto", "query_text": "BTC",
             "tools_used": [], "agent_used": "crypto", "outcome": "success",
             "quality_score": 1.0, "failure_reason": None, "created_at": "2026-03-18"}]
    with patch("core.database.experiences.DatabaseBase.query_all", return_value=rows):
        store.retrieve_relevant(user_id="u1", task_family="crypto", query="BTC", llm=mock_llm)
    mock_llm.invoke.assert_not_called()
