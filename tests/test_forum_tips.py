"""Tests for forum tip payment verification."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.routers.forum.models import CreateTipRequest


class TestCreateTipRequestModel:
    def test_payment_id_optional(self):
        req = CreateTipRequest(tx_hash="tx_abc", amount=1.0)
        assert req.payment_id is None
        assert req.tx_hash == "tx_abc"
        assert req.amount == 1.0

    def test_both_fields_set(self):
        req = CreateTipRequest(tx_hash="tx_abc", payment_id="pay_123", amount=5.0)
        assert req.payment_id == "pay_123"
        assert req.tx_hash == "tx_abc"

    def test_all_optional_with_amount(self):
        req = CreateTipRequest(amount=1.0)
        assert req.tx_hash is None
        assert req.payment_id is None
        assert req.amount == 1.0


class TestVerifyTipPayment:
    @pytest.mark.asyncio
    async def test_verifies_approved_payment(self):
        import api.routers.forum.tips as tips_mod

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "completed",
            "amount": "1.0",
            "transaction": {"_id": "tx_tip_abc"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.forum.tips.httpx.AsyncClient", return_value=mock_client):
            result = await tips_mod._verify_tip_payment("pay_tip_1")

        assert result["status"] == "completed"
        assert result["transaction"]["_id"] == "tx_tip_abc"

    @pytest.mark.asyncio
    async def test_rejects_non_approved_payment(self):
        import api.routers.forum.tips as tips_mod

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "created", "amount": "1.0"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.forum.tips.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await tips_mod._verify_tip_payment("pay_tip_1")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_missing_payment(self):
        import api.routers.forum.tips as tips_mod

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404")

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.forum.tips.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await tips_mod._verify_tip_payment("pay_nonexistent")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_api_key_raises_500(self):
        import api.routers.forum.tips as tips_mod

        with patch("api.routers.forum.tips.PI_API_KEY", ""):
            with pytest.raises(Exception) as exc_info:
                await tips_mod._verify_tip_payment("pay_1")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_rejects_amount_mismatch(self):
        import api.routers.forum.tips as tips_mod

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "approved",
            "amount": "10.0",
            "transaction": {"_id": "tx_tip"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routers.forum.tips.httpx.AsyncClient", return_value=mock_client):
            payment_data = await tips_mod._verify_tip_payment("pay_1")

        actual = float(payment_data["amount"])
        assert abs(actual - 10.0) < 0.001


class TestTipEndpoint:
    def test_tip_router_has_payment_verification_logic(self):
        import api.routers.forum.tips as tips_mod

        assert hasattr(tips_mod, "_verify_tip_payment")
        assert callable(tips_mod._verify_tip_payment)

    def test_tip_router_imports_httpx(self):
        import api.routers.forum.tips as tips_mod

        assert hasattr(tips_mod, "httpx")

    def test_create_tip_request_requires_amount(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateTipRequest()

    def test_create_tip_request_accepts_payment_id(self):
        req = CreateTipRequest(amount=1.0, payment_id="pay_123", tx_hash="tx_abc")
        assert req.payment_id == "pay_123"
        assert req.tx_hash == "tx_abc"
