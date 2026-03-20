"""Tests for the current modular admin router package."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.routers.admin import UpdateConfigRequest, router, verify_admin_key


class TestVerifyAdminKey:
    """Tests for verify_admin_key dependency."""

    def test_valid_key_passes(self):
        with patch("api.routers.admin.auth.ADMIN_API_KEY", "test-admin-key"):
            assert verify_admin_key(x_admin_key="test-admin-key") is True

    def test_invalid_key_raises_403(self):
        with patch("api.routers.admin.auth.ADMIN_API_KEY", "test-admin-key"):
            with pytest.raises(HTTPException) as exc_info:
                verify_admin_key(x_admin_key="wrong-key")
            assert exc_info.value.status_code == 403

    def test_missing_key_raises_403(self):
        with patch("api.routers.admin.auth.ADMIN_API_KEY", "test-admin-key"):
            with pytest.raises(HTTPException) as exc_info:
                verify_admin_key(x_admin_key=None)
            assert exc_info.value.status_code == 403

    def test_unconfigured_key_raises_403(self):
        with patch("api.routers.admin.auth.ADMIN_API_KEY", None):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(HTTPException) as exc_info:
                    verify_admin_key(x_admin_key="any-key")
                assert exc_info.value.status_code == 403
                assert "not configured" in exc_info.value.detail

    def test_admin_key_from_environment(self):
        with patch("api.routers.admin.auth.ADMIN_API_KEY", None):
            with patch.dict("os.environ", {"ADMIN_API_KEY": "env-test-key"}):
                assert verify_admin_key(x_admin_key="env-test-key") is True


class TestRequestModels:
    """Tests for exposed request models."""

    def test_update_config_request_valid(self):
        req = UpdateConfigRequest(value="new_value")
        assert req.value == "new_value"

    def test_update_config_request_missing_fields(self):
        with pytest.raises(Exception):
            UpdateConfigRequest()


class TestAdminRouterRoutes:
    """Tests for current route definitions."""

    def test_router_defined(self):
        assert router is not None

    def test_router_has_routes(self):
        assert len(router.routes) > 0

    def test_has_config_all_route(self):
        routes = [r.path for r in router.routes]
        assert "/api/admin/config/all" in routes

    def test_has_config_update_route(self):
        routes = [r.path for r in router.routes]
        assert "/api/admin/config/{key}" in routes

    def test_has_config_audit_route(self):
        routes = [r.path for r in router.routes]
        assert "/api/admin/config/audit" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
