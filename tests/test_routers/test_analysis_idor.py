import pytest


@pytest.mark.integration
class TestAnalysisIdor:
    @pytest.mark.asyncio
    async def test_delete_session_requires_ownership(self, client, auth_headers):
        from unittest.mock import patch

        with patch("api.routers.analysis.run_sync") as mock_run:
            mock_run.return_value = []
            response = await client.delete(
                "/api/chat/sessions/other-users-session-id",
                headers=auth_headers,
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_pin_session_requires_ownership(self, client, auth_headers):
        from unittest.mock import patch

        with patch("api.routers.analysis.run_sync") as mock_run:
            mock_run.return_value = []
            response = await client.put(
                "/api/chat/sessions/other-users-session-id/pin?is_pinned=true",
                headers=auth_headers,
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_own_session_succeeds(self, client, auth_headers):
        from unittest.mock import patch

        session_id = "my-session-123"
        with patch("api.routers.analysis.run_sync") as mock_run:

            def fake_run(fn, *args):
                if callable(fn):
                    return [{"id": session_id}]
                return None

            mock_run.side_effect = fake_run
            response = await client.delete(
                f"/api/chat/sessions/{session_id}",
                headers=auth_headers,
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_pin_own_session_succeeds(self, client, auth_headers):
        from unittest.mock import patch

        session_id = "my-session-456"
        with patch("api.routers.analysis.run_sync") as mock_run:

            def fake_run(fn, *args):
                if callable(fn):
                    return [{"id": session_id}]
                return None

            mock_run.side_effect = fake_run
            response = await client.put(
                f"/api/chat/sessions/{session_id}/pin?is_pinned=true",
                headers=auth_headers,
            )
        assert response.status_code == 200
