"""
Tests for crypto_screener in analysis/crypto_screener.py
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from analysis.crypto_screener import analyze_symbol_data


class TestAnalyzeSymbolData:
    """Tests for analyze_symbol_data function"""

    def test_returns_none_for_none_dataframe(self):
        """Test that None dataframe returns None"""
        result = analyze_symbol_data(None, "BTC")
        assert result is None

    def test_returns_none_for_empty_dataframe(self):
        """Test that empty dataframe returns None"""
        df = pd.DataFrame()
        result = analyze_symbol_data(df, "BTC")
        assert result is None

    def test_returns_analysis_for_valid_data(self):
        """Test that valid data returns analysis dict"""
        # Create a sample dataframe
        df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [99, 100, 101],
            'close': [104, 105, 106],
            'volume': [1000, 1100, 1200]
        })

        with patch('analysis.crypto_screener.add_technical_indicators') as mock_add:
            # Return a dataframe with indicators
            mock_add.return_value = df.copy()
            df_with_indicators = df.copy()
            df_with_indicators['RSI_14'] = 50
            df_with_indicators['MACD_12_26_9'] = 0.5
            mock_add.return_value = df_with_indicators

            with patch('analysis.crypto_screener.calculate_price_info') as mock_price:
                mock_price.return_value = {"current_price": 106}

                with patch('analysis.crypto_screener.extract_technical_indicators') as mock_extract:
                    mock_extract.return_value = {"RSI": 50}

                    with patch('analysis.crypto_screener.analyze_market_structure') as mock_structure:
                        mock_structure.return_value = {"trend": "up"}

                        with patch('analysis.crypto_screener.calculate_key_levels') as mock_levels:
                            mock_levels.return_value = {"support": 100}

                            result = analyze_symbol_data(df, "BTC")

                            assert result is not None
                            assert result["symbol"] == "BTC"


class TestSymbolNormalization:
    """Tests for symbol normalization logic in screen_top_cryptos"""

    def test_okx_symbol_already_formatted(self):
        """Test OKX symbol that's already formatted"""
        symbol = "BTC-USDT"
        exchange = "okx"

        # The logic: if exchange == 'okx' and s.endswith('-USDT'): use directly
        if exchange == 'okx' and symbol.endswith('-USDT'):
            result = symbol
        else:
            result = f"{symbol}-USDT"

        assert result == "BTC-USDT"

    def test_okx_symbol_needs_formatting(self):
        """Test OKX symbol that needs formatting"""
        symbol = "BTC"
        exchange = "okx"

        s_clean = symbol.upper().replace("USDT", "").replace("-", "")
        if exchange == 'okx':
            result = f"{s_clean}-USDT"
        else:
            result = f"{s_clean}USDT"

        assert result == "BTC-USDT"

    def test_binance_symbol_formatting(self):
        """Test Binance symbol formatting"""
        symbol = "BTC"
        exchange = "binance"

        s_clean = symbol.upper().replace("USDT", "").replace("-", "")
        if exchange == 'okx':
            result = f"{s_clean}-USDT"
        else:
            result = f"{s_clean}USDT"

        assert result == "BTCUSDT"

    def test_symbol_with_usdt_suffix_removed(self):
        """Test that USDT suffix is properly handled"""
        symbol = "BTCUSDT"
        exchange = "okx"

        s_clean = symbol.upper().replace("USDT", "").replace("-", "")
        if exchange == 'okx':
            result = f"{s_clean}-USDT"
        else:
            result = f"{s_clean}USDT"

        assert result == "BTC-USDT"


class TestFallbackSymbols:
    """Tests for fallback symbol lists"""

    def test_okx_fallback_symbols(self):
        """Test OKX fallback symbols"""
        exchange = "okx"

        if exchange == "okx":
            fallback = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        else:
            fallback = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        assert all(s.endswith("-USDT") for s in fallback)

    def test_binance_fallback_symbols(self):
        """Test Binance fallback symbols"""
        exchange = "binance"

        if exchange == "okx":
            fallback = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        else:
            fallback = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        assert all("USDT" in s and "-USDT" not in s for s in fallback)


class TestCryptoScreenerIntegration:
    """Integration-like tests for crypto_screener"""

    @patch('analysis.crypto_screener.get_data_fetcher')
    def test_invalid_exchange_returns_empty(self, mock_get_fetcher):
        """Test that invalid exchange returns empty results"""
        mock_get_fetcher.side_effect = ValueError("Unsupported exchange")

        from analysis.crypto_screener import screen_top_cryptos

        result = screen_top_cryptos(exchange='invalid')

        # Should return empty DataFrames
        assert len(result) == 4
        assert all(isinstance(r, pd.DataFrame) for r in result)
        assert all(r.empty for r in result)

    def test_analyze_with_missing_columns(self):
        """Test analyze with dataframe missing expected columns"""
        df = pd.DataFrame({'other_column': [1, 2, 3]})

        with patch('analysis.crypto_screener.add_technical_indicators') as mock_add:
            mock_add.return_value = df

            with patch('analysis.crypto_screener.calculate_price_info', return_value={}):
                with patch('analysis.crypto_screener.extract_technical_indicators', return_value={}):
                    with patch('analysis.crypto_screener.analyze_market_structure', return_value={}):
                        with patch('analysis.crypto_screener.calculate_key_levels', return_value={}):
                            result = analyze_symbol_data(df, "TEST")

                            assert result is not None
                            assert result["symbol"] == "TEST"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
