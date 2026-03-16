"""Tests for TWSymbolResolver — uses mocked HTTP to avoid network dependency."""
import pytest
from unittest.mock import patch, MagicMock
from core.tools.tw_symbol_resolver import TWSymbolResolver


# Minimal stock list for testing
MOCK_TWSE = [
    {"公司代號": "2330", "公司簡稱": "台積電", "公司全名": "台灣積體電路製造股份有限公司"},
    {"公司代號": "2317", "公司簡稱": "鴻海", "公司全名": "鴻海精密工業股份有限公司"},
]
MOCK_TPEX = [
    {"公司代號": "6488", "公司簡稱": "環球晶", "公司全名": "環球晶圓股份有限公司"},
]


def _make_mock_resp(data):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data
    return resp


@pytest.fixture
def resolver():
    with patch("httpx.get") as mock_get:
        # Return TWSE data for first call, TPEX for second
        mock_get.side_effect = [_make_mock_resp(MOCK_TWSE), _make_mock_resp(MOCK_TPEX)]
        r = TWSymbolResolver()
        r._get_stock_list()  # Pre-warm cache
    return r


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
    """TSMC 無法精確比對時不報錯，返回 None 或有效 ticker"""
    result = resolver.resolve("TSMC")
    assert result is None or isinstance(result, str)


def test_resolve_unknown(resolver):
    """完全無法識別 → None"""
    result = resolver.resolve("XYZABC_DEFINITELY_NOT_A_STOCK_12345")
    assert result is None


def test_stock_list_cached(resolver):
    """快取已建立（不為空）"""
    assert resolver._cache is not None
    assert len(resolver._cache) > 0
