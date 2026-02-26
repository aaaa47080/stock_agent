"""
Tests for API request/response models in api/models.py
"""
import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock

from api.models import (
    QueryRequest,
    ScreenerRequest,
    WatchlistRequest,
    UserRegisterRequest,
    UserLoginRequest,
    KlineRequest,
    BacktestRequest,
    UserSettings,
    APIKeySettings,
    TradeExecutionRequest,
    RefreshPulseRequest,
    KeyValidationRequest
)


class TestQueryRequest:
    """Tests for QueryRequest model"""

    def test_required_fields(self):
        """Test that required fields are enforced"""
        data = {
            "message": "Test message",
            "user_api_key": "test-key",
            "user_provider": "openai"
        }
        request = QueryRequest(**data)
        assert request.message == "Test message"
        assert request.user_api_key == "test-key"
        assert request.user_provider == "openai"

    def test_default_values(self):
        """Test default values"""
        request = QueryRequest(message="Test", user_api_key="key", user_provider="google_gemini")
        assert request.interval == "1d"  # DEFAULT_INTERVAL
        assert request.auto_execute is False
        assert request.market_type == "spot"
        assert request.session_id == "default"

    def test_custom_values(self):
        """Test with custom values"""
        data = {
            "message": "Test",
            "user_api_key": "key",
            "interval": "4h",
            "limit": 200,
            "manual_selection": ["analyst1", "analyst2"],
            "auto_execute": True,
            "market_type": "futures",
            "user_provider": "openai",
            "user_model": "gpt-4",
            "session_id": "custom-session"
        }
        request = QueryRequest(**data)
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
            exchange="binance",
            symbols=["BTC", "ETH"],
            refresh=True
        )
        assert request.exchange == "binance"
        assert request.symbols == ["BTC", "ETH"]
        assert request.refresh is True


class TestWatchlistRequest:
    """Tests for WatchlistRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = WatchlistRequest(user_id="user123", symbol="BTC")
        assert request.user_id == "user123"
        assert request.symbol == "BTC"

    def test_missing_required_fields(self):
        """Test that missing fields raise ValidationError"""
        with pytest.raises(ValidationError):
            WatchlistRequest(user_id="user123")  # Missing symbol


class TestUserRegisterRequest:
    """Tests for UserRegisterRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = UserRegisterRequest(username="testuser", password="testpass")  # pragma: allowlist secret
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
        request = UserLoginRequest(username="testuser", password="testpass")  # pragma: allowlist secret
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
            symbol="SOL",
            exchange="binance",
            interval="4h",
            limit=200
        )
        assert request.exchange == "binance"
        assert request.interval == "4h"
        assert request.limit == 200


