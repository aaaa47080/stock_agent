"""
Tests for trading router in api/routers/trading.py
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException


class TestTradingRouter:
    """Tests for trading router"""

    def test_router_defined(self):
        """Test that router is defined"""
        from api.routers.trading import router
        assert router is not None

    def test_router_has_routes(self):
        """Test that router has routes"""
        from api.routers.trading import router
        assert len(router.routes) > 0

    def test_has_test_connection_route(self):
        """Test that test connection route exists"""
        from api.routers.trading import router
        routes = [r.path for r in router.routes]
        assert "/api/okx/test-connection" in routes

    def test_has_assets_route(self):
        """Test that assets route exists"""
        from api.routers.trading import router
        routes = [r.path for r in router.routes]
        assert "/api/account/assets" in routes

    def test_has_positions_route(self):
        """Test that positions route exists"""
        from api.routers.trading import router
        routes = [r.path for r in router.routes]
        assert "/api/account/positions" in routes

    def test_has_execute_route(self):
        """Test that execute route exists"""
        from api.routers.trading import router
        routes = [r.path for r in router.routes]
        assert "/api/trade/execute" in routes


class TestOKXConnectionEndpoint:
    """Tests for OKX connection test endpoint"""

    @pytest.mark.asyncio
    async def test_missing_credentials(self):
        """Test with missing credentials"""
        from api.routers.trading import test_okx_connection

        mock_request = MagicMock()
        mock_request.headers = {}

        mock_user = {"user_id": "test"}

        result = await test_okx_connection(mock_request, mock_user)

        assert result["success"] is False
        assert "缺少" in result["message"]

    @pytest.mark.asyncio
    async def test_valid_credentials(self):
        """Test with valid credentials"""
        from api.routers.trading import test_okx_connection

        mock_request = MagicMock()
        mock_request.headers = {
            'X-OKX-API-KEY': 'test-key',
            'X-OKX-SECRET-KEY': 'test-secret',
            'X-OKX-PASSPHRASE': 'test-pass'
        }

        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.validate_okx_credentials') as mock_validate:
            mock_validate.return_value = {"valid": True, "message": "Success"}
            result = await test_okx_connection(mock_request, mock_user)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        """Test with invalid credentials"""
        from api.routers.trading import test_okx_connection

        mock_request = MagicMock()
        mock_request.headers = {
            'X-OKX-API-KEY': 'invalid-key',
            'X-OKX-SECRET-KEY': 'invalid-secret',
            'X-OKX-PASSPHRASE': 'invalid-pass'
        }

        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.validate_okx_credentials') as mock_validate:
            mock_validate.return_value = {"valid": False, "message": "Invalid key"}
            result = await test_okx_connection(mock_request, mock_user)

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling"""
        from api.routers.trading import test_okx_connection

        mock_request = MagicMock()
        mock_request.headers = {
            'X-OKX-API-KEY': 'key',
            'X-OKX-SECRET-KEY': 'secret',
            'X-OKX-PASSPHRASE': 'pass'
        }

        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.validate_okx_credentials') as mock_validate:
            mock_validate.side_effect = Exception("Network error")
            result = await test_okx_connection(mock_request, mock_user)

            assert result["success"] is False
            assert "失敗" in result["message"]


class TestAccountAssetsEndpoint:
    """Tests for account assets endpoint"""

    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self):
        """Test that missing credentials raises HTTPException"""
        from api.routers.trading import get_account_assets

        mock_request = MagicMock()
        mock_request.headers = {}

        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request') as mock_get:
            mock_get.side_effect = HTTPException(status_code=401, detail="Missing")

            with pytest.raises(HTTPException):
                await get_account_assets(mock_request, mock_user)

    @pytest.mark.asyncio
    async def test_empty_balance(self):
        """Test with empty balance"""
        from api.routers.trading import get_account_assets

        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {"code": "0", "data": []}

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            result = await get_account_assets(mock_request, mock_user)

            assert result["total_equity"] == 0
            assert result["details"] == []

    @pytest.mark.asyncio
    async def test_successful_assets(self):
        """Test successful assets retrieval"""
        from api.routers.trading import get_account_assets

        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {
            "code": "0",
            "data": [{
                "totalEq": "1000.00",
                "uTime": "1700000000000",
                "details": [
                    {"ccy": "USDT", "eq": "500.00", "availBal": "400.00", "frozenBal": "100.00", "eqUsd": "500.00"},
                    {"ccy": "BTC", "eq": "0.05", "availBal": "0.05", "frozenBal": "0", "eqUsd": "2500.00"}
                ]
            }]
        }

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            result = await get_account_assets(mock_request, mock_user)

            assert result["total_equity"] == 1000.0
            assert len(result["details"]) == 2
            # Should be sorted by USD value
            assert result["details"][0]["usd_value"] >= result["details"][1]["usd_value"]

    @pytest.mark.asyncio
    async def test_filters_zero_balance(self):
        """Test that zero balance items are filtered"""
        from api.routers.trading import get_account_assets

        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {
            "code": "0",
            "data": [{
                "totalEq": "100.00",
                "uTime": "1700000000000",
                "details": [
                    {"ccy": "USDT", "eq": "100.00", "availBal": "100.00", "frozenBal": "0", "eqUsd": "100.00"},
                    {"ccy": "BTC", "eq": "0", "availBal": "0", "frozenBal": "0", "eqUsd": "0"}
                ]
            }]
        }

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            result = await get_account_assets(mock_request, mock_user)

            # Should filter out zero balance
            assert len(result["details"]) == 1


