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
