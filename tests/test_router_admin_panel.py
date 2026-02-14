"""
Tests for admin panel router in api/routers/admin_panel.py
"""
import pytest
from unittest.mock import patch, MagicMock

from api.routers.admin_panel import (
    router,
    BroadcastRequest,
    SetRoleRequest,
    SetMembershipRequest,
    SetStatusRequest,
    PostVisibilityRequest,
    PostPinRequest,
    ResolveReportRequest,
    UpdateConfigRequest
)


class TestRequestModels:
    """Tests for Pydantic request models"""

    def test_broadcast_request_valid(self):
        """Test valid BroadcastRequest"""
        req = BroadcastRequest(
            title="System Update",
            body="We have updated our system.",
            type="announcement"
        )
        assert req.title == "System Update"
        assert req.type == "announcement"

    def test_broadcast_request_defaults(self):
        """Test BroadcastRequest default values"""
        req = BroadcastRequest(title="Test", body="Body")
        assert req.type == "announcement"

    def test_broadcast_request_invalid_type(self):
        """Test BroadcastRequest with invalid type"""
        with pytest.raises(Exception):
            BroadcastRequest(title="Test", body="Body", type="invalid")

    def test_set_role_request_valid(self):
        """Test valid SetRoleRequest"""
        req = SetRoleRequest(role="admin")
        assert req.role == "admin"

        req = SetRoleRequest(role="user")
        assert req.role == "user"

    def test_set_role_request_invalid(self):
        """Test SetRoleRequest with invalid role"""
        with pytest.raises(Exception):
            SetRoleRequest(role="superadmin")

    def test_set_membership_request_valid(self):
        """Test valid SetMembershipRequest"""
        req = SetMembershipRequest(tier="pro", months=3)
        assert req.tier == "pro"
        assert req.months == 3

    def test_set_membership_request_defaults(self):
        """Test SetMembershipRequest defaults"""
        req = SetMembershipRequest(tier="free")
        assert req.months == 1

    def test_set_membership_request_invalid_tier(self):
        """Test SetMembershipRequest with invalid tier"""
        with pytest.raises(Exception):
            SetMembershipRequest(tier="enterprise")

    def test_set_membership_request_months_bounds(self):
        """Test SetMembershipRequest months bounds"""
        # Valid bounds
        req = SetMembershipRequest(tier="pro", months=1)
        assert req.months == 1
        req = SetMembershipRequest(tier="pro", months=12)
        assert req.months == 12

    def test_set_status_request_valid(self):
        """Test valid SetStatusRequest"""
        req = SetStatusRequest(active=True)
        assert req.active is True
        assert req.reason is None

        req = SetStatusRequest(active=False, reason="Violation")
        assert req.active is False
        assert req.reason == "Violation"

    def test_post_visibility_request_valid(self):
        """Test valid PostVisibilityRequest"""
        req = PostVisibilityRequest(is_hidden=True)
        assert req.is_hidden is True

    def test_post_pin_request_valid(self):
        """Test valid PostPinRequest"""
        req = PostPinRequest(is_pinned=True)
        assert req.is_pinned is True

    def test_resolve_report_request_valid(self):
        """Test valid ResolveReportRequest"""
        req = ResolveReportRequest(decision="approved")
        assert req.decision == "approved"

        req = ResolveReportRequest(decision="rejected", violation_level="severe")
        assert req.violation_level == "severe"

    def test_resolve_report_request_invalid_decision(self):
        """Test ResolveReportRequest with invalid decision"""
        with pytest.raises(Exception):
            ResolveReportRequest(decision="pending")

    def test_update_config_request_valid(self):
        """Test valid UpdateConfigRequest"""
        req = UpdateConfigRequest(value="new_value")
        assert req.value == "new_value"


class TestAdminPanelRouter:
    """Tests for admin panel router"""

    def test_router_defined(self):
        """Test that router is defined"""
        assert router is not None

    def test_router_prefix(self):
        """Test router prefix"""
        assert router.prefix == "/api/admin"

    def test_router_has_routes(self):
        """Test that router has routes"""
        assert len(router.routes) > 0


class TestBroadcastRequestValidation:
    """Tests for BroadcastRequest validation"""

    def test_title_min_length(self):
        """Test title minimum length"""
        req = BroadcastRequest(title="A", body="Body")
        assert req.title == "A"

    def test_title_max_length(self):
        """Test title maximum length"""
        title = "A" * 200
        req = BroadcastRequest(title=title, body="Body")
        assert len(req.title) == 200

    def test_body_min_length(self):
        """Test body minimum length"""
        req = BroadcastRequest(title="Title", body="A")
        assert req.body == "A"

    def test_body_max_length(self):
        """Test body maximum length"""
        body = "A" * 1000
        req = BroadcastRequest(title="Title", body=body)
        assert len(req.body) == 1000

    def test_type_pattern_valid(self):
        """Test type pattern valid values"""
        for t in ["announcement", "system_update"]:
            req = BroadcastRequest(title="Title", body="Body", type=t)
            assert req.type == t


class TestResolveReportValidation:
    """Tests for ResolveReportRequest validation"""

    def test_decision_pattern_valid(self):
        """Test decision pattern valid values"""
        for d in ["approved", "rejected"]:
            req = ResolveReportRequest(decision=d)
            assert req.decision == d

    def test_violation_level_pattern_valid(self):
        """Test violation_level pattern valid values"""
        for v in ["mild", "medium", "severe", "critical", None]:
            req = ResolveReportRequest(decision="approved", violation_level=v)
            assert req.violation_level == v


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
