"""Tests for price alerts API router."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create test client with mocked auth."""
    from api_server import app
    with patch("api.deps.get_current_user", return_value={"user_id": "test-user-001", "username": "TestUser"}):
        with TestClient(app) as c:
            yield c


class TestCreateAlert:
    def test_create_alert_success(self, client):
        with patch("api.routers.alerts.create_alert", return_value={
            "id": "alert-1", "symbol": "AAPL", "market": "us_stock",
            "condition": "above", "target": 200.0, "repeat": 0,
            "triggered": 0, "created_at": "2026-02-26T00:00:00",
        }):
            resp = client.post("/api/alerts", json={
                "symbol": "AAPL",
                "market": "us_stock",
                "condition": "above",
                "target": 200.0,
                "repeat": False,
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["alert"]["symbol"] == "AAPL"

    def test_create_alert_limit_exceeded(self, client):
        with patch("api.routers.alerts.create_alert", side_effect=ValueError("已達警報上限")):
            resp = client.post("/api/alerts", json={
                "symbol": "BTC",
                "market": "crypto",
                "condition": "above",
                "target": 100000.0,
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 400

    def test_create_alert_invalid_market(self, client):
        resp = client.post("/api/alerts", json={
            "symbol": "BTC",
            "market": "invalid",
            "condition": "above",
            "target": 100000.0,
        }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 422


class TestGetAlerts:
    def test_get_alerts_returns_list(self, client):
        with patch("api.routers.alerts.get_user_alerts", return_value=[]):
            resp = client.get("/api/alerts", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert "alerts" in resp.json()


class TestDeleteAlert:
    def test_delete_alert_success(self, client):
        with patch("api.routers.alerts.delete_alert", return_value=True):
            resp = client.delete("/api/alerts/alert-1", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200

    def test_delete_alert_not_found(self, client):
        with patch("api.routers.alerts.delete_alert", return_value=False):
            resp = client.delete("/api/alerts/nonexistent", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 404
