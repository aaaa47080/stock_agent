"""
Tests for governance router in api/routers/governance.py
"""
import pytest
from unittest.mock import patch, MagicMock

from api.routers.governance import (
    router,
    PRO_DAILY_REPORT_LIMIT,
    DEFAULT_DAILY_REPORT_LIMIT,
    MIN_VOTES_REQUIRED,
    CONSENSUS_APPROVE_THRESHOLD,
    CONSENSUS_REJECT_THRESHOLD
)


class TestGovernanceRouter:
    """Tests for governance router"""

    def test_router_defined(self):
        """Test that router is defined"""
        assert router is not None

    def test_router_prefix(self):
        """Test router prefix"""
        assert router.prefix == "/api/governance"

    def test_router_has_routes(self):
        """Test that router has routes"""
        assert len(router.routes) > 0


class TestGovernanceConstants:
    """Tests for governance constants"""

    def test_pro_daily_report_limit_defined(self):
        """Test PRO daily report limit is defined"""
        assert PRO_DAILY_REPORT_LIMIT is not None
        assert isinstance(PRO_DAILY_REPORT_LIMIT, int)

    def test_default_daily_report_limit_defined(self):
        """Test default daily report limit is defined"""
        assert DEFAULT_DAILY_REPORT_LIMIT is not None
        assert isinstance(DEFAULT_DAILY_REPORT_LIMIT, int)

    def test_min_votes_required_defined(self):
        """Test minimum votes required is defined"""
        assert MIN_VOTES_REQUIRED is not None
        assert isinstance(MIN_VOTES_REQUIRED, int)

    def test_consensus_approve_threshold_defined(self):
        """Test consensus approve threshold is defined"""
        assert CONSENSUS_APPROVE_THRESHOLD is not None

    def test_consensus_reject_threshold_defined(self):
        """Test consensus reject threshold is defined"""
        assert CONSENSUS_REJECT_THRESHOLD is not None

    def test_pro_limit_higher_than_default(self):
        """Test PRO limit is higher than default"""
        assert PRO_DAILY_REPORT_LIMIT > DEFAULT_DAILY_REPORT_LIMIT


class TestGovernanceEndpoints:
    """Tests for governance endpoint paths"""

    def test_has_reports_endpoint(self):
        """Test reports endpoint exists"""
        routes = [r.path for r in router.routes]
        # Check for reports-related routes
        assert any("reports" in r for r in routes)

    def test_has_vote_endpoint(self):
        """Test vote endpoint exists"""
        routes = [r.path for r in router.routes]
        assert any("vote" in r for r in routes)

    def test_has_statistics_endpoint(self):
        """Test statistics endpoint exists"""
        routes = [r.path for r in router.routes]
        assert any("statistics" in r.lower() or "stats" in r.lower() for r in routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
