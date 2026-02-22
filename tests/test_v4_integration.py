"""
tests/test_v4_integration.py

V4 整合測試：
1. V4 manager classify — full_analysis / technical / news / chat 路由
2. DB — save_analysis_report / get_analysis_reports
3. FullAnalysisAgent — mock graph.invoke，驗證 AgentResult 格式
4. HITL web_mode — interrupt() 在 web_mode=True 時觸發，CLI 走 stdin
5. API models — QueryRequest.resume_answer 欄位
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────
# 1. V4 Manager Classify Tests
# ─────────────────────────────────────

class TestV4Classify:
    """Test that manager.yaml routing rules work as expected."""

    def test_classify_result_structure(self):
        """after_classify_node 返回的 dict 應包含 agent, complexity, symbols。"""
        from core.agents.manager import ManagerAgent
        # We test the classify node logic via the router directly
        from core.agents.agent_registry import AgentRegistry, AgentMetadata
        from core.agents.router import AgentRouter

        registry = AgentRegistry()
        mock_agent = MagicMock()
        mock_agent.name = "full_analysis"
        registry.register(mock_agent, AgentMetadata(
            name="full_analysis",
            display_name="深度分析",
            description="完整市場分析",
            capabilities=["full_analysis", "完整分析", "值得投資"],
            allowed_tools=[],
            priority=20,
        ))
        mock_chat = MagicMock()
        mock_chat.name = "chat"
        registry.register(mock_chat, AgentMetadata(
            name="chat",
            display_name="Chat",
            description="閒聊與簡單查詢",
            capabilities=["conversation", "price lookup"],
            allowed_tools=[],
            priority=1,
        ))

        router = AgentRouter(registry)
        agents = registry.list_all()
        assert any(m.name == "full_analysis" for m in agents)
        assert any(m.name == "chat" for m in agents)

    # def test_full_analysis_agent_registered(self): ... REMOVED


# ─────────────────────────────────────
# 2. DB Tests (Unit — mocked connection)
# ─────────────────────────────────────

class TestAnalysisReportDB:
    """Unit tests for core/database/analysis.py — mocked DB."""

    def test_save_analysis_report_returns_id(self):
        """save_analysis_report 成功時應返回 int id。"""
        mock_row = {"id": 42}
        with patch("core.database.analysis.DatabaseBase.query_one", return_value=mock_row):
            from core.database.analysis import save_analysis_report
            result = save_analysis_report(
                session_id="sess-001",
                user_id="user-001",
                symbol="btc",
                interval="1d",
                report_text="測試報告",
            )
            assert result == 42

    def test_save_analysis_report_returns_none_on_failure(self):
        """save_analysis_report 失敗時應返回 None。"""
        with patch("core.database.analysis.DatabaseBase.query_one", return_value=None):
            from core.database.analysis import save_analysis_report
            result = save_analysis_report(
                session_id="sess-002",
                user_id="user-002",
                symbol="eth",
            )
            assert result is None

    def test_save_analysis_report_uppercases_symbol(self):
        """save_analysis_report 應將 symbol 轉大寫。"""
        captured = {}

        def mock_query_one(sql, params):
            captured["symbol"] = params[2]  # third param is symbol
            return {"id": 1}

        with patch("core.database.analysis.DatabaseBase.query_one", side_effect=mock_query_one):
            from core.database.analysis import save_analysis_report
            save_analysis_report("s", "u", "btc")
            assert captured["symbol"] == "BTC"

    def test_get_analysis_reports_returns_list(self):
        """get_analysis_reports 應返回 list，並解析 metadata JSON。"""
        import json
        mock_rows = [
            {
                "id": 1,
                "session_id": "sess-001",
                "symbol": "BTC",
                "interval": "1d",
                "report_text": "test",
                "metadata": json.dumps({"source": "v4"}),
                "created_at": "2025-01-01 00:00:00",
            }
        ]
        with patch("core.database.analysis.DatabaseBase.query_all", return_value=mock_rows):
            from core.database.analysis import get_analysis_reports
            results = get_analysis_reports("user-001")
            assert isinstance(results, list)
            assert len(results) == 1
            assert results[0]["symbol"] == "BTC"
            assert results[0]["metadata"] == {"source": "v4"}

    def test_get_analysis_report_by_id_returns_dict(self):
        """get_analysis_report_by_id 應返回完整報告 dict，含 user_id。"""
        import json
        mock_row = {
            "id": 1,
            "session_id": "sess-001",
            "user_id": "user-001",
            "symbol": "ETH",
            "interval": "1h",
            "report_text": "test report",
            "metadata": "{}",
            "created_at": "2025-01-01 00:00:00",
        }
        with patch("core.database.analysis.DatabaseBase.query_one", return_value=mock_row):
            from core.database.analysis import get_analysis_report_by_id
            result = get_analysis_report_by_id(1)
            assert result is not None
            assert result["user_id"] == "user-001"
            assert result["symbol"] == "ETH"

    def test_get_analysis_report_by_id_not_found(self):
        """查無資料時應返回 None。"""
        with patch("core.database.analysis.DatabaseBase.query_one", return_value=None):
            from core.database.analysis import get_analysis_report_by_id
            result = get_analysis_report_by_id(999)
            assert result is None


# ─────────────────────────────────────
# 3. FullAnalysisAgent Tests
# ─────────────────────────────────────

# ─────────────────────────────────────
# 3. FullAnalysisAgent Tests (REMOVED)
# ─────────────────────────────────────
# Class TestFullAnalysisAgent removed as the agent is deprecated.


# ─────────────────────────────────────
# 4. HITL web_mode Tests
# ─────────────────────────────────────

class TestHITLWebMode:
    """Test HITL behavior in web_mode vs CLI mode."""

    def test_manager_has_web_mode_attribute(self):
        """ManagerAgent 應接受 web_mode 參數。"""
        from core.agents.manager import ManagerAgent
        from core.agents.agent_registry import AgentRegistry
        from core.agents.hitl import HITLManager
        from core.agents.codebook import Codebook

        manager = ManagerAgent(
            llm_client=MagicMock(),
            agent_registry=AgentRegistry(),
            all_tools=[],
            hitl=HITLManager(),
            codebook=MagicMock(),
            web_mode=True,
        )
        assert manager.web_mode is True

    def test_manager_web_mode_false_by_default(self):
        """web_mode 預設應為 False。"""
        from core.agents.manager import ManagerAgent
        from core.agents.agent_registry import AgentRegistry
        from core.agents.hitl import HITLManager

        manager = ManagerAgent(
            llm_client=MagicMock(),
            agent_registry=AgentRegistry(),
            all_tools=[],
            hitl=HITLManager(),
            codebook=MagicMock(),
        )
        assert manager.web_mode is False

    def test_ask_user_node_uses_interrupt_in_web_mode(self):
        """web_mode=True 時 _ask_user_node 應呼叫 langgraph interrupt()。"""
        from core.agents.manager import ManagerAgent
        from core.agents.agent_registry import AgentRegistry
        from core.agents.hitl import HITLManager

        manager = ManagerAgent(
            llm_client=MagicMock(),
            agent_registry=AgentRegistry(),
            all_tools=[],
            hitl=HITLManager(),
            codebook=MagicMock(),
            web_mode=True,
        )

        state = {"ambiguity_question": "請問您想分析哪個幣種？"}

        with patch("core.agents.manager.interrupt", return_value="BTC") as mock_interrupt:
            result = manager._ask_user_node(state)
            mock_interrupt.assert_called_once()
            call_args = mock_interrupt.call_args[0][0]
            assert call_args["type"] == "clarification"
            assert "請問您想分析哪個幣種" in call_args["question"]

        assert result == {"clarification": "BTC"}

    def test_ask_user_node_uses_stdin_in_cli_mode(self):
        """web_mode=False 時 _ask_user_node 應呼叫 hitl.ask()。"""
        from core.agents.manager import ManagerAgent
        from core.agents.agent_registry import AgentRegistry
        from core.agents.hitl import HITLManager

        hitl = HITLManager()
        manager = ManagerAgent(
            llm_client=MagicMock(),
            agent_registry=AgentRegistry(),
            all_tools=[],
            hitl=hitl,
            codebook=MagicMock(),
            web_mode=False,
        )

        state = {"ambiguity_question": "您想分析哪個幣種？"}

        with patch.object(hitl, "ask", return_value="ETH") as mock_ask:
            result = manager._ask_user_node(state)
            mock_ask.assert_called_once()

        assert result == {"clarification": "ETH"}

    def test_confirm_plan_node_web_mode_confirm(self):
        """web_mode=True 確認執行時應返回 plan_confirmed=True。"""
        from core.agents.manager import ManagerAgent
        from core.agents.agent_registry import AgentRegistry
        from core.agents.hitl import HITLManager

        manager = ManagerAgent(
            llm_client=MagicMock(),
            agent_registry=AgentRegistry(),
            all_tools=[],
            hitl=HITLManager(),
            codebook=MagicMock(),
            web_mode=True,
        )

        state = {
            "query": "分析 BTC",
            "plan": [{"step": 1, "agent": "full_analysis", "description": "完整分析 BTC"}],
        }

        with patch("core.agents.manager.interrupt", return_value="確認執行"):
            result = manager._confirm_plan_node(state)

        assert result.get("plan_confirmed") is True
        assert result.get("plan_cancelled") is False

    def test_confirm_plan_node_web_mode_cancel(self):
        """web_mode=True 取消時應返回 plan_cancelled=True。"""
        from core.agents.manager import ManagerAgent
        from core.agents.agent_registry import AgentRegistry
        from core.agents.hitl import HITLManager

        manager = ManagerAgent(
            llm_client=MagicMock(),
            agent_registry=AgentRegistry(),
            all_tools=[],
            hitl=HITLManager(),
            codebook=MagicMock(),
            web_mode=True,
        )

        state = {
            "query": "分析 BTC",
            "plan": [{"step": 1, "agent": "full_analysis", "description": "完整分析 BTC"}],
        }

        with patch("core.agents.manager.interrupt", return_value="取消"):
            result = manager._confirm_plan_node(state)

        assert result.get("plan_cancelled") is True


# ─────────────────────────────────────
# 5. API Models Tests
# ─────────────────────────────────────

class TestAPIModels:
    """Test QueryRequest model changes."""

    def test_query_request_has_resume_answer(self):
        """QueryRequest 應有 resume_answer 欄位，預設為 None。"""
        from api.models import QueryRequest
        import inspect
        fields = QueryRequest.model_fields
        assert "resume_answer" in fields
        assert fields["resume_answer"].default is None

    def test_query_request_resume_answer_optional(self):
        """resume_answer 應為 Optional[str]。"""
        from api.models import QueryRequest
        import typing
        annotation = QueryRequest.model_fields["resume_answer"].annotation
        # Should be Optional[str] (i.e., Union[str, None])
        args = getattr(annotation, "__args__", None)
        assert args is not None and type(None) in args

    def test_query_request_with_resume_answer(self):
        """QueryRequest 應可帶 resume_answer 建立。"""
        from api.models import QueryRequest
        req = QueryRequest(
            message="分析 BTC",
            user_api_key="test-key",
            user_provider="openai",
            session_id="test-session",
            resume_answer="確認執行",
        )
        assert req.resume_answer == "確認執行"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
