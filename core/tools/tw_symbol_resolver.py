"""
Taiwan Stock Symbol Resolver

Resolves Chinese names, English tickers, or bare codes to Yahoo Finance format.
Examples: "台積電" → "2330.TW", "TSMC" → "2330.TW", "2330" → "2330.TW"

Data sources:
  - TWSE: openapi.twse.com.tw  (上市)
  - TPEX: openapi.tpex.org.tw  (上櫃)
Cache: in-memory, 24h TTL
"""
import httpx
from datetime import datetime, timedelta
from typing import Optional
from rapidfuzz import process, fuzz


class TWSymbolResolver:
    TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    TPEX_URL = "https://openapi.tpex.org.tw/v1/opendata/t187ap04_L"
    CACHE_TTL_HOURS = 24
    FUZZY_THRESHOLD = 80

    def __init__(self):
        self._cache: Optional[list] = None
        self._cache_time: Optional[datetime] = None

    def resolve(self, input_str: str) -> Optional[str]:
        """Resolve input to Yahoo Finance TW ticker (e.g., '2330.TW').
        Returns None if no match found."""
        s = input_str.strip()

        # Rule 1: already has suffix
        upper = s.upper()
        if upper.endswith(".TW") or upper.endswith(".TWO"):
            return upper

        # Rule 2: pure digit code (4–6 digits) → assume listed stock
        if s.isdigit() and 4 <= len(s) <= 6:
            return f"{s}.TW"

        # Rule 3: fuzzy match against full name list
        stock_list = self._get_stock_list()
        if stock_list:
            return self._fuzzy_match(s, stock_list)

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
                print(f"[TWSymbolResolver] fetch error {url}: {e}")

        if stocks:
            self._cache = stocks
            self._cache_time = now

        return stocks or []

    def _fuzzy_match(self, query: str, stock_list: list) -> Optional[str]:
        """Return best-match ticker or None if score < threshold."""
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
            return target_map[match_str]["ticker"]

        return None
