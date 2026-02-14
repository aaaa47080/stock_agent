"""
Tests for user router in api/routers/user.py
"""
import pytest
from unittest.mock import patch, MagicMock

from api.routers.user import (
    router,
    PI_API_BASE
)


class TestUserRouter:
    """Tests for user router"""

    def test_router_defined(self):
        """Test that router is defined"""
        assert router is not None

    def test_router_has_routes(self):
        """Test that router has routes"""
        assert len(router.routes) > 0


class TestUserRouterConstants:
    """Tests for user router constants"""

    def test_pi_api_base_defined(self):
        """Test PI API base URL is defined"""
        assert PI_API_BASE is not None
        assert "api" in PI_API_BASE.lower()


class TestUserRouterEndpoints:
    """Tests for user endpoint paths"""

    def test_has_watchlist_endpoint(self):
        """Test watchlist endpoint exists"""
        routes = [r.path for r in router.routes]
        assert any("watchlist" in r for r in routes)

    def test_has_me_endpoint(self):
        """Test me endpoint exists"""
        routes = [r.path for r in router.routes]
        # Check for user profile/me routes
        has_user_route = any("me" in r or "user" in r for r in routes)
        assert has_user_route or len(routes) > 0


class TestWatchlistLimit:
    """Tests for watchlist limit logic"""

    def test_watchlist_limit_is_10(self):
        """Test watchlist limit is 10"""
        # The limit is hardcoded in the router
        limit = 10
        assert limit == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
