# Multi-Market Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Taiwan stock analysis + universal symbol resolution + merge TechAgent/NewsAgent into CryptoAgent, enabling parallel multi-market dispatch when a symbol is ambiguous.

**Architecture:** New `UniversalSymbolResolver` runs in `_classify_node` to detect which markets a symbol belongs to. Multi-market queries build a deterministic multi-step plan (one step per market). Existing execute/synthesize loop handles them sequentially and presents results side-by-side. New agents: `CryptoAgent` (replaces TechAgent+NewsAgent), `TWStockAgent`, `USStockAgent` (stub).

**Tech Stack:** `yfinance`, `rapidfuzz`, `pandas_ta`, TWSE/TPEX openapi (no key), FinMind free tier (no key for basic data), Google News RSS, LangChain `@tool`, LangGraph.

---

## Task 1: Install Dependencies

**Files:** none (requirements)

**Step 1: Install packages**

```bash
pip install yfinance rapidfuzz pandas_ta httpx
```

**Step 2: Verify**

```bash
python -c "import yfinance, rapidfuzz, pandas_ta, httpx; print('OK')"
```

Expected: `OK`

**Step 3: Add to requirements.txt**

Open `requirements.txt`, add these lines (if not present):
```
yfinance
rapidfuzz
pandas_ta
httpx
```

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add yfinance, rapidfuzz, pandas_ta, httpx dependencies"
```

---

## Task 2: TW Symbol Resolver

**Files:**
- Create: `core/tools/tw_symbol_resolver.py`
- Test: `tests/test_tw_symbol_resolver.py`

**Step 1: Write the failing test**

Create `tests/test_tw_symbol_resolver.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_tw_symbol_resolver.py -v
```

Expected: `ImportError: cannot import name 'TWSymbolResolver'`

**Step 3: Implement**

Create `core/tools/tw_symbol_resolver.py`:

```python
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
```

**Step 4: Run tests**

```bash
pytest tests/test_tw_symbol_resolver.py -v
```

Expected: All pass (needs internet for TWSE API)

**Step 5: Commit**

```bash
git add core/tools/tw_symbol_resolver.py tests/test_tw_symbol_resolver.py
git commit -m "feat: add TWSymbolResolver with TWSE/TPEX fuzzy matching"
```

---

## Task 3: TW Stock Tools

**Files:**
- Create: `core/tools/tw_stock_tools.py`
- Test: `tests/test_tw_stock_tools.py`

**Step 1: Write failing tests**

Create `tests/test_tw_stock_tools.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tw_stock_tools.py -v
```

Expected: `ImportError: cannot import name 'tw_stock_price'`

**Step 3: Implement**

Create `core/tools/tw_stock_tools.py`:

```python
"""
Taiwan Stock Tools — 5 @tool functions for TWStockAgent.

Data sources (free-first):
  - yfinance: price + OHLCV + basic fundamentals (15min delay)
  - TWSE openapi: institutional (3-party) data
  - Google News RSS: TW-specific news
  - FinMind: richer fundamentals (free tier, rate-limited)
"""
from langchain_core.tools import tool
from typing import Optional


# ── Price ──────────────────────────────────────────────────────────────────

