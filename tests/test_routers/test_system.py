import pytest


@pytest.mark.integration
class TestSystemConfigNoDataLeak:
    @pytest.mark.asyncio
    async def test_test_mode_does_not_leak_full_user_data(self, client):
        response = await client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        if data.get("test_mode") is True:
            test_user = data.get("test_user", {})
            assert "pi_uid" not in test_user
            assert "token" not in test_user
            assert "password" not in test_user
            assert "api_key" not in test_user

    @pytest.mark.asyncio
    async def test_config_returns_supported_exchanges(self, client):
        response = await client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "supported_exchanges" in data
        assert isinstance(data["supported_exchanges"], list)

    @pytest.mark.asyncio
    async def test_config_does_not_expose_raw_api_keys(self, client):
        response = await client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        settings = data.get("current_settings", {})
        assert "has_openai_key" in settings
        assert "has_google_key" in settings
        assert isinstance(settings["has_openai_key"], bool)
