"""
Tests for rate limit middleware in api/middleware/rate_limit.py
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import Request
from pathlib import Path
import json
import time
import tempfile
import os

from api.middleware.rate_limit import (
    get_user_identifier,
    get_rate_limit_for_route,
    PersistentRateLimiter,
    RATE_LIMITS
)


class TestGetUserIdentifier:
    """Tests for get_user_identifier function"""

    def test_returns_user_id_when_authenticated(self):
        """Test returns user: prefixed ID when authenticated"""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user = {"user_id": "user-123", "username": "test"}

        result = get_user_identifier(request)
        assert result == "user:user-123"

    def test_returns_ip_when_not_authenticated(self):
        """Test returns ip: prefixed address when not authenticated"""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user = None

        with patch('api.middleware.rate_limit.get_remote_address', return_value='192.168.1.1'):
            result = get_user_identifier(request)
            assert result == "ip:192.168.1.1"

    def test_handles_missing_user_in_state(self):
        """Test handles missing user gracefully"""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user = None

        with patch('api.middleware.rate_limit.get_remote_address', return_value='10.0.0.1'):
            result = get_user_identifier(request)
            assert result.startswith("ip:")


class TestGetRateLimitForRoute:
    """Tests for get_rate_limit_for_route function"""

    def test_auth_endpoints_strict_limit(self):
        """Test auth endpoints have strict limit"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/user/login"
        request.method = "POST"

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["auth"]

    def test_payment_endpoints_strict_limit(self):
        """Test payment endpoints have strict limit"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/payment/approve"
        request.method = "POST"

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["payment"]

    def test_admin_endpoints_moderate_limit(self):
        """Test admin endpoints have moderate limit"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/admin/config"
        request.method = "GET"

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["admin"]

    def test_write_operations_limit(self):
        """Test write operations have write limit"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/data"
        request.method = "POST"

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["write"]

    def test_public_endpoints_lenient_limit(self):
        """Test public endpoints have lenient limit"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/forum/posts"
        request.method = "GET"

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["public"]

    def test_governance_report_is_write_limit(self):
        """Test governance report POST gets write limit (write is checked first)"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/governance/reports"
        request.method = "post"  # Must be lowercase

        # Note: Write operations are checked before governance in the code
        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["write"]

    def test_governance_read_limit(self):
        """Test governance read gets governance_read limit"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/governance/reports"
        request.method = "get"  # GET request

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["governance_read"]

    def test_governance_vote_is_write_limit(self):
        """Test governance vote POST gets write limit (write is checked first)"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/governance/vote"
        request.method = "post"

        # Note: Write operations are checked before governance in the code
        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["write"]

    def test_default_read_limit(self):
        """Test default read limit for GET requests"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/unknown"
        request.method = "GET"

        result = get_rate_limit_for_route(request)
        assert result == RATE_LIMITS["read"]


class TestPersistentRateLimiter:
    """Tests for PersistentRateLimiter class"""

    def test_init_creates_file(self, tmp_path):
        """Test initialization creates storage file"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # State should be initialized
        assert limiter.state is not None

    def test_check_limit_allows_under_limit(self, tmp_path):
        """Test allows requests under limit"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        result = limiter.check_limit("user:123", limit=10, window=3600)
        assert result is True

    def test_check_limit_denies_over_limit(self, tmp_path):
        """Test denies requests over limit"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Make requests up to limit
        for i in range(10):
            limiter.check_limit("user:123", limit=10, window=3600)

        # Next request should be denied
        result = limiter.check_limit("user:123", limit=10, window=3600)
        assert result is False

    def test_check_limit_resets_after_window(self, tmp_path):
        """Test limit resets after window expires"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Make requests
        for i in range(5):
            limiter.check_limit("user:123", limit=5, window=1)  # 1 second window

        # Wait for window to expire
        time.sleep(1.5)

        # Should be allowed now
        result = limiter.check_limit("user:123", limit=5, window=1)
        assert result is True

    def test_get_remaining_returns_correct_count(self, tmp_path):
        """Test get_remaining returns correct count"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Make 3 requests
        for i in range(3):
            limiter.check_limit("user:123", limit=10, window=3600)

        remaining = limiter.get_remaining("user:123", limit=10, window=3600)
        assert remaining == 7

    def test_get_remaining_full_when_no_requests(self, tmp_path):
        """Test get_remaining returns full limit when no requests"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        remaining = limiter.get_remaining("user:123", limit=10, window=3600)
        assert remaining == 10

    def test_reset_key_clears_history(self, tmp_path):
        """Test reset_key clears history"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Make requests
        for i in range(5):
            limiter.check_limit("user:123", limit=10, window=3600)

        # Reset
        limiter.reset_key("user:123")

        # Should have full limit again
        remaining = limiter.get_remaining("user:123", limit=10, window=3600)
        assert remaining == 10

    def test_state_persists_to_file(self, tmp_path):
        """Test state persists to file"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Make a request
        limiter.check_limit("user:123", limit=10, window=3600)

        # Check file exists
        assert storage_file.exists()

        # Load and verify
        with open(storage_file, 'r') as f:
            state = json.load(f)
        assert "user:123" in state

    def test_handles_corrupted_file(self, tmp_path):
        """Test handles corrupted file gracefully"""
        storage_file = tmp_path / "rate_limits.json"

        # Write corrupted JSON
        with open(storage_file, 'w') as f:
            f.write("not valid json {{{")

        # Should not crash
        limiter = PersistentRateLimiter(str(storage_file))
        assert limiter.state == {}

    def test_cleanup_removes_old_entries(self, tmp_path):
        """Test cleanup removes old entries"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Add old entry (simulate by directly manipulating state)
        old_time = int(time.time()) - 100000
        limiter.state["old_key"] = [old_time]

        # Cleanup
        limiter.cleanup_old_entries(older_than_seconds=86400)

        # Old entry should be removed
        assert "old_key" not in limiter.state

    def test_different_keys_have_separate_limits(self, tmp_path):
        """Test different keys have separate limits"""
        storage_file = tmp_path / "rate_limits.json"
        limiter = PersistentRateLimiter(str(storage_file))

        # Exhaust limit for user:123
        for i in range(10):
            limiter.check_limit("user:123", limit=10, window=3600)

        # user:456 should still be allowed
        result = limiter.check_limit("user:456", limit=10, window=3600)
        assert result is True


class TestRateLimitsConstants:
    """Tests for RATE_LIMITS constants"""

    def test_auth_limit_is_strict(self):
        """Test auth limit is strict"""
        assert RATE_LIMITS["auth"] == "5/minute"

    def test_payment_limit_is_strict(self):
        """Test payment limit is strict"""
        assert RATE_LIMITS["payment"] == "10/minute"

    def test_public_limit_is_lenient(self):
        """Test public limit is lenient"""
        assert RATE_LIMITS["public"] == "200/minute"

    def test_all_limits_defined(self):
        """Test all expected limits are defined"""
        expected_keys = [
            "auth", "write", "payment", "read",
            "admin", "public", "governance_report",
            "governance_vote", "governance_read"
        ]
        for key in expected_keys:
            assert key in RATE_LIMITS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
