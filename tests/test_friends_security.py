"""Tests for friends router security: user_id derived from token, not client."""


class TestFriendsRouterNoClientUserId:
    """Verify no endpoint accepts user_id from the client."""

    def test_search_users_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.search_users_endpoint)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names, (
            "search_users should not accept user_id from client"
        )

    def test_get_blocked_list_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_blocked_list)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_get_friends_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_friends)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_get_counts_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_counts)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_get_received_requests_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_received_requests)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_get_sent_requests_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_sent_requests)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_get_status_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_status)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_send_request_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.send_request)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_accept_request_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.accept_request)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_reject_request_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.reject_request)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_cancel_request_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.cancel_request)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_remove_friend_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.remove_friend_endpoint)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_block_user_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.block_user_endpoint)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_unblock_user_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.unblock_user_endpoint)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names

    def test_get_user_profile_no_user_id_param(self):
        import inspect

        import api.routers.friends as fr

        sig = inspect.signature(fr.get_user_profile)
        param_names = list(sig.parameters.keys())
        assert "user_id" not in param_names


class TestFriendsRouterUsesCurrentUser:
    """Verify endpoints use current_user internally."""

    def test_all_endpoints_have_current_user_dep(self):
        import inspect

        import api.routers.friends as fr

        for name in dir(fr):
            obj = getattr(fr, name)
            if callable(obj) and hasattr(obj, "__wrapped__"):
                continue
            if not inspect.iscoroutinefunction(obj):
                continue
            sig = inspect.signature(obj)
            if "current_user" in sig.parameters:
                param = sig.parameters["current_user"]
                assert param.default is not inspect.Parameter.empty, (
                    f"{name}: current_user should have a default (Depends)"
                )
