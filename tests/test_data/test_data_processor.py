import pandas as pd
import pytest


@pytest.mark.unit
class TestPrepareRecentHistory:
    def test_returns_list_of_dicts(self):
        from data.data_processor import prepare_recent_history

        df = pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104],
                "High": [105, 106, 107, 108, 109],
                "Low": [95, 96, 97, 98, 99],
                "Close": [101, 102, 103, 104, 105],
                "Volume": [1000, 1100, 1200, 1300, 1400],
            }
        )
        result = prepare_recent_history(df, days=3)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_days_limited_by_dataframe_length(self):
        from data.data_processor import prepare_recent_history

        df = pd.DataFrame(
            {
                "Open": [100],
                "High": [105],
                "Low": [95],
                "Close": [101],
                "Volume": [1000],
            }
        )
        result = prepare_recent_history(df, days=5)
        assert len(result) == 1

    def test_each_entry_has_expected_keys(self):
        from data.data_processor import prepare_recent_history

        df = pd.DataFrame(
            {
                "Open": [100],
                "High": [105],
                "Low": [95],
                "Close": [101],
                "Volume": [1000],
            }
        )
        result = prepare_recent_history(df, days=1)
        entry = result[0]
        assert "開盤" in entry
        assert "最高" in entry
        assert "最低" in entry
        assert "收盤" in entry
        assert "交易量" in entry


@pytest.mark.unit
class TestCalculateKeyLevels:
    def test_returns_dict_with_expected_keys(self):
        from data.data_processor import calculate_key_levels

        df = pd.DataFrame(
            {
                "High": [110, 115, 120, 125, 130, 135, 140, 145, 150, 155],
                "Low": [90, 92, 94, 96, 98, 100, 102, 104, 106, 108],
            }
        )
        result = calculate_key_levels(df, period=10)
        assert "30天最高價" in result
        assert "30天最低價" in result
        assert "支撐位" in result
        assert "壓力位" in result
        assert "20日最高價" in result
        assert "20日最低價" in result

    def test_support_less_than_resistance(self):
        from data.data_processor import calculate_key_levels

        df = pd.DataFrame(
            {
                "High": [150, 155, 160, 165, 170, 175, 180, 185, 190, 195],
                "Low": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
            }
        )
        result = calculate_key_levels(df, period=10)
        assert result["支撐位"] < result["壓力位"]


@pytest.mark.unit
class TestAnalyzeMarketStructure:
    def test_returns_dict_with_trend(self):
        from data.data_processor import analyze_market_structure

        df = pd.DataFrame(
            {
                "Close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
                "Volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
            }
        )
        result = analyze_market_structure(df)
        assert "趨勢" in result
        assert result["趨勢"] in ("上漲", "下跌")
        assert "波動率" in result
        assert "平均交易量" in result
        assert "爆量" in result

    def test_uptrend_detected(self):
        from data.data_processor import analyze_market_structure

        df = pd.DataFrame(
            {
                "Close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
                "Volume": [1000] * 10,
            }
        )
        result = analyze_market_structure(df)
        assert result["趨勢"] == "上漲"


@pytest.mark.unit
class TestExtractTechnicalIndicators:
    def test_returns_dict_with_expected_keys(self):
        from data.data_processor import extract_technical_indicators

        latest = pd.Series(
            {
                "RSI_14": 55.0,
                "MACD_12_26_9": 0.5,
                "BBU_20_2.0_2.0": 110.0,
                "BBL_20_2.0_2.0": 90.0,
                "SMA_7": 105.0,
                "SMA_25": 103.0,
            }
        )
        result = extract_technical_indicators(latest)
        assert "RSI_14" in result
        assert "MACD_線" in result
        assert "布林帶上軌" in result
        assert "布林帶下軌" in result
        assert "MA_7" in result
        assert "MA_25" in result

    def test_missing_indicators_use_defaults(self):
        from data.data_processor import extract_technical_indicators

        latest = pd.Series({})
        result = extract_technical_indicators(latest)
        assert result["RSI_14"] == 50.0
        assert result["MACD_線"] == 0


@pytest.mark.unit
class TestCalculatePriceInfo:
    def test_returns_current_price(self):
        from data.data_processor import calculate_price_info

        df = pd.DataFrame(
            {
                "Open": [100],
                "High": [110],
                "Low": [90],
                "Close": [105],
                "Volume": [1000],
            }
        )
        result = calculate_price_info(df)
        assert "當前價格" in result
        assert result["當前價格"] == 105.0

    def test_price_change_with_enough_data(self):
        from data.data_processor import calculate_price_info

        df = pd.DataFrame(
            {
                "Open": [100] * 10,
                "High": [110] * 10,
                "Low": [90] * 10,
                "Close": [100, 100, 100, 100, 100, 100, 100, 105],
                "Volume": [1000] * 8,
            }
        )
        result = calculate_price_info(df)
        assert "7天價格變化百分比" in result

    def test_single_row_no_change(self):
        from data.data_processor import calculate_price_info

        df = pd.DataFrame(
            {
                "Open": [100],
                "High": [110],
                "Low": [90],
                "Close": [100],
                "Volume": [1000],
            }
        )
        result = calculate_price_info(df)
        assert result["7天價格變化百分比"] == 0
        assert result["24小時價格變化百分比"] == 0
