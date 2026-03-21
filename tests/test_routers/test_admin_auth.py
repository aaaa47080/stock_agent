import pytest


@pytest.mark.integration
class TestAdminAuth:
    @pytest.mark.asyncio
    async def test_admin_invalid_key_returns_403(self, client):
        response = await client.get(
            "/api/admin/config", headers={"X-Admin-Key": "wrong-key"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_missing_key_returns_403(self, client):
        response = await client.get("/api/admin/config")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_correct_key_returns_200_or_404(self, client, admin_headers):
        response = await client.get("/api/admin/config", headers=admin_headers)
        assert response.status_code in (200, 404)
