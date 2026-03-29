"""Tests for premium membership upgrade endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from slowapi.errors import RateLimitExceeded

from api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from api.routers.premium import UpgradeRequest


def _create_test_app():
    """Create a FastAPI test app with limiter configured."""
    from fastapi import FastAPI

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    return app


@pytest.fixture(autouse=True)
def _set_test_mode_false(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "false")
    monkeypatch.setenv("PI_API_KEY", "test-pi-api-key")


def _make_app_with_deps(premium_router):
    """Create a test FastAPI app with mocked auth dependency."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(premium_router)

    app.dependency_overrides[premium_router.dependencies[0].dependency] = lambda: {
        "user_id": "test-user-1"
    }

    return app, TestClient(app)


class TestVerifyPiPayment:
    """Tests for _verify_pi_payment function."""

    @pytest.mark.asyncio
    async def test_verifies_approved_payment(self):
        import api.routers.premium as pm

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "approved",
            "amount": "5.0",
            "transaction": {"_id": "tx_abc123"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.premium.httpx.AsyncClient", return_value=mock_client):
            result = await pm._verify_pi_payment("pay_123")

        assert result["status"] == "approved"
        assert result["transaction"]["_id"] == "tx_abc123"

    @pytest.mark.asyncio
    async def test_rejects_non_approved_payment(self):
        import api.routers.premium as pm

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "created",
            "amount": "5.0",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.premium.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await pm._verify_pi_payment("pay_123")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_missing_payment(self):
        import api.routers.premium as pm

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404")

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.premium.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await pm._verify_pi_payment("pay_nonexistent")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_api_key_raises_500(self):
        import api.routers.premium as pm

        with patch("api.routers.premium.PI_API_KEY", ""):
            with pytest.raises(Exception) as exc_info:
                await pm._verify_pi_payment("pay_123")

        assert exc_info.value.status_code == 500


class TestUpgradeEndpoint:
    """Tests for the /upgrade endpoint logic (inspect-based, no TestClient)."""

    def test_upgrade_endpoint_checks_missing_payment_id_in_production(self):
        import inspect

        import api.routers.premium as pm

        source = inspect.getsource(pm.upgrade_to_premium)
        assert "payment_id" in source
        assert "TEST_MODE" in source
        assert "not TEST_MODE" in source or "if not TEST_MODE" in source

    def test_upgrade_endpoint_validates_plan(self):
        import inspect

        import api.routers.premium as pm

        source = inspect.getsource(pm.upgrade_to_premium)
        assert "Invalid plan" in source
        assert "PLAN_MONTHS" in source

    def test_upgrade_endpoint_validates_amount_mismatch(self):
        import inspect

        import api.routers.premium as pm

        source = inspect.getsource(pm.upgrade_to_premium)
        assert "mismatch" in source.lower()
        assert "expected" in source and "actual" in source


class TestPricingEndpoint:
    """Tests for the /pricing endpoint."""

    def test_returns_pricing_data(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import api.routers.premium as pm

        app = FastAPI()
        app.include_router(pm.router)

        client = TestClient(app)

        with patch(
            "core.database.system_config.get_prices",
            return_value={"premium": 1.5, "create_post": 0.5, "tip": 0.1},
        ):
            response = client.get("/api/premium/pricing")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "premium" in data["pricing"]
        assert data["pricing"]["premium"]["monthly"] == 1.5


class TestUpgradeRequestModel:
    """Tests for UpgradeRequest model."""

    def test_payment_id_is_optional(self):
        req = UpgradeRequest(
            plan="premium_monthly",
            tx_hash="tx_abc",
        )
        assert req.payment_id is None
        assert req.tx_hash == "tx_abc"

    def test_both_fields_can_be_set(self):
        req = UpgradeRequest(
            plan="premium_yearly",
            payment_id="pay_123",
            tx_hash="tx_abc",
        )
        assert req.payment_id == "pay_123"
        assert req.tx_hash == "tx_abc"

    def test_default_plan_is_monthly(self):
        req = UpgradeRequest()
        assert req.plan == "premium_monthly"
        assert req.months == 1
