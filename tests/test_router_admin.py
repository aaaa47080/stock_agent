"""
Tests for admin router in api/routers/admin.py
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from api.routers.admin import (
    verify_admin_key,
    UpdatePriceRequest,
    UpdateLimitRequest,
    UpdateConfigRequest,
    BulkUpdateRequest
)


class TestVerifyAdminKey:
    """Tests for verify_admin_key dependency"""

    def test_valid_key_passes(self):
        """Test that valid key passes verification"""
        with patch('api.routers.admin.ADMIN_API_KEY', 'test-admin-key'):
            result = verify_admin_key(x_admin_key='test-admin-key')
            assert result is True

    def test_invalid_key_raises_403(self):
        """Test that invalid key raises 403"""
        with patch('api.routers.admin.ADMIN_API_KEY', 'test-admin-key'):
            with pytest.raises(HTTPException) as exc_info:
                verify_admin_key(x_admin_key='wrong-key')

            assert exc_info.value.status_code == 403
            assert "Invalid" in exc_info.value.detail

    def test_missing_key_raises_403(self):
        """Test that missing key raises 403"""
        with patch('api.routers.admin.ADMIN_API_KEY', 'test-admin-key'):
            with pytest.raises(HTTPException) as exc_info:
                verify_admin_key(x_admin_key=None)

            assert exc_info.value.status_code == 403

    def test_unconfigured_key_raises_403(self):
        """Test that unconfigured ADMIN_API_KEY raises 403"""
        with patch('api.routers.admin.ADMIN_API_KEY', None):
            with pytest.raises(HTTPException) as exc_info:
                verify_admin_key(x_admin_key='any-key')

            assert exc_info.value.status_code == 403
            assert "not configured" in exc_info.value.detail


class TestRequestModels:
    """Tests for Pydantic request models"""

    def test_update_price_request(self):
        """Test UpdatePriceRequest model"""
        req = UpdatePriceRequest(key="create_post", value=10.0)
        assert req.key == "create_post"
        assert req.value == 10.0

    def test_update_limit_request(self):
        """Test UpdateLimitRequest model"""
        req = UpdateLimitRequest(key="daily_post_free", value=10)
        assert req.key == "daily_post_free"
        assert req.value == 10

    def test_update_limit_request_none_value(self):
        """Test UpdateLimitRequest with None value (unlimited)"""
        req = UpdateLimitRequest(key="daily_post_free", value=None)
        assert req.value is None

    def test_update_config_request(self):
        """Test UpdateConfigRequest model"""
        req = UpdateConfigRequest(
            key="test_key",
            value="test_value",
            value_type="string",
            category="test",
            description="Test description"
        )
        assert req.key == "test_key"
        assert req.value == "test_value"

    def test_update_config_request_defaults(self):
        """Test UpdateConfigRequest default values"""
        req = UpdateConfigRequest(key="test_key", value="test_value")
        assert req.value_type == "string"
        assert req.category == "general"
        assert req.description == ""

    def test_bulk_update_request(self):
        """Test BulkUpdateRequest model"""
        req = BulkUpdateRequest(configs={"key1": "value1", "key2": 123})
        assert req.configs["key1"] == "value1"
        assert req.configs["key2"] == 123

    def test_update_price_request_missing_fields(self):
        """Test UpdatePriceRequest validation"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            UpdatePriceRequest()  # Missing required fields

    def test_update_limit_request_missing_fields(self):
        """Test UpdateLimitRequest validation"""
        with pytest.raises(Exception):
            UpdateLimitRequest()  # Missing required fields


class TestAdminRouterRoutes:
    """Tests for route definitions"""

    def test_router_defined(self):
        """Test that router is defined"""
        from api.routers.admin import router
        assert router is not None

    def test_router_has_routes(self):
        """Test that router has routes"""
        from api.routers.admin import router
        assert len(router.routes) > 0

    def test_has_debug_log_route(self):
        """Test that debug log route exists"""
        from api.routers.admin import router
        routes = [r.path for r in router.routes]
        assert "/api/debug/log" in routes

    def test_has_config_route(self):
        """Test that config route exists"""
        from api.routers.admin import router
        routes = [r.path for r in router.routes]
        assert "/api/admin/config" in routes

    def test_has_prices_route(self):
        """Test that prices route exists"""
        from api.routers.admin import router
        routes = [r.path for r in router.routes]
        assert "/api/admin/config/prices" in routes

    def test_has_limits_route(self):
        """Test that limits route exists"""
        from api.routers.admin import router
        routes = [r.path for r in router.routes]
        assert "/api/admin/config/limits" in routes


class TestAdminEnvironmentVariables:
    """Tests for admin environment variables"""

    def test_admin_key_from_environment(self):
        """Test that admin key can be set from environment"""
        import os
        with patch.dict(os.environ, {'ADMIN_API_KEY': 'env-test-key'}):
            # Re-import to get new value
            import importlib
            import api.routers.admin
            importlib.reload(api.routers.admin)
            from api.routers.admin import ADMIN_API_KEY
            assert ADMIN_API_KEY == 'env-test-key'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
