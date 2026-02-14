"""
Tests for Pydantic schema validation in core/tools/schemas.py
"""
import pytest
from pydantic import ValidationError

from core.tools.schemas import (
    TechnicalAnalysisInput,
    NewsAnalysisInput,
    FullInvestmentAnalysisInput,
    PriceInput,
    CurrentTimeInput,
    MarketPulseInput,
    BacktestStrategyInput,
    ExtractCryptoSymbolsInput
)


class TestTechnicalAnalysisInput:
    """Tests for TechnicalAnalysisInput schema"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        data = {"symbol": "BTC"}
        model = TechnicalAnalysisInput(**data)
        assert model.symbol == "BTC"

    def test_default_interval(self):
        """Test default interval value"""
        model = TechnicalAnalysisInput(symbol="ETH")
        assert model.interval == "1d"

    def test_default_exchange(self):
        """Test default exchange is None"""
        model = TechnicalAnalysisInput(symbol="BTC")
        assert model.exchange is None

    def test_custom_values(self):
        """Test with custom values"""
        model = TechnicalAnalysisInput(
            symbol="SOL",
            interval="4h",
            exchange="binance"
        )
        assert model.symbol == "SOL"
        assert model.interval == "4h"
        assert model.exchange == "binance"

    def test_missing_symbol_raises_error(self):
        """Test that missing symbol raises ValidationError"""
        with pytest.raises(ValidationError):
            TechnicalAnalysisInput()


class TestNewsAnalysisInput:
    """Tests for NewsAnalysisInput schema"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        model = NewsAnalysisInput(symbol="BTC")
        assert model.symbol == "BTC"

    def test_default_include_sentiment(self):
        """Test default include_sentiment is True"""
        model = NewsAnalysisInput(symbol="ETH")
        assert model.include_sentiment is True

    def test_include_sentiment_false(self):
        """Test setting include_sentiment to False"""
        model = NewsAnalysisInput(symbol="BTC", include_sentiment=False)
        assert model.include_sentiment is False


class TestFullInvestmentAnalysisInput:
    """Tests for FullInvestmentAnalysisInput schema"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        model = FullInvestmentAnalysisInput(symbol="BTC")
        assert model.symbol == "BTC"

    def test_all_defaults(self):
        """Test all default values"""
        model = FullInvestmentAnalysisInput(symbol="ETH")
        assert model.interval == "1d"
        assert model.include_futures is True
        assert model.leverage == 5

    def test_custom_leverage(self):
        """Test custom leverage value"""
        model = FullInvestmentAnalysisInput(symbol="BTC", leverage=10)
        assert model.leverage == 10

    def test_leverage_minimum(self):
        """Test leverage minimum value (ge=1)"""
        model = FullInvestmentAnalysisInput(symbol="BTC", leverage=1)
        assert model.leverage == 1

    def test_leverage_maximum(self):
        """Test leverage maximum value (le=125)"""
        model = FullInvestmentAnalysisInput(symbol="BTC", leverage=125)
        assert model.leverage == 125

    def test_leverage_below_minimum_raises_error(self):
        """Test that leverage below 1 raises ValidationError"""
        with pytest.raises(ValidationError):
            FullInvestmentAnalysisInput(symbol="BTC", leverage=0)

    def test_leverage_above_maximum_raises_error(self):
        """Test that leverage above 125 raises ValidationError"""
        with pytest.raises(ValidationError):
            FullInvestmentAnalysisInput(symbol="BTC", leverage=126)

    def test_include_futures_false(self):
        """Test setting include_futures to False"""
        model = FullInvestmentAnalysisInput(symbol="BTC", include_futures=False)
        assert model.include_futures is False


class TestPriceInput:
    """Tests for PriceInput schema"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        model = PriceInput(symbol="BTC")
        assert model.symbol == "BTC"

    def test_default_exchange(self):
        """Test default exchange is None"""
        model = PriceInput(symbol="ETH")
        assert model.exchange is None

    def test_custom_exchange(self):
        """Test custom exchange value"""
        model = PriceInput(symbol="SOL", exchange="binance")
        assert model.exchange == "binance"


class TestCurrentTimeInput:
    """Tests for CurrentTimeInput schema"""

    def test_default_timezone(self):
        """Test default timezone is Asia/Taipei"""
        model = CurrentTimeInput()
        assert model.timezone == "Asia/Taipei"

    def test_custom_timezone(self):
        """Test custom timezone value"""
        model = CurrentTimeInput(timezone="UTC")
        assert model.timezone == "UTC"

    def test_various_timezones(self):
        """Test various valid timezone strings"""
        timezones = ["America/New_York", "Europe/London", "Asia/Tokyo"]
        for tz in timezones:
            model = CurrentTimeInput(timezone=tz)
            assert model.timezone == tz


class TestMarketPulseInput:
    """Tests for MarketPulseInput schema"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        model = MarketPulseInput(symbol="BTC")
        assert model.symbol == "BTC"

    def test_various_symbols(self):
        """Test various cryptocurrency symbols"""
        for symbol in ["ETH", "SOL", "DOGE", "PI"]:
            model = MarketPulseInput(symbol=symbol)
            assert model.symbol == symbol

    def test_missing_symbol_raises_error(self):
        """Test that missing symbol raises ValidationError"""
        with pytest.raises(ValidationError):
            MarketPulseInput()


class TestBacktestStrategyInput:
    """Tests for BacktestStrategyInput schema"""

    def test_required_symbol(self):
        """Test that symbol is required"""
        model = BacktestStrategyInput(symbol="BTC")
        assert model.symbol == "BTC"

    def test_defaults(self):
        """Test default values"""
        model = BacktestStrategyInput(symbol="ETH")
        assert model.interval == "1d"
        assert model.period == 90

    def test_custom_values(self):
        """Test custom values"""
        model = BacktestStrategyInput(
            symbol="SOL",
            interval="4h",
            period=30
        )
        assert model.symbol == "SOL"
        assert model.interval == "4h"
        assert model.period == 30

    def test_various_intervals(self):
        """Test various interval values"""
        intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        for interval in intervals:
            model = BacktestStrategyInput(symbol="BTC", interval=interval)
            assert model.interval == interval


class TestExtractCryptoSymbolsInput:
    """Tests for ExtractCryptoSymbolsInput schema"""

    def test_required_user_query(self):
        """Test that user_query is required"""
        model = ExtractCryptoSymbolsInput(user_query="What is BTC price?")
        assert model.user_query == "What is BTC price?"

    def test_chinese_query(self):
        """Test with Chinese query"""
        model = ExtractCryptoSymbolsInput(user_query="BTC現在多少錢？")
        assert model.user_query == "BTC現在多少錢？"

    def test_multi_symbol_query(self):
        """Test with multiple symbols in query"""
        model = ExtractCryptoSymbolsInput(user_query="Compare BTC and ETH")
        assert "BTC" in model.user_query
        assert "ETH" in model.user_query

    def test_missing_query_raises_error(self):
        """Test that missing user_query raises ValidationError"""
        with pytest.raises(ValidationError):
            ExtractCryptoSymbolsInput()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
