import pytest


@pytest.mark.integration
class TestNegativePaths:
    @pytest.mark.asyncio
    async def test_unauthenticated_access_returns_401(self, client):
        response = await client.get("/api/chat/sessions")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self, client):
        response = await client.get(
            "/api/chat/sessions",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, client, auth_headers):
        response = await client.post(
            "/api/chat/query",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_nonexistent_route_returns_404(self, client, auth_headers):
        response = await client.get("/api/nonexistent-endpoint", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_health_endpoint_always_accessible(self, client):
        response = await client.get("/health")
        assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_post_to_get_only_endpoint(self, client):
        response = await client.post("/health")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_empty_authorization_header_returns_401(self, client):
        response = await client.get(
            "/api/chat/sessions",
            headers={"Authorization": ""},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_without_token_returns_401(self, client):
        response = await client.get(
            "/api/chat/sessions",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401
