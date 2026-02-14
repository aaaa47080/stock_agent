"""
Tests for OKX authentication utilities
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from fastapi import HTTPException, Request

from utils.okx_auth import (
    get_okx_connector_from_request,
    get_legacy_okx_connector,
    validate_okx_credentials
)


class TestGetOkxConnectorFromRequest:
    """Tests for get_okx_connector_from_request function"""

    def _create_mock_request(self, headers=None):
        """Helper to create mock request with headers"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = headers or {}
        return mock_request

    @patch('utils.okx_auth.OKXAPIConnector')
    def test_extracts_credentials_and_creates_connector(self, mock_connector_class):
        """Test successful credential extraction and connector creation"""
        mock_connector = MagicMock()
        mock_connector_class.return_value = mock_connector

        headers = {
            'X-OKX-API-KEY': 'test-api-key',
            'X-OKX-SECRET-KEY': 'test-secret-key',
            'X-OKX-PASSPHRASE': 'test-passphrase'
        }
        request = self._create_mock_request(headers)

        result = get_okx_connector_from_request(request)

        assert result.api_key == 'test-api-key'
        assert result.secret_key == 'test-secret-key'
        assert result.passphrase == 'test-passphrase'

    def test_raises_401_when_api_key_missing(self):
        """Test that missing API key raises 401"""
        headers = {
            'X-OKX-SECRET-KEY': 'test-secret-key',
            'X-OKX-PASSPHRASE': 'test-passphrase'
        }
        request = self._create_mock_request(headers)

        with pytest.raises(HTTPException) as exc_info:
            get_okx_connector_from_request(request)

        assert exc_info.value.status_code == 401
        assert "missing_okx_credentials" in str(exc_info.value.detail)

    def test_raises_401_when_secret_key_missing(self):
        """Test that missing secret key raises 401"""
        headers = {
            'X-OKX-API-KEY': 'test-api-key',
            'X-OKX-PASSPHRASE': 'test-passphrase'
        }
        request = self._create_mock_request(headers)

        with pytest.raises(HTTPException) as exc_info:
            get_okx_connector_from_request(request)

        assert exc_info.value.status_code == 401

    def test_raises_401_when_passphrase_missing(self):
        """Test that missing passphrase raises 401"""
        headers = {
            'X-OKX-API-KEY': 'test-api-key',
            'X-OKX-SECRET-KEY': 'test-secret-key'
        }
        request = self._create_mock_request(headers)

        with pytest.raises(HTTPException) as exc_info:
            get_okx_connector_from_request(request)

        assert exc_info.value.status_code == 401

    def test_raises_401_when_all_credentials_missing(self):
        """Test that missing all credentials raises 401"""
        request = self._create_mock_request({})

        with pytest.raises(HTTPException) as exc_info:
            get_okx_connector_from_request(request)

        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert detail["error"] == "missing_okx_credentials"


class TestGetLegacyOkxConnector:
    """Tests for get_legacy_okx_connector function"""

    def test_raises_503_when_not_initialized(self):
        """Test that 503 is raised when connector not initialized"""
        with pytest.raises(HTTPException) as exc_info:
            get_legacy_okx_connector()

        assert exc_info.value.status_code == 503
        assert "尚未初始化" in str(exc_info.value.detail)


class TestValidateOkxCredentials:
    """Tests for validate_okx_credentials function"""

    @patch('utils.okx_auth.OKXAPIConnector')
    def test_valid_credentials_returns_success(self, mock_connector_class):
        """Test that valid credentials return success"""
        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {"code": "0", "data": []}
        mock_connector_class.return_value = mock_connector

        result = validate_okx_credentials(
            api_key="test-key",
            secret_key="test-secret",
            passphrase="test-pass"
        )

        assert result["valid"] is True
        assert "成功" in result["message"]
        assert result["details"]["connection"] == "ok"

    @patch('utils.okx_auth.OKXAPIConnector')
    def test_invalid_credentials_returns_failure(self, mock_connector_class):
        """Test that invalid credentials return failure"""
        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {
            "code": "50113",
            "msg": "Invalid API key"
        }
        mock_connector_class.return_value = mock_connector

        result = validate_okx_credentials(
            api_key="invalid-key",
            secret_key="invalid-secret",
            passphrase="invalid-pass"
        )

        assert result["valid"] is False
        assert "失敗" in result["message"]
        assert result["details"]["error_code"] == "50113"

    @patch('utils.okx_auth.OKXAPIConnector')
    def test_exception_returns_failure_with_details(self, mock_connector_class):
        """Test that exceptions are caught and returned as failure"""
        mock_connector = MagicMock()
        mock_connector.get_account_balance.side_effect = ConnectionError("Network error")
        mock_connector_class.return_value = mock_connector

        result = validate_okx_credentials(
            api_key="test-key",
            secret_key="test-secret",
            passphrase="test-pass"
        )

        assert result["valid"] is False
        assert "錯誤" in result["message"]
        assert "Network error" in result["details"]["exception"]

    @patch('utils.okx_auth.OKXAPIConnector')
    def test_sets_credentials_on_connector(self, mock_connector_class):
        """Test that credentials are set on the connector"""
        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {"code": "0"}
        mock_connector_class.return_value = mock_connector

        validate_okx_credentials(
            api_key="my-api-key",
            secret_key="my-secret-key",
            passphrase="my-passphrase"
        )

        assert mock_connector.api_key == "my-api-key"
        assert mock_connector.secret_key == "my-secret-key"
        assert mock_connector.passphrase == "my-passphrase"


class TestOkxAuthIntegration:
    """Integration-like tests for OKX auth module"""

    @patch('utils.okx_auth.OKXAPIConnector')
    def test_full_flow_with_valid_credentials(self, mock_connector_class):
        """Test the full flow with valid credentials"""
        mock_connector = MagicMock()
        mock_connector.get_account_balance.return_value = {"code": "0", "data": []}
        mock_connector_class.return_value = mock_connector

        # Validate credentials
        validation = validate_okx_credentials("key", "secret", "pass")
        assert validation["valid"] is True

    def test_error_messages_are_user_friendly(self):
        """Test that error messages are user-friendly (Chinese)"""
        headers = {}
        request = MagicMock(spec=Request)
        request.headers = headers

        with pytest.raises(HTTPException) as exc_info:
            get_okx_connector_from_request(request)

        detail = exc_info.value.detail
        # Check that the message contains Chinese characters
        assert any('\u4e00' <= c <= '\u9fff' for c in str(detail))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
