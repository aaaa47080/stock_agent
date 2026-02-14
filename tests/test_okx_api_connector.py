"""
Tests for OKX API connector in trading/okx_api_connector.py
"""
import pytest
from unittest.mock import patch, MagicMock
import base64
import hmac
import hashlib
import json

from trading.okx_api_connector import OKXAPIConnector


class TestOKXAPIConnectorInit:
    """Tests for OKXAPIConnector initialization"""

    def test_init_with_credentials(self):
        """Test initialization with credentials"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-api-key',
            'OKX_API_SECRET': 'test-secret-key',
            'OKX_PASSPHRASE': 'test-passphrase'
        }):
            connector = OKXAPIConnector()
            assert connector.api_key == 'test-api-key'
            assert connector.secret_key == 'test-secret-key'
            assert connector.passphrase == 'test-passphrase'

    def test_init_without_credentials_shows_warning(self):
        """Test initialization without credentials shows warning"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': '',
            'OKX_API_SECRET': '',
            'OKX_PASSPHRASE': ''
        }, clear=True):
            with patch('trading.okx_api_connector.logger') as mock_logger:
                OKXAPIConnector._has_warned_missing_creds = False
                connector = OKXAPIConnector()
                assert mock_logger.warning.called

    def test_custom_base_url(self):
        """Test custom base URL"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret',
            'OKX_PASSPHRASE': 'test-pass',
            'OKX_BASE_URL': 'https://custom.okx.com'
        }):
            connector = OKXAPIConnector()
            assert connector.base_url == 'https://custom.okx.com'

    def test_default_base_url(self):
        """Test default base URL"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()
            assert connector.base_url == 'https://www.okx.com'

    def test_public_endpoints_defined(self):
        """Test public endpoints are defined"""
        connector = OKXAPIConnector()
        assert len(connector.public_endpoints) > 0
        assert '/market/ticker' in connector.public_endpoints


class TestGenerateSignature:
    """Tests for _generate_signature method"""

    def test_signature_format(self):
        """Test signature format is base64"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()
            timestamp = '2024-01-01T00:00:00.000Z'
            signature = connector._generate_signature(timestamp, 'GET', '/api/v5/account/balance')

            # Should be a non-empty base64 string
            assert signature
            assert isinstance(signature, str)

    def test_signature_includes_timestamp(self):
        """Test signature includes timestamp"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            sig1 = connector._generate_signature('2024-01-01T00:00:00.000Z', 'GET', '/api/v5/test')
            sig2 = connector._generate_signature('2024-01-01T00:00:01.000Z', 'GET', '/api/v5/test')

            # Different timestamps should produce different signatures
            assert sig1 != sig2

    def test_signature_includes_method(self):
        """Test signature includes method"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()
            timestamp = '2024-01-01T00:00:00.000Z'

            sig_get = connector._generate_signature(timestamp, 'GET', '/api/v5/test')
            sig_post = connector._generate_signature(timestamp, 'POST', '/api/v5/test')

            assert sig_get != sig_post

    def test_signature_includes_path(self):
        """Test signature includes request path"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()
            timestamp = '2024-01-01T00:00:00.000Z'

            sig1 = connector._generate_signature(timestamp, 'GET', '/api/v5/path1')
            sig2 = connector._generate_signature(timestamp, 'GET', '/api/v5/path2')

            assert sig1 != sig2

    def test_empty_signature_without_secret(self):
        """Test empty signature without secret"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': '',
            'OKX_PASSPHRASE': ''
        }):
            connector = OKXAPIConnector()
            signature = connector._generate_signature('2024-01-01T00:00:00.000Z', 'GET', '/api/v5/test')
            assert signature == ""


class TestMakeRequest:
    """Tests for _make_request method"""

    def test_get_request_with_params(self):
        """Test GET request with parameters"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {"code": "0", "data": []}
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector._make_request('GET', '/market/ticker', params={'instId': 'BTC-USDT'})

                assert result["code"] == "0"

    def test_post_request_with_data(self):
        """Test POST request with data"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {"code": "0", "data": {}}
            mock_response.raise_for_status = MagicMock()

            with patch('requests.post', return_value=mock_response):
                result = connector._make_request('POST', '/trade/order', data={'instId': 'BTC-USDT'})

                assert result["code"] == "0"

    def test_public_endpoint_without_credentials(self):
        """Test public endpoint works without credentials"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': '',
            'OKX_API_SECRET': '',
            'OKX_PASSPHRASE': ''
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {"code": "0", "data": [{"instId": "BTC-USDT"}]}
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector._make_request('GET', '/market/ticker', params={'instId': 'BTC-USDT'})

                assert result["code"] == "0"

    def test_private_endpoint_without_credentials_returns_error(self):
        """Test private endpoint returns error without credentials"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': '',
            'OKX_API_SECRET': '',
            'OKX_PASSPHRASE': ''
        }):
            connector = OKXAPIConnector()

            result = connector._make_request('GET', '/account/balance')

            assert result["code"] == "50000"
            assert "未設置" in result["msg"]

    def test_handles_request_exception(self):
        """Test handles request exception"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            with patch('requests.get', side_effect=Exception("Network error")):
                result = connector._make_request('GET', '/market/ticker')

                assert "code" in result


class TestAccountMethods:
    """Tests for account-related methods"""

    def test_get_account_balance(self):
        """Test get account balance"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": "0",
                "data": [{"ccy": "USDT", "bal": "1000.00"}]
            }
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector.get_account_balance("USDT")

                assert result["code"] == "0"

    def test_get_positions(self):
        """Test get positions"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {"code": "0", "data": []}
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector.get_positions()

                assert result["code"] == "0"


class TestMarketDataMethods:
    """Tests for market data methods"""

    def test_get_instruments(self):
        """Test get instruments"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": "0",
                "data": [{"instId": "BTC-USDT"}]
            }
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector.get_instruments("SPOT")

                assert result["code"] == "0"

    def test_get_ticker(self):
        """Test get ticker"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": "0",
                "data": [{"instId": "BTC-USDT", "last": "50000"}]
            }
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector.get_ticker("BTC-USDT")

                assert result["code"] == "0"

    def test_get_tickers(self):
        """Test get tickers"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": "0",
                "data": [{"instId": "BTC-USDT"}, {"instId": "ETH-USDT"}]
            }
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector.get_tickers("SPOT")

                assert result["code"] == "0"


class TestConnection:
    """Tests for connection testing"""

    def test_test_connection_success(self):
        """Test connection test success"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            mock_response = MagicMock()
            mock_response.json.return_value = {"code": "0", "data": []}
            mock_response.raise_for_status = MagicMock()

            with patch('requests.get', return_value=mock_response):
                result = connector.test_connection()

                # test_connection returns boolean
                assert result is True

    def test_test_connection_failure(self):
        """Test connection test failure"""
        with patch.dict('os.environ', {
            'OKX_API_KEY': 'test-key',
            'OKX_API_SECRET': 'test-secret-key-12345678901234567890',
            'OKX_PASSPHRASE': 'test-pass'
        }):
            connector = OKXAPIConnector()

            with patch('requests.get', side_effect=Exception("Connection failed")):
                result = connector.test_connection()

                # test_connection returns boolean
                assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
