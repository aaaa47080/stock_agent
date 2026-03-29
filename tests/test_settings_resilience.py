from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_current_user
from api.routers import notifications, premium


def _make_client(*routers):
    app = FastAPI()
    for router in routers:
        app.include_router(router.router)

    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-user-001",
        "username": "TestUser",
    }
    return TestClient(app)


def test_notifications_endpoint_falls_back_when_async_driver_missing():
    with (
        _make_client(notifications) as client,
        patch(
            "api.routers.notifications.notifications_repo.get_notifications",
            AsyncMock(side_effect=ModuleNotFoundError("asyncpg")),
        ),
        patch(
            "api.routers.notifications.legacy_get_notifications",
            return_value=[{"id": "n1", "title": "fallback", "is_read": False}],
        ),
        patch(
            "api.routers.notifications.legacy_get_unread_count",
            return_value=1,
        ),
    ):
        response = client.get(
            "/api/notifications", headers={"Authorization": "Bearer test"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["notifications"][0]["id"] == "n1"
    assert payload["unread_count"] == 1


def test_notifications_unread_count_falls_back_when_async_driver_missing():
    with (
        _make_client(notifications) as client,
        patch(
            "api.routers.notifications.notifications_repo.get_unread_count",
            AsyncMock(side_effect=ModuleNotFoundError("asyncpg")),
        ),
        patch(
            "api.routers.notifications.legacy_get_unread_count",
            return_value=3,
        ),
    ):
        response = client.get(
            "/api/notifications/unread-count",
            headers={"Authorization": "Bearer test"},
        )

    assert response.status_code == 200
    assert response.json() == {"success": True, "count": 3}


def test_premium_status_falls_back_when_async_driver_missing():
    with (
        _make_client(premium) as client,
        patch(
            "api.routers.premium.user_repo.get_membership",
            AsyncMock(side_effect=ModuleNotFoundError("asyncpg")),
        ),
        patch(
            "api.routers.premium.get_user_membership",
            return_value={"tier": "premium", "is_premium": True},
        ),
    ):
        response = client.get(
            "/api/premium/status", headers={"Authorization": "Bearer test"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["membership"]["membership_tier"] == "premium"
    assert payload["membership"]["is_premium"] is True
    assert payload["membership"]["days_remaining"] == 0


def test_premium_status_falls_back_when_async_session_wrapper_is_broken():
    with (
        _make_client(premium) as client,
        patch(
            "api.routers.premium.user_repo.get_membership",
            AsyncMock(
                side_effect=TypeError(
                    "'async_generator' object does not support the asynchronous context manager protocol"
                )
            ),
        ),
        patch(
            "api.routers.premium.get_user_membership",
            return_value={"tier": "free", "is_premium": False},
        ),
    ):
        response = client.get(
            "/api/premium/status", headers={"Authorization": "Bearer test"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["membership"]["membership_tier"] == "free"
    assert payload["membership"]["is_premium"] is False
