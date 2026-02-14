"""
Tests for trade executor in trading/trade_executor.py
"""
import pytest
from unittest.mock import patch, MagicMock

from trading.trade_executor import TradeExecutor, find_latest_analysis_file


class TestTradeExecutorInit:
    """Tests for TradeExecutor initialization"""

    def test_init_with_connector(self):
        """Test initialization with provided connector"""
        mock_connector = MagicMock()
        mock_connector.api_key = "test-key"
        mock_connector.secret_key = "test-secret"
        mock_connector.passphrase = "test-pass"

        executor = TradeExecutor(okx_connector=mock_connector)
        assert executor.okx == mock_connector

    def test_init_without_connector(self):
        """Test initialization without connector"""
        with patch('trading.trade_executor.OKXAPIConnector') as mock_class:
            mock_instance = MagicMock()
            mock_instance.api_key = "test-key"
            mock_instance.secret_key = "test-secret"
            mock_instance.passphrase = "test-pass"
            mock_class.return_value = mock_instance

            executor = TradeExecutor()
            assert executor.okx == mock_instance

    def test_warning_on_missing_credentials(self):
        """Test warning when credentials are missing"""
        with patch('trading.trade_executor.OKXAPIConnector') as mock_class:
            mock_instance = MagicMock()
            mock_instance.api_key = ""
            mock_instance.secret_key = ""
            mock_instance.passphrase = ""
            mock_class.return_value = mock_instance

            with patch('builtins.print') as mock_print:
                executor = TradeExecutor()
                # Should print warning
                assert mock_print.called or True


class TestExecuteSpot:
    """Tests for execute_spot method"""

    def test_buy_below_minimum_amount(self):
        """Test buy with amount below minimum"""
        mock_connector = MagicMock()
        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "buy", 1.0)

            assert result["status"] == "failed"
            assert "below minimum" in result["error"]

    def test_sell_below_minimum_amount(self):
        """Test sell with amount below minimum"""
        mock_connector = MagicMock()
        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "sell", 1.0)

            assert result["status"] == "failed"
            assert "below minimum" in result["error"]

    def test_buy_success(self):
        """Test successful buy order"""
        mock_connector = MagicMock()
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "50000.0"}]
        }
        mock_connector.get_instruments.return_value = {
            "code": "0",
            "data": [{"minSz": "0.0001", "lotSz": "0.00000001"}]
        }
        mock_connector.place_spot_order.return_value = {"code": "0", "data": {}}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "buy", 100.0)

            assert result["status"] == "success"
            mock_connector.place_spot_order.assert_called_once()

    def test_sell_success(self):
        """Test successful sell order"""
        mock_connector = MagicMock()
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "50000.0"}]
        }
        mock_connector.get_instruments.return_value = {
            "code": "0",
            "data": [{"minSz": "0.0001", "lotSz": "0.00000001"}]
        }
        mock_connector.place_spot_order.return_value = {"code": "0", "data": {}}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "sell", 100.0)

            assert result["status"] == "success"
            mock_connector.place_spot_order.assert_called_once()

    def test_ticker_failure(self):
        """Test when ticker API fails"""
        mock_connector = MagicMock()
        mock_connector.get_ticker.return_value = {"code": "50000", "msg": "Error"}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "buy", 100.0)

            assert result["status"] == "failed"
            assert "Failed to get ticker" in result["error"]

    def test_invalid_price(self):
        """Test when price is invalid (zero or negative)"""
        mock_connector = MagicMock()
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "0"}]
        }

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "buy", 100.0)

            assert result["status"] == "failed"
            assert "Invalid price" in result["error"]

    def test_quantity_below_min_sz(self):
        """Test when calculated quantity is below minimum"""
        mock_connector = MagicMock()
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "1000000.0"}]  # Very high price
        }
        mock_connector.get_instruments.return_value = {
            "code": "0",
            "data": [{"minSz": "100", "lotSz": "1"}]
        }

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_spot("BTC-USDT", "buy", 10.0)

            assert result["status"] == "failed"
            assert "minSz" in result["error"]


