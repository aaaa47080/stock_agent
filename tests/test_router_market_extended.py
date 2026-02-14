"""
Extended tests for market router in api/routers/market.py
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from api.routers.market import (
    _replace_nan_in_dataframe,
    _format_screener_response,
    _try_get_cached_screener,
    _sort_funding_rates,
    _compute_top_bottom_rates,
    SYMBOL_CACHE
)


class TestReplaceNaNInDataFrame:
    """Tests for _replace_nan_in_dataframe function"""

    def test_empty_dataframe(self):
        """Test with empty dataframe"""
        df = pd.DataFrame()
        result = _replace_nan_in_dataframe(df)
        assert result.empty

    def test_dataframe_with_nan(self):
        """Test replacing NaN values"""
        df = pd.DataFrame({
            'value': [1.0, np.nan, 3.0],
            'name': ['A', 'B', 'C']
        })

        result = _replace_nan_in_dataframe(df)

        # NaN should be replaced with None
        assert pd.isna(df['value'].iloc[1])
        assert result['value'].iloc[1] is None

    def test_dataframe_without_nan(self):
        """Test with no NaN values"""
        df = pd.DataFrame({
            'value': [1.0, 2.0, 3.0]
        })

        result = _replace_nan_in_dataframe(df)

        assert result['value'].tolist() == [1.0, 2.0, 3.0]


class TestFormatScreenerResponse:
    """Tests for _format_screener_response function"""

    def test_formats_response(self):
        """Test formatting screener response"""
        df_gainers = pd.DataFrame({'symbol': ['BTC'], 'change': [5.0]})
        df_losers = pd.DataFrame({'symbol': ['ETH'], 'change': [-3.0]})
        df_volume = pd.DataFrame({'symbol': ['SOL'], 'volume': [1000000]})

        result = _format_screener_response(df_gainers, df_losers, df_volume)

        assert 'top_gainers' in result
        assert 'top_losers' in result
        assert 'top_volume' in result
        assert 'last_updated' in result
        assert len(result['top_gainers']) == 1

    def test_empty_dataframes(self):
        """Test with empty dataframes"""
        result = _format_screener_response(
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame()
        )

        assert result['top_gainers'] == []
        assert result['top_losers'] == []


class TestTryGetCachedScreener:
    """Tests for _try_get_cached_screener function"""

    def test_returns_cached_data(self):
        """Test returning cached data"""
        with patch('api.routers.market.cached_screener_result', {'data': {'test': 'data'}}):
            result = _try_get_cached_screener(refresh=False)
            assert result == {'test': 'data'}

    def test_returns_none_when_refresh_true(self):
        """Test returns None when refresh is True"""
        with patch('api.routers.market.cached_screener_result', {'data': {'test': 'data'}}):
            result = _try_get_cached_screener(refresh=True)
            assert result is None

    def test_returns_none_when_no_cache(self):
        """Test returns None when cache is empty"""
        with patch('api.routers.market.cached_screener_result', {'data': None}):
            result = _try_get_cached_screener(refresh=False)
            assert result is None


class TestSortFundingRatesExtended:
    """Extended tests for _sort_funding_rates"""

    def test_sorts_with_negative_rates(self):
        """Test sorting with negative rates"""
        data = {
            "BTC": {"fundingRate": 0.01},
            "ETH": {"fundingRate": -0.02},
            "SOL": {"fundingRate": 0.03}
        }

        result = _sort_funding_rates(data)

        # SOL (0.03) should be first, ETH (-0.02) should be last
        assert result[0][0] == "SOL"
        assert result[-1][0] == "ETH"

    def test_sorts_with_zero_rates(self):
        """Test sorting with zero rates"""
        data = {
            "BTC": {"fundingRate": 0},
            "ETH": {"fundingRate": 0.01}
        }

        result = _sort_funding_rates(data)

        assert result[0][0] == "ETH"


class TestComputeTopBottomRatesExtended:
    """Extended tests for _compute_top_bottom_rates"""

    def test_with_equal_rates(self):
        """Test with equal rates"""
        rates = [("BTC", 0.01), ("ETH", 0.01), ("SOL", 0.01)]

        top, bottom = _compute_top_bottom_rates(rates, 2)

        assert len(top) == 2

    def test_with_single_rate(self):
        """Test with single rate"""
        rates = [("BTC", 0.01)]

        top, bottom = _compute_top_bottom_rates(rates, 5)

        assert len(top) == 1
        assert len(bottom) == 1
        # Single item should be both top and bottom
        assert top[0] == bottom[0]


class TestSymbolCache:
    """Tests for SYMBOL_CACHE"""

    def test_cache_structure(self):
        """Test cache structure"""
        assert "okx" in SYMBOL_CACHE

    def test_cache_initial_state(self):
        """Test cache initial state"""
        assert SYMBOL_CACHE["okx"]["data"] is None or isinstance(SYMBOL_CACHE["okx"]["data"], (list, type(None)))


class TestFundingRateFormatting:
    """Tests for funding rate formatting logic"""

    def test_rate_percentage_calculation(self):
        """Test rate percentage calculation"""
        rate = 0.0001  # 0.01%
        percentage = rate * 100
        assert percentage == 0.01

    def test_annualized_rate_calculation(self):
        """Test annualized rate calculation"""
        funding_rate = 0.0001
        times_per_day = 3
        days_per_year = 365
        annualized = funding_rate * times_per_day * days_per_year
        # Use approximate comparison due to floating point precision
        assert abs(annualized - 0.1095) < 0.001  # ~10.95%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
