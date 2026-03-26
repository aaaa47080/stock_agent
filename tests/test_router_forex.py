"""Tests for forex market router."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api_server import app

    return TestClient(app)


def test_forex_router_registered(client):
    """Verify /api/forex routes exist."""
    response = client.get("/api/forex/market")
    assert response.status_code != 404


def test_forex_market_gracefully_degrades_when_quotes_unavailable(client, monkeypatch):
    """Verify market endpoint returns an empty payload instead of 404 when source fails."""
    from api.routers import forex

    forex._cache.clear()
    monkeypatch.setattr(forex, "_fetch_forex_sync", lambda *args, **kwargs: None)

    response = client.get("/api/forex/market?pairs=EURUSD")

    assert response.status_code == 200
    assert response.json()["pairs"] == []
    assert response.json()["partial_failure"] is True
    assert "warning" in response.json()


def test_forex_router_prefix():
    """Verify router prefix and tags."""
    from api.routers.forex import router

    assert router.prefix == "/api/forex"
    assert "Forex" in router.tags


def test_normalize_forex_symbol():
    """Verify _normalize_forex_symbol handles common input formats."""
    from api.routers.forex import _normalize_forex_symbol

    assert _normalize_forex_symbol("EURUSD") == "EURUSD=X"
    assert _normalize_forex_symbol("EUR/USD") == "EURUSD=X"
    assert _normalize_forex_symbol("EUR_USD") == "EURUSD=X"
    assert _normalize_forex_symbol("USDJPY") == "JPY=X"
    assert _normalize_forex_symbol("USDTWD") == "TWD=X"
    assert _normalize_forex_symbol("TWD=X") == "TWD=X"


def test_forex_default_pairs():
    """Verify default pair list includes key currencies."""
    from api.routers.forex import DEFAULT_PAIRS

    symbols = [p["symbol"] for p in DEFAULT_PAIRS]
    assert "TWD=X" in symbols  # USD/TWD
    assert "EURUSD=X" in symbols  # EUR/USD
    assert "JPY=X" in symbols  # USD/JPY


def test_forex_cache():
    """Verify cache set/get works."""
    from api.routers.forex import _get_cache, _set_cache

    _set_cache("market:test", {"pairs": []}, ttl=60)
    assert _get_cache("market:test") == {"pairs": []}
