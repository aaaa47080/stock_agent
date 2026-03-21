"""
Tests for market router in api/routers/market/
"""

import pytest

from api.routers.market import router
from api.routers.market.helpers import (
    compute_top_bottom_rates,
    filter_funding_data_by_symbols,
    normalize_funding_symbol,
    parse_symbols_param,
    sort_funding_rates,
)


class TestNormalizeFundingSymbol:
    """Tests for normalize_funding_symbol function"""

    def test_removes_usdt_suffix(self):
        """Test removing -USDT suffix"""
        result = normalize_funding_symbol("BTC-USDT")
        assert result == "BTC"

    def test_removes_swap_suffix(self):
        """Test removing -SWAP suffix"""
        result = normalize_funding_symbol("ETH-USDT-SWAP")
        assert result == "ETH"

    def test_removes_plain_usdt(self):
        """Test removing plain USDT"""
        result = normalize_funding_symbol("BTCUSDT")
        assert result == "BTC"

    def test_uppercase_conversion(self):
        """Test uppercase conversion"""
        result = normalize_funding_symbol("btc-usdt")
        assert result == "BTC"

    def test_combined_normalization(self):
        """Test combined normalization"""
        result = normalize_funding_symbol("btc-usdt-swap")
        assert result == "BTC"

    def test_already_normalized(self):
        """Test already normalized symbol"""
        result = normalize_funding_symbol("BTC")
        assert result == "BTC"


class TestFilterFundingDataBySymbols:
    """Tests for filter_funding_data_by_symbols function"""

    def test_filters_by_symbols(self):
        """Test filtering data by symbol list"""
        data = {
            "BTC": {"fundingRate": 0.01},
            "ETH": {"fundingRate": 0.02},
            "SOL": {"fundingRate": 0.03},
        }
        symbol_list = ["BTC", "ETH"]

        result = filter_funding_data_by_symbols(data, symbol_list)

        assert "BTC" in result
        assert "ETH" in result
        assert "SOL" not in result

    def test_empty_symbol_list(self):
        """Test with empty symbol list"""
        data = {"BTC": {"fundingRate": 0.01}}

        result = filter_funding_data_by_symbols(data, [])

        assert result == {}

    def test_normalizes_symbols(self):
        """Test that symbols are normalized during filtering"""
        data = {"BTC": {"fundingRate": 0.01}}
        symbol_list = ["BTC-USDT"]

        result = filter_funding_data_by_symbols(data, symbol_list)

        assert "BTC" in result

    def test_handles_missing_symbols(self):
        """Test handling of symbols not in data"""
        data = {"BTC": {"fundingRate": 0.01}}
        symbol_list = ["ETH"]

        result = filter_funding_data_by_symbols(data, symbol_list)

        assert result == {}


class TestParseSymbolsParam:
    """Tests for parse_symbols_param function"""

    def test_single_symbol(self):
        """Test parsing single symbol"""
        result = parse_symbols_param("BTC")
        assert result == ["BTC"]

    def test_multiple_symbols(self):
        """Test parsing multiple symbols"""
        result = parse_symbols_param("BTC,ETH,SOL")
        assert result == ["BTC", "ETH", "SOL"]

    def test_handles_spaces(self):
        """Test handling spaces"""
        result = parse_symbols_param("BTC, ETH, SOL")
        assert result == ["BTC", "ETH", "SOL"]

    def test_uppercase_conversion(self):
        """Test uppercase conversion"""
        result = parse_symbols_param("btc,eth")
        assert result == ["BTC", "ETH"]

    def test_empty_string(self):
        """Test empty string"""
        result = parse_symbols_param("")
        assert result == []

    def test_trailing_comma(self):
        """Test trailing comma"""
        result = parse_symbols_param("BTC,ETH,")
        assert result == ["BTC", "ETH"]


class TestComputeTopBottomRates:
    """Tests for compute_top_bottom_rates function"""

    def test_computes_top_and_bottom(self):
        """Test computing top and bottom rates"""
        rates = [("BTC", 0.05), ("ETH", 0.03), ("SOL", 0.02), ("DOGE", -0.01)]

        top_bullish, top_bearish = compute_top_bottom_rates(rates, 2)

        assert len(top_bullish) == 2
        assert top_bullish[0] == ("BTC", 0.05)
        assert len(top_bearish) == 2
        assert top_bearish[0] == ("DOGE", -0.01)

    def test_empty_rates(self):
        """Test with empty rates"""
        top_bullish, top_bearish = compute_top_bottom_rates([], 5)

        assert top_bullish == []
        assert top_bearish == []

    def test_fewer_rates_than_limit(self):
        """Test with fewer rates than limit"""
        rates = [("BTC", 0.05)]

        top_bullish, top_bearish = compute_top_bottom_rates(rates, 5)

        assert len(top_bullish) == 1
        assert len(top_bearish) == 1


class TestSortFundingRates:
    """Tests for sort_funding_rates function"""

    def test_sorts_descending(self):
        """Test sorting in descending order"""
        data = {
            "BTC": {"fundingRate": 0.01},
            "ETH": {"fundingRate": 0.05},
            "SOL": {"fundingRate": 0.03},
        }

        result = sort_funding_rates(data)

        assert result[0][0] == "ETH"  # Highest rate
        assert result[2][0] == "BTC"  # Lowest rate

    def test_handles_missing_rate(self):
        """Test handling missing funding rate"""
        data = {"BTC": {}}  # No fundingRate

        result = sort_funding_rates(data)

        assert result[0][1] == 0  # Default value

    def test_empty_data(self):
        """Test with empty data"""
        result = sort_funding_rates({})
        assert result == []


class TestMarketRouter:
    """Tests for market router"""

    def test_router_defined(self):
        """Test that router is defined"""
        assert router is not None

    def test_router_has_routes(self):
        """Test that router has routes"""
        assert len(router.routes) > 0

    def test_has_klines_route(self):
        """Test that klines route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/klines" in routes

    def test_has_screener_route(self):
        """Test that screener route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/screener" in routes

    def test_has_pulse_route(self):
        """Test that market pulse route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/market-pulse/{symbol}" in routes

    def test_has_funding_route(self):
        """Test that funding rates route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/funding-rates" in routes

    def test_has_symbols_route(self):
        """Test that symbols route exists"""
        routes = [r.path for r in router.routes]
        assert "/api/market/symbols" in routes

    def test_has_websocket_routes(self):
        """Test that websocket routes exist"""
        routes = [r.path for r in router.routes]
        assert "/ws/klines" in routes
        assert "/ws/tickers" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
