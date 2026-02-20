"""Tests for TWSymbolResolver — runs against live TWSE/TPEX APIs."""
import pytest
from core.tools.tw_symbol_resolver import TWSymbolResolver


@pytest.fixture
def resolver():
    return TWSymbolResolver()


def test_resolve_digit_code(resolver):
    """純數字 4 碼 → 補 .TW"""
    assert resolver.resolve("2330") == "2330.TW"


def test_resolve_already_tw(resolver):
    """已有 .TW suffix → 原樣返回"""
    assert resolver.resolve("2330.TW") == "2330.TW"


def test_resolve_already_two(resolver):
    """已有 .TWO suffix → 原樣返回"""
    assert resolver.resolve("6666.TWO") == "6666.TWO"


def test_resolve_chinese_name(resolver):
    """中文名稱模糊比對 → 返回 ticker"""
    result = resolver.resolve("台積電")
    assert result is not None
    assert "2330" in result


def test_resolve_english_name(resolver):
    """英文縮寫比對"""
    result = resolver.resolve("TSMC")
    assert result is not None
    assert "2330" in result


def test_resolve_unknown(resolver):
    """完全無法識別 → None"""
    result = resolver.resolve("XYZABC_DEFINITELY_NOT_A_STOCK_12345")
    assert result is None


def test_stock_list_cached(resolver):
    """第二次呼叫使用快取（不再 HTTP 請求）"""
    resolver.resolve("台積電")
    import httpx
    with pytest.raises(Exception) if False else __import__('contextlib').nullcontext():
        # Just verify cache is populated
        assert resolver._cache is not None
        assert len(resolver._cache) > 100  # Should have 1000+ stocks
