"""Tests for commodity market router."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api_server import app
    return TestClient(app)


def test_commodity_router_registered(client):
    """Verify /api/commodity routes are accessible (auth not required for market)."""
    # Routes should exist (may return 401 or 200, not 404)
    response = client.get("/api/commodity/market")
    assert response.status_code != 404


def test_commodity_router_prefix():
    """Verify router has correct prefix and tags."""
    from api.routers.commodity import router
    assert router.prefix == "/api/commodity"
    assert "Commodity" in router.tags


def test_normalize_commodity_defaults():
    """Verify default commodity list has expected symbols."""
    from api.routers.commodity import DEFAULT_COMMODITIES
    symbols = [c["symbol"] for c in DEFAULT_COMMODITIES]
    assert "GC=F" in symbols   # Gold
    assert "CL=F" in symbols   # WTI Oil
    assert "NG=F" in symbols   # Natural Gas


def test_commodity_klines_cache_key():
    """Verify klines cache key format."""
    from api.routers.commodity import _get_cache, _set_cache
    _set_cache("klines:GC=F:1d", {"test": True}, ttl=300)
    result = _get_cache("klines:GC=F:1d")
    assert result == {"test": True}


def test_commodity_cache_expiry():
    """Verify expired cache returns None."""
    import time
    from api.routers.commodity import _get_cache, _set_cache
    _set_cache("test_expired", {"data": 1}, ttl=0)
    time.sleep(0.01)
    result = _get_cache("test_expired")
    assert result is None
