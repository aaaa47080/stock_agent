from unittest.mock import MagicMock

from core.tools.universal_resolver import UniversalSymbolResolver


def test_resolve_bitcoin():
    r = UniversalSymbolResolver()
    result = r.resolve("BTC")
    assert result["crypto"] == "BTC"
    assert result["tw"] is None
    assert result["us"] is None


def test_resolve_tw_digit():
    r = UniversalSymbolResolver()
    result = r.resolve("2330")
    assert result["tw"] == "2330.TW"
    assert result["crypto"] is None


def test_resolve_tsm_ambiguous():
    """TSM could match US stock; TW resolver won't match (no 'TSM' ticker in TW)"""
    r = UniversalSymbolResolver()
    result = r.resolve("TSM")
    # TSM is NYSE, not crypto, not a TW 4-digit code
    # tw fuzzy might or might not match - if it does, both tw+us set
    assert result["us"] == "TSM" or result["tw"] is not None


def test_resolve_with_context_prefers_us_for_tsm_without_tw_hints():
    r = UniversalSymbolResolver()
    r.tw_resolver.resolve_with_metadata = MagicMock(
        return_value={
            "ticker": "2330.TW",
            "match_type": "fuzzy",
            "matched_text": "TSMC",
            "score": 83,
            "input": "TSM",
        }
    )
    result = r.resolve_with_context("TSM", context_text="TSM現在多少？")

    assert result["resolution"]["us"] == "TSM"
    assert result["primary_market"] == "us"
    assert (
        result["candidates"]["us"]["score"]
        > result["candidates"].get("tw", {"score": 0})["score"]
    )


def test_resolve_with_context_prefers_tw_when_tw_hints_are_present():
    r = UniversalSymbolResolver()
    r.tw_resolver.resolve_with_metadata = MagicMock(
        return_value={
            "ticker": "2330.TW",
            "match_type": "fuzzy",
            "matched_text": "TSMC",
            "score": 89,
            "input": "TSMC",
        }
    )
    result = r.resolve_with_context("TSMC", context_text="台股 TSMC 現在多少？")

    assert result["resolution"]["tw"] is not None
    assert result["primary_market"] == "tw"


def test_resolve_with_context_skips_tw_probe_for_plain_us_like_ticker_without_tw_hints():
    r = UniversalSymbolResolver()
    r.tw_resolver.resolve_with_metadata = MagicMock(
        return_value={
            "ticker": "2330.TW",
            "match_type": "fuzzy",
            "matched_text": "TSMC",
            "score": 83,
            "input": "TSM",
        }
    )

    result = r.resolve_with_context("TSM", context_text="TSM現在多少？")

    r.tw_resolver.resolve_with_metadata.assert_not_called()
    assert result["primary_market"] == "us"


def test_resolve_with_context_still_probes_tw_with_explicit_tw_hints():
    r = UniversalSymbolResolver()
    r.tw_resolver.resolve_with_metadata = MagicMock(
        return_value={
            "ticker": "2330.TW",
            "match_type": "fuzzy",
            "matched_text": "TSMC",
            "score": 89,
            "input": "TSMC",
        }
    )

    r.resolve_with_context("TSMC", context_text="台股 TSMC 現在多少？")

    r.tw_resolver.resolve_with_metadata.assert_called_once_with("TSMC")


def test_has_matches_true():
    r = UniversalSymbolResolver()
    assert r.has_matches({"crypto": "BTC", "tw": None, "us": None}) is True


def test_has_matches_false():
    r = UniversalSymbolResolver()
    assert r.has_matches({"crypto": None, "tw": None, "us": None}) is False


def test_primary_market_single():
    r = UniversalSymbolResolver()
    assert r.primary_market({"crypto": "BTC", "tw": None, "us": None}) == "crypto"


def test_primary_market_ambiguous():
    r = UniversalSymbolResolver()
    assert r.primary_market({"crypto": "BTC", "tw": "2330.TW", "us": None}) is None
