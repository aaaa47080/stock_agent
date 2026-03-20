"""
Tests for API request/response models in api/models.py
"""

import pytest
from pydantic import ValidationError

from api.models import (
    KeyValidationRequest,
    KlineRequest,
    QueryRequest,
    RefreshPulseRequest,
    ScreenerRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserSettings,
    WatchlistRequest,
)


class TestQueryRequest:
    """Tests for QueryRequest model"""

    def test_required_fields(self):
        """Test that required fields are enforced"""
        data = {
            "message": "Test message",
            "user_api_key": "test-key-12345",
            "user_provider": "openai",
        }
        request = QueryRequest(**data)
        assert request.message == "Test message"
        assert request.user_api_key == "test-key-12345"
        assert request.user_provider == "openai"

    def test_default_values(self):
        """Test default values"""
        request = QueryRequest(
            message="Test", user_api_key="key-1234567", user_provider="google_gemini"
        )
        assert request.analysis_mode == "quick"
        assert request.interval == "1d"  # DEFAULT_INTERVAL
        assert request.auto_execute is False
        assert request.market_type == "spot"
        assert request.session_id == "default"

    def test_custom_values(self):
        """Test with custom values"""
        data = {
            "message": "Test",
            "analysis_mode": "verified",
            "user_api_key": "key-1234567",
            "interval": "4h",
            "limit": 200,
            "manual_selection": ["analyst1", "analyst2"],
            "auto_execute": True,
            "market_type": "futures",
            "user_provider": "openai",
            "user_model": "gpt-4",
            "session_id": "custom-session",
        }
        request = QueryRequest(**data)
        assert request.analysis_mode == "verified"
        assert request.interval == "4h"
        assert request.limit == 200
        assert request.auto_execute is True
        assert request.market_type == "futures"

    def test_missing_required_fields(self):
        """Test that missing required fields raise ValidationError"""
        with pytest.raises(ValidationError):
            QueryRequest(message="Test")  # Missing user_api_key


class TestScreenerRequest:
    """Tests for ScreenerRequest model"""

    def test_default_values(self):
        """Test default values"""
        request = ScreenerRequest()
        assert request.exchange == "okx"  # SUPPORTED_EXCHANGES[0]
        assert request.symbols is None
        assert request.refresh is False

    def test_custom_values(self):
        """Test with custom values"""
        request = ScreenerRequest(
            exchange="binance", symbols=["BTC", "ETH"], refresh=True
        )
        assert request.exchange == "binance"
        assert request.symbols == ["BTC", "ETH"]
        assert request.refresh is True


class TestWatchlistRequest:
    """Tests for WatchlistRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = WatchlistRequest(symbol="BTC")
        assert request.symbol == "BTC"

    def test_missing_required_fields(self):
        """Test that missing fields raise ValidationError"""
        with pytest.raises(ValidationError):
            WatchlistRequest()  # Missing symbol


class TestUserRegisterRequest:
    """Tests for UserRegisterRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = UserRegisterRequest(
            username="testuser", password="testpass"
        )  # pragma: allowlist secret
        assert request.username == "testuser"
        assert request.password == "testpass"  # pragma: allowlist secret

    def test_missing_fields(self):
        """Test that missing fields raise ValidationError"""
        with pytest.raises(ValidationError):
            UserRegisterRequest(username="testuser")


class TestUserLoginRequest:
    """Tests for UserLoginRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = UserLoginRequest(
            username="testuser", password="testpass"
        )  # pragma: allowlist secret
        assert request.username == "testuser"
        assert request.password == "testpass"  # pragma: allowlist secret


class TestKlineRequest:
    """Tests for KlineRequest model"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        request = KlineRequest(symbol="BTC")
        assert request.symbol == "BTC"

    def test_default_values(self):
        """Test default values"""
        request = KlineRequest(symbol="ETH")
        assert request.exchange == "okx"
        assert request.interval == "1d"
        assert request.limit == 100

    def test_custom_values(self):
        """Test with custom values"""
        request = KlineRequest(
            symbol="SOL", exchange="binance", interval="4h", limit=200
        )
        assert request.exchange == "binance"
        assert request.interval == "4h"
        assert request.limit == 200


class TestUserSettings:
    """Tests for UserSettings model"""

    def test_default_values(self):
        """Test default values"""
        settings = UserSettings()
        assert settings.openai_api_key is None
        assert settings.google_api_key is None
        assert settings.primary_model_provider == "google_gemini"

    def test_custom_values(self):
        """Test with custom values"""
        settings = UserSettings(
            openai_api_key="sk-test",  # pragma: allowlist secret
            primary_model_provider="openai",
            primary_model_name="gpt-4",
        )
        assert settings.openai_api_key == "sk-test"  # pragma: allowlist secret
        assert settings.primary_model_provider == "openai"


class TestRefreshPulseRequest:
    """Tests for RefreshPulseRequest model"""

    def test_default_symbols_none(self):
        """Test default symbols is None"""
        request = RefreshPulseRequest()
        assert request.symbols is None

    def test_custom_symbols(self):
        """Test with custom symbols"""
        request = RefreshPulseRequest(symbols=["BTC", "ETH", "SOL"])
        assert request.symbols == ["BTC", "ETH", "SOL"]

    def test_empty_symbols_list(self):
        """Test with empty symbols list"""
        request = RefreshPulseRequest(symbols=[])
        assert request.symbols == []


class TestKeyValidationRequest:
    """Tests for KeyValidationRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = KeyValidationRequest(
            provider="openai",
            api_key="sk-test-key",  # pragma: allowlist secret
        )
        assert request.provider == "openai"
        assert request.api_key == "sk-test-key"  # pragma: allowlist secret
        assert request.model is None

    def test_with_model(self):
        """Test with model specified"""
        request = KeyValidationRequest(
            provider="google_gemini", api_key="gemini-key", model="gemini-pro"
        )
        assert request.model == "gemini-pro"

    def test_various_providers(self):
        """Test various provider values"""
        for provider in ["openai", "google_gemini", "openrouter"]:
            request = KeyValidationRequest(provider=provider, api_key="test-key")
            assert request.provider == provider


class TestModelValidation:
    """Tests for model validation edge cases"""

    def test_query_request_with_empty_message(self):
        """Test QueryRequest with empty message"""
        request = QueryRequest(message="", user_api_key="key-1234567", user_provider="openai")
        assert request.message == ""

    def test_kline_request_with_zero_limit(self):
        """Test KlineRequest with zero limit"""
        request = KlineRequest(symbol="BTC", limit=0)
        assert request.limit == 0

    def test_user_settings_with_all_none(self):
        """Test UserSettings with all optional fields None"""
        settings = UserSettings()
        assert settings.openai_api_key is None
        assert settings.google_api_key is None
        assert settings.openrouter_api_key is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