class TestBacktestRequest:
    """Tests for BacktestRequest model"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        request = BacktestRequest(symbol="BTC")
        assert request.symbol == "BTC"

    def test_default_values(self):
        """Test default values"""
        request = BacktestRequest(symbol="ETH")
        assert request.signal_type == "RSI_OVERSOLD"
        assert request.interval == "1h"

    def test_custom_values(self):
        """Test with custom signal type"""
        request = BacktestRequest(symbol="BTC", signal_type="MACD_CROSS", interval="4h")
        assert request.signal_type == "MACD_CROSS"
        assert request.interval == "4h"


class TestUserSettings:
    """Tests for UserSettings model"""

    def test_default_values(self):
        """Test default values"""
        settings = UserSettings()
        assert settings.openai_api_key is None
        assert settings.google_api_key is None
        assert settings.primary_model_provider == "google_gemini"
        assert settings.enable_committee is False
        assert settings.bull_committee_models is None

    def test_custom_values(self):
        """Test with custom values"""
        settings = UserSettings(
            openai_api_key="sk-test",  # pragma: allowlist secret
            primary_model_provider="openai",
            primary_model_name="gpt-4",
            enable_committee=True
        )
        assert settings.openai_api_key == "sk-test"  # pragma: allowlist secret
        assert settings.primary_model_provider == "openai"
        assert settings.enable_committee is True

    def test_committee_models(self):
        """Test committee model settings"""
        settings = UserSettings(
            enable_committee=True,
            bull_committee_models=[
                {"provider": "openai", "model": "gpt-4"},
                {"provider": "google_gemini", "model": "gemini-pro"}
            ],
            bear_committee_models=[
                {"provider": "openrouter", "model": "llama-2"}
            ]
        )
        assert len(settings.bull_committee_models) == 2
        assert len(settings.bear_committee_models) == 1

    def test_okx_keys(self):
        """Test OKX key settings"""
        settings = UserSettings(
            okx_api_key="okx-key",
            okx_secret_key="okx-secret",  # pragma: allowlist secret
            okx_passphrase="okx-pass"  # pragma: allowlist secret
        )
        assert settings.okx_api_key == "okx-key"
        assert settings.okx_secret_key == "okx-secret"  # pragma: allowlist secret


class TestAPIKeySettings:
    """Tests for APIKeySettings model"""

    def test_required_fields(self):
        """Test required fields"""
        settings = APIKeySettings(
            api_key="test-key",
            secret_key="test-secret",  # pragma: allowlist secret
            passphrase="test-pass"  # pragma: allowlist secret
        )
        assert settings.api_key == "test-key"
        assert settings.secret_key == "test-secret"  # pragma: allowlist secret
        assert settings.passphrase == "test-pass"  # pragma: allowlist secret

    def test_missing_fields(self):
        """Test that missing fields raise ValidationError"""
        with pytest.raises(ValidationError):
            APIKeySettings(api_key="key", secret_key="secret")  # Missing passphrase  # pragma: allowlist secret


class TestTradeExecutionRequest:
    """Tests for TradeExecutionRequest model"""

    def test_required_fields(self):
        """Test required fields"""
        request = TradeExecutionRequest(
            symbol="BTC",
            market_type="spot",
            side="buy",
            amount=100.0
        )
        assert request.symbol == "BTC"
        assert request.market_type == "spot"
        assert request.side == "buy"
        assert request.amount == 100.0

    def test_default_values(self):
        """Test default values"""
        request = TradeExecutionRequest(
            symbol="ETH",
            market_type="futures",
            side="long",
            amount=50.0
        )
        assert request.leverage == 1
        assert request.stop_loss is None
        assert request.take_profit is None

    def test_futures_with_all_fields(self):
        """Test futures trade with all optional fields"""
        request = TradeExecutionRequest(
            symbol="BTC",
            market_type="futures",
            side="short",
            amount=100.0,
            leverage=10,
            stop_loss=50000.0,
            take_profit=45000.0
        )
        assert request.leverage == 10
        assert request.stop_loss == 50000.0
        assert request.take_profit == 45000.0

    def test_various_sides(self):
        """Test various side values"""
        for side in ["buy", "sell", "long", "short"]:
            request = TradeExecutionRequest(
                symbol="BTC",
                market_type="spot",
                side=side,
                amount=100.0
            )
            assert request.side == side


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
            api_key="sk-test-key"  # pragma: allowlist secret
        )
        assert request.provider == "openai"
        assert request.api_key == "sk-test-key"  # pragma: allowlist secret
        assert request.model is None

    def test_with_model(self):
        """Test with model specified"""
        request = KeyValidationRequest(
            provider="google_gemini",
            api_key="gemini-key",
            model="gemini-pro"
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
        request = QueryRequest(message="", user_api_key="key", user_provider="openai")
        assert request.message == ""

    def test_kline_request_with_zero_limit(self):
        """Test KlineRequest with zero limit"""
        request = KlineRequest(symbol="BTC", limit=0)
        assert request.limit == 0

    def test_trade_request_with_zero_amount(self):
        """Test TradeExecutionRequest with zero amount"""
        request = TradeExecutionRequest(
            symbol="BTC",
            market_type="spot",
            side="buy",
            amount=0.0
        )
        assert request.amount == 0.0

    def test_user_settings_with_all_none(self):
        """Test UserSettings with all optional fields None"""
        settings = UserSettings()
        assert settings.openai_api_key is None
        assert settings.google_api_key is None
        assert settings.openrouter_api_key is None
        assert settings.okx_api_key is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