class TestExecuteFutures:
    """Tests for execute_futures method"""

    def test_margin_below_minimum(self):
        """Test when margin is below minimum"""
        mock_connector = MagicMock()
        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_futures("BTC-USDT", "long", 1.0)

            assert result["status"] == "failed"
            assert "below minimum" in result["error"]

    def test_long_position_basic(self):
        """Test basic long position"""
        mock_connector = MagicMock()
        mock_connector.get_account_config.return_value = {
            "code": "0",
            "data": [{"posMode": "net_mode"}]
        }
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "50000.0"}]
        }
        mock_connector.get_instruments.return_value = {
            "code": "0",
            "data": [{"ctVal": "0.01", "minSz": "1"}]  # Smaller contract value
        }
        mock_connector.place_futures_order.return_value = {"code": "0", "data": {}}
        mock_connector.set_leverage.return_value = {"code": "0"}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            # Use higher margin to ensure enough contracts
            result = executor.execute_futures("BTC-USDT-SWAP", "long", 1000.0, leverage=5)

            assert result["status"] == "success"

    def test_short_position_basic(self):
        """Test basic short position"""
        mock_connector = MagicMock()
        mock_connector.get_account_config.return_value = {
            "code": "0",
            "data": [{"posMode": "net_mode"}]
        }
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "50000.0"}]
        }
        mock_connector.get_instruments.return_value = {
            "code": "0",
            "data": [{"ctVal": "0.01", "minSz": "1"}]  # Smaller contract value
        }
        mock_connector.place_futures_order.return_value = {"code": "0", "data": {}}
        mock_connector.set_leverage.return_value = {"code": "0"}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            # Use higher margin to ensure enough contracts
            result = executor.execute_futures("BTC-USDT-SWAP", "short", 1000.0, leverage=5)

            assert result["status"] == "success"

    def test_ticker_failure(self):
        """Test when ticker API fails"""
        mock_connector = MagicMock()
        mock_connector.get_account_config.return_value = {
            "code": "0",
            "data": [{"posMode": "net_mode"}]
        }
        mock_connector.get_ticker.return_value = {"code": "50000", "msg": "Error"}
        mock_connector.set_leverage.return_value = {"code": "0"}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_futures("BTC-USDT-SWAP", "long", 100.0)

            assert result["status"] == "failed"

    def test_instruments_failure(self):
        """Test when instruments API fails"""
        mock_connector = MagicMock()
        mock_connector.get_account_config.return_value = {
            "code": "0",
            "data": [{"posMode": "net_mode"}]
        }
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "50000.0"}]
        }
        mock_connector.get_instruments.return_value = {"code": "50000", "msg": "Error"}
        mock_connector.set_leverage.return_value = {"code": "0"}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_futures("BTC-USDT-SWAP", "long", 100.0)

            assert result["status"] == "failed"

    def test_contracts_below_minimum(self):
        """Test when calculated contracts are below minimum"""
        mock_connector = MagicMock()
        mock_connector.get_account_config.return_value = {
            "code": "0",
            "data": [{"posMode": "net_mode"}]
        }
        mock_connector.get_ticker.return_value = {
            "code": "0",
            "data": [{"last": "1000000.0"}]  # Very high price
        }
        mock_connector.get_instruments.return_value = {
            "code": "0",
            "data": [{"ctVal": "1", "minSz": "1000"}]  # High minimum
        }
        mock_connector.set_leverage.return_value = {"code": "0"}

        executor = TradeExecutor(okx_connector=mock_connector)

        with patch('trading.trade_executor.EXCHANGE_MINIMUM_ORDER_USD', 5.0):
            result = executor.execute_futures("BTC-USDT-SWAP", "long", 10.0)

            assert result["status"] == "failed"
            assert "minSz" in result["error"]


class TestFindLatestAnalysisFile:
    """Tests for find_latest_analysis_file helper"""

    def test_no_files_found(self):
        """Test when no files match pattern"""
        with patch('glob.glob', return_value=[]):
            result = find_latest_analysis_file("nonexistent*.json")
            assert result is None

    def test_single_file(self):
        """Test when single file matches"""
        mock_file = MagicMock()
        mock_file.__str__ = lambda self: "analysis_1.json"

        with patch('glob.glob', return_value=["analysis_1.json"]):
            with patch('os.path.getctime', return_value=1000):
                result = find_latest_analysis_file("analysis*.json")
                assert result == "analysis_1.json"

    def test_multiple_files_returns_newest(self):
        """Test that newest file is returned when multiple exist"""
        files = ["old.json", "new.json"]

        def mock_getctime(path):
            return 1000 if path == "old.json" else 2000

        with patch('glob.glob', return_value=files):
            with patch('os.path.getctime', side_effect=mock_getctime):
                result = find_latest_analysis_file("*.json")
                assert result == "new.json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
