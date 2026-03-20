"""Tests for Phase 3 performance improvements."""

import inspect

import pytest


class TestPaginationAdded:
    """Verify pagination parameters on list endpoints."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "list_comments",
        ],
    )
    def test_comments_has_limit_offset(self, func_name):
        import api.routers.forum.comments as mod

        func = getattr(mod, func_name, None)
        assert func is not None
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert "limit" in params, f"{func_name} missing 'limit' param"
        assert "offset" in params, f"{func_name} missing 'offset' param"

    @pytest.mark.parametrize(
        "func_name",
        [
            "get_user_sessions",
        ],
    )
    def test_sessions_has_limit_offset(self, func_name):
        import api.routers.analysis as mod

        func = getattr(mod, func_name, None)
        assert func is not None
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert "limit" in params, f"{func_name} missing 'limit' param"
        assert "offset" in params, f"{func_name} missing 'offset' param"

    @pytest.mark.parametrize(
        "func_name",
        [
            "get_my_sent_tips",
            "get_my_received_tips",
            "get_my_payments",
        ],
    )
    def test_me_endpoints_have_offset(self, func_name):
        import api.routers.forum.me as mod

        func = getattr(mod, func_name, None)
        assert func is not None
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert "offset" in params, f"{func_name} missing 'offset' param"

    @pytest.mark.parametrize(
        "func_name",
        [
            "get_sent_tips",
            "get_received_tips",
        ],
    )
    def test_tips_endpoints_have_offset(self, func_name):
        import api.routers.forum.tips as mod

        func = getattr(mod, func_name, None)
        assert func is not None
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert "offset" in params, f"{func_name} missing 'offset' param"

    @pytest.mark.parametrize(
        "func_name",
        [
            "list_my_reports",
            "get_my_activity_logs",
        ],
    )
    def test_governance_endpoints_have_offset(self, func_name):
        import api.routers.governance as mod

        func = getattr(mod, func_name, None)
        assert func is not None
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert "offset" in params, f"{func_name} missing 'offset' param"

    @pytest.mark.parametrize(
        "func_name",
        [
            "get_blocked_list",
            "get_received_requests",
            "get_sent_requests",
        ],
    )
    def test_friends_endpoints_have_limit(self, func_name):
        import api.routers.friends as mod

        func = getattr(mod, func_name, None)
        assert func is not None
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert "limit" in params, f"{func_name} missing 'limit' param"


class TestDbLayerPagination:
    """Verify DB layer functions accept limit/offset."""

    def test_get_comments_accepts_limit_offset(self):
        import core.database.forum as mod

        sig = inspect.signature(mod.get_comments)
        params = list(sig.parameters.keys())
        assert "limit" in params
        assert "offset" in params

    def test_get_comments_has_limit_offset_sql(self):
        import core.database.forum as mod

        src = inspect.getsource(mod.get_comments)
        assert "LIMIT" in src
        assert "OFFSET" in src

    def test_get_tips_sent_accepts_offset(self):
        import core.database.forum as mod

        sig = inspect.signature(mod.get_tips_sent)
        assert "offset" in sig.parameters

    def test_get_tips_received_accepts_offset(self):
        import core.database.forum as mod

        sig = inspect.signature(mod.get_tips_received)
        assert "offset" in sig.parameters

    def test_get_user_payment_history_accepts_offset(self):
        import core.database.forum as mod

        sig = inspect.signature(mod.get_user_payment_history)
        assert "offset" in sig.parameters

    def test_get_sessions_accepts_offset(self):
        import core.database.chat as mod

        sig = inspect.signature(mod.get_sessions)
        assert "offset" in sig.parameters

    def test_get_user_reports_accepts_offset(self):
        import core.database.governance.reports as mod

        sig = inspect.signature(mod.get_user_reports)
        assert "offset" in sig.parameters

    def test_get_blocked_users_accepts_limit(self):
        import core.database.friends as mod

        sig = inspect.signature(mod.get_blocked_users)
        assert "limit" in sig.parameters

    def test_get_pending_requests_received_accepts_limit(self):
        import core.database.friends as mod

        sig = inspect.signature(mod.get_pending_requests_received)
        assert "limit" in sig.parameters

    def test_get_pending_requests_sent_accepts_limit(self):
        import core.database.friends as mod

        sig = inspect.signature(mod.get_pending_requests_sent)
        assert "limit" in sig.parameters


class TestPoolTuning:
    """Verify connection pool is configurable via environment variables."""

    def test_pool_size_uses_env_vars(self):
        import core.database.connection as mod

        src = inspect.getsource(mod)
        assert "DB_MIN_POOL_SIZE" in src
        assert "DB_MAX_POOL_SIZE" in src

    def test_connect_timeout_uses_env_var(self):
        import core.database.connection as mod

        src = inspect.getsource(mod)
        assert "DB_CONNECT_TIMEOUT" in src

    def test_statement_timeout_uses_env_var(self):
        import core.database.connection as mod

        src = inspect.getsource(mod)
        assert "DB_STATEMENT_TIMEOUT" in src
        assert "statement_timeout" in src

    def test_pool_defaults_are_sensible(self):
        import core.database.connection as mod

        assert 1 <= mod.MIN_POOL_SIZE <= 10
        assert 5 <= mod.MAX_POOL_SIZE <= 100
        assert mod.MIN_POOL_SIZE <= mod.MAX_POOL_SIZE
