"""
Tests for helper functions in core/tools/helpers.py
"""
import pytest
from unittest.mock import patch, MagicMock

from core.tools.helpers import (
    normalize_symbol,
    extract_crypto_symbols,
    CRYPTO_SYMBOLS,
    COMMON_WORDS
)


class TestNormalizeSymbol:
    """Tests for normalize_symbol function"""

    def test_basic_symbol_okx(self):
        """Test basic symbol normalization for OKX"""
        result = normalize_symbol("BTC", "okx")
        assert result == "BTC-USDT"

    def test_basic_symbol_binance(self):
        """Test basic symbol normalization for Binance"""
        result = normalize_symbol("BTC", "binance")
        assert result == "BTCUSDT"

    def test_symbol_with_usdt_suffix(self):
        """Test symbol already with USDT suffix"""
        result = normalize_symbol("BTCUSDT", "okx")
        assert result == "BTC-USDT"

    def test_symbol_with_dash(self):
        """Test symbol with dash separator"""
        result = normalize_symbol("BTC-USDT", "okx")
        assert result == "BTC-USDT"

    def test_symbol_with_underscore(self):
        """Test symbol with underscore separator"""
        result = normalize_symbol("BTC_USDT", "okx")
        assert result == "BTC-USDT"

    def test_lowercase_symbol(self):
        """Test lowercase symbol is converted to uppercase"""
        result = normalize_symbol("btc", "okx")
        assert result == "BTC-USDT"

    def test_symbol_with_whitespace(self):
        """Test symbol with leading/trailing whitespace"""
        result = normalize_symbol("  BTC  ", "okx")
        assert result == "BTC-USDT"

    def test_empty_symbol(self):
        """Test empty symbol returns empty string"""
        result = normalize_symbol("", "okx")
        assert result == ""

    def test_busd_symbol(self):
        """Test symbol with BUSD suffix"""
        result = normalize_symbol("BTCBUSD", "okx")
        assert result == "BTC-USDT"

    def test_usd_symbol(self):
        """Test symbol with USD suffix (not USDT)"""
        result = normalize_symbol("BTCUSD", "okx")
        assert result == "BTC-USDT"

    def test_eth_symbol(self):
        """Test ETH symbol"""
        result = normalize_symbol("ETH", "okx")
        assert result == "ETH-USDT"

    def test_default_exchange_is_okx(self):
        """Test that default exchange is OKX"""
        result = normalize_symbol("SOL")
        assert result == "SOL-USDT"

    def test_various_symbols(self):
        """Test various cryptocurrency symbols"""
        test_cases = [
            ("ETH", "okx", "ETH-USDT"),
            ("SOL", "binance", "SOLUSDT"),
            ("DOGE-USDT", "okx", "DOGE-USDT"),
            ("xrp", "okx", "XRP-USDT"),
        ]
        for symbol, exchange, expected in test_cases:
            result = normalize_symbol(symbol, exchange)
            assert result == expected


class TestExtractCryptoSymbols:
    """Tests for extract_crypto_symbols function"""

    def test_extract_single_symbol(self):
        """Test extracting single crypto symbol from text"""
        result = extract_crypto_symbols("What is the price of BTC?")
        assert "BTC" in result

    def test_extract_multiple_symbols(self):
        """Test extracting multiple symbols"""
        result = extract_crypto_symbols("Compare BTC and ETH prices")
        assert "BTC" in result
        assert "ETH" in result

    def test_extract_from_chinese_text(self):
        """Test extracting from Chinese text"""
        result = extract_crypto_symbols("BTC現在多少錢？")
        assert "BTC" in result

    def test_no_symbols_in_text(self):
        """Test text without crypto symbols"""
        result = extract_crypto_symbols("Hello world, how are you?")
        assert result == []

    def test_filter_common_words(self):
        """Test that common English words are filtered out"""
        # These words might match but should be filtered
        result = extract_crypto_symbols("The key to success")
        assert "KEY" not in result or result == []

    def test_case_insensitive(self):
        """Test case insensitive extraction"""
        result_lower = extract_crypto_symbols("btc is great")
        result_upper = extract_crypto_symbols("BTC is great")
        assert result_lower == result_upper

    def test_deduplicate_symbols(self):
        """Test that duplicate symbols are removed"""
        result = extract_crypto_symbols("BTC and BTC and more BTC")
        assert result.count("BTC") <= 1

    def test_symbol_at_boundaries(self):
        """Test symbols at word boundaries"""
        result = extract_crypto_symbols("BTCETH is not valid but BTC and ETH are")
        assert "BTC" in result
        assert "ETH" in result

    def test_extract_sol(self):
        """Test extracting SOL symbol"""
        result = extract_crypto_symbols("SOL price analysis")
        assert "SOL" in result

    def test_extract_doge(self):
        """Test extracting DOGE symbol"""
        result = extract_crypto_symbols("DOGE to the moon")
        assert "DOGE" in result

    def test_mixed_content(self):
        """Test mixed content with multiple symbols and text"""
        text = "I'm comparing ETH vs SOL vs BTC for investment"
        result = extract_crypto_symbols(text)
        assert "ETH" in result
        assert "SOL" in result
        assert "BTC" in result


class TestCryptoSymbolList:
    """Tests for crypto symbol constants"""

    def test_crypto_symbols_not_empty(self):
        """Test that CRYPTO_SYMBOLS list is not empty"""
        assert len(CRYPTO_SYMBOLS) > 0

    def test_btc_in_list(self):
        """Test that BTC is in the list"""
        assert "BTC" in CRYPTO_SYMBOLS

    def test_eth_in_list(self):
        """Test that ETH is in the list"""
        assert "ETH" in CRYPTO_SYMBOLS

    def test_common_words_not_empty(self):
        """Test that COMMON_WORDS set is not empty"""
        assert len(COMMON_WORDS) > 0

    def test_common_words_contains_buy_sell(self):
        """Test that common trading words are in COMMON_WORDS"""
        assert "BUY" in COMMON_WORDS
        assert "SELL" in COMMON_WORDS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
