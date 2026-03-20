"""Tests for Phase 5 ORM infrastructure and models."""
import inspect
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


class TestOrmSessionModule:
    """Verify ORM session module is properly structured."""

    def test_session_module_exists(self):
        from core.orm.session import get_async_session, get_engine, close_async_engine
        assert callable(get_async_session)
        assert callable(get_engine)
        assert callable(close_async_engine)

    def test_get_async_session_is_async_generator(self):
        from core.orm.session import get_async_session
        assert inspect.isasyncgenfunction(get_async_session)

    def test_close_async_engine_is_async(self):
        from core.orm.session import close_async_engine
        assert inspect.iscoroutinefunction(close_async_engine)

    def test_resolve_async_url_handles_env_vars(self):
        from core.orm.session import _resolve_async_url
        import os

        with patch.dict(os.environ, {
            "POSTGRESQL_HOST": "localhost",
            "POSTGRESQL_USER": "test",
            "POSTGRESQL_PASSWORD": "pass",
            "POSTGRESQL_DB": "mydb",
            "POSTGRESQL_PORT": "5432",
        }, clear=False):
            url = _resolve_async_url()
            assert url is not None
            assert "postgresql+asyncpg://" in url
            assert "localhost" in url
            assert "mydb" in url

    def test_resolve_async_url_uses_database_url_fallback(self):
        from core.orm.session import _resolve_async_url
        import os

        env = {k: v for k, v in os.environ.items() if not k.startswith("POSTGRESQL")}
        env["DATABASE_URL"] = "postgresql://user:pass@host:5432/db?sslmode=require&channel_binding=require"

        with patch.dict(os.environ, env, clear=True):
            url = _resolve_async_url()
            assert url is not None
            assert "postgresql+asyncpg://" in url
            assert "ssl=require" in url
            assert "sslmode" not in url
            assert "channel_binding" not in url

    def test_resolve_async_url_returns_none_when_no_config(self):
        from core.orm.session import _resolve_async_url
        import os

        with patch.dict(os.environ, {}, clear=True):
            url = _resolve_async_url()
            assert url is None


class TestOrmModels:
    """Verify ORM models are properly defined."""

    def test_user_model_has_correct_columns(self):
        from core.orm.models import User
        columns = {c.name: c.type for c in User.__table__.columns}
        assert "user_id" in columns
        assert "username" in columns
        assert "membership_tier" in columns
        assert "is_active" in columns
        assert "role" in columns

    def test_user_model_primary_key(self):
        from core.orm.models import User
        pk = User.__table__.primary_key
        assert len(pk.columns) == 1
        assert pk.columns[0].name == "user_id"

    def test_membership_payment_amount_is_numeric(self):
        from core.orm.models import MembershipPayment
        col = MembershipPayment.__table__.columns["amount"]
        assert "NUMERIC" in str(col.type).upper() or "Numeric" in str(col.type)

    def test_tip_amount_is_numeric(self):
        from core.orm.models import Tip
        col = Tip.__table__.columns["amount"]
        assert "NUMERIC" in str(col.type).upper() or "Numeric" in str(col.type)

    def test_post_has_board_fk(self):
        from core.orm.models import Post
        fk_names = [fk.target_fullname for fk in Post.__table__.foreign_keys]
        assert "boards.id" in fk_names

    def test_comment_has_post_fk(self):
        from core.orm.models import ForumComment
        fk_names = [fk.target_fullname for fk in ForumComment.__table__.foreign_keys]
        assert "posts.id" in fk_names

    def test_tip_has_post_fk(self):
        from core.orm.models import Tip
        fk_names = [fk.target_fullname for fk in Tip.__table__.foreign_keys]
        assert "posts.id" in fk_names

    def test_notification_on_delete_cascade(self):
        from core.orm.models import Notification
        for fk in Notification.__table__.foreign_keys:
            if fk.target_fullname == "users.user_id":
                assert fk.ondelete == "CASCADE"

    def test_price_alert_target_is_numeric(self):
        from core.orm.models import PriceAlert
        col = PriceAlert.__table__.columns["target"]
        assert "NUMERIC" in str(col.type).upper() or "Numeric" in str(col.type)

    @pytest.mark.parametrize("model_name,table_name", [
        ("User", "users"),
        ("Board", "boards"),
        ("Post", "posts"),
        ("ForumComment", "forum_comments"),
        ("Tip", "tips"),
        ("Friendship", "friendships"),
        ("Notification", "notifications"),
        ("DmConversation", "dm_conversations"),
        ("DmMessage", "dm_messages"),
        ("SystemConfig", "system_config"),
        ("PriceAlert", "price_alerts"),
        ("MembershipPayment", "membership_payments"),
    ])
    def test_model_table_name(self, model_name, table_name):
        from core.orm import models
        model = getattr(models, model_name)
        assert model.__tablename__ == table_name


class TestUserRepository:
    """Test UserRepository without database (mock-based)."""

    def test_user_to_dict_converts_correctly(self):
        from core.orm.repositories import _user_to_dict
        from core.orm.models import User

        user = User(
            user_id="test-123",
            username="TestUser",
            auth_method="pi",
            role="user",
            is_active=True,
            membership_tier="premium",
            membership_expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        result = _user_to_dict(user)

        assert result["user_id"] == "test-123"
        assert result["username"] == "TestUser"
        assert result["is_premium"] is True
        assert result["membership_tier"] == "premium"

    def test_user_to_dict_free_user(self):
        from core.orm.repositories import _user_to_dict
        from core.orm.models import User

        user = User(
            user_id="free-123",
            username="FreeUser",
            membership_tier="free",
            is_active=True,
        )
        result = _user_to_dict(user)

        assert result["is_premium"] is False
        assert result["membership_tier"] == "free"

    def test_days_remaining_calculation(self):
        from core.orm.repositories import UserRepository

        future = datetime(2026, 12, 31, tzinfo=timezone.utc).isoformat()
        assert UserRepository._days_remaining(future) > 0

        past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        assert UserRepository._days_remaining(past) == 0

        assert UserRepository._days_remaining(None) == 0

    def test_normalize_membership_tier(self):
        from core.orm.repositories import _normalize_membership_tier

        assert _normalize_membership_tier("premium") == "premium"
        assert _normalize_membership_tier("plus") == "premium"
        assert _normalize_membership_tier("pro") == "premium"
        assert _normalize_membership_tier("free") == "free"
        assert _normalize_membership_tier(None) == "free"
        assert _normalize_membership_tier("") == "free"

    def test_user_repo_singleton(self):
        from core.orm.repositories import user_repo
        assert user_repo is not None
        assert hasattr(user_repo, "get_by_id")
        assert hasattr(user_repo, "get_membership")


class TestOrmModelsCount:
    """Verify we have models for all critical tables."""

    def test_at_least_12_models(self):
        from core.orm.models import Base
        table_names = {cls.__tablename__ for cls in Base.__subclasses__()}
        assert len(table_names) >= 12, f"Expected >=12 models, got {len(table_names)}: {table_names}"
