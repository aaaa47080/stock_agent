"""
Universal Symbol Resolver

Checks all markets (crypto, TW stocks, US stocks) and returns
which markets the input symbol belongs to.

Usage:
    resolver = UniversalSymbolResolver()
    result = resolver.resolve("TSM")
    # {"crypto": None, "tw": None, "us": "TSM"}
"""
import re
from typing import Dict, Optional

from .tw_symbol_resolver import TWSymbolResolver

# Top crypto symbols for quick pattern matching (no API call needed)
_KNOWN_CRYPTO = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "DOT",
    "MATIC", "LINK", "UNI", "ATOM", "LTC", "ETC", "XLM", "ALGO", "VET",
    "PI", "USDT", "USDC", "BUSD", "DAI",
}

# US stock pattern: 1-5 uppercase letters only
_US_PATTERN = re.compile(r'^[A-Z]{1,5}$')


class UniversalSymbolResolver:
    def __init__(self):
        self.tw_resolver = TWSymbolResolver()

    def resolve(self, input_str: str) -> Dict[str, Optional[str]]:
        """
        Returns market resolution dict:
            {"crypto": str|None, "tw": str|None, "us": str|None}

        None means no match for that market.
        Multiple non-None values = ambiguous (parallel dispatch needed).
        """
        s      = input_str.strip()
        upper  = s.upper()
        result = {"crypto": None, "tw": None, "us": None}

        # ── 1. Crypto check (before TW, to prevent "BTC" fuzzy-matching a TW stock) ──
        if upper in _KNOWN_CRYPTO:
            result["crypto"] = upper

        # ── 2. TW check (most specific: digits, .TW suffix, fuzzy name) ──
        # Skip TW fuzzy match if input is a known crypto symbol
        if result["crypto"] is None:
            tw = self.tw_resolver.resolve(s)
            if tw:
                result["tw"] = tw

        # ── 3. US stock check ──
        # Only if: matches 1-5 uppercase letter pattern,
        #          not a known crypto,
        #          not resolved as a TW digit-code (pure digits)
        is_digit = s.isdigit()
        if (not is_digit and not result.get("crypto")
                and _US_PATTERN.match(upper)
                and upper not in _KNOWN_CRYPTO):
            result["us"] = upper

        return result

    def has_matches(self, resolution: dict) -> bool:
        """True if at least one market matched."""
        return any(v is not None for v in resolution.values())

    def primary_market(self, resolution: dict) -> Optional[str]:
        """Return the single matched market name, or None if ambiguous/none."""
        matches = [k for k, v in resolution.items() if v is not None]
        return matches[0] if len(matches) == 1 else None

    def matched_markets(self, resolution: dict) -> list:
        """Return list of matched market names."""
        return [k for k, v in resolution.items() if v is not None]