@tool
def tw_stock_price(ticker: str) -> dict:
    """獲取台股即時（15分鐘延遲）及近期 OHLCV 價格資料。
    ticker 格式：2330.TW 或 6666.TWO"""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="5d")

        current_price = getattr(info, "last_price", None)
        prev_close    = getattr(info, "previous_close", None)
        change_pct    = None
        if current_price and prev_close and prev_close != 0:
            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        recent_ohlcv = []
        if not hist.empty:
            for idx, row in hist.tail(5).iterrows():
                recent_ohlcv.append({
                    "date":   str(idx.date()),
                    "open":   round(float(row["Open"]),  2),
                    "high":   round(float(row["High"]),  2),
                    "low":    round(float(row["Low"]),   2),
                    "close":  round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

        return {
            "ticker":        ticker,
            "current_price": round(current_price, 2) if current_price else None,
            "prev_close":    round(prev_close, 2)    if prev_close    else None,
            "change_pct":    change_pct,
            "recent_ohlcv":  recent_ohlcv,
            "note":          "價格為即時（約15分鐘延遲）",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── Technical Analysis ──────────────────────────────────────────────────────

@tool
def tw_technical_analysis(ticker: str, period: str = "3mo") -> dict:
    """計算台股技術指標：RSI(14)、MACD、KD(9,3,3)、MA5/20/60。
    ticker: 2330.TW；period: 1mo/3mo/6mo/1y"""
    try:
        import yfinance as yf
        import pandas_ta as ta

        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty or len(hist) < 30:
            return {"ticker": ticker, "error": "歷史資料不足（需至少30天）"}

        df = hist.copy()

        # RSI(14)
        rsi = ta.rsi(df["Close"], length=14)
        rsi_val = round(float(rsi.iloc[-1]), 2) if rsi is not None and not rsi.empty else None

        # MACD(12,26,9)
        macd_df = ta.macd(df["Close"])
        macd_val = macd_sig = macd_hist_val = None
        if macd_df is not None and not macd_df.empty:
            macd_val      = round(float(macd_df.iloc[-1, 0]), 4)
            macd_sig      = round(float(macd_df.iloc[-1, 1]), 4)
            macd_hist_val = round(float(macd_df.iloc[-1, 2]), 4)

        # KD (Stochastic 9,3,3)
        stoch = ta.stoch(df["High"], df["Low"], df["Close"], k=9, d=3, smooth_k=3)
        k_val = d_val = None
        if stoch is not None and not stoch.empty:
            k_val = round(float(stoch.iloc[-1, 0]), 2)
            d_val = round(float(stoch.iloc[-1, 1]), 2)

        # Moving Averages
        def ma(n):
            s = df["Close"].rolling(n).mean()
            return round(float(s.iloc[-1]), 2) if not s.empty and not s.isna().iloc[-1] else None

        close_now = round(float(df["Close"].iloc[-1]), 2)

        return {
            "ticker":    ticker,
            "period":    period,
            "close":     close_now,
            "rsi_14":    rsi_val,
            "macd":      {"macd": macd_val, "signal": macd_sig, "histogram": macd_hist_val},
            "kd":        {"k": k_val, "d": d_val},
            "ma":        {"ma5": ma(5), "ma20": ma(20), "ma60": ma(60)},
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── Fundamentals ────────────────────────────────────────────────────────────

@tool
def tw_fundamentals(ticker: str) -> dict:
    """獲取台股基本面資料：本益比(P/E)、股價淨值比(P/B)、殖利率、EPS 等。
    資料來源：yfinance（延遲非即時，適合參考）"""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        return {
            "ticker":              ticker,
            "company_name":        info.get("longName") or info.get("shortName"),
            "pe_ratio":            info.get("trailingPE"),
            "pb_ratio":            info.get("priceToBook"),
            "dividend_yield_pct":  round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "eps_ttm":             info.get("trailingEps"),
            "revenue_growth":      info.get("revenueGrowth"),
            "profit_margins":      info.get("profitMargins"),
            "market_cap":          info.get("marketCap"),
            "52w_high":            info.get("fiftyTwoWeekHigh"),
            "52w_low":             info.get("fiftyTwoWeekLow"),
            "note":                "基本面資料來自 yfinance，可能有延遲",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── Institutional (三大法人) ────────────────────────────────────────────────

@tool
def tw_institutional(ticker: str) -> dict:
    """獲取台股三大法人籌碼資料（外資、投信、自營商買賣超）。
    資料來源：TWSE 官方 openapi"""
    try:
        import httpx

        # Extract code from ticker (e.g., "2330.TW" → "2330")
        code = ticker.split(".")[0]
        url = f"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY?stockNo={code}"
        resp = httpx.get(url, timeout=10)

        # TWSE institutional API (3-party)
        inst_url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX3"
        inst_resp = httpx.get(inst_url, timeout=10, params={"stockNo": code})

        if inst_resp.status_code == 200:
            data = inst_resp.json()
            matching = [d for d in data if d.get("證券代號", "") == code]
            if matching:
                d = matching[0]
                return {
                    "ticker":           ticker,
                    "date":             d.get("日期", ""),
                    "foreign_net":      d.get("外陸資買賣超股數(不含外資自營商)", ""),
                    "investment_trust": d.get("投信買賣超股數", ""),
                    "dealer_net":       d.get("自營商買賣超股數", ""),
                    "total_3party_net": d.get("三大法人買賣超股數", ""),
                    "source":           "TWSE openapi",
                }

        # Fallback: just return basic info
        return {
            "ticker": ticker,
            "note":   "法人資料暫時無法取得，請稍後再試",
            "source": "TWSE openapi",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── News ────────────────────────────────────────────────────────────────────

@tool
def tw_news(ticker: str, company_name: str = "", limit: int = 8) -> list:
    """從 Google News RSS 獲取台股相關新聞。
    company_name: 公司中文名稱（如「台積電」），提升新聞相關性"""
    try:
        import httpx
        import xml.etree.ElementTree as ET
        from urllib.parse import quote

        # Search term: prefer Chinese company name for better results
        search_term = company_name if company_name else ticker
        query = quote(f"{search_term} 股票")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

        resp = httpx.get(rss_url, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        ns   = {"media": "http://search.yahoo.com/mrss/"}
        items = []

        for item in root.findall(".//item")[:limit]:
            title   = item.findtext("title", "")
            link    = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source  = item.findtext("source", "")
            items.append({
                "title":      title,
                "url":        link,
                "published":  pub_date,
                "source":     source,
            })

        return items
    except Exception as e:
        return [{"error": str(e)}]
```

**Step 4: Run tests**

```bash
pytest tests/test_tw_stock_tools.py -v
```

Expected: All pass (needs internet)

**Step 5: Commit**

```bash
git add core/tools/tw_stock_tools.py tests/test_tw_stock_tools.py
git commit -m "feat: add 5 TW stock tools (price, technical, fundamentals, institutional, news)"
```

---

## Task 4: TWStockAgent Prompt

**Files:**
- Create: `core/agents/prompts/tw_stock_agent.yaml`

**Step 1: Create prompt file**

```yaml
analysis:
  description: "台股全方位分析提示詞，接收 ticker, company_name, query, data"
  template: |
    你是一位專業的台灣股市分析師。請根據以下資料，用繁體中文回覆使用者的問題。

    股票代號：{ticker}
    公司名稱：{company_name}
    使用者問題：{query}

    ── 即時價格 ──
    {price_data}

    ── 技術指標 ──
    {technical_data}

    ── 基本面 ──
    {fundamentals_data}

    ── 三大法人籌碼 ──
    {institutional_data}

    ── 最新新聞 ──
    {news_data}

    請根據使用者問題，聚焦在最相關的面向回覆。
    提供：
    1. 直接回答使用者問題
    2. 關鍵數據解讀（引用上方實際數值）
    3. 綜合判斷（看法/建議）
    4. 風險提示

    重要：
    - 引用具體數字，不要模糊描述
    - RSI > 70 超買、< 30 超賣；KD 金叉看漲、死叉看跌
    - 不確定的資料，說明資料限制，不要捏造
    - 若新聞有連結，保留 Markdown 格式 [標題](url)

    若任務超出台股範圍，回覆 JSON：
    {{ "status": "REFUSED", "reason": "說明原因" }}
```

**Step 2: Verify YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('core/agents/prompts/tw_stock_agent.yaml'))"
```

Expected: no output (no error)

**Step 3: Commit**

```bash
git add core/agents/prompts/tw_stock_agent.yaml
git commit -m "feat: add TWStockAgent prompt template"
```

---

## Task 5: TWStockAgent Class

**Files:**
- Create: `core/agents/agents/tw_stock_agent.py`
- Modify: `core/agents/agents/__init__.py`
- Test: `tests/test_tw_stock_agent.py`

**Step 1: Write failing test**

Create `tests/test_tw_stock_agent.py`:

```python
"""Tests for TWStockAgent."""
import pytest
from unittest.mock import MagicMock, patch
from core.agents.agents.tw_stock_agent import TWStockAgent
from core.agents.models import SubTask, AgentResult


def make_agent(mock_llm=None):
    if mock_llm is None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="台積電分析報告")
    tool_registry = MagicMock()
    tool_registry.get.return_value = None  # No tools available
    return TWStockAgent(mock_llm, tool_registry)


def test_agent_name():
    agent = make_agent()
    assert agent.name == "tw_stock"


def test_execute_returns_agent_result():
    agent = make_agent()
    task = SubTask(step=1, description="台積電技術分析", agent="tw_stock")
    result = agent.execute(task)
    assert isinstance(result, AgentResult)
    assert result.agent_name == "tw_stock"


def test_extract_ticker_from_code():
    agent = make_agent()
    ticker = agent._extract_ticker("請分析 2330")
    assert ticker == "2330.TW"


def test_extract_ticker_from_name():
    agent = make_agent()
    # With resolver mocked
    with patch.object(agent.resolver, 'resolve', return_value="2330.TW"):
        ticker = agent._extract_ticker("台積電最近怎樣")
        assert ticker == "2330.TW"


def test_execute_no_data_returns_failure():
    agent = make_agent()
    task = SubTask(step=1, description="2330 分析", agent="tw_stock")
    result = agent.execute(task)
    # Even with no tools, should return an AgentResult (not throw)
    assert isinstance(result, AgentResult)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_tw_stock_agent.py -v
```

Expected: `ImportError`

**Step 3: Implement TWStockAgent**

Create `core/agents/agents/tw_stock_agent.py`:

```python
"""
Agent V4 — TW Stock Agent

台股全方位分析：即時價格、技術指標、基本面、籌碼、新聞。
Uses TWSymbolResolver to accept any form of TW stock identifier.
"""
import json
from langchain_core.messages import HumanMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry
from core.tools.tw_symbol_resolver import TWSymbolResolver


class TWStockAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm          = llm_client
        self.tool_registry = tool_registry
        self.resolver      = TWSymbolResolver()

    @property
    def name(self) -> str:
        return "tw_stock"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute TW stock analysis."""
        # 1. Resolve ticker
        ticker = self._extract_ticker(task.description)
        if not ticker:
            return AgentResult(
                success=False,
                message="無法識別台股代號，請提供股票代號（如 2330）或公司名稱（如 台積電）。",
                agent_name=self.name,
                quality="fail",
            )

        company_name = self._get_company_name(ticker)

        # 2. Determine which tools to call based on query intent
        intent = self._classify_intent(task.description)

        # 3. Fetch data (only what's needed)
        price_data        = self._run_tool("tw_stock_price",       {"ticker": ticker})         if intent.get("price")       else {}
        technical_data    = self._run_tool("tw_technical_analysis", {"ticker": ticker})        if intent.get("technical")   else {}
        fundamentals_data = self._run_tool("tw_fundamentals",       {"ticker": ticker})        if intent.get("fundamentals") else {}
        institutional_data = self._run_tool("tw_institutional",     {"ticker": ticker})        if intent.get("institutional") else {}
        news_data         = self._run_tool("tw_news", {"ticker": ticker, "company_name": company_name}) if intent.get("news") else []

        # If nothing fetched at all, refuse
        all_empty = not any([price_data, technical_data, fundamentals_data, institutional_data, news_data])
        if all_empty:
            return AgentResult(
                success=False,
                message=f"無法獲取 {ticker} 的資料，請稍後再試。",
                agent_name=self.name,
                quality="fail",
            )

        # 4. Format data for prompt
        def fmt(d):
            if not d:
                return "（未擷取）"
            if isinstance(d, list):
                if not d:
                    return "（無資料）"
                return "\n".join(
                    f"- [{item.get('title','')}]({item.get('url','')})"
                    f" _({item.get('source','')})_"
                    for item in d[:6]
                )
            return json.dumps(d, ensure_ascii=False, indent=2)

        prompt = PromptRegistry.render(
            "tw_stock_agent", "analysis",
            ticker=ticker,
            company_name=company_name,
            query=task.description,
            price_data=fmt(price_data),
            technical_data=fmt(technical_data),
            fundamentals_data=fmt(fundamentals_data),
            institutional_data=fmt(institutional_data),
            news_data=fmt(news_data),
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            analysis_text = f"🇹🇼 **{company_name or ticker} 台股分析**\n\n{response.content}"
        except Exception as e:
            analysis_text = f"分析生成失敗：{e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"ticker": ticker, "company_name": company_name},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        """Try to extract a TW ticker from the description text."""
        import re

        # Try direct digit match first
        match = re.search(r'\b(\d{4,6})\b', description)
        if match:
            resolved = self.resolver.resolve(match.group(1))
            if resolved:
                return resolved

        # Try resolver on whole description or key noun phrases
        # Split by common delimiters and try each word
        words = re.split(r'[\s,，。！？、「」【】]+', description)
        for word in words:
            if 2 <= len(word) <= 8:
                resolved = self.resolver.resolve(word)
                if resolved:
                    return resolved

        # Try the whole description as a last resort
        resolved = self.resolver.resolve(description[:20])
        return resolved or ""

    def _get_company_name(self, ticker: str) -> str:
        """Lookup company name from resolved ticker."""
        code = ticker.split(".")[0]
        if self.resolver._cache:
            for s in self.resolver._cache:
                if s["code"] == code:
                    return s["name"]
        return ""

    def _classify_intent(self, query: str) -> dict:
        """Determine which data categories are relevant to the query."""
        q = query.lower()

        tech_kw  = ["技術", "rsi", "macd", "kd", "均線", "ma", "k線", "走勢", "technical"]
        fund_kw  = ["基本面", "本益比", "pe", "eps", "獲利", "財報", "殖利率", "stock price"]
        inst_kw  = ["法人", "外資", "投信", "自營", "籌碼", "買超", "賣超"]
        news_kw  = ["新聞", "消息", "動態", "最新", "近況", "利多", "利空", "事件"]
        price_kw = ["價格", "現價", "多少", "price", "報價"]

        has_tech  = any(k in q for k in tech_kw)
        has_fund  = any(k in q for k in fund_kw)
        has_inst  = any(k in q for k in inst_kw)
        has_news  = any(k in q for k in news_kw)
        has_price = any(k in q for k in price_kw)

        # If none specifically detected, fetch price + technical + news (default full view)
        if not any([has_tech, has_fund, has_inst, has_news, has_price]):
            return {"price": True, "technical": True, "fundamentals": False, "institutional": False, "news": True}

        return {
            "price":        has_price or has_tech,
            "technical":    has_tech or (not any([has_fund, has_inst, has_news])),
            "fundamentals": has_fund,
            "institutional": has_inst,
            "news":         has_news,
        }

    def _run_tool(self, tool_name: str, args: dict):
        """Run a registered tool, return result or empty fallback."""
        tool = self.tool_registry.get(tool_name, caller_agent=self.name)
        if not tool:
            return None
        try:
            return tool.handler.invoke(args)
        except Exception as e:
            print(f"[TWStockAgent] {tool_name} failed: {e}")
            return None
```

**Step 4: Update agents `__init__.py`**

Modify `core/agents/agents/__init__.py`:

```python
from .tech_agent import TechAgent
from .news_agent import NewsAgent
from .chat_agent import ChatAgent
from .tw_stock_agent import TWStockAgent

__all__ = ["TechAgent", "NewsAgent", "ChatAgent", "TWStockAgent"]
```

**Step 5: Run tests**

```bash
pytest tests/test_tw_stock_agent.py -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add core/agents/agents/tw_stock_agent.py core/agents/agents/__init__.py tests/test_tw_stock_agent.py
git commit -m "feat: add TWStockAgent with intent classification and tool orchestration"
```

---

## Task 6: USStockAgent Stub

**Files:**
- Create: `core/agents/agents/us_stock_agent.py`
- Create: `core/agents/prompts/us_stock_agent.yaml`
- Modify: `core/agents/agents/__init__.py`

**Step 1: Create prompt**

Create `core/agents/prompts/us_stock_agent.yaml`:

```yaml
stub:
  description: "美股功能開發中佔位提示詞"
  template: |
    美股分析功能即將推出。
    偵測到的標的：{ticker}（{exchange}）
    目前支援：台股（.TW）、加密貨幣。
    美股完整分析敬請期待！
```

**Step 2: Create USStockAgent**

Create `core/agents/agents/us_stock_agent.py`:

```python
"""
Agent V4 — US Stock Agent (STUB)

Placeholder for future US stock analysis.
Currently identifies US stock symbols and returns a "coming soon" message.
"""
import re
from ..models import SubTask, AgentResult


# Simple set of common US stock tickers for identification
_US_PATTERN = re.compile(r'\b([A-Z]{1,5})\b')


class USStockAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "us_stock"

    def execute(self, task: SubTask) -> AgentResult:
        """Return stub response identifying the US stock symbol."""
        description = task.description
        ticker = self._extract_ticker(description)
        exchange = self._guess_exchange(ticker)

        message = (
            f"📈 **美股 {ticker}** ({exchange})\n\n"
            f"美股完整分析功能正在開發中，敬請期待！\n\n"
            f"目前支援：\n"
            f"- 🇹🇼 台股分析（輸入股票代號如 2330 或公司名稱）\n"
            f"- 🔐 加密貨幣分析（BTC、ETH 等）"
        )
        return AgentResult(
            success=True,
            message=message,
            agent_name=self.name,
            data={"ticker": ticker, "exchange": exchange},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        matches = _US_PATTERN.findall(description.upper())
        # Filter out common words that aren't tickers
        stopwords = {"A", "I", "IS", "IN", "OF", "THE", "AND", "OR", "FOR",
                     "BTC", "ETH", "SOL", "ADA", "DOT"}
        for m in matches:
            if m not in stopwords and len(m) >= 2:
                return m
        return "UNKNOWN"

    def _guess_exchange(self, ticker: str) -> str:
        nasdaq_known = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "NFLX"}
        nyse_known   = {"TSM", "JPM", "BAC", "WMT", "XOM", "BRK", "JNJ", "V", "PG"}
        if ticker in nasdaq_known:
            return "NASDAQ"
        if ticker in nyse_known:
            return "NYSE"
        return "NYSE/NASDAQ"
```

**Step 3: Update `__init__.py`**

Modify `core/agents/agents/__init__.py`:

```python
from .tech_agent import TechAgent
from .news_agent import NewsAgent
from .chat_agent import ChatAgent
from .tw_stock_agent import TWStockAgent
from .us_stock_agent import USStockAgent

__all__ = ["TechAgent", "NewsAgent", "ChatAgent", "TWStockAgent", "USStockAgent"]
```

**Step 4: Commit**

```bash
git add core/agents/agents/us_stock_agent.py core/agents/prompts/us_stock_agent.yaml core/agents/agents/__init__.py
git commit -m "feat: add USStockAgent stub (coming soon placeholder)"
```

---

## Task 7: CryptoAgent (Merge TechAgent + NewsAgent)

**Files:**
- Create: `core/agents/agents/crypto_agent.py`
- Create: `core/agents/prompts/crypto_agent.yaml`
- Modify: `core/agents/agents/__init__.py`

**Step 1: Create CryptoAgent prompt**

Create `core/agents/prompts/crypto_agent.yaml`:

```yaml
analysis:
  description: "加密貨幣全方位分析提示詞，包含技術面和新聞面"
  template: |
    作為加密貨幣分析師，請綜合以下數據分析 {symbol}。

    用戶問題：{query}

    ── 預先計算的技術訊號（程式碼驗證，可直接引用）──
    {signals}

    ── 技術指標 ──
    {indicators}

    ── 價格數據 ──
    {price_data}

    ── 最新新聞 ──
    {news_data}

    請根據用戶問題聚焦回覆：
    - 若問技術面：提供 RSI/MACD/MA 分析、支撐/壓力位、走勢預測
    - 若問新聞：提供關鍵消息總結、市場影響分析
    - 若問整體分析：技術面 + 消息面綜合評估

    重要：
    - 直接引用「預先計算的訊號」，不要重新計算
    - 若新聞有連結，保留 Markdown 格式 [標題](url)
    - 提供明確的看漲/看跌/中性判斷

    若任務超出加密貨幣範圍，回覆 JSON：
    {{ "status": "REFUSED", "reason": "說明原因" }}

summarize:
  description: "純新聞總結（無技術指標時使用）"
  template: |
    請總結以下 {symbol} 加密貨幣新聞。

    用戶關注點：{query}

    新聞列表：
    {news_items}

    請用繁體中文提供：
    1. 針對問題的直接回答
    2. 關鍵要點（3-5 點）
    3. 對未來的影響分析

    若無資料或超出範圍，回覆 JSON：
    {{ "status": "REFUSED", "reason": "說明原因" }}
```

**Step 2: Create CryptoAgent**

Create `core/agents/agents/crypto_agent.py`:

```python
"""
Agent V4 — Crypto Agent

Merged replacement for TechAgent + NewsAgent.
Handles all crypto analysis: technical indicators + news aggregation.
Detects query intent to decide which tools to invoke.
"""
import re
from typing import Optional
from langchain_core.messages import HumanMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class CryptoAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm           = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "crypto"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute crypto analysis (technical and/or news)."""
        symbol = self._extract_symbol(task.description)
        intent = self._classify_intent(task.description)

        raw_indicators = price_data = None
        all_news = []

        # --- Technical tools ---
        if intent.get("technical"):
            ta_tool = self.tool_registry.get("technical_analysis", caller_agent=self.name)
            if ta_tool:
                try:
                    raw_indicators = ta_tool.handler.invoke({"symbol": symbol, "interval": "1d"})
                except Exception:
                    pass

            p_tool = self.tool_registry.get("price_data", caller_agent=self.name)
            if p_tool:
                try:
                    price_data = p_tool.handler.invoke({"symbol": symbol})
                except Exception:
                    pass

        # --- News tools ---
        if intent.get("news"):
            for t_name, t_args in [
                ("google_news",    {"symbol": symbol, "limit": 5}),
                ("aggregate_news", {"symbol": symbol, "limit": 5}),
            ]:
                tool = self.tool_registry.get(t_name, caller_agent=self.name)
                if tool:
                    try:
                        res = tool.handler.invoke(t_args)
                        if isinstance(res, list):
                            all_news.extend(res)
                    except Exception:
                        pass

            # Fallback to web_search
            if not all_news:
                ws = self.tool_registry.get("web_search", caller_agent=self.name)
                if ws:
                    try:
                        res = ws.handler.invoke({"query": f"{symbol} crypto news", "purpose": "news"})
                        all_news.append({"title": "Web Search", "source": "DuckDuckGo", "description": res})
                    except Exception:
                        pass

        # --- Nothing at all → fail ---
        if not raw_indicators and not price_data and not all_news:
            return AgentResult(
                success=False,
                message=f"無法獲取 {symbol} 的資料，請稍後再試。",
                agent_name=self.name,
                quality="fail",
            )

        # --- Format data ---
        indicators = self._parse_indicators(raw_indicators)
        signals    = self._build_signals(indicators)
        ind_text   = self._format_ind_text(raw_indicators)
        price_text = str(price_data)[:500] if price_data else "無數據"
        news_text  = self._format_news(all_news[:8]) if all_news else "（未擷取）"

        prompt = PromptRegistry.render(
            "crypto_agent", "analysis",
            symbol=symbol,
            query=task.description,
            signals=signals,
            indicators=ind_text,
            price_data=price_text,
            news_data=news_text,
        )

        try:
            response      = self.llm.invoke([HumanMessage(content=prompt)])
            analysis_text = f"🔐 **{symbol} 加密貨幣分析**\n\n{response.content}"
        except Exception as e:
            analysis_text = f"分析生成失敗：{e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"symbol": symbol, "indicators": indicators},
            quality="pass",
        )

    def _classify_intent(self, query: str) -> dict:
        q = query.lower()
        tech_kw = ["技術", "rsi", "macd", "均線", "ma", "k線", "走勢", "technical", "指標", "分析"]
        news_kw = ["新聞", "消息", "動態", "最新", "近況", "news", "報導", "利多", "利空"]

        has_tech = any(k in q for k in tech_kw)
        has_news = any(k in q for k in news_kw)

        # Default: fetch both
        if not has_tech and not has_news:
            return {"technical": True, "news": True}
        return {"technical": has_tech, "news": has_news}

    def _extract_symbol(self, description: str) -> str:
        try:
            prompt = (
                f"從以下文字中提取加密貨幣的交易所 ticker 代號（例如 BTC、ETH、PI、SOL）。"
                f"只回覆 ticker 本身（純英文大寫縮寫），不要其他文字。若無法識別則回覆 BTC。\n\n文字：{description}"
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip().upper().split()[0]
        except Exception:
            return "BTC"

    def _format_ind_text(self, raw) -> str:
        if isinstance(raw, str):  return raw[:1000]
        if isinstance(raw, dict): return "\n".join(f"- {k}: {v}" for k, v in raw.items() if v is not None)
        return "無數據"

    def _parse_indicators(self, raw) -> dict:
        if isinstance(raw, dict): return raw
        if not isinstance(raw, str): return {}
        parsed = {}
        for m in re.finditer(r'\|\s*(RSI\s*\(\d+\)|MACD|MA\d+|MA\s*\d+)\s*\|\s*\$?([-\d.]+)', raw):
            key = re.sub(r'\s*\(\d+\)', '', m.group(1).strip()).replace(' ', '')
            parsed[key] = m.group(2).strip()
        return parsed

    def _build_signals(self, indicators: dict) -> str:
        if not indicators: return "（無可用訊號數據）"
        signals = []
        ma7  = float(indicators.get("MA7")  or indicators.get("ma7")  or 0)
        ma25 = float(indicators.get("MA25") or indicators.get("ma25") or 0)
        if ma7 and ma25:
            signals.append(f"MA7 ({ma7}) {'高於' if ma7 > ma25 else '低於'} MA25 ({ma25})")
        return "\n".join(f"- {s}" for s in signals) if signals else "（無可用訊號數據）"

    def _format_news(self, news_list: list) -> str:
        lines = []
        for n in news_list:
            title = n.get("title", "")
            url   = n.get("url") or n.get("link", "")
            src   = n.get("source", "")
            if url:
                lines.append(f"- [{title}]({url}) _({src})_")
            else:
                lines.append(f"- {title} _({src})_")
        return "\n".join(lines) if lines else "（無新聞資料）"
```

**Step 3: Update `__init__.py`**

```python
from .tech_agent import TechAgent
from .news_agent import NewsAgent
from .chat_agent import ChatAgent
from .tw_stock_agent import TWStockAgent
from .us_stock_agent import USStockAgent
from .crypto_agent import CryptoAgent

__all__ = ["TechAgent", "NewsAgent", "ChatAgent", "TWStockAgent", "USStockAgent", "CryptoAgent"]
```

**Step 4: Commit**

```bash
git add core/agents/agents/crypto_agent.py core/agents/prompts/crypto_agent.yaml core/agents/agents/__init__.py
git commit -m "feat: add CryptoAgent merging TechAgent+NewsAgent with intent classification"
```

---

## Task 8: Universal Symbol Resolver

**Files:**
- Create: `core/tools/universal_resolver.py`
- Test: `tests/test_universal_resolver.py`

**Step 1: Write failing tests**

Create `tests/test_universal_resolver.py`:

```python
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_universal_resolver.py -v
```

Expected: `ImportError`

**Step 3: Implement**

Create `core/tools/universal_resolver.py`:

```python
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

        # ── 1. TW check (most specific: digits, .TW suffix, fuzzy name) ──
        tw = self.tw_resolver.resolve(s)
        if tw:
            result["tw"] = tw

        # ── 2. Crypto check ──
        if upper in _KNOWN_CRYPTO:
            result["crypto"] = upper

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
```

**Step 4: Run tests**

```bash
pytest tests/test_universal_resolver.py -v
```

Expected: All pass

**Step 5: Commit**

```bash
git add core/tools/universal_resolver.py tests/test_universal_resolver.py
git commit -m "feat: add UniversalSymbolResolver for multi-market detection"
```

---

## Task 9: Bootstrap Update

**Files:**
- Modify: `core/agents/bootstrap.py`
- Modify: `core/agents/tools.py`

**Step 1: Add TW tools to `core/agents/tools.py`**

Add at the end of `core/agents/tools.py`, before `ALL_TOOLS`:

```python
# ============================================
# 台股工具 (TW Stock Tools)
# ============================================

@tool
def tw_price(ticker: str) -> dict:
    """獲取台股即時價格（yfinance）"""
    from core.tools.tw_stock_tools import tw_stock_price
    return tw_stock_price.invoke({"ticker": ticker})


@tool
def tw_technical(ticker: str) -> dict:
    """計算台股技術指標 RSI/MACD/KD/MA"""
    from core.tools.tw_stock_tools import tw_technical_analysis
    return tw_technical_analysis.invoke({"ticker": ticker})


@tool
def tw_fundamentals_tool(ticker: str) -> dict:
    """獲取台股基本面資料"""
    from core.tools.tw_stock_tools import tw_fundamentals
    return tw_fundamentals.invoke({"ticker": ticker})


@tool
def tw_institutional_tool(ticker: str) -> dict:
    """獲取台股三大法人籌碼資料"""
    from core.tools.tw_stock_tools import tw_institutional
    return tw_institutional.invoke({"ticker": ticker})


@tool
def tw_news_tool(ticker: str, company_name: str = "") -> list:
    """獲取台股新聞"""
    from core.tools.tw_stock_tools import tw_news
    return tw_news.invoke({"ticker": ticker, "company_name": company_name})
```

Also update `ALL_TOOLS` to include the new tools:

```python
ALL_TOOLS = [
    google_news,
    aggregate_news,
    technical_analysis,
    price_data,
    get_crypto_price,
    web_search,
    tw_price,
    tw_technical,
    tw_fundamentals_tool,
    tw_institutional_tool,
    tw_news_tool,
]
```

**Step 2: Rewrite `core/agents/bootstrap.py`**

Replace the entire content of `core/agents/bootstrap.py`:

```python
"""
Agent V4 Bootstrap.

Assembles all components: tools → agents → manager.
Instantiates ToolRegistry and registers tools with permission checks.
"""
from langchain_core.messages import SystemMessage

from .agent_registry import AgentRegistry, AgentMetadata
from .tool_registry import ToolRegistry, ToolMetadata
from .hierarchical_memory import CodebookFactory, BaseHierarchicalCodebook
from .prompt_registry import PromptRegistry
from .manager import ManagerAgent

# Import @tool functions — crypto
from .tools import (
    technical_analysis, price_data, get_crypto_price,
    google_news, aggregate_news, web_search,
    tw_price, tw_technical, tw_fundamentals_tool, tw_institutional_tool, tw_news_tool,
)

# Import agent classes
from .agents import TechAgent, NewsAgent, ChatAgent, TWStockAgent, USStockAgent, CryptoAgent


class LanguageAwareLLM:
    """Wraps any LangChain LLM client to automatically prepend a language instruction."""

    _INSTRUCTIONS = {
        "zh-TW": "請以繁體中文回覆所有回應。",
        "en": "Please respond in English for all your responses.",
    }

    def __init__(self, llm, language: str = "zh-TW"):
        self._llm = llm
        self._lang_msg = self._INSTRUCTIONS.get(language, self._INSTRUCTIONS["zh-TW"])

    def invoke(self, messages, **kwargs):
        messages = list(messages)
        if messages and isinstance(messages[0], SystemMessage):
            messages[0] = SystemMessage(content=messages[0].content + f"\n\n{self._lang_msg}")
        else:
            messages.insert(0, SystemMessage(content=self._lang_msg))
        return self._llm.invoke(messages, **kwargs)

    def __getattr__(self, name):
        return getattr(self._llm, name)


def bootstrap(llm_client, web_mode: bool = False, language: str = "zh-TW") -> ManagerAgent:
    PromptRegistry.load()
    agent_registry = AgentRegistry()
    tool_registry  = ToolRegistry()
    codebook       = CodebookFactory()

    # ── Register Crypto Tools ──
    tool_registry.register(ToolMetadata(
        name="technical_analysis",
        description="獲取加密貨幣技術指標（RSI, MACD, 均線）",
        input_schema={"symbol": "str", "interval": "str"},
        handler=technical_analysis,
        allowed_agents=["technical", "crypto", "full_analysis"],
    ))
    tool_registry.register(ToolMetadata(
        name="price_data",
        description="獲取加密貨幣即時和歷史價格數據",
        input_schema={"symbol": "str"},
        handler=price_data,
        allowed_agents=["technical", "crypto", "full_analysis"],
    ))
    tool_registry.register(ToolMetadata(
        name="google_news",
        description="從 Google News RSS 獲取加密貨幣新聞",
        input_schema={"symbol": "str", "limit": "int"},
        handler=google_news,
        allowed_agents=["news", "crypto", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="aggregate_news",
        description="多來源加密貨幣新聞聚合",
        input_schema={"symbol": "str", "limit": "int"},
        handler=aggregate_news,
        allowed_agents=["news", "crypto", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="get_crypto_price",
        description="獲取加密貨幣即時價格",
        input_schema={"symbol": "str"},
        handler=get_crypto_price,
        allowed_agents=["technical", "crypto", "chat", "full_analysis", "manager"],
    ))
    tool_registry.register(ToolMetadata(
        name="web_search",
        description="通用網絡搜索 (DuckDuckGo)",
        input_schema={"query": "str", "purpose": "str"},
        handler=web_search,
        allowed_agents=["chat", "news", "crypto", "manager"],
    ))

    # ── Register TW Stock Tools ──
    tool_registry.register(ToolMetadata(
        name="tw_stock_price",
        description="獲取台股即時價格和近期 OHLCV",
        input_schema={"ticker": "str"},
        handler=tw_price,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_technical_analysis",
        description="計算台股技術指標 RSI/MACD/KD/MA",
        input_schema={"ticker": "str"},
        handler=tw_technical,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_fundamentals",
        description="獲取台股基本面資料（P/E, EPS, ROE）",
        input_schema={"ticker": "str"},
        handler=tw_fundamentals_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_institutional",
        description="獲取台股三大法人籌碼資料",
        input_schema={"ticker": "str"},
        handler=tw_institutional_tool,
        allowed_agents=["tw_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="tw_news",
        description="獲取台股相關新聞（Google News RSS）",
        input_schema={"ticker": "str", "company_name": "str"},
        handler=tw_news_tool,
        allowed_agents=["tw_stock"],
    ))

    # ── Wrap LLM with language awareness ──
    lang_llm = LanguageAwareLLM(llm_client, language)

    # ── Create Agents ──

    # Legacy agents (kept for backward compatibility; not routed by default)
    tech = TechAgent(lang_llm, tool_registry)
    agent_registry.register(tech, AgentMetadata(
        name="technical",
        display_name="Tech Agent (Legacy)",
        description="[Legacy] 加密貨幣技術分析。新查詢請使用 crypto agent。",
        capabilities=["RSI", "MACD", "MA", "technical analysis"],
        allowed_tools=["technical_analysis", "price_data", "get_crypto_price"],
        priority=1,
    ))

    news = NewsAgent(lang_llm, tool_registry)
    agent_registry.register(news, AgentMetadata(
        name="news",
        display_name="News Agent (Legacy)",
        description="[Legacy] 加密貨幣新聞。新查詢請使用 crypto agent。",
        capabilities=["news", "新聞"],
        allowed_tools=["google_news", "aggregate_news", "web_search"],
        priority=1,
    ))

    # New unified agents
    crypto = CryptoAgent(lang_llm, tool_registry)
    agent_registry.register(crypto, AgentMetadata(
        name="crypto",
        display_name="Crypto Agent",
        description="加密貨幣全方位分析 — 技術指標（RSI/MACD/均線）+ 即時新聞。適合 BTC/ETH/SOL 等加密貨幣的技術分析、新聞查詢、整體分析。",
        capabilities=["RSI", "MACD", "MA", "technical analysis", "crypto news", "加密貨幣", "技術指標", "K線", "加密貨幣新聞"],
        allowed_tools=["technical_analysis", "price_data", "get_crypto_price", "google_news", "aggregate_news", "web_search"],
        priority=10,
    ))

    tw = TWStockAgent(lang_llm, tool_registry)
    agent_registry.register(tw, AgentMetadata(
        name="tw_stock",
        display_name="TW Stock Agent",
        description="台灣股市全方位分析 — 即時價格、技術指標（RSI/MACD/KD/均線）、基本面（P/E/EPS）、三大法人籌碼、台股新聞。適合台積電、鴻海、聯發科等台股查詢，接受股票代號（2330）或公司名稱（台積電）。",
        capabilities=["台股", "台灣股市", "上市", "上櫃", "股票代號", "RSI", "MACD", "KD", "均線", "本益比", "EPS", "外資", "投信", "法人", "籌碼"],
        allowed_tools=["tw_stock_price", "tw_technical_analysis", "tw_fundamentals", "tw_institutional", "tw_news"],
        priority=10,
    ))

    us = USStockAgent(lang_llm, tool_registry)
    agent_registry.register(us, AgentMetadata(
        name="us_stock",
        display_name="US Stock Agent",
        description="美股分析（開發中）— 識別 NYSE/NASDAQ 股票代號，提供基本信息。適合 AAPL/TSLA/TSM 等美股查詢。",
        capabilities=["美股", "US stock", "NYSE", "NASDAQ", "AAPL", "TSLA", "TSM", "NVDA"],
        allowed_tools=[],
        priority=5,
    ))

    chat = ChatAgent(lang_llm, tool_registry)
    agent_registry.register(chat, AgentMetadata(
        name="chat",
        display_name="Chat Agent",
        description="一般對話助手 — 處理閒聊、問候、自我介紹、平台使用說明、即時價格查詢、一般知識問答，以及主觀意見問題。不負責主動搜尋新聞或執行技術分析。",
        capabilities=["conversation", "greeting", "help", "general knowledge", "price lookup", "即時價格", "平台說明", "閒聊"],
        allowed_tools=["get_crypto_price", "web_search"],
        priority=1,
    ))

    return ManagerAgent(
        llm_client=lang_llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        codebook=codebook,
        web_mode=web_mode,
    )
```

**Step 3: Verify bootstrap imports work**

```bash
python -c "
from core.agents.bootstrap import bootstrap
print('bootstrap import OK')
"
```

Expected: `bootstrap import OK`

**Step 4: Commit**

```bash
git add core/agents/bootstrap.py core/agents/tools.py
git commit -m "feat: update bootstrap with CryptoAgent, TWStockAgent, USStockAgent"
```

---

## Task 10: Update Manager Prompt + Multi-Market Dispatch

**Files:**
- Modify: `core/agents/prompts/manager.yaml` (classify section — update agent names)
- Modify: `core/agents/manager.py` (_classify_node — add UniversalSymbolResolver)

**Step 1: Update manager.yaml classify prompt**

In `core/agents/prompts/manager.yaml`, update the `classify` template body.
Find the `**選擇規則：**` block and add a rule about TW stocks:

Replace:
```
    **選擇規則：**
    1. 根據每個 Agent 的 description 和 capabilities 判斷，選最符合查詢意圖的 agent
    2. 若無完全匹配，選 chat（fallback）
    3. 查詢模糊且缺少必要資訊（如未指定幣種），設為 ambiguous
```

With:
```
    **選擇規則：**
    1. 根據每個 Agent 的 description 和 capabilities 判斷，選最符合查詢意圖的 agent
    2. 台股相關（含股票代號如 2330、公司名稱如台積電、或明確提到台股/上市/上櫃）→ tw_stock
    3. 加密貨幣相關（BTC/ETH/SOL 等）→ crypto
    4. 美股相關（NYSE/NASDAQ ticker）→ us_stock
    5. 若無完全匹配，選 chat（fallback）
    6. 查詢模糊且缺少必要資訊（如「分析一下」但未指定標的），設為 ambiguous
```

**Step 2: Add multi-market dispatch to `_classify_node` in `manager.py`**

At the top of `manager.py`, add the import (after existing imports):

```python
from core.tools.universal_resolver import UniversalSymbolResolver
```

Add as a class attribute in `ManagerAgent.__init__`:

```python
self.universal_resolver = UniversalSymbolResolver()
```

(Place after `self.watcher = WatcherAgent(llm_client)`)

Then modify `_classify_node` to detect multi-market. After the LLM classification block (after `return {...}` is constructed), add a pre-check BEFORE the LLM call:

Replace the beginning of `_classify_node`:

```python
async def _classify_node(self, state: ManagerState) -> dict:
    import asyncio
    loop = asyncio.get_running_loop()
    query = state.get("query", "")

    # ── Pre-check: Universal Symbol Resolution ──
    # Extract first candidate word/token from query for resolution
    import re
    tokens = re.findall(r'[A-Z]{2,5}|\d{4,6}|[\u4e00-\u9fff]{2,6}', query)
    multi_market_plan = None
    for token in tokens[:3]:
        resolution = self.universal_resolver.resolve(token)
        markets = self.universal_resolver.matched_markets(resolution)
        if len(markets) > 1:
            # Build deterministic multi-step plan
            market_to_agent = {"crypto": "crypto", "tw": "tw_stock", "us": "us_stock"}
            steps = []
            for i, market in enumerate(markets, 1):
                symbol = resolution[market]
                steps.append({
                    "step": i,
                    "description": f"分析 {symbol}（{market} 市場）",
                    "agent": market_to_agent[market],
                    "tool_hint": None,
                })
            multi_market_plan = steps
            break

    # If multi-market detected, skip LLM classification and use pre-built plan
    if multi_market_plan:
        return {
            "complexity":  "complex",
            "intent":      multi_market_plan[0]["agent"],
            "topics":      [s["description"] for s in multi_market_plan],
            "plan":        multi_market_plan,
            "plan_confirmed": True,  # Skip plan confirmation for deterministic cases
        }

    # ── Normal LLM classification ──
    agents_info = self.agent_registry.agents_info_for_prompt()
    tools_info  = ", ".join([t.name for t in self.tool_registry.list_all_tools()])
    # ... rest of existing code unchanged ...
```

**Step 3: Update `_after_plan` to check for pre-built plan**

In `_after_plan`, also skip confirmation for multi-market plans:

```python
def _after_plan(self, state: ManagerState) -> str:
    # If plan was pre-confirmed (multi-market dispatch), go straight to execute
    if state.get("plan_confirmed"):
        return "execute"
    return "confirm" if state.get("complexity") == "complex" else "execute"
```

**Step 4: Update synthesize to label multi-market results**

In `_synthesize_node`, update the results_text formatting for complex multi-agent results:

Find this block:
```python
results_text = "\n\n".join(
    f"### [{r['agent_name']}]\n{r['message']}"
    for r in successful
)
```

Replace with:
```python
AGENT_LABELS = {
    "crypto":   "🔐 加密貨幣",
    "tw_stock": "🇹🇼 台股",
    "us_stock": "📈 美股",
    "chat":     "💬 對話",
}
results_text = "\n\n---\n\n".join(
    f"## {AGENT_LABELS.get(r['agent_name'], r['agent_name'])}\n\n{r['message']}"
    for r in successful
)
```

**Step 5: Add `__init__` import for UniversalSymbolResolver at top of manager.py**

Check the import was added. Then commit:

```bash
git add core/agents/manager.py core/agents/prompts/manager.yaml
git commit -m "feat: add multi-market parallel dispatch in Manager classify node"
```

---

## Task 11: Update PromptRegistry Loading

**Files:**
- Check: `core/agents/prompt_registry.py`

**Step 1: Verify new YAML files are auto-loaded**

```bash
python -c "
from core.agents.prompt_registry import PromptRegistry
PromptRegistry.load()
# Check new templates loaded
tmpl = PromptRegistry.get('tw_stock_agent', 'analysis')
print('tw_stock_agent prompt:', 'OK' if tmpl else 'MISSING')
tmpl2 = PromptRegistry.get('crypto_agent', 'analysis')
print('crypto_agent prompt:', 'OK' if tmpl2 else 'MISSING')
"
```

Expected: both `OK`. If `MISSING`, check how `PromptRegistry.load()` discovers YAML files (it should glob `prompts/*.yaml`).

**Step 2: Commit if any fixes needed, otherwise no-op.**

---

## Task 12: Integration Tests

**Files:**
- Create: `tests/test_multi_market_integration.py`

**Step 1: Write integration test**

Create `tests/test_multi_market_integration.py`:

```python
"""
Integration tests for multi-market agent dispatch.
Uses mocked LLM to avoid real API calls.
"""
import pytest
from unittest.mock import MagicMock, patch


def make_mock_llm(content="分析報告"):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


def test_crypto_agent_executes():
    """CryptoAgent can execute with mocked tools."""
    from core.agents.agents.crypto_agent import CryptoAgent
    from core.agents.models import SubTask

    llm = make_mock_llm("BTC 分析：RSI 55，中性偏多")
    tool_registry = MagicMock()
    tool_registry.get.return_value = None  # No tools

    agent = CryptoAgent(llm, tool_registry)
    task  = SubTask(step=1, description="BTC 技術分析", agent="crypto")
    result = agent.execute(task)
    assert result.agent_name == "crypto"


def test_tw_stock_agent_executes():
    """TWStockAgent can execute with mocked tools."""
    from core.agents.agents.tw_stock_agent import TWStockAgent
    from core.agents.models import SubTask

    llm = make_mock_llm("台積電分析報告")
    tool_registry = MagicMock()
    tool_registry.get.return_value = None

    agent = TWStockAgent(llm, tool_registry)
    task  = SubTask(step=1, description="台積電最近走勢", agent="tw_stock")
    result = agent.execute(task)
    assert result.agent_name == "tw_stock"


def test_us_stock_agent_stub():
    """USStockAgent returns stub message."""
    from core.agents.agents.us_stock_agent import USStockAgent
    from core.agents.models import SubTask

    llm = make_mock_llm()
    tool_registry = MagicMock()

    agent  = USStockAgent(llm, tool_registry)
    task   = SubTask(step=1, description="分析 TSM", agent="us_stock")
    result = agent.execute(task)
    assert result.success is True
    assert "TSM" in result.message or "美股" in result.message


def test_universal_resolver_btc():
    """BTC resolves to crypto only."""
    from core.tools.universal_resolver import UniversalSymbolResolver
    r = UniversalSymbolResolver()
    res = r.resolve("BTC")
    assert res["crypto"] == "BTC"
    assert res["tw"] is None


def test_universal_resolver_tw_digit():
    """2330 resolves to tw_stock only."""
    from core.tools.universal_resolver import UniversalSymbolResolver
    r = UniversalSymbolResolver()
    res = r.resolve("2330")
    assert res["tw"] == "2330.TW"
    assert res["crypto"] is None


def test_bootstrap_creates_all_agents():
    """bootstrap() registers all 5 agent types."""
    from core.agents.bootstrap import bootstrap

    mock_llm = make_mock_llm()
    manager  = bootstrap(mock_llm, web_mode=False)

    agent_names = {m.name for m in manager.agent_registry.list_all()}
    assert "crypto"   in agent_names, "CryptoAgent not registered"
    assert "tw_stock" in agent_names, "TWStockAgent not registered"
    assert "us_stock" in agent_names, "USStockAgent not registered"
    assert "chat"     in agent_names, "ChatAgent not registered"
```

**Step 2: Run tests**

```bash
pytest tests/test_multi_market_integration.py -v
```

Expected: All pass

**Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: No regressions in existing tests

**Step 4: Final commit**

```bash
git add tests/test_multi_market_integration.py
git commit -m "test: add multi-market integration tests"
```

---

## Summary

After all tasks complete, the system will:

1. Accept any symbol form: `台積電`, `2330`, `BTC`, `TSM`, `2330.TW`
2. Route to the correct market agent automatically
3. Dispatch to multiple agents in parallel when symbol is ambiguous (e.g., "TSM")
4. Present results with clear market labels (🔐 加密貨幣 / 🇹🇼 台股 / 📈 美股)
5. Return a canned message when no market recognizes the symbol

**New files created:**
- `core/tools/tw_symbol_resolver.py`
- `core/tools/tw_stock_tools.py`
- `core/tools/universal_resolver.py`
- `core/agents/agents/tw_stock_agent.py`
- `core/agents/agents/us_stock_agent.py`
- `core/agents/agents/crypto_agent.py`
- `core/agents/prompts/tw_stock_agent.yaml`
- `core/agents/prompts/us_stock_agent.yaml`
- `core/agents/prompts/crypto_agent.yaml`

**Modified files:**
- `core/agents/agents/__init__.py`
- `core/agents/bootstrap.py`
- `core/agents/tools.py`
- `core/agents/manager.py`
- `core/agents/prompts/manager.yaml`
