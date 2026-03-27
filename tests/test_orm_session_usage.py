from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.orm.forum_repo import forum_repo
from core.orm.messages_repo import messages_repo
from core.orm.repositories import user_repo


@pytest.mark.asyncio
async def test_user_repo_get_by_id_uses_session_scope_when_session_not_provided():
    mock_user = SimpleNamespace(
        user_id="u1",
        username="Danny",
        auth_method="pi_network",
        role="user",
        is_active=True,
        membership_tier="premium",
        membership_expires_at=None,
        created_at=None,
        pi_uid="pi-u1",
        pi_username="DannyPi",
    )
    mock_result = SimpleNamespace(scalar_one_or_none=lambda: mock_user)
    mock_session = SimpleNamespace(execute=AsyncMock(return_value=mock_result))

    @asynccontextmanager
    async def _fake_using_session(existing=None):
        yield mock_session

    with patch("core.orm.repositories.using_session", _fake_using_session):
        result = await user_repo.get_by_id("u1")

    assert result["user_id"] == "u1"
    assert result["is_premium"] is True


@pytest.mark.asyncio
async def test_forum_repo_get_boards_uses_session_scope_when_session_not_provided():
    mock_result = SimpleNamespace(
        fetchall=lambda: [(1, "General", "general", "desc", 5, True)]
    )
    mock_session = SimpleNamespace(execute=AsyncMock(return_value=mock_result))

    @asynccontextmanager
    async def _fake_using_session(existing=None):
        yield mock_session

    with patch("core.orm.forum_repo.using_session", _fake_using_session):
        result = await forum_repo.get_boards()

    assert result == [
        {
            "id": 1,
            "name": "General",
            "slug": "general",
            "description": "desc",
            "post_count": 5,
            "is_active": True,
        }
    ]


@pytest.mark.asyncio
async def test_messages_repo_get_or_create_conversation_uses_session_scope():
    existing = SimpleNamespace(
        id=7,
        user1_id="u1",
        user2_id="u2",
        last_message_at=None,
        user1_unread_count=0,
        user2_unread_count=0,
        created_at=None,
    )
    mock_result = SimpleNamespace(scalar_one_or_none=lambda: existing)
    mock_session = SimpleNamespace(execute=AsyncMock(return_value=mock_result))

    @asynccontextmanager
    async def _fake_using_session(existing_session=None):
        yield mock_session

    with patch("core.orm.messages_repo.using_session", _fake_using_session):
        result = await messages_repo.get_or_create_conversation("u1", "u2")

    assert result["id"] == 7
    assert result["is_new"] is False
