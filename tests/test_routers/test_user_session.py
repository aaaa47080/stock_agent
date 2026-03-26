from unittest.mock import AsyncMock, patch

import pytest

from api.deps import create_access_token, create_refresh_token, verify_token


@pytest.mark.asyncio
async def test_user_me_returns_session_restore_fields(client):
    token = create_access_token(data={"sub": "pi-user-123", "username": "PiUser"})

    mocked_user = {
        "user_id": "pi-user-123",
        "username": "PiUser",
        "role": "user",
        "auth_method": "pi_network",
        "membership_tier": "premium",
        "pi_uid": "pi-user-123",
        "pi_username": "PiPioneer",
        "is_active": True,
    }

    with patch("api.deps.user_repo.get_by_id", new=AsyncMock(return_value=mocked_user)):
        response = await client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["user"] == {
        "user_id": "pi-user-123",
        "username": "PiUser",
        "role": "user",
        "auth_method": "pi_network",
        "membership_tier": "premium",
        "pi_uid": "pi-user-123",
        "pi_username": "PiPioneer",
        "has_wallet": True,
    }


@pytest.mark.asyncio
async def test_refresh_uses_refresh_cookie_and_rotates_tokens(client):
    refresh_token = create_refresh_token(
        data={"sub": "pi-user-123", "username": "PiUser"}
    )
    client.cookies.set("refresh_token", refresh_token)

    response = await client.post("/api/user/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]

    decoded_access = verify_token(payload["access_token"])
    assert decoded_access["sub"] == "pi-user-123"
    assert decoded_access["type"] == "access"

    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith("access_token=") for header in set_cookie_headers)
    assert any(header.startswith("refresh_token=") for header in set_cookie_headers)


@pytest.mark.asyncio
async def test_refresh_rejects_when_refresh_cookie_missing(client):
    response = await client.post("/api/user/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token is required"
