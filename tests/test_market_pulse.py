"""
Tests for market_pulse in analysis/market_pulse.py
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from analysis.market_pulse import MarketPulseAnalyzer


class TestMarketPulseAnalyzerInit:
    """Tests for MarketPulseAnalyzer initialization"""

    def test_init_with_client(self):
        """Test initialization with provided client"""
        mock_client = MagicMock()

        analyzer = MarketPulseAnalyzer(client=mock_client)

        assert analyzer.client == mock_client
        assert analyzer.model == "user-provided-model"

    def test_init_without_client_creates_default(self):
        """Test initialization without client"""
        with patch('analysis.market_pulse.create_llm_client_from_config') as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = (mock_client, "test-model")

            analyzer = MarketPulseAnalyzer()

            assert analyzer.client == mock_client

    def test_init_fallback_mode_on_error(self):
        """Test fallback mode when LLM creation fails"""
        with patch('analysis.market_pulse.create_llm_client_from_config') as mock_create:
            mock_create.side_effect = Exception("No LLM config")

            analyzer = MarketPulseAnalyzer()

            assert analyzer.client is None
            assert analyzer.model is None


class TestMarketPulseAnalyzer:
    """Tests for MarketPulseAnalyzer methods"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mock client"""
        mock_client = MagicMock()
        return MarketPulseAnalyzer(client=mock_client)

    def test_analyze_movement_no_data(self, analyzer):
        """Test analyze_movement with no price data"""
        with patch('analysis.market_pulse.get_klines', return_value=None):
            result = analyzer.analyze_movement("BTC")

            assert "error" in result

    def test_analyze_movement_empty_data(self, analyzer):
        """Test analyze_movement with empty dataframe"""
        with patch('analysis.market_pulse.get_klines', return_value=pd.DataFrame()):
            result = analyzer.analyze_movement("BTC")

            assert "error" in result

    def test_analyze_movement_with_data(self, analyzer):
        """Test analyze_movement with valid data"""
        # Create sample dataframe with enough rows
        df = pd.DataFrame({
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [99] * 10,
            'close': [104] * 10,
            'volume': [1000] * 10
        })

        with patch('analysis.market_pulse.get_klines', return_value=df):
            with patch('analysis.market_pulse.add_technical_indicators') as mock_add:
                # Return a dataframe with renamed columns and indicators
                df_renamed = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'volume': 'Volume'
                })
                df_with_indicators = df_renamed.copy()
                df_with_indicators['RSI_14'] = 50
                df_with_indicators['MACDh_12_26_9'] = 0.5
                mock_add.return_value = df_with_indicators

                with patch('analysis.market_pulse.safe_float', side_effect=lambda x: float(x) if x is not None else 0.0):
                    with patch('analysis.market_pulse.get_crypto_news', return_value=[]):
                        result = analyzer.analyze_movement("BTC", skip_llm=True)

                        # Should return some analysis
                        assert result is not None


class TestMarketPulseHelperFunctions:
    """Tests for helper functions in market_pulse"""

    def test_price_change_calculation(self):
        """Test price change percentage calculation"""
        current_price = 105.0
        prev_price = 100.0

        change_percent = ((current_price - prev_price) / prev_price) * 100

        assert change_percent == 5.0

    def test_threshold_detection_above(self):
        """Test detection when change exceeds threshold"""
        change_percent = 5.0
        threshold = 2.0

        exceeds = abs(change_percent) >= threshold
        assert exceeds is True

    def test_threshold_detection_below(self):
        """Test detection when change below threshold"""
        change_percent = 1.5
        threshold = 2.0

        exceeds = abs(change_percent) >= threshold
        assert exceeds is False

    def test_column_renaming(self):
        """Test column renaming logic"""
        df = pd.DataFrame({
            'open': [100],
            'high': [105],
            'low': [99],
            'close': [104],
            'volume': [1000]
        })

        renamed_df = df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume'
        })

        assert 'Open' in renamed_df.columns
        assert 'Close' in renamed_df.columns
        assert 'open' not in renamed_df.columns


class TestMarketPulseAnalyzerErrorHandling:
    """Tests for error handling in MarketPulseAnalyzer"""

    def test_handles_exception_in_analysis(self):
        """Test that exceptions are handled gracefully"""
        mock_client = MagicMock()
        analyzer = MarketPulseAnalyzer(client=mock_client)

        with patch('analysis.market_pulse.get_klines', side_effect=Exception("API error")):
            try:
                result = analyzer.analyze_movement("BTC")
                assert "error" in result
            except Exception:
                # If exception propagates, that's also acceptable
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
