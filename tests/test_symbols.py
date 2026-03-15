from api.symbols import (
    normalize_base_symbol,
    normalize_pair_symbol,
    sanitize_base_symbols,
    sanitize_pair_symbols,
)


def test_normalize_base_symbol_handles_pairs_and_suffixes():
    assert normalize_base_symbol("btc-usdt") == "BTC"
    assert normalize_base_symbol("ETHUSDT") == "ETH"
    assert normalize_base_symbol("sol/usdt") == "SOL"


def test_normalize_base_symbol_rejects_ui_keywords():
    assert normalize_base_symbol("PROGRESS") == ""
    assert normalize_base_symbol("loading") == ""


def test_normalize_pair_symbol_generates_default_quote():
    assert normalize_pair_symbol("btc") == "BTC-USDT"
    assert normalize_pair_symbol("eth/usdt") == "ETH-USDT"


def test_normalize_pair_symbol_rejects_invalid_tokens():
    assert normalize_pair_symbol("PROGRESS") == ""
    assert normalize_pair_symbol("$$$") == ""


def test_sanitize_base_symbols_deduplicates_and_drops_invalid():
    assert sanitize_base_symbols(["btc", "BTC-USDT", "PROGRESS", "eth"]) == ["BTC", "ETH"]


def test_sanitize_pair_symbols_deduplicates_and_drops_invalid():
    assert sanitize_pair_symbols(["btc", "BTC-USDT", "progress", "eth/usdt"]) == [
        "BTC-USDT",
        "ETH-USDT",
    ]

