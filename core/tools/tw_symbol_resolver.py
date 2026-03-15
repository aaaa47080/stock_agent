"""
Taiwan Stock Symbol Resolver

Resolves Chinese names, English tickers, or bare codes to Yahoo Finance format.
Examples: "[公司名稱]" → "[代號].TW", "[英文簡稱]" → "[代號].TW", "[代號]" → "[代號].TW"

Data sources:
  - TWSE: openapi.twse.com.tw  (上市)
  - TPEX: openapi.tpex.org.tw  (上櫃)
Cache: in-memory, 24h TTL
"""
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from rapidfuzz import process, fuzz

logger = logging.getLogger(__name__)


class TWSymbolResolver:
    TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    TPEX_URL = "https://openapi.tpex.org.tw/v1/opendata/t187ap04_L"
    CACHE_TTL_HOURS = 24
    FUZZY_THRESHOLD = 80

    def __init__(self):
        self._cache: Optional[list] = None
        self._cache_time: Optional[datetime] = None

    def resolve(self, input_str: str) -> Optional[str]:
        """Resolve input to Yahoo Finance TW ticker (e.g., '[代號].TW').
        Returns None if no match found."""
        result = self.resolve_with_metadata(input_str)
        return result["ticker"] if result else None

    def resolve_with_metadata(self, input_str: str) -> Optional[dict]:
        """Resolve input and return ticker with match metadata."""
        s = input_str.strip()

        # Rule 1: already has suffix
        upper = s.upper()
        if upper.endswith(".TW") or upper.endswith(".TWO"):
            return {
                "ticker": upper,
                "match_type": "suffix",
                "input": s,
            }

        # Rule 2: pure digit code (4–6 digits) → assume listed stock
        if s.isdigit() and 4 <= len(s) <= 6:
            return {
                "ticker": f"{s}.TW",
                "match_type": "code",
                "input": s,
            }

        # Rule 3: fuzzy match against full name list
        stock_list = self._get_stock_list()
        if stock_list:
            fuzzy_match = self._fuzzy_match(s, stock_list)
            if fuzzy_match:
                return {
                    "ticker": fuzzy_match["ticker"],
                    "match_type": "fuzzy",
                    "matched_text": fuzzy_match["matched_text"],
                    "score": fuzzy_match["score"],
                    "input": s,
                }

        return None

    def _get_stock_list(self) -> list:
        """Return cached stock list, refreshing if stale."""
        now = datetime.now()
        if (self._cache is not None and self._cache_time is not None
                and now - self._cache_time < timedelta(hours=self.CACHE_TTL_HOURS)):
            return self._cache

        stocks = []
        sources = [
            (self.TWSE_URL, ".TW"),
            (self.TPEX_URL, ".TWO"),
        ]
        for url, suffix in sources:
            try:
                resp = httpx.get(url, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        code = item.get("公司代號", "").strip()
                        name = item.get("公司簡稱", "").strip()
                        eng  = item.get("英文簡稱", "").strip()
                        if code and name:
                            stocks.append({
                                "code": code,
                                "name": name,
                                "eng":  eng,
                                "ticker": f"{code}{suffix}",
                            })
            except Exception as e:
                logger.warning(f"[TWSymbolResolver] fetch error {url}: {e}")

        if stocks:
            self._cache = stocks
            self._cache_time = now

        return stocks or []

    def _fuzzy_match(self, query: str, stock_list: list) -> Optional[dict]:
        """Return best-match metadata or None if score < threshold."""
        target_map: dict[str, dict] = {}
        for s in stock_list:
            target_map[s["name"]] = s
            if s["eng"]:
                target_map[s["eng"]] = s

        result = process.extractOne(
            query,
            list(target_map.keys()),
            scorer=fuzz.WRatio,
            score_cutoff=self.FUZZY_THRESHOLD,
        )
        if result:
            match_str, _score, _idx = result
            return {
                "ticker": target_map[match_str]["ticker"],
                "matched_text": match_str,
                "score": _score,
            }

        return None
