"""Tests for TW stock tool functions — require internet."""
import pytest
from core.tools.tw_stock_tools import (
    tw_stock_price,
    tw_technical_analysis,
    tw_fundamentals,
    tw_institutional,
    tw_news,
)


def test_tw_stock_price_returns_dict():
    result = tw_stock_price.invoke({"ticker": "2330.TW"})
    assert isinstance(result, dict)
    assert "ticker" in result
    assert "current_price" in result or "error" in result


def test_tw_technical_analysis_returns_dict():
    result = tw_technical_analysis.invoke({"ticker": "2330.TW"})
    assert isinstance(result, dict)
    assert "ticker" in result


def test_tw_fundamentals_returns_dict():
    result = tw_fundamentals.invoke({"ticker": "2330.TW"})
    assert isinstance(result, dict)
    assert "ticker" in result


def test_tw_institutional_returns_dict():
    result = tw_institutional.invoke({"ticker": "2330.TW"})
    assert isinstance(result, dict)
    assert "ticker" in result


def test_tw_news_returns_list():
    result = tw_news.invoke({"ticker": "2330.TW", "company_name": "台積電"})
    assert isinstance(result, list)
