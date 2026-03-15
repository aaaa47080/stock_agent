"""
Market symbol normalization and sanitization helpers.
"""

from __future__ import annotations

import re
from typing import Iterable, List

# Keywords that occasionally leak from UI states/localStorage and are not tradable symbols.
INVALID_SYMBOL_KEYWORDS = {
    "PROGRESS",
    "ALL",
    "NONE",
    "LOADING",
    "AUTO",
}

_BASE_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,15}$")
_PAIR_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,15}-[A-Z0-9]{2,10}$")


def _normalize_token(symbol: str) -> str:
    if not isinstance(symbol, str):
        return ""
    return symbol.strip().upper().replace(" ", "").replace("_", "-")


def is_invalid_symbol_keyword(symbol: str) -> bool:
    token = _normalize_token(symbol)
    return token in INVALID_SYMBOL_KEYWORDS


def normalize_base_symbol(symbol: str) -> str:
    """
    Normalize a symbol to base form (e.g. BTC-USDT -> BTC, btcusdt -> BTC).
    Returns empty string when input is invalid.
    """
    token = _normalize_token(symbol)
    if not token:
        return ""

    if "/" in token:
        token = token.split("/", 1)[0]
    if "-" in token:
        token = token.split("-", 1)[0]

    if token.endswith("USDT"):
        token = token[:-4]
    elif token.endswith("BUSD"):
        token = token[:-4]
    elif token.endswith("USD"):
        token = token[:-3]

    if not token or token in INVALID_SYMBOL_KEYWORDS:
        return ""
    if not _BASE_SYMBOL_PATTERN.fullmatch(token):
        return ""
    return token


def normalize_pair_symbol(symbol: str, default_quote: str = "USDT") -> str:
    """
    Normalize a symbol to pair form (e.g. BTC -> BTC-USDT, btc/usdt -> BTC-USDT).
    Returns empty string when input is invalid.
    """
    token = _normalize_token(symbol)
    if not token or token in INVALID_SYMBOL_KEYWORDS:
        return ""

    token = token.replace("/", "-")

    parts = [p for p in token.split("-") if p]
    if not parts:
        return ""

    if len(parts) == 1:
        base = normalize_base_symbol(parts[0])
        if not base:
            return ""
        candidate = f"{base}-{default_quote}"
    else:
        base = normalize_base_symbol(parts[0])
        if not base:
            return ""
        quote = parts[1]
        if quote in {"SWAP", "PERP"} and len(parts) > 2:
            quote = parts[2]
        if not re.fullmatch(r"[A-Z0-9]{2,10}", quote):
            return ""
        candidate = f"{base}-{quote}"

    if not _PAIR_SYMBOL_PATTERN.fullmatch(candidate):
        return ""
    return candidate


def sanitize_base_symbols(symbols: Iterable[str]) -> List[str]:
    """Deduplicate and keep valid base symbols."""
    cleaned: List[str] = []
    seen: set[str] = set()
    for symbol in symbols or []:
        normalized = normalize_base_symbol(symbol)
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def sanitize_pair_symbols(symbols: Iterable[str]) -> List[str]:
    """Deduplicate and keep valid pair symbols."""
    cleaned: List[str] = []
    seen: set[str] = set()
    for symbol in symbols or []:
        normalized = normalize_pair_symbol(symbol)
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned

