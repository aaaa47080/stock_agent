"""Tests for all ORM repositories — structure, signatures, and patterns."""
import inspect
import pytest


class TestFriendsRepoStructure:
    """Verify friends_repo has all expected methods."""

    REQUIRED_METHODS = [
        "search_users",
        "get_friends_list",
        "get_friendship_status",
        "send_friend_request",
        "accept_friend_request",
        "reject_friend_request",
        "remove_friend",
        "block_user",
        "unblock_user",
        "get_blocked_users",
        "is_friend",
        "is_blocked",
        "get_friends_count",
        "get_pending_count",
    ]

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        from core.orm.friends_repo import friends_repo
        assert hasattr(friends_repo, method), f"Missing method: {method}"

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_is_async(self, method):
        from core.orm.friends_repo import friends_repo
        func = getattr(friends_repo, method)
        assert inspect.iscoroutinefunction(func), f"{method} is not async"

    def test_friends_repo_singleton(self):
        from core.orm.friends_repo import friends_repo
        assert friends_repo is not None


class TestNotificationsRepoStructure:
    """Verify notifications_repo has all expected methods."""

    REQUIRED_METHODS = [
        "create_notification",
        "get_notifications",
        "get_unread_count",
        "mark_notification_as_read",
        "mark_all_as_read",
        "delete_notification",
    ]

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        from core.orm.notifications_repo import notifications_repo
        assert hasattr(notifications_repo, method), f"Missing method: {method}"

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_is_async(self, method):
        from core.orm.notifications_repo import notifications_repo
        func = getattr(notifications_repo, method)
        assert inspect.iscoroutinefunction(func), f"{method} is not async"


class TestForumRepoStructure:
    """Verify forum_repo has all expected methods."""

    REQUIRED_METHODS = [
        "get_boards",
        "get_board_by_slug",
        "get_post_by_id",
        "get_posts",
        "create_post",
        "update_post",
        "delete_post",
        "add_comment",
        "get_comments",
        "create_tip",
        "get_tips_sent",
        "get_tips_received",
    ]

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        from core.orm.forum_repo import forum_repo
        assert hasattr(forum_repo, method), f"Missing method: {method}"

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_is_async(self, method):
        from core.orm.forum_repo import forum_repo
        func = getattr(forum_repo, method)
        assert inspect.iscoroutinefunction(func), f"{method} is not async"


class TestMessagesRepoStructure:
    """Verify messages_repo has all expected methods."""

    REQUIRED_METHODS = [
        "get_or_create_conversation",
        "get_conversations",
        "get_conversation_by_id",
        "send_message",
        "get_messages",
        "mark_as_read",
        "get_unread_count",
        "validate_message_send",
    ]

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        from core.orm.messages_repo import messages_repo
        assert hasattr(messages_repo, method), f"Missing method: {method}"

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_is_async(self, method):
        from core.orm.messages_repo import messages_repo
        func = getattr(messages_repo, method)
        assert inspect.iscoroutinefunction(func), f"{method} is not async"


class TestRepoMethodSignatures:
    """Verify method signatures match expected parameters."""

    def test_get_friends_list_has_pagination(self):
        from core.orm.friends_repo import friends_repo
        sig = inspect.signature(friends_repo.get_friends_list)
        assert "limit" in sig.parameters
        assert "offset" in sig.parameters

    def test_get_notifications_has_pagination(self):
        from core.orm.notifications_repo import notifications_repo
        sig = inspect.signature(notifications_repo.get_notifications)
        assert "limit" in sig.parameters
        assert "offset" in sig.parameters

    def test_get_posts_has_pagination(self):
        from core.orm.forum_repo import forum_repo
        sig = inspect.signature(forum_repo.get_posts)
        assert "limit" in sig.parameters
        assert "offset" in sig.parameters

    def test_get_comments_has_pagination(self):
        from core.orm.forum_repo import forum_repo
        sig = inspect.signature(forum_repo.get_comments)
        assert "limit" in sig.parameters
        assert "offset" in sig.parameters

    def test_get_conversations_has_pagination(self):
        from core.orm.messages_repo import messages_repo
        sig = inspect.signature(messages_repo.get_conversations)
        assert "limit" in sig.parameters
        assert "offset" in sig.parameters

    def test_create_notification_params(self):
        from core.orm.notifications_repo import notifications_repo
        sig = inspect.signature(notifications_repo.create_notification)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "notification_type" in params
        assert "title" in params
        assert "body" in params

    def test_send_message_params(self):
        from core.orm.messages_repo import messages_repo
        sig = inspect.signature(messages_repo.send_message)
        params = list(sig.parameters.keys())
        assert "from_user_id" in params
        assert "to_user_id" in params
        assert "content" in params

    def test_create_post_params(self):
        from core.orm.forum_repo import forum_repo
        sig = inspect.signature(forum_repo.create_post)
        params = list(sig.parameters.keys())
        assert "board_id" in params
        assert "user_id" in params
        assert "category" in params
        assert "title" in params
        assert "content" in params

    def test_create_tip_params(self):
        from core.orm.forum_repo import forum_repo
        sig = inspect.signature(forum_repo.create_tip)
        params = list(sig.parameters.keys())
        assert "post_id" in params
        assert "from_user_id" in params
        assert "to_user_id" in params
        assert "amount" in params
        assert "tx_hash" in params


class TestReposUseSessionParameter:
    """Verify all repo methods accept optional session parameter."""

    def test_friends_repo_accepts_session(self):
        from core.orm.friends_repo import friends_repo
        sig = inspect.signature(friends_repo.get_friends_list)
        assert "session" in sig.parameters

    def test_forum_repo_accepts_session(self):
        from core.orm.forum_repo import forum_repo
        sig = inspect.signature(forum_repo.get_posts)
        assert "session" in sig.parameters

    def test_messages_repo_accepts_session(self):
        from core.orm.messages_repo import messages_repo
        sig = inspect.signature(messages_repo.get_conversations)
        assert "session" in sig.parameters

    def test_notifications_repo_accepts_session(self):
        from core.orm.notifications_repo import notifications_repo
        sig = inspect.signature(notifications_repo.get_notifications)
        assert "session" in sig.parameters


class TestOrmPackageExports:
    """Verify the ORM package exports all key items."""

    def test_exports_models(self):
        from core.orm import (
            Base, User, Board, Post, ForumComment, Tip,
            Friendship, Notification, DmConversation, DmMessage,
            SystemConfig, PriceAlert, MembershipPayment,
        )
        assert Base is not None

    def test_exports_session(self):
        from core.orm import get_async_session, get_engine, close_async_engine
        assert callable(get_async_session)
        assert callable(get_engine)

    def test_exports_repos(self):
        from core.orm import user_repo
        assert user_repo is not None

    def test_exports_repo_modules(self):
        from core.orm import friends_repo
        from core.orm.notifications_repo import notifications_repo
        from core.orm.forum_repo import forum_repo
        from core.orm.messages_repo import messages_repo
        assert friends_repo is not None
        assert notifications_repo is not None
        assert forum_repo is not None
        assert messages_repo is not None
