"""
Tests for friends router in api/routers/friends.py
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from api.routers.friends import (
    router,
    FriendActionRequest
)


class TestFriendActionRequest:
    """Tests for FriendActionRequest model"""

    def test_valid_request(self):
        """Test valid request"""
        req = FriendActionRequest(target_user_id="user-456")
        assert req.target_user_id == "user-456"

    def test_missing_target_user_id(self):
        """Test missing target_user_id"""
        with pytest.raises(Exception):
            FriendActionRequest()


class TestFriendsRouter:
    """Tests for friends router"""

    def test_router_defined(self):
        """Test that router is defined"""
        assert router is not None

    def test_router_has_routes(self):
        """Test that router has routes"""
        assert len(router.routes) > 0

    def test_has_search_route(self):
        """Test search route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/search" in routes

    def test_has_list_route(self):
        """Test list route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/list" in routes

    def test_has_request_route(self):
        """Test request route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/request" in routes

    def test_has_accept_route(self):
        """Test accept route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/accept" in routes

    def test_has_reject_route(self):
        """Test reject route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/reject" in routes

    def test_has_remove_route(self):
        """Test remove route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/remove" in routes

    def test_has_block_route(self):
        """Test block route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/block" in routes

    def test_has_unblock_route(self):
        """Test unblock route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/friends/unblock" in routes


class TestFriendActionValidation:
    """Tests for friend action validation"""

    def test_target_user_id_required(self):
        """Test target_user_id is required"""
        with pytest.raises(Exception):
            FriendActionRequest()

    def test_target_user_id_type(self):
        """Test target_user_id type"""
        req = FriendActionRequest(target_user_id="123")
        assert isinstance(req.target_user_id, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