class TestAccountPositionsEndpoint:
    """Tests for account positions endpoint"""

    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self):
        """Test that missing credentials raises HTTPException"""
        from api.routers.trading import get_account_positions

        mock_request = MagicMock()
        mock_request.headers = {}

        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request') as mock_get:
            mock_get.side_effect = HTTPException(status_code=401, detail="Missing")

            with pytest.raises(HTTPException):
                await get_account_positions(mock_request, mock_user)

    @pytest.mark.asyncio
    async def test_empty_positions(self):
        """Test with empty positions"""
        from api.routers.trading import get_account_positions

        mock_connector = MagicMock()
        mock_connector.get_positions.return_value = {"code": "0", "data": []}

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            result = await get_account_positions(mock_request, mock_user)

            assert result["positions"] == []

    @pytest.mark.asyncio
    async def test_successful_positions(self):
        """Test successful positions retrieval"""
        from api.routers.trading import get_account_positions

        mock_connector = MagicMock()
        mock_connector.get_positions.return_value = {
            "code": "0",
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "instType": "SWAP",
                    "posSide": "long",
                    "pos": "1",
                    "avgPx": "50000",
                    "markPx": "51000",
                    "upl": "100",
                    "uplRatio": "0.02",
                    "lever": "10",
                    "margin": "5000",
                    "liqPx": "45000"
                }
            ]
        }

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            result = await get_account_positions(mock_request, mock_user)

            assert len(result["positions"]) == 1
            assert result["positions"][0]["symbol"] == "BTC-USDT-SWAP"


class TestTradeExecutionEndpoint:
    """Tests for trade execution endpoint"""

    @pytest.mark.asyncio
    async def test_spot_trade_success(self):
        """Test successful spot trade"""
        from api.routers.trading import execute_trade_api
        from api.models import TradeExecutionRequest

        mock_connector = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_spot.return_value = {"status": "success"}

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}
        trade_req = TradeExecutionRequest(
            symbol="BTC-USDT",
            market_type="spot",
            side="buy",
            amount=100.0
        )

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            with patch('api.routers.trading.TradeExecutor', return_value=mock_executor):
                result = await execute_trade_api(trade_req, mock_request, mock_user)

                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_futures_trade_success(self):
        """Test successful futures trade"""
        from api.routers.trading import execute_trade_api
        from api.models import TradeExecutionRequest

        mock_connector = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_futures.return_value = {"status": "success"}

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}
        trade_req = TradeExecutionRequest(
            symbol="BTC-USDT-SWAP",
            market_type="futures",
            side="long",
            amount=100.0,
            leverage=10
        )

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            with patch('api.routers.trading.TradeExecutor', return_value=mock_executor):
                result = await execute_trade_api(trade_req, mock_request, mock_user)

                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_invalid_market_type(self):
        """Test invalid market type"""
        from api.routers.trading import execute_trade_api
        from api.models import TradeExecutionRequest

        mock_connector = MagicMock()
        mock_executor = MagicMock()

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}
        trade_req = TradeExecutionRequest(
            symbol="BTC-USDT",
            market_type="invalid",  # Invalid type
            side="buy",
            amount=100.0
        )

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            with patch('api.routers.trading.TradeExecutor', return_value=mock_executor):
                with pytest.raises(HTTPException) as exc_info:
                    await execute_trade_api(trade_req, mock_request, mock_user)

                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_trade_failure(self):
        """Test trade execution failure"""
        from api.routers.trading import execute_trade_api
        from api.models import TradeExecutionRequest

        mock_connector = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_spot.return_value = {"status": "failed", "error": "Insufficient balance"}

        mock_request = MagicMock()
        mock_user = {"user_id": "test"}
        trade_req = TradeExecutionRequest(
            symbol="BTC-USDT",
            market_type="spot",
            side="buy",
            amount=100.0
        )

        with patch('api.routers.trading.get_okx_connector_from_request', return_value=mock_connector):
            with patch('api.routers.trading.TradeExecutor', return_value=mock_executor):
                with pytest.raises(HTTPException) as exc_info:
                    await execute_trade_api(trade_req, mock_request, mock_user)

                assert exc_info.value.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
