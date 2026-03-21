import pandas as pd
import pytest


@pytest.fixture
def sample_kline_df():
    n = 50
    return pd.DataFrame(
        {
            "Open_time": pd.date_range("2026-01-01", periods=n, freq="1d"),
            "Open": [100 + i * 0.5 for i in range(n)],
            "High": [105 + i * 0.5 for i in range(n)],
            "Low": [95 + i * 0.5 for i in range(n)],
            "Close": [102 + i * 0.5 for i in range(n)],
            "Volume": [1000 + i * 10 for i in range(n)],
            "Close_time": pd.date_range("2026-01-01 23:59:59", periods=n, freq="1d"),
        }
    )


@pytest.mark.unit
class TestAddTechnicalIndicators:
    def test_returns_dataframe(self, sample_kline_df):
        from data.indicator_calculator import add_technical_indicators

        result = add_technical_indicators(sample_kline_df)
        assert isinstance(result, pd.DataFrame)

    def test_adds_indicator_columns(self, sample_kline_df):
        from data.indicator_calculator import add_technical_indicators

        result = add_technical_indicators(sample_kline_df)
        assert "RSI_14" in result.columns
        assert "SMA_7" in result.columns
        assert "SMA_25" in result.columns

    def test_none_returns_empty_dataframe(self):
        from data.indicator_calculator import add_technical_indicators

        result = add_technical_indicators(None)
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_empty_dataframe_returns_empty(self):
        from data.indicator_calculator import add_technical_indicators

        result = add_technical_indicators(pd.DataFrame())
        assert result.empty

    def test_preserves_original_columns(self, sample_kline_df):
        from data.indicator_calculator import add_technical_indicators

        result = add_technical_indicators(sample_kline_df)
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in result.columns
